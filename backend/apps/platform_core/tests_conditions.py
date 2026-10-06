"""Phase 2 Task B.4 — conditions evaluator tests (every operator, nesting, errors)."""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.platform_core import services_conditions as cond


class ConditionEvaluatorTests(SimpleTestCase):
    def test_empty_condition_is_always_true(self):
        self.assertTrue(cond.evaluate({}, {}))

    def test_eq(self):
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'eq', 'value': 1}]}, {'x': 1}))
        self.assertFalse(cond.evaluate({'all': [{'field': 'x', 'op': 'eq', 'value': 1}]}, {'x': 2}))

    def test_ne(self):
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'ne', 'value': 1}]}, {'x': 2}))

    def test_in_not_in(self):
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'in', 'value': [1, 2]}]}, {'x': 1}))
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'not_in', 'value': [1, 2]}]}, {'x': 3}))

    def test_empty_not_empty(self):
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'empty'}]}, {'x': ''}))
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'empty'}]}, {}))
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'not_empty'}]}, {'x': 'something'}))

    def test_gt_lt_gte_lte(self):
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'gt', 'value': 5}]}, {'x': 10}))
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'lt', 'value': 5}]}, {'x': 1}))
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'gte', 'value': 5}]}, {'x': 5}))
        self.assertTrue(cond.evaluate({'all': [{'field': 'x', 'op': 'lte', 'value': 5}]}, {'x': 5}))

    def test_comparison_with_missing_value_is_false_not_an_error(self):
        self.assertFalse(cond.evaluate({'all': [{'field': 'missing', 'op': 'gt', 'value': 5}]}, {}))

    def test_all_requires_every_clause(self):
        condition = {'all': [{'field': 'x', 'op': 'eq', 'value': 1}, {'field': 'y', 'op': 'eq', 'value': 2}]}
        self.assertTrue(cond.evaluate(condition, {'x': 1, 'y': 2}))
        self.assertFalse(cond.evaluate(condition, {'x': 1, 'y': 3}))

    def test_any_requires_one_clause(self):
        condition = {'any': [{'field': 'x', 'op': 'eq', 'value': 1}, {'field': 'y', 'op': 'eq', 'value': 2}]}
        self.assertTrue(cond.evaluate(condition, {'x': 1, 'y': 999}))
        self.assertFalse(cond.evaluate(condition, {'x': 999, 'y': 999}))

    def test_nesting_up_to_3_levels(self):
        condition = {
            'all': [
                {'any': [
                    {'all': [{'field': 'a', 'op': 'eq', 'value': 1}]},
                    {'field': 'b', 'op': 'eq', 'value': 2},
                ]},
            ],
        }
        self.assertTrue(cond.evaluate(condition, {'a': 1, 'b': 999}))
        self.assertTrue(cond.evaluate(condition, {'a': 999, 'b': 2}))
        self.assertFalse(cond.evaluate(condition, {'a': 999, 'b': 999}))

    def test_nesting_beyond_limit_raises(self):
        # Build 5 levels of nesting — exceeds MAX_NESTING_DEPTH=3.
        innermost = {'field': 'x', 'op': 'eq', 'value': 1}
        condition = innermost
        for _ in range(5):
            condition = {'all': [condition]}
        with self.assertRaises(cond.ConditionError):
            cond.evaluate(condition, {'x': 1})

    def test_both_all_and_any_at_same_level_raises(self):
        with self.assertRaises(cond.ConditionError):
            cond.evaluate({'all': [], 'any': []}, {})

    def test_unknown_operator_raises(self):
        with self.assertRaises(cond.ConditionError):
            cond.evaluate({'all': [{'field': 'x', 'op': 'bogus', 'value': 1}]}, {'x': 1})

    def test_incomparable_types_raise_not_crash_silently(self):
        with self.assertRaises(cond.ConditionError):
            cond.evaluate({'all': [{'field': 'x', 'op': 'gt', 'value': 'not_a_number'}]}, {'x': 5})
