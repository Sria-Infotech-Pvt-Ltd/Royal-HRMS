"""
Phase 5B Task D/E — tests for the employment action engine: apply,
idempotency, conflict detection, reversal, future/back-dating rules, plus
the EmployeeRelationship service and employment lookup attribute reads.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.accounts.models import OrgUnit, Position, User
from apps.accounts.models_actions import ActionType, EmploymentAction
from apps.accounts.services_actions import (
    ActionConflictError, apply_employment_action, reverse_employment_action,
)
from apps.accounts.services_employment_lookups import (
    get_employment_status_category, get_employment_type_attributes, is_probation_applicable,
)
from apps.accounts.services_placement import assign_position
from apps.accounts.services_relationships import (
    RelationshipConflictError, create_relationship, resolve_relationship_as_of,
)


class EmploymentLookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_employment_lookups')

    def test_permanent_employee_type_has_expected_attributes(self):
        attrs = get_employment_type_attributes('Permanent')
        self.assertTrue(attrs['probation_applicable'])
        self.assertTrue(attrs['pf_default_eligible'])
        self.assertTrue(is_probation_applicable('Permanent'))

    def test_intern_employee_type_is_temporary_and_not_probation_applicable(self):
        attrs = get_employment_type_attributes('Intern')
        self.assertFalse(attrs['probation_applicable'])
        self.assertTrue(attrs['is_temporary'])

    def test_unknown_employee_type_returns_empty_attributes(self):
        self.assertEqual(get_employment_type_attributes('NotARealType'), {})

    def test_employment_status_category_resolves(self):
        self.assertEqual(get_employment_status_category('probation'), 'active')
        self.assertEqual(get_employment_status_category('confirmed'), 'active')
        self.assertIsNone(get_employment_status_category('nonexistent'))


class EmployeeRelationshipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_employment_lookups')

    def setUp(self):
        self.employee = make_user('relemp@test.com', password='TestPass123!')
        self.manager_1 = make_user('mgr1@test.com', password='TestPass123!')
        self.manager_2 = make_user('mgr2@test.com', password='TestPass123!')

    def test_create_and_resolve_manual_relationship(self):
        create_relationship(
            self.employee, 'REPORTING_MANAGER', self.manager_1,
            effective_from=date(2026, 1, 1),
        )
        resolved = resolve_relationship_as_of(self.employee, 'REPORTING_MANAGER', as_of=date(2026, 6, 1))
        self.assertEqual(resolved.id, self.manager_1.id)

    def test_overlapping_single_type_relationship_rejected(self):
        create_relationship(self.employee, 'REPORTING_MANAGER', self.manager_1, effective_from=date(2026, 1, 1))
        with self.assertRaises(RelationshipConflictError):
            create_relationship(self.employee, 'REPORTING_MANAGER', self.manager_2, effective_from=date(2026, 3, 1))

    def test_allow_multiple_type_does_not_conflict(self):
        create_relationship(self.employee, 'MENTOR', self.manager_1, effective_from=date(2026, 1, 1))
        # Should not raise even though it overlaps — MENTOR is allow_multiple.
        create_relationship(self.employee, 'MENTOR', self.manager_2, effective_from=date(2026, 1, 1))
        self.assertEqual(self.employee.relationships_v2.filter(relationship_type__code='MENTOR').count(), 2)

    def test_resolve_returns_none_when_nothing_covers_the_date(self):
        create_relationship(self.employee, 'REPORTING_MANAGER', self.manager_1, effective_from=date(2026, 6, 1))
        self.assertIsNone(resolve_relationship_as_of(self.employee, 'REPORTING_MANAGER', as_of=date(2026, 1, 1)))


class EmploymentActionEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_action_types')

    def setUp(self):
        self.unit = OrgUnit.objects.create(name='Sales')
        self.position_a = Position.objects.create(org_unit=self.unit, title='Sales Exec', grade='L1')
        self.position_b = Position.objects.create(org_unit=self.unit, title='Senior Sales Exec', grade='L2')
        self.employee = make_user(
            'actionemp@test.com', password='TestPass123!', full_name='Action Employee',
        )
        self.employee.employment_status = User.EMPLOYMENT_STATUS_PROBATION
        self.employee.save(update_fields=['employment_status'])
        assign_position(self.employee, self.position_a, effective_from=date(2026, 1, 1))
        self.hr_user = make_user('hractionuser@test.com', password='TestPass123!')

    def test_confirmation_action_applies_and_sets_status(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate(),
            created_by=self.hr_user,
        )
        applied = apply_employment_action(action)

        self.assertEqual(applied.status, EmploymentAction.STATUS_APPLIED)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, User.EMPLOYMENT_STATUS_CONFIRMED)
        self.assertEqual(applied.previous_values['set_employment_status'], User.EMPLOYMENT_STATUS_PROBATION)

    def test_confirmation_action_blocked_from_wrong_status(self):
        self.employee.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        self.employee.save(update_fields=['employment_status'])
        action_type = ActionType.objects.get(code='CONFIRMATION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate(),
        )
        with self.assertRaises(ActionConflictError):
            apply_employment_action(action)

    def test_applying_twice_is_idempotent(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate(),
        )
        apply_employment_action(action)
        second = apply_employment_action(action)
        self.assertEqual(second.status, EmploymentAction.STATUS_APPLIED)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, User.EMPLOYMENT_STATUS_CONFIRMED)

    def test_promotion_action_changes_placement(self):
        action_type = ActionType.objects.get(code='PROMOTION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate() - timedelta(days=10),
            payload={'position_id': str(self.position_b.id)}, created_by=self.hr_user,
        )
        action = apply_employment_action(action)

        placement = self.employee.placements.filter(effective_to__isnull=True).first()
        self.assertEqual(placement.position_id, self.position_b.id)
        self.assertEqual(action.previous_values['set_placement']['position_id'], str(self.position_a.id))

    def test_conflicting_pending_actions_same_date_rejected(self):
        action_type = ActionType.objects.get(code='PROMOTION')
        same_date = timezone.localdate() - timedelta(days=10)
        EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=same_date,
            payload={'position_id': str(self.position_b.id)}, status=EmploymentAction.STATUS_PENDING_APPROVAL,
        )
        second = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=same_date,
            payload={'position_id': str(self.position_b.id)},
        )
        with self.assertRaises(ActionConflictError):
            apply_employment_action(second)

    def test_reversal_restores_previous_placement(self):
        action_type = ActionType.objects.get(code='PROMOTION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate() - timedelta(days=10),
            payload={'position_id': str(self.position_b.id)}, created_by=self.hr_user,
        )
        action = apply_employment_action(action)

        correction = reverse_employment_action(action, reason='wrong position', created_by=self.hr_user)

        action.refresh_from_db()
        self.assertEqual(action.status, EmploymentAction.STATUS_REVERSED)
        self.assertEqual(correction.status, EmploymentAction.STATUS_APPLIED)
        self.assertEqual(correction.reversal_of_id, action.id)

        placement = self.employee.placements.filter(effective_to__isnull=True).first()
        self.assertEqual(placement.position_id, self.position_a.id)

    def test_reversal_blocked_when_a_later_action_already_applied(self):
        action_type = ActionType.objects.get(code='PROMOTION')
        first = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate() - timedelta(days=10),
            payload={'position_id': str(self.position_b.id)},
        )
        apply_employment_action(first)

        later = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=timezone.localdate(),
            payload={'position_id': str(self.position_a.id)},
        )
        apply_employment_action(later)

        with self.assertRaises(ActionConflictError):
            reverse_employment_action(first, reason='too late now', created_by=self.hr_user)

    def test_backdating_beyond_max_days_rejected(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        too_far_back = timezone.localdate() - timedelta(days=45)
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type, effective_date=too_far_back,
        )
        with self.assertRaises(ActionConflictError):
            apply_employment_action(action)
