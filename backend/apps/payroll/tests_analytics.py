"""Tests for payroll analytics (cost summary / branch breakdown) — see
views/analytics.py."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.payroll.models import EmployeePayslip, PayrollCycle
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _make_branch(code: str, name: str) -> Branch:
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(branch_code=code, branch_name=name, address='Test Address', state=state, city=city)


def _make_cycle(branch, creator, start, end, pay_date, status=PayrollCycle.STATUS_PAID) -> PayrollCycle:
    return PayrollCycle.objects.create(
        branch=branch, cycle_start=start, cycle_end=end, pay_date=pay_date, status=status, created_by=creator,
    )


def _make_payslip(cycle, employee, gross: str, net: str) -> EmployeePayslip:
    gross_d, net_d = Decimal(gross), Decimal(net)
    return EmployeePayslip.objects.create(
        cycle=cycle, employee=employee,
        annual_ctc=gross_d * 12, monthly_ctc=gross_d,
        gross_earnings=gross_d, net_pay=net_d, total_deductions=gross_d - net_d,
    )


class PayrollAnalyticsTests(TestCase):
    """
    Branch A: two payslips in its Feb cycle (₹50000/₹45000, ₹60000/₹54000),
    plus an older, CANCELLED Jan cycle that must never be picked as "the
    latest non-cancelled cycle". Branch B: one payslip in its Feb cycle
    (₹40000/₹36000).
    """

    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()

        self.branch_a = _make_branch('BRA', 'Branch A')
        self.branch_b = _make_branch('BRB', 'Branch B')

        admin_role = make_role('system_admin', permission_codenames=['settings.edit', 'payroll.view'])
        hr_role = make_role('hr', permission_codenames=['payroll.view'])
        employee_role = make_role('employee')

        self.admin = make_user('admin@test.com', role=admin_role)
        self.hr_a = make_user('hr.a@test.com', role=hr_role, branch='Branch A')
        self.hr_b = make_user('hr.b@test.com', role=hr_role, branch='Branch B')
        self.no_perm_user = make_user('noperm@test.com', role=employee_role, branch='Branch A')

        emp_a1 = make_user('emp.a1@test.com', role=employee_role, branch='Branch A')
        emp_a2 = make_user('emp.a2@test.com', role=employee_role, branch='Branch A')
        emp_b1 = make_user('emp.b1@test.com', role=employee_role, branch='Branch B')

        self.cycle_a = _make_cycle(
            self.branch_a, self.admin,
            datetime.date(2026, 2, 1), datetime.date(2026, 2, 28), datetime.date(2026, 3, 1),
        )
        self.cycle_b = _make_cycle(
            self.branch_b, self.admin,
            datetime.date(2026, 2, 1), datetime.date(2026, 2, 28), datetime.date(2026, 3, 1),
        )
        self.cancelled_cycle_a = _make_cycle(
            self.branch_a, self.admin,
            datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), datetime.date(2026, 2, 1),
            status=PayrollCycle.STATUS_CANCELLED,
        )

        _make_payslip(self.cycle_a, emp_a1, '50000', '45000')
        _make_payslip(self.cycle_a, emp_a2, '60000', '54000')
        _make_payslip(self.cycle_b, emp_b1, '40000', '36000')

    # ── PayrollCostSummaryView ────────────────────────────────────────────

    def test_cost_summary_requires_payroll_view_permission(self):
        _login(self.client, 'noperm@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'))
        self.assertEqual(resp.status_code, 403)

    def test_admin_cost_summary_aggregates_all_branches(self):
        _login(self.client, 'admin@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'))
        self.assertEqual(resp.status_code, 200)
        data = resp.data['data']
        self.assertEqual(Decimal(data['gross_earnings']), Decimal('150000'))
        self.assertEqual(Decimal(data['net_pay']), Decimal('135000'))
        self.assertEqual(data['employee_count'], 3)

    def test_branch_scoped_user_only_sees_own_branch(self):
        _login(self.client, 'hr.a@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'))
        self.assertEqual(resp.status_code, 200)
        data = resp.data['data']
        self.assertEqual(Decimal(data['gross_earnings']), Decimal('110000'))
        self.assertEqual(data['employee_count'], 2)

    def test_cancelled_cycle_excluded_from_latest_period(self):
        _login(self.client, 'hr.a@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'))
        data = resp.data['data']
        self.assertEqual(data['branches_included'][0]['cycle_id'], str(self.cycle_a.id))

    def test_month_param_wins_over_default_and_excludes_cancelled(self):
        # January only has branch A's CANCELLED cycle — excluded either way —
        # so an explicit ?month=2026-01 finds no data at all, distinct from
        # the default (offset=0) path which would have found February's.
        _login(self.client, 'hr.a@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'), {'month': '2026-01'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['employee_count'], 0)

    def test_offset_one_skips_to_the_prior_non_cancelled_cycle(self):
        # A third, later branch-A cycle makes cycle_a (Feb) offset=1 relative
        # to it — offset must still skip the cancelled Jan cycle entirely,
        # not count it as one of the two non-cancelled cycles back.
        _make_cycle(
            self.branch_a, self.admin,
            datetime.date(2026, 3, 1), datetime.date(2026, 3, 31), datetime.date(2026, 4, 1),
        )
        _login(self.client, 'hr.a@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'), {'offset': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['branches_included'][0]['cycle_id'], str(self.cycle_a.id))

    def test_invalid_month_param_returns_400(self):
        _login(self.client, 'admin@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'), {'month': 'not-a-month'})
        self.assertEqual(resp.status_code, 400)

    def test_user_with_no_branch_assigned_gets_400(self):
        role = make_role('branchless_hr', permission_codenames=['payroll.view'])
        make_user('nobranch@test.com', role=role)
        _login(self.client, 'nobranch@test.com')
        resp = self.client.get(reverse('payroll-cost-summary'))
        self.assertEqual(resp.status_code, 400)

    # ── BranchPayrollBreakdownView ────────────────────────────────────────

    def test_branch_breakdown_ordered_by_net_pay_descending(self):
        _login(self.client, 'admin@test.com')
        resp = self.client.get(reverse('payroll-branch-breakdown'))
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['data']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['branch_name'], 'Branch A')  # 99000 net > 36000 net
        self.assertGreaterEqual(Decimal(rows[0]['net_pay']), Decimal(rows[1]['net_pay']))

    def test_branch_scoped_caller_gets_single_row_not_an_error(self):
        _login(self.client, 'hr.b@test.com')
        resp = self.client.get(reverse('payroll-branch-breakdown'))
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['branch_name'], 'Branch B')
        self.assertEqual(Decimal(rows[0]['net_pay']), Decimal('36000'))

    def test_breakdown_requires_payroll_view_permission(self):
        _login(self.client, 'noperm@test.com')
        resp = self.client.get(reverse('payroll-branch-breakdown'))
        self.assertEqual(resp.status_code, 403)
