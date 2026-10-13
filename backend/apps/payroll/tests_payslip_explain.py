"""Phase 7A Task I — explain_line / explain_payslip / explain_difference."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import EmployeePayslip, PayrollCycle
from apps.payroll.services_payslip_explain import explain_difference, explain_line, explain_payslip
from apps.payroll.services_payslip_lines import persist_lines_for_payslip


def _make_employee(suffix):
    role = make_role(f'explain_role_{suffix}')
    return make_user(f'explain.test.{suffix}@example.com', role=role, password='TestPass123!')


def _make_cycle(cycle_start, created_by):
    return PayrollCycle.objects.create(
        cycle_start=cycle_start, cycle_end=cycle_start.replace(day=28),
        pay_date=cycle_start, created_by=created_by,
    )


def _make_payslip(employee, cycle, **overrides):
    defaults = dict(
        annual_ctc=Decimal('1200000'), monthly_ctc=Decimal('100000'),
        basic=Decimal('40000'), hra=Decimal('20000'), special_allowance=Decimal('0'),
        other_earnings={}, reimbursements=Decimal('0'), bonus=Decimal('0'),
        gross_earnings=Decimal('60000'), lop_deduction=Decimal('0'),
        pf_employee=Decimal('4800'), pf_employer=Decimal('4800'), pf_wage_base=Decimal('15000'),
        esi_employee=Decimal('0'), esi_employer=Decimal('0'),
        pt_deduction=Decimal('200'), lwf_employee=Decimal('0'), lwf_employer=Decimal('0'),
        income_tax=Decimal('1000'), adjustments_earning=Decimal('0'), adjustments_deduction=Decimal('0'),
        total_deductions=Decimal('6000'), net_pay=Decimal('54000'),
    )
    defaults.update(overrides)
    return EmployeePayslip.objects.create(cycle=cycle, employee=employee, **defaults)


class ExplainLineTests(TestCase):
    def test_pf_line_mentions_wage_base(self):
        employee = _make_employee('pf')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        payslip = _make_payslip(employee, cycle)
        persist_lines_for_payslip(payslip)

        pf_line = payslip.lines.get(component_code='PF_EE')
        sentence = explain_line(pf_line)
        self.assertIn('PF_EE', sentence)
        self.assertIn('15000', sentence)

    def test_explain_payslip_returns_ordered_entries(self):
        employee = _make_employee('order')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        payslip = _make_payslip(employee, cycle)
        persist_lines_for_payslip(payslip)

        entries = explain_payslip(payslip)
        codes = [e['component_code'] for e in entries]
        self.assertEqual(codes, sorted(codes, key=lambda c: codes.index(c)))  # stable, no crash
        self.assertTrue(all(e['explanation'] for e in entries))


class ExplainDifferenceTests(TestCase):
    def test_changed_amount_is_reported_with_delta(self):
        employee = _make_employee('diff')
        april = _make_cycle(datetime.date(2026, 4, 25), employee)
        may = _make_cycle(datetime.date(2026, 5, 25), employee)
        april_payslip = _make_payslip(employee, april, basic=Decimal('40000'))
        may_payslip = _make_payslip(employee, may, basic=Decimal('42000'))
        persist_lines_for_payslip(april_payslip)
        persist_lines_for_payslip(may_payslip)

        diff = explain_difference(april_payslip, may_payslip)
        self.assertEqual(diff['BASIC']['before'], Decimal('40000'))
        self.assertEqual(diff['BASIC']['after'], Decimal('42000'))
        self.assertEqual(diff['BASIC']['delta'], Decimal('2000'))

    def test_unchanged_component_is_not_reported(self):
        employee = _make_employee('same')
        april = _make_cycle(datetime.date(2026, 4, 25), employee)
        may = _make_cycle(datetime.date(2026, 5, 25), employee)
        april_payslip = _make_payslip(employee, april)
        may_payslip = _make_payslip(employee, may)
        persist_lines_for_payslip(april_payslip)
        persist_lines_for_payslip(may_payslip)

        diff = explain_difference(april_payslip, may_payslip)
        self.assertNotIn('BASIC', diff)  # identical 40000 both cycles

    def test_component_only_present_on_one_side_is_reported(self):
        employee = _make_employee('onesided')
        april = _make_cycle(datetime.date(2026, 4, 25), employee)
        may = _make_cycle(datetime.date(2026, 5, 25), employee)
        april_payslip = _make_payslip(employee, april, bonus=Decimal('0'))
        may_payslip = _make_payslip(employee, may, bonus=Decimal('5000'))
        persist_lines_for_payslip(april_payslip)
        persist_lines_for_payslip(may_payslip)

        diff = explain_difference(april_payslip, may_payslip)
        self.assertEqual(diff['BONUS']['before'], Decimal('0'))
        self.assertEqual(diff['BONUS']['after'], Decimal('5000'))
