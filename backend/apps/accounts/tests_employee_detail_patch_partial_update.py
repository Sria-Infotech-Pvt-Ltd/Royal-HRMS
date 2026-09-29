"""
Regression test for QA #68 — PATCH /api/employees/{id}/ used to support
ONLY the is_active activate/deactivate toggle: any other partial update
(e.g. correcting phone/email/address/DOB) hit `if 'is_active' not in
request.data: return error('is_active field is required.')` and 400'd
immediately, even though PUT already had full field-by-field validation
for exactly these fields. PATCH now delegates to that same
EmployeeDetailView._update_fields() logic whenever the body doesn't carry
`is_active`, while the is_active toggle itself keeps working unchanged.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


class EmployeeDetailPatchPartialUpdateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_patch_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-patch@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_patch_test', permission_codenames=[])
        self.employee = make_user(
            'employee-patch@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Pat Chester', phone='9876543210', employee_id='EMPPATCH01',
        )
        self.client.force_authenticate(user=self.hr_user)

    def test_patch_without_is_active_updates_other_fields_instead_of_erroring(self):
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'phone': '9123456780'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9123456780')

    def test_patch_is_active_still_toggles_status_as_before(self):
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'is_active': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)

    def test_patch_with_no_recognised_fields_still_errors_same_as_put(self):
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
