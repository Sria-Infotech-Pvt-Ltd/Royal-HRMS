"""
Phase 5B Task J — regression tests for the placement-overlap bug fixed in
services_placement.assign_position(): moving an employee to a different,
vacant seat used to only close their existing open placement when its
effective_from was strictly BEFORE the new one's effective_from, so a
same-day (or back-dated) reassignment left two open placements for the
same employee and collided with the placement_employee_no_overlap
exclusion constraint. See tests_onboarding_approval_position.py for the
original failing HTTP-level reproduction of this bug.
"""
from __future__ import annotations

from datetime import date

from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import OrgUnit, Placement, Position
from apps.accounts.services_placement import assign_position


class PlacementReassignmentTests(TestCase):
    def setUp(self):
        self.unit = OrgUnit.objects.create(name='Engineering')
        self.position_a = Position.objects.create(org_unit=self.unit, title='Engineer A', grade='L2')
        self.position_b = Position.objects.create(org_unit=self.unit, title='Engineer B', grade='L3')
        self.employee = make_user('reassign@test.com', password='TestPass123!', full_name='Reassign Me')

    def test_same_day_replacement_to_a_different_seat(self):
        assign_position(self.employee, self.position_a, effective_from=date(2026, 10, 1))
        placement = assign_position(self.employee, self.position_b, effective_from=date(2026, 10, 1))

        open_placements = Placement.objects.filter(employee=self.employee, effective_to__isnull=True)
        self.assertEqual(open_placements.count(), 1)
        self.assertEqual(open_placements.first().position_id, self.position_b.id)
        self.assertEqual(placement.position_id, self.position_b.id)
        # The superseded same-day placement is removed outright, not left
        # behind with an (invalid) effective_to before its own effective_from.
        self.assertFalse(Placement.objects.filter(employee=self.employee, position=self.position_a).exists())

    def test_future_dated_replacement_closes_the_prior_placement(self):
        assign_position(self.employee, self.position_a, effective_from=date(2026, 10, 1))
        assign_position(self.employee, self.position_b, effective_from=date(2026, 11, 1))

        old = Placement.objects.get(employee=self.employee, position=self.position_a)
        self.assertEqual(old.effective_to, date(2026, 10, 31))

        new = Placement.objects.get(employee=self.employee, position=self.position_b, effective_to__isnull=True)
        self.assertEqual(new.effective_from, date(2026, 11, 1))

    def test_back_dated_replacement_to_a_different_seat(self):
        assign_position(self.employee, self.position_a, effective_from=date(2026, 10, 1))
        placement = assign_position(self.employee, self.position_b, effective_from=date(2026, 9, 1))

        open_placements = Placement.objects.filter(employee=self.employee, effective_to__isnull=True)
        self.assertEqual(open_placements.count(), 1)
        self.assertEqual(open_placements.first().position_id, self.position_b.id)
        self.assertEqual(placement.effective_from, date(2026, 9, 1))
        self.assertFalse(Placement.objects.filter(employee=self.employee, position=self.position_a).exists())
