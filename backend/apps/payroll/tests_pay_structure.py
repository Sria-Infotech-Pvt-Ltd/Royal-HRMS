"""Phase 7A Task C — formula graph, sandboxed evaluator, structure evaluation."""
from decimal import Decimal

from django.test import TestCase

from apps.payroll.models_pay_structure import PayStructure, PayStructureComponent
from apps.payroll.services_pay_structure import (
    FormulaCycleError, FormulaError, build_dependency_graph,
    evaluate_formula, evaluate_structure, preview_structure,
)


def _make_structure(code='TEST_STRUCT'):
    return PayStructure.objects.create(code=code, name=code)


def _add_component(structure, code, **kwargs):
    return PayStructureComponent.objects.create(structure=structure, component_code=code, **kwargs)


class DependencyGraphTests(TestCase):
    def test_topological_order_respects_base_component(self):
        structure = _make_structure()
        _add_component(structure, 'HRA', calculation_method='percentage', base_component_code='BASIC', value=Decimal('40'))
        _add_component(structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('40'))

        order = build_dependency_graph(structure)
        self.assertLess(order.index('BASIC'), order.index('HRA'))

    def test_formula_dependency_ordering(self):
        structure = _make_structure()
        _add_component(structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('40'))
        _add_component(structure, 'SPECIAL', formula='BASIC * 2')

        order = build_dependency_graph(structure)
        self.assertLess(order.index('BASIC'), order.index('SPECIAL'))

    def test_cycle_is_rejected(self):
        structure = _make_structure()
        _add_component(structure, 'A', formula='B + 1')
        _add_component(structure, 'B', formula='A + 1')

        with self.assertRaises(FormulaCycleError):
            build_dependency_graph(structure)

    def test_aggregate_reference_not_treated_as_structure_dependency(self):
        # GROSS_FOR_PF isn't a row in this structure — referencing it must
        # not be mistaken for a dependency edge (no row to order against).
        structure = _make_structure()
        _add_component(structure, 'PF_EE', formula='GROSS_FOR_PF * 0.12')
        order = build_dependency_graph(structure)
        self.assertEqual(order, ['PF_EE'])


class FormulaSandboxTests(TestCase):
    def test_arithmetic_evaluates(self):
        result = evaluate_formula('BASIC * 2 + HRA - 100', {'BASIC': Decimal('1000'), 'HRA': Decimal('400')})
        self.assertEqual(result, Decimal('2300'))

    def test_unknown_reference_raises(self):
        with self.assertRaises(FormulaError):
            evaluate_formula('UNKNOWN_CODE + 1', {})

    def test_function_call_is_rejected(self):
        with self.assertRaises(FormulaError):
            evaluate_formula('__import__("os").system("x")', {})

    def test_attribute_access_is_rejected(self):
        with self.assertRaises(FormulaError):
            evaluate_formula('BASIC.__class__', {'BASIC': Decimal('1')})

    def test_subscript_is_rejected(self):
        with self.assertRaises(FormulaError):
            evaluate_formula('BASIC[0]', {'BASIC': Decimal('1')})


class EvaluateStructureTests(TestCase):
    def test_percentage_and_fixed_methods(self):
        structure = _make_structure()
        _add_component(structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('40'))
        _add_component(structure, 'HRA', calculation_method='percentage', base_component_code='BASIC', value=Decimal('50'))
        _add_component(structure, 'FIXED_ALLOWANCE', calculation_method='fixed', value=Decimal('2000'))

        amounts = evaluate_structure(structure, Decimal('100000'))
        self.assertEqual(amounts['BASIC'], Decimal('40000'))
        self.assertEqual(amounts['HRA'], Decimal('20000'))
        self.assertEqual(amounts['FIXED_ALLOWANCE'], Decimal('2000'))

    def test_balancing_component_absorbs_remainder(self):
        structure = _make_structure()
        structure.balancing_component_code = 'SPECIAL'
        structure.save(update_fields=['balancing_component_code'])
        _add_component(structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('40'))
        _add_component(structure, 'SPECIAL', calculation_method='fixed', value=Decimal('0'))

        amounts = evaluate_structure(structure, Decimal('100000'))
        self.assertEqual(amounts['BASIC'], Decimal('40000'))
        self.assertEqual(amounts['SPECIAL'], Decimal('60000'))

    def test_balancing_component_negative_raises(self):
        structure = _make_structure()
        structure.balancing_component_code = 'SPECIAL'
        structure.save(update_fields=['balancing_component_code'])
        _add_component(structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('150'))
        _add_component(structure, 'SPECIAL', calculation_method='fixed', value=Decimal('0'))

        with self.assertRaises(ValueError):
            evaluate_structure(structure, Decimal('100000'))

    def test_min_max_caps_applied(self):
        structure = _make_structure()
        _add_component(
            structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY',
            value=Decimal('40'), max_amount=Decimal('30000'),
        )
        amounts = evaluate_structure(structure, Decimal('100000'))
        self.assertEqual(amounts['BASIC'], Decimal('30000'))


class PreviewTests(TestCase):
    def test_preview_runs_every_sample_ctc(self):
        structure = _make_structure()
        _add_component(structure, 'BASIC', calculation_method='percentage', base_component_code='CTC_MONTHLY', value=Decimal('40'))

        results = preview_structure(structure, [Decimal('600000'), Decimal('1200000')])
        self.assertEqual(len(results), 2)
        self.assertIsNone(results[0]['error'])
        self.assertEqual(results[0]['breakdown']['BASIC'], Decimal('20000'))
        self.assertEqual(results[1]['breakdown']['BASIC'], Decimal('40000'))

    def test_preview_reports_error_without_raising(self):
        structure = _make_structure()
        _add_component(structure, 'A', formula='B + 1')
        _add_component(structure, 'B', formula='A + 1')

        results = preview_structure(structure, [Decimal('600000')])
        self.assertIsNotNone(results[0]['error'])
        self.assertIsNone(results[0]['breakdown'])
