"""
Manual employee_id correction on EmployeeDetailView PUT/PATCH
(_update_fields in apps/accounts/views/employees_detail.py) — locked behind
settings.edit (not the plain employees.edit this view otherwise requires),
validated as unique 8-digit numeric, and only warned (never blocked) when
the new ID falls outside the employee's worker type's configured range.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeCodeSeries


class EmployeeIdManualEditTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin_role = make_role('id_edit_admin', permission_codenames=['employees.edit', 'employees.view', 'settings.edit'])
        self.admin = make_user('id-edit-admin@test.com', role=self.admin_role)
        self.hr_role = make_role('id_edit_hr', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_only = make_user('id-edit-hr@test.com', role=self.hr_role)
        self.employee = make_user('id-edit-target@test.com', employee_type='Permanent', employee_id='10000050')
        EmployeeCodeSeries.objects.update_or_create(
            employment_type='Permanent',
            defaults={'range_start': 10000000, 'range_end': 19999999, 'next_sequence': 10000051},
        )

    def test_settings_edit_holder_can_correct_an_employee_id(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'employee_id': '10000099'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, '10000099')
        self.assertTrue(AuditLog.objects.filter(action='employee_updated', object_id=str(self.employee.id)).exists())

    def test_plain_employees_edit_without_settings_edit_is_forbidden(self):
        self.client.force_authenticate(user=self.hr_only)
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'employee_id': '10000099'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, '10000050')

    def test_non_8_digit_value_rejected(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'employee_id': 'EMP123'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_id_rejected(self):
        make_user('id-edit-other@test.com', employee_id='10000077')
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'employee_id': '10000077'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_id_outside_worker_types_range_is_warned_not_blocked(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'employee_id': '50000001'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('outside', resp.data['message'].lower())
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, '50000001')

    def test_unchanged_id_is_rejected_as_no_updatable_fields(self):
        # Same convention as every other field here (e.g. phone/email):
        # resubmitting the current value with nothing else in the payload
        # isn't a real update.
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'employee_id': self.employee.employee_id}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
