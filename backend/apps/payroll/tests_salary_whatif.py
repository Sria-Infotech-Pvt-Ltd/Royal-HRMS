"""Phase 7A Task K — what_if_salary_breakdown()."""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.branch.models import State
from apps.payroll.models import SalaryComponent, SalaryStructure, StatutoryConfig
from apps.payroll.services_salary_whatif import what_if_salary_breakdown


def _make_structure():
    structure = SalaryStructure.objects.create(name='Whatif Test Structure')
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


class WhatIfBreakdownTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_schemes')
        call_command('seed_tax_year_config')
        cls.structure = _make_structure()
        cls.state = State.objects.create(name='WhatifState', code='WS')
        StatutoryConfig.objects.create(
            state=cls.state, pt_applicable=True,
            pt_slabs=[{'min': 0, 'max': None, 'amount': 200}],
            esi_applicable=True, esi_wage_ceiling=Decimal('21000.00'),
            esi_employee_rate=Decimal('0.75'), esi_employer_rate=Decimal('3.25'),
        )
        call_command('seed_statutory_schemes')

    def test_basic_whatif_shape_and_label(self):
        result = what_if_salary_breakdown(
            Decimal('1200000'), self.structure, is_metro=False, statutory_state=self.state,
        )
        self.assertTrue(result['is_estimate'])
        self.assertIn('not a real payslip', result['estimate_note'])
        self.assertEqual(result['monthly_breakdown']['basic'], Decimal('40000'))

    def test_metro_vs_non_metro_hra_differs(self):
        metro = what_if_salary_breakdown(Decimal('1200000'), self.structure, is_metro=True)
        non_metro = what_if_salary_breakdown(Decimal('1200000'), self.structure, is_metro=False)
        self.assertGreater(metro['monthly_breakdown']['hra'], non_metro['monthly_breakdown']['hra'])

    def test_annual_breakdown_is_twelve_times_monthly(self):
        result = what_if_salary_breakdown(Decimal('1200000'), self.structure)
        self.assertEqual(result['annual_breakdown']['basic'], result['monthly_breakdown']['basic'] * 12)

    def test_no_lop_or_adjustments_modeled(self):
        result = what_if_salary_breakdown(
            Decimal('1200000'), self.structure, statutory_state=self.state,
        )
        # Gross should equal basic+hra+special exactly — nothing deducted for LOP (none modeled).
        monthly = result['monthly_breakdown']
        self.assertEqual(
            monthly['gross_earnings'],
            monthly['basic'] + monthly['hra'] + monthly['special_allowance'],
        )
