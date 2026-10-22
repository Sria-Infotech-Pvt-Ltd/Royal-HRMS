"""
Cycle detail showing ₹0 everywhere — reproduction and safeguards.

Reproduces the reported configuration: the only salary component is
"Basic Salary" as "% of Basic" (its name is not exactly "Basic", so nothing
fills the Basic line) → every amount is 0 → the cycle used to be payable.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.payroll.models import EmployeePayslip, PayrollCycle, SalaryComponent, SalaryStructure
from apps.payroll.tests_salary_components import SalaryFixtureMixin
from apps.payroll.views.cycles import PayrollAlreadyProcessing, process_payroll_cycle

D = Decimal


class ZeroPayslipTests(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()
        # Like the reported cycle: no statutory amount applies at ₹0 gross (no LWF either).
        from apps.payroll.models import StatutoryConfig
        StatutoryConfig.objects.update(lwf_applicable=False)
        # The reported setup: one component, "Basic Salary", 40 "% of Basic", role decided by name.
        self.bad = SalaryStructure.objects.create(name='Standard Employee Structure')
        url = reverse('salary-component-list', kwargs={'structure_pk': self.bad.pk})
        resp = self.api.post(url, {'name': 'Basic Salary', 'component_type': 'earning',
                                   'calculation_type': 'percentage_of_basic', 'value': '40'}, format='json')
        assert resp.status_code == 201, resp.data
        self.assertEqual(resp.data['data']['role'], 'other')        # "Basic Salary" is not the Basic line

    def _process_bad(self):
        self.assign(self.emp_a, ctc='50000', effective='2026-01-01', salary_structure=str(self.bad.pk))
        from apps.attendance.models import AttendanceRecord
        AttendanceRecord.objects.create(employee=self.emp_a, date=datetime.date(2026, 1, 5),
                                        status=AttendanceRecord.STATUS_HALF_DAY)
        jan = self.cycle(1)
        return jan, process_payroll_cycle(jan)

    def test_reproduces_all_zero_payslip_and_reports_it(self):
        jan, result = self._process_bad()
        p = self.payslip(jan, self.emp_a)
        self.assertEqual((p.annual_ctc, p.basic, p.gross_earnings, p.total_deductions, p.net_pay, p.pf_employee, p.lop_days),
                         (D('50000.00'), D('0.00'), D('0.00'), D('0.00'), D('0.00'), D('0.00'), D('0.5')))
        self.assertEqual(p.other_earnings, {'Basic Salary': 0.0})
        self.assertEqual(result['zero_gross'], ['Emp A'])

    def test_percent_of_ctc_basic_is_not_zero(self):
        SalaryComponent.objects.filter(structure=self.bad).update(calculation_type='percentage_of_ctc')
        jan, result = self._process_bad()
        p = self.payslip(jan, self.emp_a)
        self.assertEqual(p.gross_earnings, D('1666.67'))             # 40% of 50000/12
        self.assertEqual(result['zero_gross'], [])

    def test_cycle_totals_match_saved_payslips(self):
        self.assign(self.emp_a)                                      # 35000 gross (template)
        self.assign(self.emp_b, ctc='240000')                        # 17000 gross
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        resp = self.api.get(reverse('cycle-payslip-list', kwargs={'cycle_pk': jan.pk}), {'page_size': 1})
        totals = resp.data['data']['totals']
        saved = EmployeePayslip.objects.filter(cycle=jan)
        self.assertEqual(len(resp.data['data']['results']), 1)       # one page...
        self.assertEqual(totals['count'], 2)                          # ...totals still cover every payslip
        self.assertEqual(D(totals['total_gross_earnings']), sum(p.gross_earnings for p in saved))
        self.assertEqual(D(totals['total_net_pay']), sum(p.net_pay for p in saved))
        self.assertEqual(D(totals['total_pf_employee']), D('2760.00'))   # 1800 + 960
        self.assertEqual(totals['zero_gross_count'], 0)

    def test_zero_totals_reported_as_zero(self):
        jan, _ = self._process_bad()
        totals = self.api.get(reverse('cycle-payslip-list', kwargs={'cycle_pk': jan.pk})).data['data']['totals']
        self.assertEqual((totals['total_gross_earnings'], totals['total_net_pay'], totals['zero_gross_count']),
                         ('0.00', '0.00', 1))

    def test_zero_gross_cycle_cannot_be_confirmed_or_marked_paid(self):
        jan, _ = self._process_bad()
        EmployeePayslip.objects.filter(cycle=jan).update(status=EmployeePayslip.STATUS_ACKNOWLEDGED)
        resp = self.api.post(reverse('salary-transfer-confirm', kwargs={'cycle_pk': jan.pk}))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('₹0 gross earnings', resp.data['message'])
        self.assertIn('Emp A (SCA)', resp.data['message'])
        resp = self.api.post(reverse('payroll-mark-paid', kwargs={'pk': jan.pk}))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('₹0 gross earnings', resp.data['message'])
        jan.refresh_from_db()
        self.assertEqual(jan.status, PayrollCycle.STATUS_PAYSLIPS_GENERATED)

    def test_valid_cycle_passes_the_zero_check(self):
        self.assign(self.emp_a)
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        resp = self.api.post(reverse('payroll-mark-paid', kwargs={'pk': jan.pk}))
        # Fails later on the existing transfer-confirmation rule, not on the new check.
        self.assertNotIn('₹0 gross earnings', resp.data['message'])
        self.assertIn('Salary transfer must be confirmed', resp.data['message'])

    def test_paid_payslip_is_read_only_and_not_recalculated(self):
        jan, _ = self._process_bad()
        PayrollCycle.objects.filter(pk=jan.pk).update(status=PayrollCycle.STATUS_PAID)
        EmployeePayslip.objects.filter(cycle=jan).update(status=EmployeePayslip.STATUS_PAID)
        jan.refresh_from_db()
        # Fixing the structure later changes nothing on the paid payslip.
        SalaryComponent.objects.filter(structure=self.bad).update(calculation_type='percentage_of_ctc')
        with self.assertRaises(PayrollAlreadyProcessing):
            process_payroll_cycle(jan)
        p = self.payslip(jan, self.emp_a)
        detail = self.api.get(reverse('payslip-detail', kwargs={'pk': p.pk})).data['data']
        self.assertEqual((detail['gross_earnings'], detail['net_pay'], detail['status']), ('0.00', '0.00', 'paid'))


class PayslipDetailScopeTests(SalaryFixtureMixin, TestCase):
    """GET /payroll/payslips/<id>/ follows the cycle payslip list's branch scoping."""

    def setUp(self):
        self.make_fixtures()
        self.assign(self.emp_a)
        self.jan = self.cycle(1)
        PayrollCycle.objects.filter(pk=self.jan.pk).update(branch=self.branch)
        self.jan.refresh_from_db()
        process_payroll_cycle(self.jan)
        self.slip = self.payslip(self.jan, self.emp_a)
        self.url = reverse('payslip-detail', kwargs={'pk': self.slip.pk})

    def _client_for(self, email, perms, branch):
        from apps.accounts.factories import make_role, make_user
        from apps.payroll.tests_salary_components import _login
        from rest_framework.test import APIClient
        make_user(email, role=make_role(email.split('@')[0], permission_codenames=perms), branch=branch)
        api = APIClient()
        _login(api, email)
        return api

    def test_same_branch_hr_sees_saved_values(self):
        api = self._client_for('scope.hr@test.com', ['payroll.view'], self.branch.branch_name)
        data = api.get(self.url).data['data']
        self.assertEqual((data['gross_earnings'], data['net_pay'], data['employee_id_code']), ('35000.00', '32990.00', 'SCA'))

    def test_other_branch_hr_cannot_open_it(self):
        api = self._client_for('scope.other@test.com', ['payroll.view'], 'SomeOtherBranch')
        self.assertEqual(api.get(self.url).status_code, 404)

    def test_employee_sees_own_but_not_others(self):
        from apps.payroll.tests_salary_components import _login
        from rest_framework.test import APIClient
        own = APIClient()
        _login(own, self.emp_a.email)
        self.assertEqual(own.get(self.url).status_code, 200)
        other = APIClient()
        _login(other, self.emp_b.email)
        self.assertEqual(other.get(self.url).status_code, 403)
