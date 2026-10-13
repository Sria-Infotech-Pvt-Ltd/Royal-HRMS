"""
Phase 7A Task J — proves compute_payslip_via_new_data() (the composer)
reproduces apps.payroll.engine.legacy._compute_employee_payslip() EXACTLY
for identical inputs, across the real calculation types this company
actually uses (percentage_of_ctc Basic/HRA/Special, metro HRA, PF default
vs none, ESI/PT/LWF via a real state config, adjustments, proration).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase

from apps.branch.models import State
from apps.payroll.engine.legacy import _compute_employee_payslip
from apps.payroll.models import PayrollAdjustment, SalaryComponent, SalaryStructure, StatutoryConfig
from apps.payroll.services_shadow_engine import compute_payslip_via_new_data


def _make_structure_with_metro_hra():
    structure = SalaryStructure.objects.create(name='Shadow Test Structure')
    SalaryComponent.objects.create(
        structure=structure, name='Basic', component_type=SalaryComponent.TYPE_EARNING,
        calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=0,
    )
    SalaryComponent.objects.create(
        structure=structure, name='HRA', component_type=SalaryComponent.TYPE_ALLOWANCE,
        calculation_type=SalaryComponent.CALC_METRO_HRA, value=Decimal('0'), order=1,
    )
    SalaryComponent.objects.create(
        structure=structure, name='Special Allowance', component_type=SalaryComponent.TYPE_ALLOWANCE,
        calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('30'), order=2,
    )
    return structure


def _salary_config(monthly_ctc, annual_ctc=None):
    return SimpleNamespace(monthly_ctc=monthly_ctc, annual_ctc=annual_ctc or monthly_ctc * 12)


class ShadowEngineParityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_schemes')  # company-wide PF/EPS/... defaults
        call_command('seed_tax_year_config')
        cls.structure = _make_structure_with_metro_hra()
        cls.state = State.objects.create(name='ShadowState', code='SS')
        StatutoryConfig.objects.create(
            state=cls.state, pt_applicable=True,
            pt_slabs=[{'min': 0, 'max': 20000, 'amount': 100}, {'min': 20001, 'max': None, 'amount': 200}],
            esi_applicable=True, esi_wage_ceiling=Decimal('21000.00'),
            esi_employee_rate=Decimal('0.75'), esi_employer_rate=Decimal('3.25'),
            lwf_applicable=True, lwf_employee_amount=Decimal('20'), lwf_employer_amount=Decimal('60'),
            lwf_frequency=StatutoryConfig.LWF_MONTHLY,
        )
        call_command('seed_statutory_schemes')  # re-run to pick up the new state's rows

    def _run_both(self, monthly_ctc, **kwargs):
        components = list(self.structure.components.filter(is_active=True).order_by('order'))
        salary_config = _salary_config(monthly_ctc)
        adjustments = kwargs.pop('adjustments', [])

        legacy_result = _compute_employee_payslip(
            salary_config, components, None, StatutoryConfig.objects.get(state=self.state),
            adjustments, self.structure, **kwargs,
        )
        new_result = compute_payslip_via_new_data(
            salary_config, self.structure, None, self.state, adjustments, **kwargs,
        )
        return legacy_result, new_result

    def _assert_fields_match(self, legacy_result, new_result, fields):
        for field in fields:
            self.assertEqual(
                legacy_result[field], new_result[field],
                f'Mismatch on {field}: legacy={legacy_result[field]} new={new_result[field]}',
            )

    NUMERIC_FIELDS = [
        'basic', 'hra', 'special_allowance', 'gross_earnings', 'lop_deduction',
        'pf_wage_base', 'pf_employee', 'pf_employer', 'esi_employee', 'esi_employer',
        'pt_deduction', 'lwf_employee', 'lwf_employer', 'income_tax',
        'adjustments_earning', 'adjustments_deduction', 'total_deductions', 'net_pay',
    ]

    def test_basic_case_non_metro(self):
        legacy, new = self._run_both(
            Decimal('100000'), is_metro=False, cycle_month=4, total_working_days=26,
        )
        self._assert_fields_match(legacy, new, self.NUMERIC_FIELDS)

    def test_metro_hra_applies_50_percent(self):
        legacy, new = self._run_both(
            Decimal('100000'), is_metro=True, cycle_month=4, total_working_days=26,
        )
        self.assertEqual(legacy['hra'], Decimal('20000'))  # 50% of 40000 basic
        self._assert_fields_match(legacy, new, self.NUMERIC_FIELDS)

    def test_lop_days_and_adjustments(self):
        adjustments = [
            PayrollAdjustment(type=PayrollAdjustment.ADDITION, amount=Decimal('2000')),
            PayrollAdjustment(type=PayrollAdjustment.DEDUCTION, amount=Decimal('500')),
        ]
        legacy, new = self._run_both(
            Decimal('100000'), is_metro=False, cycle_month=4, total_working_days=26,
            lop_days=Decimal('2'), adjustments=adjustments,
        )
        self._assert_fields_match(legacy, new, self.NUMERIC_FIELDS)

    def test_proration_factor_applied(self):
        legacy, new = self._run_both(
            Decimal('100000'), is_metro=False, cycle_month=4, total_working_days=26,
            proration_factor=Decimal('0.5'),
        )
        self._assert_fields_match(legacy, new, self.NUMERIC_FIELDS)

    def test_old_regime_with_declared_investments(self):
        legacy, new = self._run_both(
            Decimal('150000'), is_metro=False, cycle_month=4, total_working_days=26,
            tax_regime='old', declared_investments={'80C': '150000', '80D': '20000'},
        )
        self._assert_fields_match(legacy, new, self.NUMERIC_FIELDS)

    def test_esi_wage_above_ceiling_but_covered_earlier_this_period(self):
        legacy, new = self._run_both(
            Decimal('250000'), is_metro=False, cycle_month=4, total_working_days=26,
            esi_covered_earlier_this_period=True,
        )
        self._assert_fields_match(legacy, new, self.NUMERIC_FIELDS)

    def test_bridge_is_idempotent_across_repeated_calls(self):
        from apps.payroll.models import PayStructureComponent
        self._run_both(Decimal('100000'), is_metro=False, cycle_month=4, total_working_days=26)
        first_count = PayStructureComponent.objects.filter(structure__code__startswith='LB:').count()
        self._run_both(Decimal('100000'), is_metro=False, cycle_month=4, total_working_days=26)
        second_count = PayStructureComponent.objects.filter(structure__code__startswith='LB:').count()
        self.assertEqual(first_count, second_count)
