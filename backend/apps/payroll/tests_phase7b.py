"""
Phase 7B — consolidated tests across Tasks B-O. Each test class covers one
task's core mechanism with 1-4 targeted tests (scoped down per-task, as
documented in each service module's own docstring) rather than the full
exhaustive matrix — consistent with every other reduced-scope task this
phase.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models_identity_bank import BankAccount
from apps.branch.models import Branch, City, State
from apps.payroll.models import (
    ArrearsRequest, EmployeeLoan, EmployeePayslip, GLMapping, LoanType,
    PayGroup, PayrollCalendar, PayrollCheck, PayrollCycle,
    PayrollRun, PayslipTemplate, SalaryComponent, SalaryStructure,
)
from apps.payroll.services_arrears import preview_compensation_arrears, total_arrears_due
from apps.payroll.services_bank_template import render_row
from apps.payroll.services_gl_journal import generate_journal, is_balanced, unmapped_components
from apps.payroll.services_loans import deduct_emi, foreclose_loan, generate_emi_schedule, outstanding_balance_for_settlement
from apps.payroll.services_multi_entity import CurrencyMismatchError, validate_compensation_currency
from apps.payroll.services_off_cycle import compute_bonus_run_amount, create_reversal, reversal_net_total
from apps.payroll.services_payment_instructions import generate_payment_instructions, total_instructed_amount
from apps.payroll.services_payroll_checks import (
    acknowledge_result, has_blocking_unacknowledged_failures, place_hold, release_hold, run_checks,
)
from apps.payroll.services_payslip_lines import persist_lines_for_payslip
from apps.payroll.services_payslip_template import render_payslip_data
from apps.payroll.services_run import (
    RunFinalizedError, SoDViolationError, approve_run, create_run, diff_versions, finalize_run, recalculate,
)
from apps.payroll.services_pay_calendar import generate_periods


_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee(role_name=None):
    role = make_role(role_name or _unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


def _make_branch():
    state = State.objects.create(name=_unique('State'), code=_unique('S')[:10])
    city = City.objects.create(name=_unique('City'), state=state)
    return Branch.objects.create(branch_code=_unique('BR'), branch_name=_unique('Branch'), address='x', state=state, city=city)


def _make_structure():
    structure = SalaryStructure.objects.create(name=_unique('Structure'))
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


def _make_cycle_and_payslip(employee, structure, created_by, **overrides):
    cycle = PayrollCycle.objects.create(
        cycle_start=datetime.date(2026, 4, 25), cycle_end=datetime.date(2026, 5, 24),
        pay_date=datetime.date(2026, 5, 30), created_by=created_by,
    )
    defaults = dict(
        salary_structure=structure, annual_ctc=Decimal('1200000'), monthly_ctc=Decimal('100000'),
        basic=Decimal('40000'), hra=Decimal('20000'), special_allowance=Decimal('40000'),
        other_earnings={}, reimbursements=Decimal('0'), bonus=Decimal('0'),
        gross_earnings=Decimal('100000'), total_working_days=26, lop_days=Decimal('0'),
        lop_deduction=Decimal('0'), pf_employee=Decimal('0'), pf_employer=Decimal('0'),
        esi_employee=Decimal('0'), esi_employer=Decimal('0'), pt_deduction=Decimal('0'),
        lwf_employee=Decimal('0'), lwf_employer=Decimal('0'), income_tax=Decimal('0'),
        adjustments_earning=Decimal('0'), adjustments_deduction=Decimal('0'),
        total_deductions=Decimal('0'), net_pay=Decimal('100000'),
    )
    defaults.update(overrides)
    payslip = EmployeePayslip.objects.create(cycle=cycle, employee=employee, **defaults)
    return cycle, payslip


def _make_pay_group_and_period():
    calendar = PayrollCalendar.objects.create(code=_unique('CAL'), name='Cal', pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE)
    periods = generate_periods(calendar, 2026)
    pay_group = PayGroup.objects.create(code=_unique('PG'), name='PG', calendar=calendar)
    period = next(p for p in periods if p.period_start.month == 4)
    return pay_group, period


def _make_run(created_by, run_type=PayrollRun.TYPE_REGULAR):
    from apps.payroll.models_run import RunStageTemplate
    pay_group, period = _make_pay_group_and_period()
    stage_template = RunStageTemplate.objects.create(code=_unique('STPL'), name='Default', stage_codes=['calculation', 'review_approval', 'close'])
    return create_run(pay_group, period, stage_template, created_by, run_type=run_type)


class RunLifecycleTests(TestCase):
    def test_sod_blocks_creator_from_approving(self):
        creator = _make_employee()
        run = _make_run(creator)
        with self.assertRaises(SoDViolationError):
            approve_run(creator, run)
        other = _make_employee()
        approve_run(other, run)  # must not raise

    def test_recalculate_versions_and_diffs(self):
        creator = _make_employee()
        run = _make_run(creator)
        v1 = recalculate(run, {'emp1': {'BASIC': '40000'}}, created_by=creator)
        v2 = recalculate(run, {'emp1': {'BASIC': '42000'}}, created_by=creator)
        diff = diff_versions(v1, v2)
        self.assertEqual(diff['emp1']['BASIC']['delta'], '2000')

    def test_finalize_blocks_further_recalculation(self):
        creator = _make_employee()
        run = _make_run(creator)
        recalculate(run, {'emp1': {'BASIC': '40000'}}, created_by=creator)
        finalize_run(run)
        with self.assertRaises(RunFinalizedError):
            recalculate(run, {'emp1': {'BASIC': '41000'}}, created_by=creator)

    def test_cannot_finalize_without_a_version(self):
        creator = _make_employee()
        run = _make_run(creator)
        with self.assertRaises(ValueError):
            finalize_run(run)


class ValidationChecksTests(TestCase):
    def test_negative_net_pay_check_fires_and_blocks(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator, net_pay=Decimal('-500'))
        run = _make_run(creator)
        PayrollCheck.objects.create(code='negative_net_pay', description='x', severity=PayrollCheck.SEVERITY_ERROR, check_function_code='negative_net_pay')

        results = run_checks(run, [payslip])
        self.assertEqual(len(results), 1)
        self.assertTrue(has_blocking_unacknowledged_failures(run))

        acknowledge_result(results[0], creator, 'Known one-off, approved by finance.')
        self.assertFalse(has_blocking_unacknowledged_failures(run))

    def test_hold_and_release(self):
        employee = _make_employee()
        placer = _make_employee()
        hold = place_hold(employee, 'Investigation pending', placed_by=placer)
        self.assertTrue(hold.is_active)
        release_hold(hold, released_by=placer)
        hold.refresh_from_db()
        self.assertFalse(hold.is_active)


class OffCycleAndReversalTests(TestCase):
    def test_bonus_marginal_tds(self):
        result = compute_bonus_run_amount(Decimal('10000'), Decimal('0.1'))
        self.assertEqual(result['TDS'], Decimal('1000.00'))
        self.assertEqual(result['net'], Decimal('9000.00'))

    def test_reversal_never_edits_original_payslip(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)
        persist_lines_for_payslip(payslip)
        original_basic = payslip.basic

        run = _make_run(creator)
        entries = create_reversal(run, payslip, 'Paid to wrong employee.')
        payslip.refresh_from_db()

        self.assertEqual(payslip.basic, original_basic)  # untouched
        basic_entry = next(e for e in entries if e.component_code == 'BASIC')
        self.assertEqual(basic_entry.amount, -original_basic)
        self.assertEqual(reversal_net_total(run), -sum((l.amount for l in payslip.lines.all()), Decimal('0')))


class ArrearsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_tax_year_config')

    def test_compensation_arrears_preview_computes_difference(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)

        request = preview_compensation_arrears(employee, [payslip], Decimal('1800000'), created_by=creator)
        self.assertEqual(request.status, ArrearsRequest.STATUS_PREVIEWED)
        basic_line = request.lines.get(component_code='BASIC')
        self.assertEqual(basic_line.original_amount, Decimal('40000.00'))
        self.assertEqual(basic_line.corrected_amount, Decimal('60000.00'))
        self.assertEqual(total_arrears_due(request) > 0, True)


class LoanTests(TestCase):
    def test_no_interest_schedule_sums_to_principal(self):
        employee = _make_employee()
        loan_type = LoanType.objects.create(code=_unique('LT'), name='No interest', interest_type=LoanType.INTEREST_NONE)
        loan = EmployeeLoan.objects.create(
            employee=employee, loan_type=loan_type, principal_amount=Decimal('10000'),
            tenure_months=3, disbursement_date=datetime.date(2026, 1, 1), outstanding_balance=Decimal('10000'),
        )
        schedule = generate_emi_schedule(loan)
        total = sum((row.principal_component for row in schedule), Decimal('0'))
        self.assertEqual(total, Decimal('10000.00'))

    def test_reducing_balance_schedule_pays_off_exactly(self):
        employee = _make_employee()
        loan_type = LoanType.objects.create(code=_unique('LT'), name='Reducing', interest_type=LoanType.INTEREST_REDUCING, interest_rate=Decimal('12'))
        loan = EmployeeLoan.objects.create(
            employee=employee, loan_type=loan_type, principal_amount=Decimal('12000'),
            tenure_months=12, disbursement_date=datetime.date(2026, 1, 1), outstanding_balance=Decimal('12000'),
        )
        schedule = generate_emi_schedule(loan)
        total_principal = sum((row.principal_component for row in schedule), Decimal('0'))
        self.assertEqual(total_principal, Decimal('12000.00'))

    def test_deduct_emi_reduces_outstanding_balance(self):
        creator = _make_employee()
        employee = _make_employee()
        loan_type = LoanType.objects.create(code=_unique('LT'), name='Simple', interest_type=LoanType.INTEREST_NONE)
        loan = EmployeeLoan.objects.create(
            employee=employee, loan_type=loan_type, principal_amount=Decimal('6000'),
            tenure_months=6, disbursement_date=datetime.date(2026, 1, 1), outstanding_balance=Decimal('6000'),
        )
        schedule = generate_emi_schedule(loan)
        run = _make_run(creator)
        deduct_emi(schedule[0], run)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, Decimal('5000.00'))

    def test_foreclose_zeroes_balance_and_skips_remaining(self):
        employee = _make_employee()
        loan_type = LoanType.objects.create(code=_unique('LT'), name='Simple', interest_type=LoanType.INTEREST_NONE)
        loan = EmployeeLoan.objects.create(
            employee=employee, loan_type=loan_type, principal_amount=Decimal('6000'),
            tenure_months=6, disbursement_date=datetime.date(2026, 1, 1), outstanding_balance=Decimal('6000'),
        )
        generate_emi_schedule(loan)
        foreclose_loan(loan)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, Decimal('0'))
        self.assertEqual(outstanding_balance_for_settlement(employee), Decimal('0'))


class PaymentInstructionTests(TestCase):
    def test_single_primary_account_gets_full_net_pay(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)
        country = _first_country()
        BankAccount.objects.create(employee=employee, country=country, is_primary=True, status=BankAccount.STATUS_ACTIVE)

        instructions = generate_payment_instructions(payslip)
        self.assertEqual(len(instructions), 1)
        self.assertEqual(total_instructed_amount(payslip), payslip.net_pay)

    def test_percentage_and_remainder_split_sums_exactly(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator, net_pay=Decimal('100000'))
        country = _first_country()
        BankAccount.objects.create(
            employee=employee, country=country, is_primary=True, priority=0,
            split_type=BankAccount.SPLIT_PERCENTAGE, split_value=Decimal('30'), status=BankAccount.STATUS_ACTIVE,
        )
        BankAccount.objects.create(
            employee=employee, country=country, priority=1,
            split_type=BankAccount.SPLIT_REMAINDER, status=BankAccount.STATUS_ACTIVE,
        )

        generate_payment_instructions(payslip)
        self.assertEqual(total_instructed_amount(payslip), Decimal('100000.00'))

    def test_no_bank_account_falls_back_to_unassigned_instruction(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)
        instructions = generate_payment_instructions(payslip)
        self.assertEqual(len(instructions), 1)
        self.assertIsNone(instructions[0].bank_account)


def _first_country():
    from apps.platform_core.models import Country
    country, _ = Country.objects.get_or_create(iso2='IN', defaults={'name': 'India', 'iso3': 'IND', 'numeric_code': '356', 'phone_code': '91'})
    return country


class BankTemplateSandboxTests(TestCase):
    def test_render_row_resolves_dotted_source(self):
        employee = _make_employee()
        row = render_row(
            [{'source': 'employee.employee_id', 'label': 'Code'}],
            {'employee': employee}, ',',
        )
        self.assertEqual(row, employee.employee_id)

    def test_render_row_rejects_unsafe_source(self):
        from apps.payroll.services_bank_template import TemplateSandboxError
        with self.assertRaises(TemplateSandboxError):
            render_row([{'source': '__import__("os").system', 'label': 'x'}], {}, ',')


class GLJournalTests(TestCase):
    def test_journal_is_balanced_and_split_by_cost_centre(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        employee.department = 'Engineering'
        employee.save(update_fields=['department'])
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)
        persist_lines_for_payslip(payslip)

        GLMapping.objects.create(component_code='BASIC', debit_account_code='SALARY_EXP', credit_account_code='SALARY_PAYABLE')
        GLMapping.objects.create(component_code='NET_PAY', debit_account_code='SALARY_PAYABLE', credit_account_code='BANK')

        run = _make_run(creator)
        entries = generate_journal(run, [payslip])
        self.assertTrue(len(entries) > 0)
        self.assertTrue(is_balanced(run))
        self.assertTrue(all(e.cost_centre == 'Engineering' for e in entries))

    def test_unmapped_components_are_reported(self):
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)
        persist_lines_for_payslip(payslip)
        run = _make_run(creator)
        unmapped = unmapped_components(run, [payslip])
        self.assertIn('BASIC', unmapped)  # no GLMapping created in this test


class PayslipTemplateTests(TestCase):
    def test_render_payslip_data_groups_by_component_payslip_group(self):
        from django.core.management import call_command
        call_command('seed_pay_components')
        creator = _make_employee()
        structure = _make_structure()
        employee = _make_employee()
        _, payslip = _make_cycle_and_payslip(employee, structure, creator)
        persist_lines_for_payslip(payslip)

        template = PayslipTemplate.objects.create(code=_unique('PST'), name='Default', section_order=['Earnings', 'Summary'])
        data = render_payslip_data(template, payslip)
        self.assertEqual(data['net_pay'], payslip.net_pay)
        earnings_section = next(s for s in data['sections'] if s['group'] == 'Earnings')
        self.assertTrue(any(l['component_code'] == 'BASIC' for l in earnings_section['lines']))


class MultiEntityCurrencyTests(TestCase):
    def test_mismatched_currency_raises(self):
        from apps.platform_core.models import Currency
        from apps.payroll.models import EmployeeCompensation

        inr, _ = Currency.objects.get_or_create(code='INR', defaults={'name': 'Indian Rupee'})
        usd, _ = Currency.objects.get_or_create(code='USD', defaults={'name': 'US Dollar'})
        calendar = PayrollCalendar.objects.create(code=_unique('CAL'), name='Cal')
        pay_group = PayGroup.objects.create(code=_unique('PG'), name='PG', calendar=calendar, currency=usd)

        employee = _make_employee()
        compensation = EmployeeCompensation.objects.create(
            employee=employee, annual_ctc=Decimal('1200000'), effective_from=datetime.date(2026, 1, 1), currency=inr,
        )
        with self.assertRaises(CurrencyMismatchError):
            validate_compensation_currency(compensation, pay_group)

    def test_matching_currency_does_not_raise(self):
        from apps.platform_core.models import Currency
        from apps.payroll.models import EmployeeCompensation

        usd, _ = Currency.objects.get_or_create(code='USD', defaults={'name': 'US Dollar'})
        calendar = PayrollCalendar.objects.create(code=_unique('CAL'), name='Cal')
        pay_group = PayGroup.objects.create(code=_unique('PG'), name='PG', calendar=calendar, currency=usd)

        employee = _make_employee()
        compensation = EmployeeCompensation.objects.create(
            employee=employee, annual_ctc=Decimal('1200000'), effective_from=datetime.date(2026, 1, 1), currency=usd,
        )
        validate_compensation_currency(compensation, pay_group)  # must not raise
