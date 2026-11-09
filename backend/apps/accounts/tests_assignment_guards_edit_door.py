"""
Employee-edit door: PUT/PATCH /api/employees/<number>/ with a `position`.

The original exploit: an HR user holding only `employees.view` + `employees.edit` edited THEIR OWN record, set `position` to a
seat carrying `settings.edit` and `payroll.edit`, got a 200 and became full-access. Fixed in
services_access_guards.assignment_refusal: no self-assignment of a different position (403), and a full-access seat is for
full-access actors only (400). Everyday edits, including re-sending the person's CURRENT position, are untouched.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Permission, Placement, Position, PositionPermission
from core.permissions import has_perm

BRANCH = 'Edit Door Branch'


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class EmployeeEditDoorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = OrgUnit.objects.create(name='Edit Door Unit')
        hr_profile = make_role('edit_door_hr', permission_codenames=['employees.view', 'employees.edit'])
        self.hr = make_user('door_hr@test.com', role=hr_profile, employee_id='ED001', branch=BRANCH)
        self.colleague = make_user('door_colleague@test.com', employee_id='ED002', branch=BRANCH)
        admin_profile = make_role('edit_door_admin', permission_codenames=['employees.view', 'employees.edit', 'settings.edit'])
        self.admin = make_user('door_admin@test.com', role=admin_profile, employee_id='ED003', branch=BRANCH)
        self.full_access_seat = self._seat('Super Seat', ['settings.edit', 'payroll.edit'])
        self.ordinary_seat = self._seat('Support Analyst', ['leave.view'])

    def _seat(self, title: str, keys: list[str]) -> Position:
        position = Position.objects.create(org_unit=self.unit, title=title, grade='L3')
        for key in keys:
            PositionPermission.objects.create(position=position, permission=Permission.objects.get(codename=key))
        return position

    def _edit(self, actor, employee, position, method='put') -> int:
        return getattr(_api(actor), method)(f'/api/employees/{employee.employee_id}/', {'position': str(position.pk)}, format='json').status_code

    def _placements(self, employee) -> int:
        return Placement.objects.filter(employee=employee).count()

    # ── the original exploit ──────────────────────────────────────────────────

    def test_an_hr_user_cannot_edit_their_own_record_into_a_full_access_seat(self):
        before = (has_perm(self.hr, 'settings.edit'), has_perm(self.hr, 'payroll.edit'))
        self.assertEqual(before, (False, False))
        self.assertEqual(self._edit(self.hr, self.hr, self.full_access_seat), 403)
        self.assertEqual(self._edit(self.hr, self.hr, self.full_access_seat, method='patch'), 403)
        self.assertEqual((has_perm(self.hr, 'settings.edit'), has_perm(self.hr, 'payroll.edit')), (False, False))
        self.assertFalse(Placement.objects.filter(employee=self.hr, position=self.full_access_seat).exists())

    def test_nobody_assigns_themselves_a_different_position_not_even_an_ordinary_one(self):
        self.assertEqual(self._edit(self.hr, self.hr, self.ordinary_seat), 403)
        self.assertEqual(self._edit(self.admin, self.admin, self.ordinary_seat), 403)

    def test_a_non_full_access_user_cannot_put_someone_else_on_a_full_access_seat(self):
        self.assertEqual(self._edit(self.hr, self.colleague, self.full_access_seat), 400)
        self.assertEqual(self._placements(self.colleague), 0)
        self.assertFalse(has_perm(self.colleague, 'settings.edit'))

    # ── everyday behavior is preserved ────────────────────────────────────────

    def test_an_hr_user_can_still_assign_someone_else_to_an_ordinary_seat(self):
        self.assertEqual(self._edit(self.hr, self.colleague, self.ordinary_seat), 200)
        self.assertTrue(Placement.objects.filter(employee=self.colleague, position=self.ordinary_seat).exists())

    def test_resending_the_current_position_is_not_refused_even_on_your_own_record(self):
        self.assertEqual(self._edit(self.admin, self.colleague, self.ordinary_seat), 200)
        self.assertEqual(self._edit(self.admin, self.colleague, self.ordinary_seat), 200)  # same seat again: nothing new
        own_seat = Placement.objects.get(employee=self.hr).position
        self.assertEqual(self._edit(self.hr, self.hr, own_seat), 200)  # the edit form re-sends the person's own current seat

    def test_a_full_access_administrator_may_assign_someone_else_to_a_full_access_seat_but_not_themselves(self):
        self.assertEqual(self._edit(self.admin, self.colleague, self.full_access_seat), 200)
        self.assertTrue(has_perm(self.colleague, 'settings.edit'))
        self.assertEqual(self._edit(self.admin, self.admin, self.full_access_seat), 403)
