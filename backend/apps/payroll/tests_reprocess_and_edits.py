"""
Payroll Phase 1 fixes (no calculation-policy change):
1. Re-processing a cycle keeps the reimbursements / bonus HR entered in the
   wizard (it used to reset them to 0 while keeping the bonus breakdown).
2. Editing LOP on a draft payslip charges LOP on the salary components only
   (not on a bonus already added to gross) and re-evaluates the employee ESI
   share, the only statutory figure that depends on LOP days.
3. Re-processing never duplicates payslips or adjustments.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.payroll.models import EmployeePayslip, PayrollAdjustment, PayrollSettings, StatutoryConfig
from apps.payroll.tests_salary_components import SalaryFixtureMixin
from apps.payroll.views.cycles import process_payroll_cycle

D = Decimal
CENT = D('0.01')


class Fixture(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()
        PayrollSettings.objects.get_or_create(defaults={'enable_bonuses': True, 'enable_reimbursements': True})

    def run_cycle(self, ctc='600000'):
        self.assertEqual(self.assign(self.emp_a, ctc=ctc).status_code, 201)
        cycle = self.cycle(1)
        process_payroll_cycle(cycle)
        return cycle

    def edit(self, payslip, body):
        return self.api.patch(reverse('payslip-reimb-bonus', kwargs={'pk': payslip.pk}), body, format='json')

    def components(self, p):
        return p.basic + p.hra + p.special_allowance + sum((D(str(v)) for v in p.other_earnings.values()), D('0'))


class ReprocessKeepsWizardEntriesTests(Fixture):
    def test_bonus_and_reimbursements_survive_reprocessing(self):
        cycle = self.run_cycle()
        slip = self.payslip(cycle, self.emp_a)
        resp = self.edit(slip, {'reimbursements': '1000', 'bonus_breakdown': [{'type': 'Annual', 'amount': '5000'}]})
        self.assertEqual(resp.status_code, 200, resp.data)
        before = self.payslip(cycle, self.emp_a)

        cycle.refresh_from_db()
        process_payroll_cycle(cycle)
        after = self.payslip(cycle, self.emp_a)

        self.assertEqual((after.reimbursements, after.bonus), (D('1000.00'), D('5000.00')))
        self.assertEqual(after.bonus_breakdown, [{'type': 'Annual', 'amount': '5000'}])
        self.assertEqual(after.net_pay, before.net_pay)
        self.assertEqual(after.gross_earnings, before.gross_earnings)
        self.assertEqual(after.net_pay, after.gross_earnings - after.total_deductions)

    def test_reprocess_without_entries_is_unchanged(self):
        cycle = self.run_cycle()
        before = self.payslip(cycle, self.emp_a)
        cycle.refresh_from_db()
        process_payroll_cycle(cycle)
        after = self.payslip(cycle, self.emp_a)
        for field in ('gross_earnings', 'total_deductions', 'net_pay', 'pf_employee', 'esi_employee', 'pt_deduction'):
            self.assertEqual(getattr(after, field), getattr(before, field), field)
        self.assertEqual((after.bonus, after.reimbursements), (D('0'), D('0')))


class NoDuplicatesTests(Fixture):
    def test_reprocessing_twice_keeps_one_payslip_and_applies_adjustment_once(self):
        self.assertEqual(self.assign(self.emp_a).status_code, 201)
        cycle = self.cycle(1)
        PayrollAdjustment.objects.create(employee=self.emp_a, month=cycle.cycle_start, type='addition',
                                         label='Arrear', amount=D('750'))
        for _ in range(3):
            process_payroll_cycle(cycle)
            cycle.refresh_from_db()
        self.assertEqual(EmployeePayslip.objects.filter(cycle=cycle, employee=self.emp_a).count(), 1)
        self.assertEqual(PayrollAdjustment.objects.filter(employee=self.emp_a).count(), 1)
        self.assertEqual(self.payslip(cycle, self.emp_a).adjustments_earning, D('750.00'))


class LopEditTests(Fixture):
    def test_lop_is_charged_on_components_not_on_bonus(self):
        cycle = self.run_cycle()
        slip = self.payslip(cycle, self.emp_a)
        self.assertEqual(self.edit(slip, {'bonus': '10000'}).status_code, 200)
        self.assertEqual(self.edit(self.payslip(cycle, self.emp_a), {'lop_days': '2'}).status_code, 200)
        p = self.payslip(cycle, self.emp_a)
        expected = (self.components(p) / p.total_working_days * 2).quantize(CENT)
        self.assertEqual(p.lop_deduction, expected)
        self.assertEqual(p.net_pay, p.gross_earnings - p.total_deductions)

    def test_lop_edit_re_evaluates_employee_esi_share(self):
        # Gross 15,000 / 26 days ≈ 577 a day: under a 1,000/day threshold the
        # employee is exempt at processing; after LOP edit the rule is re-run.
        StatutoryConfig.objects.filter(state=self.state).update(esi_daily_wage_exemption_threshold=D('1000'))
        cycle = self.run_cycle(ctc='200000')
        slip = self.payslip(cycle, self.emp_a)
        self.assertGreater(slip.esi_employer, 0)
        self.assertEqual(slip.esi_employee, D('0'))

        self.assertEqual(self.edit(slip, {'lop_days': '16'}).status_code, 200)
        p = self.payslip(cycle, self.emp_a)
        statutory = StatutoryConfig.objects.get(state=self.state)
        self.assertEqual(p.esi_employee, (self.components(p) * statutory.esi_employee_rate / 100).quantize(CENT))
        self.assertEqual(p.net_pay, p.gross_earnings - p.total_deductions)

    def test_pf_pt_lwf_unchanged_by_lop_edit(self):
        cycle = self.run_cycle()
        slip = self.payslip(cycle, self.emp_a)
        self.assertEqual(self.edit(slip, {'lop_days': '3'}).status_code, 200)
        p = self.payslip(cycle, self.emp_a)
        self.assertEqual((p.pf_employee, p.pt_deduction, p.lwf_employee),
                         (slip.pf_employee, slip.pt_deduction, slip.lwf_employee))
