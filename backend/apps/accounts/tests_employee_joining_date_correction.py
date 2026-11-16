"""Joining date after onboarding is complete: locked for plain HR editors, correctable by a full-access user (settings.edit /
superuser), who is the only one allowed to fix a wrong year. The change is audit-logged."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User


class JoiningDateCorrectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_joining_fix', permission_codenames=['employees.edit', 'employees.view'])
        admin_role = make_role('admin_joining_fix', permission_codenames=['employees.edit', 'employees.view', 'settings.edit'])
        self.hr = make_user('hr-doj@test.com', role=hr_role, password='TestPass123!')
        self.admin = make_user('admin-doj@test.com', role=admin_role, password='TestPass123!')
        self.employee = make_user(
            'emp-doj@test.com', password='TestPass123!', employee_id='10000999', full_name='Doj Person',
            date_of_joining=datetime.date(2026, 3, 2), onboarding_status=User.ONBOARDING_COMPLETE,
        )
        self.url = reverse('employee-detail', args=[self.employee.employee_id])

    def _put(self, user, doj):
        self.client.force_authenticate(user=user)
        return self.client.patch(self.url, {'date_of_joining': doj}, format='json')

    def test_plain_hr_editor_is_still_refused(self):
        response = self._put(self.hr, '2025-03-02')
        self.assertEqual(response.status_code, 409)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.date_of_joining, datetime.date(2026, 3, 2))

    def test_full_access_user_can_correct_the_year(self):
        response = self._put(self.admin, '2025-03-02')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.date_of_joining, datetime.date(2025, 3, 2))
        self.assertTrue(AuditLog.objects.filter(module='employees', object_id=str(self.employee.id)).exists())

    def test_resending_the_same_date_is_not_refused_for_anyone(self):
        self.assertEqual(self._put(self.hr, '2026-03-02').status_code, 200)
