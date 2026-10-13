"""Phase 7A Task J — shadow_recompute_payslip / run_shadow_sweep / enable_payroll_v2 gate."""
import datetime
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.payroll.models import (
    EmployeePayslip, PayrollCycle, PayrollV2Entitlement, PayslipShadowRunResult,
    SalaryComponent, SalaryStructure,
)
from apps.payroll.services_shadow_run import (
    PayrollV2GateError, approve_shadow_run_exception, enable_payroll_v2, run_shadow_sweep, shadow_recompute_payslip,
)


def _make_structure():
    structure = SalaryStructure.objects.create(name='Shadow Run Test Structure')
    SalaryComponent.objects.create(
        structure=structure, name='Basic', component_type=SalaryComponent.TYPE_EARNING,
        calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=0,
    )
    SalaryComponent.objects.create(
        structure=structure, name='HRA', component_type=SalaryComponent.TYPE_ALLOWANCE,
        calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('20'), order=1,
    )
    SalaryComponent.objects.create(
        structure=structure, name='Special Allowance', component_type=SalaryComponent.TYPE_ALLOWANCE,
        calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=2,
    )
    return structure


_state_code_counter = [0]


def _make_branch_and_employee(role_name, employee_email):
    _state_code_counter[0] += 1
    state = State.objects.create(name=f'State-{role_name}', code=f'S{_state_code_counter[0]:03d}')
    city = City.objects.create(name=f'City-{role_name}', state=state)
    branch = Branch.objects.create(
        branch_code=f'BR-{role_name}', branch_name=f'Branch {role_name}',
        address='Addr', state=state, city=city,
    )
    role = make_role(role_name)
    employee = make_user(employee_email, role=role, password='TestPass123!')
    employee.branch = branch.branch_name
    employee.save(update_fields=['branch'])
    return branch, employee


def _make_cycle(cycle_start, created_by, branch=None):
    return PayrollCycle.objects.create(
        cycle_start=cycle_start, cycle_end=cycle_start.replace(day=28),
        pay_date=cycle_start, created_by=created_by, branch=branch,
    )


def _make_payslip(employee, cycle, structure, **overrides):
    defaults = dict(
        salary_structure=structure,
        annual_ctc=Decimal('1200000'), monthly_ctc=Decimal('100000'),
        basic=Decimal('40000'), hra=Decimal('20000'), special_allowance=Decimal('40000'),
        other_earnings={}, reimbursements=Decimal('0'), bonus=Decimal('0'),
        gross_earnings=Decimal('100000'), total_working_days=26, lop_days=Decimal('0'),
        lop_deduction=Decimal('0'), pf_wage_base=Decimal('15000'),
        pf_employee=Decimal('1800'), pf_employer=Decimal('1800'),
        esi_employee=Decimal('0'), esi_employer=Decimal('0'),
        pt_deduction=Decimal('0'), lwf_employee=Decimal('0'), lwf_employer=Decimal('0'),
        income_tax=Decimal('0'), adjustments_earning=Decimal('0'), adjustments_deduction=Decimal('0'),
        total_deductions=Decimal('1800'), net_pay=Decimal('98200'),
    )
    defaults.update(overrides)
    return EmployeePayslip.objects.create(cycle=cycle, employee=employee, **defaults)


class ShadowRecomputeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_schemes')
        call_command('seed_tax_year_config')

    def test_matching_payslip_persists_clean_result(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('srmatch', 'shadowrun.match@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure)

        result = shadow_recompute_payslip(payslip)
        self.assertTrue(result.is_match, result.diffs or result.error)
        self.assertEqual(result.diffs, {})

    def test_mismatched_payslip_records_specific_diff(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('srmismatch', 'shadowrun.mismatch@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        # Stored basic deliberately wrong vs. what the structure actually computes (40% of 100000 = 40000).
        payslip = _make_payslip(employee, cycle, structure, basic=Decimal('99999'))

        result = shadow_recompute_payslip(payslip)
        self.assertFalse(result.is_match)
        self.assertIn('basic', result.diffs)
        self.assertEqual(result.diffs['basic']['stored'], '99999.00')

    def test_missing_structure_is_reported_as_error_not_silently_skipped(self):
        branch, employee = _make_branch_and_employee('srnostruct', 'shadowrun.nostruct@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure=None)

        result = shadow_recompute_payslip(payslip)
        self.assertFalse(result.is_match)
        self.assertTrue(result.error)

    def test_rerun_updates_the_same_result_row_not_a_duplicate(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('srrerun', 'shadowrun.rerun@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure)

        shadow_recompute_payslip(payslip)
        shadow_recompute_payslip(payslip)
        self.assertEqual(PayslipShadowRunResult.objects.filter(payslip=payslip).count(), 1)


class RunShadowSweepTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_schemes')
        call_command('seed_tax_year_config')

    def test_sweep_counts_match_and_mismatch_separately(self):
        structure = _make_structure()
        branch, good_employee = _make_branch_and_employee('sweepgood', 'sweep.good@example.com')
        _, bad_employee = _make_branch_and_employee('sweepbad', 'sweep.bad@example.com')
        good_cycle = _make_cycle(datetime.date(2026, 4, 25), good_employee, branch)
        bad_cycle = _make_cycle(datetime.date(2026, 5, 25), bad_employee, branch)
        _make_payslip(good_employee, good_cycle, structure)
        _make_payslip(bad_employee, bad_cycle, structure, basic=Decimal('1'))

        summary = run_shadow_sweep(EmployeePayslip.objects.filter(employee__in=[good_employee, bad_employee]))
        self.assertEqual(summary['matched'], 1)
        self.assertEqual(summary['mismatched'], 1)


class EnablePayrollV2GateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_schemes')
        call_command('seed_tax_year_config')

    def test_cannot_enable_with_outstanding_mismatches(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('gateblock', 'gate.block@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure, basic=Decimal('1'))
        shadow_recompute_payslip(payslip)

        with self.assertRaises(PayrollV2GateError):
            enable_payroll_v2()
        self.assertFalse(PayrollV2Entitlement.objects.filter(legal_entity=None, is_enabled=True).exists())

    def test_can_enable_with_an_owner_approved_exception(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('gateapprove', 'gate.approve@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure, basic=Decimal('1'))
        result = shadow_recompute_payslip(payslip)
        self.assertFalse(result.is_match)

        with self.assertRaises(PayrollV2GateError):
            enable_payroll_v2()

        approve_shadow_run_exception(result, 'Explained: historical config drift, confirmed by timestamp.')
        entitlement = enable_payroll_v2()
        self.assertTrue(entitlement.is_enabled)

    def test_approval_requires_a_note(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('gatenonote', 'gate.nonote@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure, basic=Decimal('1'))
        result = shadow_recompute_payslip(payslip)

        with self.assertRaises(ValueError):
            approve_shadow_run_exception(result, '   ')

    def test_can_enable_once_every_payslip_matches(self):
        structure = _make_structure()
        branch, employee = _make_branch_and_employee('gatepass', 'gate.pass@example.com')
        cycle = _make_cycle(datetime.date(2026, 4, 25), employee, branch)
        payslip = _make_payslip(employee, cycle, structure)
        shadow_recompute_payslip(payslip)

        entitlement = enable_payroll_v2()
        self.assertTrue(entitlement.is_enabled)
