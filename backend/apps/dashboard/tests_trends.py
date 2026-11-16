"""
Tests for the historical-trend endpoints (apps/dashboard/views/trends.py)
backing the System Admin / HR dashboard's "Stage 2" analytics: headcount
growth, leave approval/rejection volume, and payroll cost, each as a
trailing-6-month series.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, REQ_REJECTED, LeaveRequest
from apps.payroll.models import EmployeePayslip, PayrollCycle


def _make_cycle(cycle_start, created_by, status=PayrollCycle.STATUS_PAID):
    return PayrollCycle.objects.create(
        cycle_start=cycle_start, cycle_end=cycle_start.replace(day=28),
        pay_date=cycle_start, created_by=created_by, status=status,
    )


def _make_payslip(employee, cycle, net_pay):
    return EmployeePayslip.objects.create(
        cycle=cycle, employee=employee,
        annual_ctc=Decimal('1200000'), monthly_ctc=Decimal('100000'),
        basic=Decimal('40000'), hra=Decimal('20000'), special_allowance=Decimal('0'),
        other_earnings={}, reimbursements=Decimal('0'), bonus=Decimal('0'),
        gross_earnings=Decimal('60000'), lop_deduction=Decimal('0'),
        pf_employee=Decimal('0'), pf_employer=Decimal('0'), pf_wage_base=Decimal('15000'),
        esi_employee=Decimal('0'), esi_employer=Decimal('0'),
        pt_deduction=Decimal('0'), lwf_employee=Decimal('0'), lwf_employer=Decimal('0'),
        income_tax=Decimal('0'), adjustments_earning=Decimal('0'), adjustments_deduction=Decimal('0'),
        total_deductions=Decimal('0'), net_pay=net_pay,
    )


class DashboardTrendsPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user('trends-admin@test.com', role=make_role('trends_admin', permission_codenames=['employees.view']))
        self.plain = make_user('trends-plain@test.com', role=make_role('trends_plain', permission_codenames=[]))

    def test_without_employees_view_permission_403s(self):
        self.client.force_authenticate(user=self.plain)
        for path in ('/api/dashboard/trends/headcount/', '/api/dashboard/trends/leave/', '/api/dashboard/trends/payroll-cost/'):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 403, path)

    def test_with_employees_view_permission_succeeds(self):
        self.client.force_authenticate(user=self.admin)
        # Headcount/leave are fixed-length (one point per trailing month,
        # always 6, even with no data). Payroll cost's length follows
        # however many non-draft cycles actually exist — 0 in a test DB
        # with none created — so it's only checked for a 200, not a count.
        for path in ('/api/dashboard/trends/headcount/', '/api/dashboard/trends/leave/'):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, path)
            self.assertEqual(len(resp.data['data']['series']), 6, path)

        resp = self.client.get('/api/dashboard/trends/payroll-cost/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsInstance(resp.data['data']['series'], list)


class HeadcountTrendTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user('headcount-admin@test.com', role=make_role('headcount_admin', permission_codenames=['employees.view']))
        self.client.force_authenticate(user=self.admin)

    def test_series_is_non_decreasing_as_people_join_over_time(self):
        today = datetime.date.today()
        make_user('ht1@test.com', employee_id='HT001', date_of_joining=today - datetime.timedelta(days=150), onboarding_status='complete')
        make_user('ht2@test.com', employee_id='HT002', date_of_joining=today - datetime.timedelta(days=10), onboarding_status='complete')

        resp = self.client.get('/api/dashboard/trends/headcount/')
        self.assertEqual(resp.status_code, 200, resp.data)
        series = resp.data['data']['series']
        self.assertEqual(series[-1]['count'] >= series[0]['count'], True)
        # Whoever joined 10 days ago should count in the current month but not ~5 months back.
        self.assertGreater(series[-1]['count'], series[0]['count'])


class LeaveTrendTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user('leave-trend-admin@test.com', role=make_role('leave_trend_admin', permission_codenames=['employees.view']))
        self.employee = make_user('leave-trend-emp@test.com')
        self.client.force_authenticate(user=self.admin)

    def _create_request(self, status, created_on):
        req = LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', start_date=created_on, end_date=created_on,
            total_days=Decimal('1'), reason='test', status=status,
        )
        aware_created_at = timezone.make_aware(datetime.datetime.combine(created_on, datetime.time.min))
        LeaveRequest.objects.filter(pk=req.pk).update(created_at=aware_created_at)
        return req

    def test_approved_and_rejected_are_counted_in_the_right_month_bucket(self):
        today = datetime.date.today()
        self._create_request(REQ_APPROVED, today)
        self._create_request(REQ_APPROVED, today)
        self._create_request(REQ_REJECTED, today)
        self._create_request(REQ_PENDING, today)  # must not be counted in either bucket

        resp = self.client.get('/api/dashboard/trends/leave/')
        self.assertEqual(resp.status_code, 200, resp.data)
        current_month = resp.data['data']['series'][-1]
        self.assertEqual(current_month['approved'], 2)
        self.assertEqual(current_month['rejected'], 1)


class PayrollCostTrendTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user('payroll-trend-admin@test.com', role=make_role('payroll_trend_admin', permission_codenames=['employees.view']))
        self.employee = make_user('payroll-trend-emp@test.com')
        self.client.force_authenticate(user=self.admin)

    def test_draft_cycles_are_excluded_paid_cycles_are_summed(self):
        today = datetime.date.today()
        draft_cycle = _make_cycle(today.replace(day=1), self.admin, status=PayrollCycle.STATUS_DRAFT)
        _make_payslip(self.employee, draft_cycle, Decimal('999999'))  # must not appear

        paid_cycle = _make_cycle(today.replace(day=1), self.admin, status=PayrollCycle.STATUS_PAID)
        _make_payslip(self.employee, paid_cycle, Decimal('50000'))
        _make_payslip(make_user('payroll-trend-emp2@test.com'), paid_cycle, Decimal('30000'))

        resp = self.client.get('/api/dashboard/trends/payroll-cost/')
        self.assertEqual(resp.status_code, 200, resp.data)
        series = resp.data['data']['series']
        amounts = [row['amount'] for row in series]
        self.assertIn(80000.0, amounts)
        self.assertNotIn(999999.0, amounts)
