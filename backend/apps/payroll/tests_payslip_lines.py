"""Phase 7A Task E — build_lines_for_payslip() mapping and YTD accumulation."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import EmployeePayslip, PayrollCycle
from apps.payroll.models_payslip_line import PayslipLine
from apps.payroll.services_payslip_lines import build_lines_for_payslip, persist_lines_for_payslip


def _make_employee():
    role = make_role('payslip_line_role')
    return make_user('payslipline.test@example.com', role=role, password='TestPass123!')


def _make_cycle(cycle_start, created_by):
    return PayrollCycle.objects.create(
        cycle_start=cycle_start,
        cycle_end=cycle_start.replace(day=28),
        pay_date=cycle_start,
        created_by=created_by,
    )


def _make_payslip(employee, cycle, **overrides):
    defaults = dict(
        annual_ctc=Decimal('1200000'), monthly_ctc=Decimal('100000'),
        basic=Decimal('40000'), hra=Decimal('20000'), special_allowance=Decimal('0'),
        other_earnings={'Shift Allowance': 1500.0},
        reimbursements=Decimal('0'), bonus=Decimal('0'),
        gross_earnings=Decimal('61500'), lop_deduction=Decimal('0'),
        pf_employee=Decimal('4800'), pf_employer=Decimal('4800'),
        esi_employee=Decimal('0'), esi_employer=Decimal('0'),
        pt_deduction=Decimal('200'), lwf_employee=Decimal('0'), lwf_employer=Decimal('0'),
        income_tax=Decimal('1000'),
        adjustments_earning=Decimal('0'), adjustments_deduction=Decimal('0'),
        total_deductions=Decimal('6000'), net_pay=Decimal('55500'),
    )
    defaults.update(overrides)
    return EmployeePayslip.objects.create(cycle=cycle, employee=employee, **defaults)


class BuildLinesTests(TestCase):
    def test_zero_amount_scalar_columns_are_skipped(self):
        employee = _make_employee()
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        payslip = _make_payslip(employee, cycle)

        lines = build_lines_for_payslip(payslip)
        codes = {line['component_code'] for line in lines}
        self.assertIn('BASIC', codes)
        self.assertNotIn('ESI_EE', codes)   # was 0 and ESI_EE.show_if_zero is False
        self.assertNotIn('LWF_EE', codes)

    def test_other_earnings_entry_gets_a_derived_code(self):
        employee = _make_employee()
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        payslip = _make_payslip(employee, cycle)

        lines = build_lines_for_payslip(payslip)
        other_lines = [l for l in lines if l['component_code'].startswith('OTHER:')]
        self.assertEqual(len(other_lines), 1)
        self.assertEqual(other_lines[0]['component_code'], 'OTHER:SHIFT_ALLOWANCE')
        self.assertEqual(other_lines[0]['amount'], Decimal('1500.0'))

    def test_net_pay_and_basic_always_present(self):
        employee = _make_employee()
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        payslip = _make_payslip(employee, cycle)

        lines = {l['component_code']: l['amount'] for l in build_lines_for_payslip(payslip)}
        self.assertEqual(lines['BASIC'], Decimal('40000'))
        self.assertEqual(lines['NET_PAY'], Decimal('55500'))


class PersistAndYtdTests(TestCase):
    def test_ytd_accumulates_within_financial_year_in_cycle_order(self):
        employee = _make_employee()
        april_cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        may_cycle = _make_cycle(datetime.date(2026, 5, 25), employee)

        april_payslip = _make_payslip(employee, april_cycle, basic=Decimal('40000'))
        may_payslip = _make_payslip(employee, may_cycle, basic=Decimal('42000'))

        persist_lines_for_payslip(april_payslip)
        persist_lines_for_payslip(may_payslip)

        april_basic = PayslipLine.objects.get(payslip=april_payslip, component_code='BASIC')
        may_basic = PayslipLine.objects.get(payslip=may_payslip, component_code='BASIC')
        self.assertEqual(april_basic.ytd_amount, Decimal('40000'))
        self.assertEqual(may_basic.ytd_amount, Decimal('82000'))

    def test_new_financial_year_resets_ytd(self):
        employee = _make_employee()
        march_cycle = _make_cycle(datetime.date(2026, 3, 25), employee)
        april_cycle = _make_cycle(datetime.date(2026, 4, 25), employee)

        march_payslip = _make_payslip(employee, march_cycle, basic=Decimal('40000'))
        april_payslip = _make_payslip(employee, april_cycle, basic=Decimal('42000'))

        persist_lines_for_payslip(march_payslip)
        persist_lines_for_payslip(april_payslip)

        april_basic = PayslipLine.objects.get(payslip=april_payslip, component_code='BASIC')
        self.assertEqual(april_basic.ytd_amount, Decimal('42000'))  # not 82000 — new FY

    def test_persist_is_idempotent_on_reprocess(self):
        employee = _make_employee()
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee)
        payslip = _make_payslip(employee, cycle)

        persist_lines_for_payslip(payslip)
        first_count = PayslipLine.objects.filter(payslip=payslip).count()
        persist_lines_for_payslip(payslip)
        second_count = PayslipLine.objects.filter(payslip=payslip).count()
        self.assertEqual(first_count, second_count)
