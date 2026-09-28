"""
Regression tests for OnboardingApprovalView not re-asking for Position when
the target already has one (assigned via the Hire wizard before onboarding
even started) — was previously a hard-required field on every approval,
which also only offered vacant positions (never the one the employee
already holds), forcing HR through a confusing, unnecessary re-pick.
"""
from __future__ import annotations

from datetime import date

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Placement, Position, User
from apps.accounts.services_placement import assign_position


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class OnboardingApprovalPositionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_approval_test', permission_codenames=['onboarding.approve', 'settings.edit'])
        self.hr_user = make_user('hr-approval@test.com', role=self.hr_role, password='TestPass123!')
        _login(self.client, 'hr-approval@test.com')

        self.unit = OrgUnit.objects.create(name='Engineering')
        self.position = Position.objects.create(org_unit=self.unit, title='Software Engineer', grade='L2')

        self.employee_role = make_role('employee_approval_test')

    def _make_hired_employee(self, *, with_position: bool) -> User:
        """Mirrors what HireActionCompleteView produces: role + employee_id
        set, a Placement already in place (if with_position), and onboarding
        submitted — without going through the real multi-step hire wizard
        HTTP flow (slow, real file uploads) just to set up this test."""
        user = make_user(
            'new-hire@test.com', role=self.employee_role if with_position else None,
            password='TestPass123!', full_name='New Hire',
        )
        if with_position:
            user.employee_id = 'EMP99001'
            user.date_of_joining = date(2026, 10, 1)
            user.save(update_fields=['employee_id', 'date_of_joining'])
            assign_position(user, self.position, effective_from=date(2026, 10, 1), created_by=self.hr_user)
        user.onboarding_status = User.ONBOARDING_SUBMITTED
        user.save(update_fields=['onboarding_status'])
        return user

    def test_approval_succeeds_without_position_when_already_assigned(self):
        user = self._make_hired_employee(with_position=True)
        placement_before = Placement.objects.filter(employee=user, effective_to__isnull=True).first()
        self.assertIsNotNone(placement_before)

        resp = self.client.post(
            reverse('onboarding-approve', args=[user.id]), {'decision': 'approve'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        user.refresh_from_db()
        self.assertEqual(user.onboarding_status, User.ONBOARDING_COMPLETE)

        placement_after = Placement.objects.filter(employee=user, effective_to__isnull=True).first()
        self.assertEqual(placement_before.id, placement_after.id)
        self.assertEqual(Placement.objects.filter(employee=user).count(), 1)

    def test_approval_still_requires_position_for_a_true_conversion(self):
        # A candidate converted straight to employee, never touching the
        # Hire wizard — genuinely has no Position yet, so this must still
        # be required (the original, correct behavior for this case).
        user = self._make_hired_employee(with_position=False)
        resp = self.client.post(
            reverse('onboarding-approve', args=[user.id]), {'decision': 'approve'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('position', resp.data['message'].lower())

    def test_explicit_position_override_still_works_when_already_assigned(self):
        user = self._make_hired_employee(with_position=True)
        other_position = Position.objects.create(org_unit=self.unit, title='Senior Engineer', grade='L3')

        resp = self.client.post(
            reverse('onboarding-approve', args=[user.id]),
            {'decision': 'approve', 'position': str(other_position.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        placement = Placement.objects.filter(employee=user, effective_to__isnull=True).first()
        self.assertEqual(placement.position_id, other_position.id)
