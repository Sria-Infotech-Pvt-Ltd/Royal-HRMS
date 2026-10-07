"""Phase 3A Task D+E — policy resolution, specificity order, overlap
constraints, conditions, cache invalidation, and the explainer."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core import services_policies as policies
from apps.platform_core.models import Policy, PolicyAssignment, PolicyType


class PolicyResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.policy_type = PolicyType.objects.create(code='TEST_WORKING_HOURS', name='Working hours')
        self.role = make_role('policy_test_role')
        self.employee = make_user('policy-emp@test.com', role=self.role)

        self.default_policy = Policy.objects.create(
            type=self.policy_type, code='default_9_to_6', name='Default',
            parameters={'start': '09:00', 'grace_minutes': 5},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1), is_default=True,
        )

    def test_default_policy_wins_when_no_assignment_matches(self):
        result = policies.resolve('TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1))
        self.assertEqual(result['start'], '09:00')

    def test_individual_assignment_beats_default(self):
        branch_policy = Policy.objects.create(
            type=self.policy_type, code='branch_10_to_7', name='Branch',
            parameters={'start': '10:00', 'grace_minutes': 10},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
        )
        PolicyAssignment.objects.create(
            policy=branch_policy, target_type=PolicyAssignment.TARGET_INDIVIDUAL,
            target_id=str(self.employee.pk), effective_from=datetime.date(2026, 1, 1),
        )
        result = policies.resolve('TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1))
        self.assertEqual(result['start'], '10:00')

    def test_assignment_not_yet_effective_does_not_match(self):
        future_policy = Policy.objects.create(
            type=self.policy_type, code='future', name='Future', parameters={'start': '11:00'},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2030, 1, 1),
        )
        PolicyAssignment.objects.create(
            policy=future_policy, target_type=PolicyAssignment.TARGET_INDIVIDUAL,
            target_id=str(self.employee.pk), effective_from=datetime.date(2030, 1, 1),
        )
        result = policies.resolve('TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1))
        self.assertEqual(result['start'], '09:00')  # still the default — future assignment doesn't apply yet

    def test_condition_must_hold_for_assignment_to_match(self):
        contract_policy = Policy.objects.create(
            type=self.policy_type, code='contract_hours', name='Contract', parameters={'start': '08:00'},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
        )
        PolicyAssignment.objects.create(
            policy=contract_policy, target_type=PolicyAssignment.TARGET_EMPLOYMENT_TYPE, target_id='CONTRACT',
            condition={'all': [{'field': 'employment_type', 'op': 'eq', 'value': 'CONTRACT'}]},
            effective_from=datetime.date(2026, 1, 1),
        )
        result = policies.resolve(
            'TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1),
            employee_context={'employment_type': 'PERMANENT'},
        )
        self.assertEqual(result['start'], '09:00')  # condition false -> falls through to default

    def test_org_unit_assignment_with_include_children(self):
        org_policy = Policy.objects.create(
            type=self.policy_type, code='org_policy', name='Org', parameters={'start': '09:30'},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
        )
        PolicyAssignment.objects.create(
            policy=org_policy, target_type=PolicyAssignment.TARGET_ORG_UNIT, target_id='parent-unit',
            include_children=True, effective_from=datetime.date(2026, 1, 1),
        )
        result = policies.resolve(
            'TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1),
            employee_context={'org_unit_ancestor_ids': ['parent-unit', 'grandparent-unit']},
        )
        self.assertEqual(result['start'], '09:30')

    def test_no_match_and_no_default_raises(self):
        PolicyType.objects.create(code='TEST_OVERTIME', name='Overtime')
        with self.assertRaises(policies.PolicyResolutionError):
            policies.resolve('TEST_OVERTIME', self.employee, datetime.date(2026, 6, 1))

    def test_resolve_many_bounded_query_count(self):
        employees = [make_user(f'bulk-{i}@test.com', role=self.role) for i in range(10)]
        # 3 queries total (policy type, assignments, default policy) —
        # bounded and INDEPENDENT of employee count, not literally "2";
        # the property under test is "doesn't scale with len(employees)".
        with self.assertNumQueries(3):
            results = policies.resolve_many('TEST_WORKING_HOURS', employees, datetime.date(2026, 6, 1))
        self.assertEqual(len(results), 10)
        self.assertTrue(all(v['start'] == '09:00' for v in results.values()))

    def test_cache_invalidates_when_a_new_policy_is_published(self):
        result1 = policies.resolve('TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1))
        self.assertEqual(result1['start'], '09:00')

        # The namespace-version bump that invalidates this cache runs via
        # transaction.on_commit (see cache.py's own docstring) — inside a
        # plain TestCase's rolled-back-per-test transaction, on_commit
        # callbacks never fire without this, same pitfall this project's
        # OTHER platform_core tests already document and work around.
        with self.captureOnCommitCallbacks(execute=True):
            new_default = Policy.objects.create(
                type=self.policy_type, code='new_default', name='New', parameters={'start': '08:30'},
                status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
            )
            PolicyAssignment.objects.create(
                policy=new_default, target_type=PolicyAssignment.TARGET_INDIVIDUAL,
                target_id=str(self.employee.pk), effective_from=datetime.date(2026, 1, 1),
            )
        result2 = policies.resolve('TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1))
        self.assertEqual(result2['start'], '08:30')


class PolicyOverlapConstraintTests(TestCase):
    def setUp(self):
        self.policy_type = PolicyType.objects.create(code='TEST_OVERTIME', name='Overtime')

    def test_two_defaults_same_type_entity_overlapping_dates_rejected(self):
        Policy.objects.create(
            type=self.policy_type, code='d1', name='D1', parameters={}, is_default=True,
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Policy.objects.create(
                    type=self.policy_type, code='d2', name='D2', parameters={}, is_default=True,
                    status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 6, 1),
                )

    def test_two_assignments_same_target_overlapping_dates_rejected(self):
        policy = Policy.objects.create(
            type=self.policy_type, code='p1', name='P1', parameters={},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
        )
        PolicyAssignment.objects.create(
            policy=policy, target_type=PolicyAssignment.TARGET_INDIVIDUAL, target_id='emp-1',
            effective_from=datetime.date(2026, 1, 1),
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                PolicyAssignment.objects.create(
                    policy=policy, target_type=PolicyAssignment.TARGET_INDIVIDUAL, target_id='emp-1',
                    effective_from=datetime.date(2026, 6, 1),
                )


class PolicyExplainerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.policy_type = PolicyType.objects.create(code='TEST_WORKING_HOURS', name='Working hours')
        self.role = make_role('explainer_role')
        self.employee = make_user('explainer-emp@test.com', role=self.role)
        Policy.objects.create(
            type=self.policy_type, code='default', name='Default', parameters={'start': '09:00'},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1), is_default=True,
        )

    def test_explain_shows_rejected_candidates_with_reasons(self):
        unmatched_policy = Policy.objects.create(
            type=self.policy_type, code='other_branch', name='Other', parameters={'start': '11:00'},
            status=Policy.STATUS_PUBLISHED, effective_from=datetime.date(2026, 1, 1),
        )
        PolicyAssignment.objects.create(
            policy=unmatched_policy, target_type=PolicyAssignment.TARGET_INDIVIDUAL,
            target_id='someone-else', effective_from=datetime.date(2026, 1, 1),
        )
        result = policies.explain('TEST_WORKING_HOURS', self.employee, datetime.date(2026, 6, 1))
        self.assertTrue(result['used_default'])
        self.assertEqual(len(result['rejected']), 1)
        self.assertIn('does not match', result['rejected'][0]['reason'])
