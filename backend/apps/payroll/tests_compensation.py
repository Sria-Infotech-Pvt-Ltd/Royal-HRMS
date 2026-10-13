"""Phase 7A Task D — create_compensation() dual-write and ctc_breakup()."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import EmployeeSalaryConfig
from apps.payroll.models_compensation import EmployeeCompensation
from apps.payroll.models_pay_structure import PayStructure, PayStructureComponent
from apps.payroll.services_compensation import create_compensation, ctc_breakup, resolve_compensation


def _make_employee():
    role = make_role('emp_comp_role')
    return make_user('compensation.test@example.com', role=role, password='TestPass123!')


def _make_published_structure(code='COMP_TEST_STRUCT'):
    structure = PayStructure.objects.create(code=code, name=code, status=PayStructure.STATUS_PUBLISHED)
    PayStructureComponent.objects.create(
        structure=structure, component_code='BASIC',
        calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('40'),
    )
    return structure


class CreateCompensationTests(TestCase):
    def test_dual_write_creates_both_rows_linked(self):
        employee = _make_employee()
        structure = _make_published_structure()

        compensation, legacy = create_compensation(
            employee, Decimal('600000'), date(2026, 1, 1),
            pay_structure=structure, reason='increment',
        )

        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=employee).count(), 1)
        self.assertEqual(EmployeeCompensation.objects.filter(employee=employee).count(), 1)
        self.assertEqual(compensation.legacy_salary_config_id, legacy.id)
        self.assertEqual(legacy.annual_ctc, Decimal('600000'))
        self.assertEqual(compensation.annual_ctc, Decimal('600000'))

    def test_resolve_compensation_picks_latest_effective_row(self):
        employee = _make_employee()
        create_compensation(employee, Decimal('600000'), date(2025, 1, 1))
        create_compensation(employee, Decimal('720000'), date(2026, 1, 1))

        resolved = resolve_compensation(employee, date(2026, 6, 1))
        self.assertEqual(resolved.annual_ctc, Decimal('720000'))

        resolved_earlier = resolve_compensation(employee, date(2025, 6, 1))
        self.assertEqual(resolved_earlier.annual_ctc, Decimal('600000'))


class CtcBreakupTests(TestCase):
    def test_breakup_uses_pinned_structure_and_traces_it(self):
        employee = _make_employee()
        structure = _make_published_structure()
        create_compensation(employee, Decimal('1200000'), date(2026, 1, 1), pay_structure=structure)

        result = ctc_breakup(employee, date(2026, 6, 1))
        self.assertEqual(result['structure_code'], structure.code)
        self.assertEqual(result['monthly_ctc'], Decimal('100000'))
        self.assertEqual(result['monthly_breakdown']['BASIC'], Decimal('40000'))
        self.assertEqual(result['annual_breakdown']['BASIC'], Decimal('480000'))

    def test_breakup_returns_none_without_a_resolvable_compensation(self):
        employee = _make_employee()
        self.assertIsNone(ctc_breakup(employee, date(2026, 6, 1)))

    def test_override_value_replaces_structure_amount(self):
        employee = _make_employee()
        structure = _make_published_structure()
        compensation, _ = create_compensation(
            employee, Decimal('1200000'), date(2026, 1, 1), pay_structure=structure,
            component_overrides=[{'component_code': 'BASIC', 'value': Decimal('55000')}],
        )

        result = ctc_breakup(employee, date(2026, 6, 1))
        self.assertEqual(result['monthly_breakdown']['BASIC'], Decimal('55000'))
        self.assertIn('BASIC', result['overrides_applied'])
