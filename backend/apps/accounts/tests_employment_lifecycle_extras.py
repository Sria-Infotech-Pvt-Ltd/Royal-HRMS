"""
Phase 5B Task F/I — tests for the scheduled-action-apply job and the
as-of/timeline read endpoints.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Position, User
from apps.accounts.models_actions import ActionType, EmploymentAction
from apps.accounts.services_placement import assign_position
from apps.accounts.tasks import apply_scheduled_employment_actions


class ScheduledActionApplyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_action_types')

    def setUp(self):
        self.unit = OrgUnit.objects.create(name='Ops')
        self.position_a = Position.objects.create(org_unit=self.unit, title='Ops Exec', grade='L1')
        self.employee = make_user('scheduledemp@test.com', password='TestPass123!')
        self.employee.employment_status = User.EMPLOYMENT_STATUS_PROBATION
        self.employee.save(update_fields=['employment_status'])
        assign_position(self.employee, self.position_a, effective_from=timezone.localdate() - timedelta(days=60))

    def test_due_action_is_applied(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type,
            effective_date=timezone.localdate() - timedelta(days=1),
            status=EmploymentAction.STATUS_APPROVED,
        )
        result = apply_scheduled_employment_actions()

        action.refresh_from_db()
        self.assertEqual(action.status, EmploymentAction.STATUS_APPLIED)
        self.assertEqual(result['applied'], 1)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, User.EMPLOYMENT_STATUS_CONFIRMED)

    def test_future_dated_action_is_not_applied_yet(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type,
            effective_date=timezone.localdate() + timedelta(days=5),
            status=EmploymentAction.STATUS_APPROVED,
        )
        apply_scheduled_employment_actions()

        action.refresh_from_db()
        self.assertEqual(action.status, EmploymentAction.STATUS_APPROVED)

    def test_running_twice_does_not_double_apply(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type,
            effective_date=timezone.localdate(), status=EmploymentAction.STATUS_APPROVED,
        )
        apply_scheduled_employment_actions()
        result2 = apply_scheduled_employment_actions()

        # Second run finds nothing left in approved/scheduled for this action.
        action.refresh_from_db()
        self.assertEqual(action.status, EmploymentAction.STATUS_APPLIED)
        self.assertEqual(result2['applied'], 0)

    def test_a_failing_action_does_not_block_others(self):
        action_type = ActionType.objects.get(code='CONFIRMATION')
        # This one is already confirmed -> validate_employment_action rejects it.
        self.employee.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        self.employee.save(update_fields=['employment_status'])
        bad = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type,
            effective_date=timezone.localdate(), status=EmploymentAction.STATUS_APPROVED,
        )

        other_position = Position.objects.create(org_unit=self.unit, title='Ops Exec 2', grade='L1')
        other_employee = make_user('scheduledemp2@test.com', password='TestPass123!')
        other_employee.employment_status = User.EMPLOYMENT_STATUS_PROBATION
        other_employee.save(update_fields=['employment_status'])
        assign_position(other_employee, other_position, effective_from=timezone.localdate() - timedelta(days=60))
        good = EmploymentAction.objects.create(
            employee=other_employee, action_type=action_type,
            effective_date=timezone.localdate(), status=EmploymentAction.STATUS_APPROVED,
        )

        result = apply_scheduled_employment_actions()

        bad.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual(bad.status, EmploymentAction.STATUS_APPROVED)
        self.assertEqual(good.status, EmploymentAction.STATUS_APPLIED)
        self.assertEqual(result['applied'], 1)
        self.assertEqual(len(result['failed']), 1)


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class AsOfAndTimelineViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_action_types')

    def setUp(self):
        cache.clear()
        self.unit = OrgUnit.objects.create(name='Finance')
        self.position_a = Position.objects.create(org_unit=self.unit, title='Analyst', grade='L1')
        self.position_b = Position.objects.create(org_unit=self.unit, title='Senior Analyst', grade='L2')

        self.hr_role = make_role('hr_lifecycle_test', permission_codenames=['employees.view'])
        self.hr_user = make_user('hr-lifecycle@test.com', role=self.hr_role, password='TestPass123!')
        self.employee = make_user('lifecycleemp@test.com', password='TestPass123!', full_name='Lifecycle Employee')
        self.employee.employee_id = 'EMP88001'
        self.employee.save(update_fields=['employee_id'])

        self.client = APIClient()
        _login(self.client, 'hr-lifecycle@test.com')

    def test_as_of_returns_position_effective_on_date(self):
        assign_position(self.employee, self.position_a, effective_from=date(2026, 1, 1))
        assign_position(self.employee, self.position_b, effective_from=date(2026, 6, 1))

        resp = self.client.get(
            reverse('employee-as-of', args=[self.employee.employee_id]), {'date': '2026-03-01'},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['position']['position_id'], str(self.position_a.id))

        resp2 = self.client.get(
            reverse('employee-as-of', args=[self.employee.employee_id]), {'date': '2026-07-01'},
        )
        self.assertEqual(resp2.data['data']['position']['position_id'], str(self.position_b.id))

    def test_as_of_invalid_date_rejected(self):
        resp = self.client.get(
            reverse('employee-as-of', args=[self.employee.employee_id]), {'date': 'not-a-date'},
        )
        self.assertEqual(resp.status_code, 400)

    def test_timeline_includes_applied_action(self):
        assign_position(self.employee, self.position_a, effective_from=timezone.localdate() - timedelta(days=30))
        action_type = ActionType.objects.get(code='PROMOTION')
        action = EmploymentAction.objects.create(
            employee=self.employee, action_type=action_type,
            effective_date=timezone.localdate(), payload={'position_id': str(self.position_b.id)},
        )
        from apps.accounts.services_actions import apply_employment_action
        apply_employment_action(action)

        resp = self.client.get(reverse('employee-lifecycle-timeline', args=[self.employee.employee_id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        kinds = [event['kind'] for event in resp.data['data']]
        self.assertIn('employment_action', kinds)
