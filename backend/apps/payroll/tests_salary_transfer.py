"""
Regression tests for the dual-confirmation salary transfer workflow (see
apps/payroll/views/salary_transfer.py) — the employer-confirmation gate,
the locked bank-detail snapshot, and MarkCyclePaidView's dependency on it.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile
from apps.payroll.models import (
    EmployeePayslip, PayrollCycle, PayrollSettings,
    SalaryTransferBatch, SalaryTransferItem,
)


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class SalaryTransferConfirmationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role(
            'hr', permission_codenames=['payroll.view', 'payroll.edit', 'settings.edit'],
        )
        self.hr_user = make_user('sthr@test.com', role=hr_role, password='TestPass123!')

        employee_role = make_role('employee')
        self.employee = make_user('stemp@test.com', role=employee_role, password='TestPass123!')
        self.profile = EmployeeProfile.objects.create(
            user=self.employee,
            account_number='1111222233334444', ifsc_code='SBIN0001111',
            account_holder_name='St Employee', bank_name='SBI',
        )

        PayrollSettings.objects.get_or_create(id='00000000-0000-0000-0000-000000000001')
        self.cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 1, 1), cycle_end=datetime.date(2026, 1, 31),
            pay_date=datetime.date(2026, 2, 1), created_by=self.hr_user,
            status=PayrollCycle.STATUS_PAYSLIPS_GENERATED,
        )
        self.payslip = EmployeePayslip.objects.create(
            cycle=self.cycle, employee=self.employee,
            annual_ctc=Decimal('600000.00'), monthly_ctc=Decimal('50000.00'),
            basic=Decimal('20000.00'), net_pay=Decimal('45000.00'),
            total_working_days=26, status=EmployeePayslip.STATUS_SENT,
        )
        _login(self.client, 'sthr@test.com')

    def _confirm_url(self):
        return reverse('salary-transfer-confirm', kwargs={'cycle_pk': self.cycle.pk})

    def _mark_paid_url(self):
        return reverse('payroll-mark-paid', kwargs={'pk': self.cycle.pk})

    def _acknowledge_payslip(self):
        self.payslip.status = EmployeePayslip.STATUS_ACKNOWLEDGED
        self.payslip.save(update_fields=['status'])

    def test_confirmation_blocked_while_payslip_unacknowledged(self):
        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(SalaryTransferBatch.objects.filter(cycle=self.cycle).exists())

    def test_confirmation_succeeds_once_acknowledged_and_locks_snapshot(self):
        self._acknowledge_payslip()
        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 200, resp.data)

        batch = SalaryTransferBatch.objects.get(cycle=self.cycle)
        self.assertEqual(batch.status, SalaryTransferBatch.STATUS_CONFIRMED)
        self.assertEqual(batch.confirmed_by_id, self.hr_user.id)

        item = SalaryTransferItem.objects.get(batch=batch)
        self.assertEqual(item.account_number, '1111222233334444')
        self.assertEqual(item.ifsc_code, 'SBIN0001111')
        self.assertEqual(item.amount, Decimal('45000.00'))

    def test_bank_detail_change_after_confirmation_does_not_alter_locked_snapshot(self):
        self._acknowledge_payslip()
        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 200, resp.data)

        # Simulate a bank-detail change AFTER confirmation (e.g. a compromised account).
        self.profile.account_number = '9999888877776666'
        self.profile.save()

        item = SalaryTransferItem.objects.get(payslip=self.payslip)
        self.assertEqual(item.account_number, '1111222233334444', 'locked snapshot must not change')

    def test_mark_paid_blocked_without_confirmed_transfer(self):
        resp = self.client.post(self._mark_paid_url())
        self.assertEqual(resp.status_code, 400, resp.data)
        self.cycle.refresh_from_db()
        self.assertNotEqual(self.cycle.status, PayrollCycle.STATUS_PAID)

    def test_mark_paid_succeeds_after_confirmed_transfer(self):
        self._acknowledge_payslip()
        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = self.client.post(self._mark_paid_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, PayrollCycle.STATUS_PAID)

    def test_missing_bank_details_blocks_confirmation(self):
        self.profile.account_number = ''
        self.profile.save()
        self._acknowledge_payslip()

        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(
            SalaryTransferItem.objects.filter(payslip=self.payslip).exists()
        )

    def test_cannot_confirm_twice(self):
        self._acknowledge_payslip()
        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 200, resp.data)

        resp = self.client.post(self._confirm_url())
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_download_requires_confirmed_batch(self):
        url = reverse('salary-transfer-download', kwargs={'cycle_pk': self.cycle.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_download_returns_locked_data_not_live_profile(self):
        self._acknowledge_payslip()
        self.client.post(self._confirm_url())

        # Change bank details after confirmation but before download.
        self.profile.account_number = '9999888877776666'
        self.profile.save()

        url = reverse('salary-transfer-download', kwargs={'cycle_pk': self.cycle.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('1111222233334444', content)
        self.assertNotIn('9999888877776666', content)
