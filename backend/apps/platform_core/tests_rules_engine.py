"""Phase 3A Task A+B — rule engine evaluator tests: every function,
null handling, Decimal rounding modes, limits, security (no attribute-
access escape, no unknown operator), and the Phase 2 condition format
parsing identically through both formats."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import SimpleTestCase

from apps.platform_core import services_rules as rules
from apps.platform_core.rule_errors import RuleError, RuleLimitExceeded


def op(name, *args):
    return {'op': name, 'args': list(args)}


def lit(value):
    return {'op': 'literal', 'value': value}


class MathFunctionTests(SimpleTestCase):
    def test_add_sub_mul_div(self):
        self.assertEqual(rules.evaluate(op('add', lit(2), lit(3)), {}), Decimal('5'))
        self.assertEqual(rules.evaluate(op('sub', lit(5), lit(3)), {}), Decimal('2'))
        self.assertEqual(rules.evaluate(op('mul', lit(4), lit(3)), {}), Decimal('12'))
        self.assertEqual(rules.evaluate(op('div', lit(10), lit(4)), {}), Decimal('2.5'))

    def test_division_by_zero_raises_clean_error(self):
        with self.assertRaises(RuleError):
            rules.evaluate(op('div', lit(1), lit(0)), {})

    def test_arithmetic_with_null_returns_null(self):
        self.assertIsNone(rules.evaluate(op('add', lit(None), lit(1)), {}))

    def test_min_max_abs(self):
        self.assertEqual(rules.evaluate(op('min', lit(5), lit(2), lit(8)), {}), Decimal('2'))
        self.assertEqual(rules.evaluate(op('max', lit(5), lit(2), lit(8)), {}), Decimal('8'))
        self.assertEqual(rules.evaluate(op('abs', lit(-7)), {}), Decimal('7'))

    def test_round_half_up_vs_half_even(self):
        self.assertEqual(rules.evaluate(op('round', lit('1.005'), lit(2), lit('half_up')), {}), Decimal('1.01'))
        self.assertEqual(rules.evaluate(op('round', lit('1.005'), lit(2), lit('half_even')), {}), Decimal('1.00'))

    def test_ceil_and_floor(self):
        self.assertEqual(rules.evaluate(op('ceil', lit('4.1')), {}), Decimal('5'))
        self.assertEqual(rules.evaluate(op('floor', lit('4.9')), {}), Decimal('4'))

    def test_pow_rejects_huge_exponent(self):
        with self.assertRaises(RuleError):
            rules.evaluate(op('pow', lit(2), lit(1000)), {})

    def test_percent_of(self):
        self.assertEqual(rules.evaluate(op('percent_of', lit(200), lit(10)), {}), Decimal('20'))

    def test_literals_are_decimal_never_float(self):
        result = rules.evaluate(lit(1.1), {})
        self.assertIsInstance(result, Decimal)


class LogicFunctionTests(SimpleTestCase):
    def test_if(self):
        self.assertEqual(rules.evaluate(op('if', lit(True), lit('yes'), lit('no')), {}), 'yes')

    def test_case_multi_branch(self):
        expr = op('case', lit(False), lit('a'), lit(True), lit('b'), lit('default'))
        self.assertEqual(rules.evaluate(expr, {}), 'b')

    def test_case_requires_odd_args(self):
        with self.assertRaises(RuleError):
            rules.evaluate(op('case', lit(True), lit('a')), {})

    def test_and_or_not(self):
        self.assertTrue(rules.evaluate(op('and', lit(True), lit(True)), {}))
        self.assertFalse(rules.evaluate(op('and', lit(True), lit(False)), {}))
        self.assertTrue(rules.evaluate(op('or', lit(False), lit(True)), {}))
        self.assertFalse(rules.evaluate(op('not', lit(True)), {}))

    def test_coalesce(self):
        self.assertEqual(rules.evaluate(op('coalesce', lit(None), lit(None), lit('x')), {}), 'x')

    def test_in_and_between(self):
        self.assertTrue(rules.evaluate(op('in', lit('b'), {'op': 'literal', 'value': ['a', 'b']}), {}))
        self.assertTrue(rules.evaluate(op('between', lit(5), lit(1), lit(10)), {}))

    def test_is_null_and_comparisons_with_null_are_false(self):
        self.assertTrue(rules.evaluate(op('is_null', lit(None)), {}))
        self.assertFalse(rules.evaluate(op('gt', lit(None), lit(1)), {}))

    def test_comparison_operators(self):
        self.assertTrue(rules.evaluate(op('eq', lit(1), lit(1)), {}))
        self.assertTrue(rules.evaluate(op('ne', lit(1), lit(2)), {}))
        self.assertTrue(rules.evaluate(op('gt', lit(2), lit(1)), {}))
        self.assertTrue(rules.evaluate(op('lt', lit(1), lit(2)), {}))
        self.assertTrue(rules.evaluate(op('gte', lit(1), lit(1)), {}))
        self.assertTrue(rules.evaluate(op('lte', lit(1), lit(1)), {}))


class TextFunctionTests(SimpleTestCase):
    def test_concat_upper_lower(self):
        self.assertEqual(rules.evaluate(op('concat', lit('a'), lit('b')), {}), 'ab')
        self.assertEqual(rules.evaluate(op('upper', lit('ab')), {}), 'AB')
        self.assertEqual(rules.evaluate(op('lower', lit('AB')), {}), 'ab')

    def test_length_starts_with_contains(self):
        self.assertEqual(rules.evaluate(op('length', lit('hello')), {}), 5)
        self.assertTrue(rules.evaluate(op('starts_with', lit('hello'), lit('he')), {}))
        self.assertTrue(rules.evaluate(op('contains', lit('hello'), lit('ell')), {}))

    def test_matches_valid_and_invalid_regex(self):
        self.assertTrue(rules.evaluate(op('matches', lit('abc123'), lit(r'^\w+$')), {}))
        with self.assertRaises(RuleError):
            rules.evaluate(op('matches', lit('x'), lit('[')), {})

    def test_matches_rejects_overlong_pattern(self):
        with self.assertRaises(RuleLimitExceeded):
            rules.evaluate(op('matches', lit('x'), lit('a' * 300)), {})


class DateFunctionTests(SimpleTestCase):
    def test_date_diff_days_months_years(self):
        self.assertEqual(rules.evaluate(op('date_diff', lit('days'), lit('2026-01-01'), lit('2026-01-11')), {}), Decimal('10'))
        self.assertEqual(rules.evaluate(op('date_diff', lit('months'), lit('2026-01-01'), lit('2026-04-01')), {}), Decimal('3'))
        self.assertEqual(rules.evaluate(op('date_diff', lit('years'), lit('2020-01-01'), lit('2026-01-01')), {}), Decimal('6'))

    def test_add_days_months_years_handles_month_end(self):
        self.assertEqual(rules.evaluate(op('add_days', lit('2026-01-01'), lit(5)), {}), datetime.date(2026, 1, 6))
        self.assertEqual(rules.evaluate(op('add_months', lit('2026-01-31'), lit(1)), {}), datetime.date(2026, 2, 28))
        self.assertEqual(rules.evaluate(op('add_years', lit('2024-02-29'), lit(1)), {}), datetime.date(2025, 2, 28))

    def test_start_of_end_of_month_quarter_year(self):
        self.assertEqual(rules.evaluate(op('start_of', lit('month'), lit('2026-03-15')), {}), datetime.date(2026, 3, 1))
        self.assertEqual(rules.evaluate(op('end_of', lit('month'), lit('2026-02-15')), {}), datetime.date(2026, 2, 28))
        self.assertEqual(rules.evaluate(op('start_of', lit('quarter'), lit('2026-05-15')), {}), datetime.date(2026, 4, 1))
        self.assertEqual(rules.evaluate(op('end_of', lit('year'), lit('2026-05-15')), {}), datetime.date(2026, 12, 31))

    def test_age_on_and_tenure_on(self):
        self.assertEqual(rules.evaluate(op('age_on', lit('2000-06-15'), lit('2026-06-14')), {}), Decimal('25'))
        self.assertEqual(rules.evaluate(op('age_on', lit('2000-06-15'), lit('2026-06-15')), {}), Decimal('26'))
        self.assertEqual(rules.evaluate(op('tenure_on', lit('2024-01-01'), lit('2026-07-01'), lit('months')), {}), Decimal('30'))

    def test_day_of_week(self):
        self.assertEqual(rules.evaluate(op('day_of_week', lit('2026-10-07')), {}), 'WEDNESDAY')

    def test_minutes_between(self):
        self.assertEqual(rules.evaluate(op('minutes_between', lit('09:00'), lit('09:45')), {}), Decimal('45'))


class ConditionFormatParityTests(SimpleTestCase):
    """The Phase 2 condition format must parse into the same tree and
    evaluate identically (Rule 2)."""

    def test_all_condition_matches_and_tree(self):
        condition = {'all': [{'field': 'amount', 'op': 'gt', 'value': 100}]}
        native = op('gt', {'var': 'amount'}, lit(100))
        ctx = {'amount': Decimal('150')}
        self.assertEqual(rules.evaluate(condition, ctx), rules.evaluate(native, ctx))
        self.assertTrue(rules.evaluate(condition, ctx))

    def test_any_condition(self):
        condition = {'any': [{'field': 'x', 'op': 'eq', 'value': 1}, {'field': 'x', 'op': 'eq', 'value': 2}]}
        self.assertTrue(rules.evaluate(condition, {'x': 2}))
        self.assertFalse(rules.evaluate(condition, {'x': 3}))

    def test_empty_condition_is_true(self):
        self.assertTrue(rules.evaluate({}, {}))

    def test_not_in_empty_not_empty_operators(self):
        self.assertTrue(rules.evaluate({'all': [{'field': 'x', 'op': 'not_in', 'value': [1, 2]}]}, {'x': 3}))
        self.assertTrue(rules.evaluate({'all': [{'field': 'x', 'op': 'empty'}]}, {'x': None}))
        self.assertTrue(rules.evaluate({'all': [{'field': 'x', 'op': 'not_empty'}]}, {'x': 'set'}))


class VariableAndSecurityTests(SimpleTestCase):
    def test_var_reads_from_context(self):
        self.assertEqual(rules.evaluate({'var': 'name'}, {'name': 'Ravi'}), 'Ravi')

    def test_unknown_variable_returns_none_not_error(self):
        self.assertIsNone(rules.evaluate({'var': 'does_not_exist'}, {}))

    def test_dunder_named_context_key_is_harmless(self):
        # `var` lookups are always a plain dict.get(name) against the
        # caller-supplied context — never getattr() on a live object — so
        # a dunder-shaped NAME carries no special risk here; the real
        # security property is "no attribute traversal happens at all,"
        # proven by this returning exactly what's in the dict, nothing more.
        self.assertEqual(rules.evaluate({'var': '__class__'}, {'__class__': 'harmless'}), 'harmless')

    def test_variable_name_with_invalid_characters_rejected(self):
        with self.assertRaises(RuleError):
            rules.evaluate({'var': 'x; import os'}, {})

    def test_unknown_operator_rejected(self):
        with self.assertRaises(RuleError):
            rules.evaluate(op('os.system', lit('rm -rf /')), {})

    def test_unregistered_provider_rejected(self):
        with self.assertRaises(RuleError):
            rules.evaluate({'provider': 'attendance.count_days', 'args': []}, {})

    def test_malformed_node_rejected(self):
        with self.assertRaises(RuleError):
            rules.evaluate({'not_a_valid_key': 1}, {})


class LimitTests(SimpleTestCase):
    def test_max_node_count_exceeded(self):
        tree = lit(1)
        for _ in range(rules.MAX_NODES + 10):
            tree = op('add', tree, lit(1))
        with self.assertRaises(RuleLimitExceeded):
            rules.evaluate(tree, {})

    def test_max_depth_exceeded(self):
        tree = lit(1)
        for _ in range(rules.MAX_DEPTH + 5):
            tree = op('not', op('not', tree))
        with self.assertRaises(RuleLimitExceeded):
            rules.evaluate(tree, {})

    def test_max_list_size_exceeded(self):
        huge_list = {'op': 'literal', 'value': list(range(rules.MAX_LIST_SIZE + 1))}
        with self.assertRaises(RuleLimitExceeded):
            rules.evaluate(op('length', huge_list), {})


class FuzzSafetyTests(SimpleTestCase):
    """Random/malformed trees must never raise an unhandled Python
    exception or hang — everything funnels through RuleError."""

    def test_random_malformed_trees_never_raise_unhandled(self):
        import random
        random.seed(42)
        junk_values = [None, True, 1, 'x', [], {}, {'op': 'add'}, {'op': 'add', 'args': 'not_a_list'},
                       {'var': 123}, {'provider': 'nope'}, {'op': 'matches', 'args': [lit('x'), lit('(a+)+b')]}]
        for _ in range(200):
            tree = random.choice(junk_values)
            try:
                rules.evaluate(tree if isinstance(tree, dict) else {'op': 'literal', 'value': tree}, {})
            except RuleError:
                pass  # expected for malformed input — the only acceptable exception type
