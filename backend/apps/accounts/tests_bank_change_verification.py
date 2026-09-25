"""Regression tests for the bank-detail-change verification gate — a
self-service edit that would overwrite ALREADY-FILLED bank details is held
pending HR review (EmployeeProfile.submit_bank_change) instead of writing
straight to the columns payroll reads from. First-time entry (empty ->
filled) is unaffected. See views/shared.py's _save_profile_step bank-change
gate and EmployeeBankChangeReviewView (views/employees_detail.py).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


BANK_STEP = 2
_BANK_PAYLOAD = {
    'account_number': '1234567890', 'ifsc_code': 'HDFC0001234',
    'bank_name': 'HDFC Bank', 'bank_branch_name': 'Kondapur',
    'account_holder_name': 'Test Employee', 'account_type': 'savings',
}


class BankChangeFirstEntryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.role = make_role('bank_test_employee')
        self.employee = make_user('bankfirst@test.com', role=self.role, password='TestPass123!')
        _login(self.client, 'bankfirst@test.com')

    def test_first_time_bank_entry_saves_directly_no_pending(self):
        resp = self.client.patch(reverse('onboarding-step', args=[BANK_STEP]), _BANK_PAYLOAD, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.employee)
        self.assertEqual(profile.account_number, '1234567890')
        self.assertEqual(profile.bank_change_status, EmployeeProfile.BANK_CHANGE_NONE)


class BankChangeMixedRequestTests(TestCase):
    """Regression test for the "any field already filled -> whole request
    pending" bug: a request mixing a genuine overwrite of one already-filled
    field with a FIRST-TIME entry for other, still-blank required fields must
    apply the first-time fields immediately, not sweep them into pending
    alongside the real overwrite."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.role = make_role('bank_test_employee_mixed')
        self.employee = make_user('bankmixed@test.com', role=self.role, password='TestPass123!')
        # Only account_number/ifsc_code pre-filled — account_type/bank_name/
        # bank_branch_name/account_holder_name are still genuinely blank,
        # exactly like a partially-completed Bank Details step.
        self.profile = EmployeeProfile.objects.create(
            user=self.employee, account_number='1111111111', ifsc_code='HDFC0000001',
        )
        _login(self.client, 'bankmixed@test.com')

    def test_first_time_fields_apply_directly_alongside_an_overwrite(self):
        resp = self.client.patch(reverse('onboarding-step', args=[BANK_STEP]), {
            'account_number': '2222222222',  # overwrite of an existing value
            'account_type': 'savings', 'bank_name': 'HDFC Bank',  # first-time
            'bank_branch_name': 'Kondapur', 'account_holder_name': 'Test Employee',  # first-time
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.profile.refresh_from_db()
        # The overwrite is held pending, not applied live.
        self.assertEqual(self.profile.account_number, '1111111111')
        self.assertEqual(self.profile.pending_account_number, '2222222222')
        self.assertEqual(self.profile.bank_change_status, EmployeeProfile.BANK_CHANGE_PENDING)
        # The first-time fields are applied immediately — not stuck pending.
        self.assertEqual(self.profile.account_type, 'savings')
        self.assertEqual(self.profile.bank_name, 'HDFC Bank')
        self.assertEqual(self.profile.bank_branch_name, 'Kondapur')
        self.assertEqual(self.profile.account_holder_name, 'Test Employee')


class BankChangeOverwriteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.role = make_role('bank_test_employee2')
        self.employee = make_user('bankoverwrite@test.com', role=self.role, password='TestPass123!')
        self.profile = EmployeeProfile.objects.create(user=self.employee, **_BANK_PAYLOAD)
        _login(self.client, 'bankoverwrite@test.com')

    def test_overwrite_is_held_pending_not_applied_live(self):
        resp = self.client.patch(reverse('onboarding-step', args=[BANK_STEP]), {
            'account_number': '9999999999', 'ifsc_code': 'ICIC0005678',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('submitted', resp.data['message'].lower())
        self.profile.refresh_from_db()
        # Live payroll-facing fields are untouched.
        self.assertEqual(self.profile.account_number, '1234567890')
        self.assertEqual(self.profile.ifsc_code, 'HDFC0001234')
        # New values are held on the pending side.
        self.assertEqual(self.profile.pending_account_number, '9999999999')
        self.assertEqual(self.profile.bank_change_status, EmployeeProfile.BANK_CHANGE_PENDING)

    def test_get_step_reports_pending_status(self):
        self.client.patch(reverse('onboarding-step', args=[BANK_STEP]), {'account_number': '9999999999'}, format='json')
        resp = self.client.get(reverse('onboarding-step', args=[BANK_STEP]))
        self.assertEqual(resp.data['data']['bank_change_status'], EmployeeProfile.BANK_CHANGE_PENDING)


class BankChangeHRReviewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        emp_role = make_role('bank_test_employee3')
        self.employee = make_user('bankreview@test.com', role=emp_role, password='TestPass123!', employee_id='EMPBANK01')
        self.profile = EmployeeProfile.objects.create(user=self.employee, **_BANK_PAYLOAD)
        self.profile.submit_bank_change({'account_number': '5555555555', 'ifsc_code': 'SBIN0009999'})

        hr_role = make_role('bank_test_hr', permission_codenames=['employees.edit'])
        self.hr = make_user('bankhr@test.com', role=hr_role, password='TestPass123!')
        _login(self.client, 'bankhr@test.com')

    def _url(self, decision):
        return reverse('employee-bank-change-review', args=[self.employee.employee_id, decision])

    def test_approve_applies_pending_values_to_live_fields(self):
        resp = self.client.post(self._url('approve'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.account_number, '5555555555')
        self.assertEqual(self.profile.ifsc_code, 'SBIN0009999')
        self.assertEqual(self.profile.bank_change_status, EmployeeProfile.BANK_CHANGE_NONE)

    def test_reject_discards_pending_keeps_previous_live_values(self):
        resp = self.client.post(self._url('reject'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.account_number, '1234567890')
        self.assertEqual(self.profile.pending_account_number, '')
        self.assertEqual(self.profile.bank_change_status, EmployeeProfile.BANK_CHANGE_NONE)

    def test_review_denied_without_employees_edit_permission(self):
        no_perm = make_user('banknoperm@test.com', role=make_role('bank_no_perm_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.post(self._url('approve'))
        self.assertEqual(resp.status_code, 403)

    def test_review_with_no_pending_change_errors(self):
        self.client.post(self._url('approve'))
        resp = self.client.post(self._url('approve'))
        self.assertEqual(resp.status_code, 400)
