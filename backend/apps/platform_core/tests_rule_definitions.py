"""Phase 3A Task C — RuleDefinition publish-gate, type-checking,
version-by-effective-date, and where-used/retire tests."""
from __future__ import annotations

import datetime

from django.test import TestCase

from apps.platform_core import services_rule_definitions as rule_defs
from apps.platform_core.models import Policy, PolicyAssignment, PolicyType, RuleDefinition, RuleTestCase


class RulePublishGateTests(TestCase):
    def setUp(self):
        self.rule = RuleDefinition.objects.create(
            code='eligible_for_bonus', name='Eligible for bonus',
            input_context={'tenure_months': {'type': 'number'}},
            return_type='boolean',
            expression={'op': 'gte', 'args': [{'var': 'tenure_months'}, {'op': 'literal', 'value': 6}]},
        )

    def test_publish_blocked_without_test_cases(self):
        with self.assertRaises(rule_defs.RulePublishError):
            rule_defs.publish(self.rule)

    def test_publish_blocked_when_a_test_case_fails(self):
        RuleTestCase.objects.create(rule=self.rule, name='t1', inputs={'tenure_months': 12}, expected_output=False)
        with self.assertRaises(rule_defs.RulePublishError):
            rule_defs.publish(self.rule)

    def test_publish_succeeds_when_all_test_cases_pass(self):
        RuleTestCase.objects.create(rule=self.rule, name='eligible', inputs={'tenure_months': 12}, expected_output=True)
        RuleTestCase.objects.create(rule=self.rule, name='not_eligible', inputs={'tenure_months': 3}, expected_output=False)
        version = rule_defs.publish(self.rule)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.status, RuleDefinition.STATUS_PUBLISHED)
        self.assertEqual(version.version, 1)

    def test_republish_increments_version(self):
        RuleTestCase.objects.create(rule=self.rule, name='eligible', inputs={'tenure_months': 12}, expected_output=True)
        rule_defs.publish(self.rule)
        self.rule.refresh_from_db()
        version2 = rule_defs.publish(self.rule, effective_from=datetime.date(2027, 1, 1))
        self.assertEqual(version2.version, 2)

    def test_type_check_rejects_undeclared_variable(self):
        self.rule.expression = {'op': 'gte', 'args': [{'var': 'not_declared'}, {'op': 'literal', 'value': 1}]}
        self.rule.save()
        RuleTestCase.objects.create(rule=self.rule, name='t', inputs={'tenure_months': 1}, expected_output=True)
        with self.assertRaises(rule_defs.RulePublishError) as ctx:
            rule_defs.publish(self.rule)
        self.assertIn('not_declared', ctx.exception.errors[0])


class RuleVersionByDateTests(TestCase):
    def setUp(self):
        self.rule = RuleDefinition.objects.create(
            code='overtime_multiplier', input_context={'x': {'type': 'number'}}, return_type='number',
            expression={'op': 'literal', 'value': 1.5},
        )
        RuleTestCase.objects.create(rule=self.rule, name='t', inputs={}, expected_output=1.5)
        rule_defs.publish(self.rule, effective_from=datetime.date(2026, 1, 1))
        self.rule.refresh_from_db()
        self.rule.expression = {'op': 'literal', 'value': 2.0}
        self.rule.save()
        RuleTestCase.objects.all().delete()
        RuleTestCase.objects.create(rule=self.rule, name='t2', inputs={}, expected_output=2.0)
        rule_defs.publish(self.rule, effective_from=datetime.date(2027, 1, 1))

    def test_historical_date_uses_the_version_effective_then(self):
        from decimal import Decimal
        result = rule_defs.evaluate_effective('overtime_multiplier', {}, datetime.date(2026, 6, 1))
        self.assertEqual(result, Decimal('1.5'))

    def test_later_date_uses_the_newer_version(self):
        from decimal import Decimal
        result = rule_defs.evaluate_effective('overtime_multiplier', {}, datetime.date(2027, 6, 1))
        self.assertEqual(result, Decimal('2.0'))

    def test_date_before_any_version_raises(self):
        from apps.platform_core.rule_errors import RuleError
        with self.assertRaises(RuleError):
            rule_defs.evaluate_effective('overtime_multiplier', {}, datetime.date(2020, 1, 1))


class RuleWhereUsedTests(TestCase):
    def setUp(self):
        self.rule = RuleDefinition.objects.create(
            code='high_value_expense', input_context={'amount': {'type': 'number'}}, return_type='boolean',
            expression={'op': 'gt', 'args': [{'var': 'amount'}, {'op': 'literal', 'value': 50000}]},
        )
        RuleTestCase.objects.create(rule=self.rule, name='t', inputs={'amount': 60000}, expected_output=True)
        rule_defs.publish(self.rule)
        self.rule.refresh_from_db()

        self.policy_type = PolicyType.objects.create(code='EXP_APPROVAL', name='Expense approval')
        self.policy = Policy.objects.create(type=self.policy_type, code='default', name='Default', effective_from=datetime.date(2026, 1, 1))

    def test_retire_blocked_while_referenced(self):
        PolicyAssignment.objects.create(
            policy=self.policy, target_type=PolicyAssignment.TARGET_LEGAL_ENTITY, target_id='',
            condition={'rule': 'high_value_expense'}, effective_from=datetime.date(2026, 1, 1),
        )
        with self.assertRaises(rule_defs.RulePublishError):
            rule_defs.retire(self.rule)

    def test_retire_succeeds_when_unreferenced(self):
        rule_defs.retire(self.rule)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.status, RuleDefinition.STATUS_RETIRED)
