"""
UAT-030 — personal email/mobile number were locked once onboarding is
complete (PUT /api/employees/{id}/) with no override at all, so HR had no
way to correct a typo post-hire. A new `confirm_contact_change` flag lets
HR deliberately bypass the lock for these two fields specifically, with the
change recorded in the audit log either way.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User


class EmployeeDetailContactLockTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_contact_lock_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-contact-lock@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_contact_lock_test', permission_codenames=[])
        self.employee = make_user(
            'employee-contact-lock@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Contact Lock', employee_id='EMPLOCK01', phone='9000000000',
        )
        self.employee.onboarding_status = User.ONBOARDING_COMPLETE
        self.employee.save(update_fields=['onboarding_status'])
        self.client.force_authenticate(user=self.hr_user)

    def _put(self, **data):
        return self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]), data, format='json',
        )

    def test_phone_change_refused_without_confirm_flag_once_locked(self):
        resp = self._put(phone='9111111111')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9000000000')

    def test_phone_change_allowed_with_confirm_flag_and_audited(self):
        resp = self._put(phone='9111111111', confirm_contact_change=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9111111111')
        entry = AuditLog.objects.filter(action='employee_updated', object_id=str(self.employee.id)).latest('created_at')
        self.assertEqual(entry.changes['phone']['to'], '9111111111')
        self.assertTrue(entry.changes['phone']['hr_override'])

    def test_email_change_refused_without_confirm_flag_once_locked(self):
        resp = self._put(email='new-address@test.com')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.employee.refresh_from_db()
        self.assertNotEqual(self.employee.email, 'new-address@test.com')

    def test_email_change_allowed_with_confirm_flag_and_audited(self):
        resp = self._put(email='new-address@test.com', confirm_contact_change=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'new-address@test.com')
        entry = AuditLog.objects.filter(action='employee_updated', object_id=str(self.employee.id)).latest('created_at')
        self.assertEqual(entry.changes['email']['to'], 'new-address@test.com')
        self.assertTrue(entry.changes['email']['hr_override'])

    def test_email_change_rejected_when_already_in_use(self):
        make_user('someone-else@test.com', role=self.employee_role, password='TestPass123!')
        resp = self._put(email='someone-else@test.com', confirm_contact_change=True)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_invalid_email_format_rejected(self):
        resp = self._put(email='not-an-email', confirm_contact_change=True)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_phone_change_allowed_without_confirm_flag_when_not_onboarded(self):
        self.employee.onboarding_status = User.ONBOARDING_DRAFT
        self.employee.save(update_fields=['onboarding_status'])
        resp = self._put(phone='9222222222')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9222222222')
