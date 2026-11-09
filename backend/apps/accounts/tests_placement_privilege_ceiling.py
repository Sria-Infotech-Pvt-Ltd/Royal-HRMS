"""
Placement privilege ceiling: a person may not put someone on a seat that carries more than they can grant.

Rule (services_access_guards.placement_refusal): nobody places themselves; a superuser or a `settings.edit` holder may fill
any other seat; everyone else may fill a seat only if every permission on it is one of THEIR OWN seat's permissions or the
company baseline (personal extras do not count) and, for a seat that manages a whole branch, they hold that flag too.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import BaselinePermission, EmployeePermission, OrgUnit, Permission, Placement, Position, PositionPermission

PLACER_KEYS = ['org_structure.edit', 'org_chart.view', 'employees.view', 'employees.edit', 'leave.approve']


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class PlacementPrivilegeCeilingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate()
        self.unit = OrgUnit.objects.create(name='Ceiling Unit')
        self.placer = make_user('ceil_placer@test.com', role=make_role('ceil_placer', permission_codenames=PLACER_KEYS), employee_id='CP001')
        self.admin = make_user(
            'ceil_admin@test.com', employee_id='CP002',
            role=make_role('ceil_admin', permission_codenames=['settings.edit', 'settings.view', 'org_structure.edit', 'org_chart.view']),
        )
        self.superuser = make_user('ceil_root@test.com', employee_id='CP003', is_superuser=True)
        self.people = [make_user(f'ceil_person{i}@test.com', employee_id=f'CP01{i}') for i in range(6)]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _seat(self, title: str, keys: list[str], **flags) -> Position:
        position = Position.objects.create(org_unit=self.unit, title=title, grade='L3', **flags)
        for key in keys:
            PositionPermission.objects.create(position=position, permission=Permission.objects.get(codename=key))
        return position

    def _place(self, actor, employee, position, start=None) -> int:
        payload = {'employee': str(employee.pk), 'effective_from': (start or self.today).isoformat()}
        return _api(actor).post(f'/api/org-structure/positions/{position.pk}/placements/', payload, format='json').status_code

    def _placed(self, employee, position) -> bool:
        return Placement.objects.filter(employee=employee, position=position).exists()

    # ── legitimate assignments ────────────────────────────────────────────────

    def test_a_seat_within_the_placers_own_permissions_is_allowed(self):
        subset = self._seat('Records Clerk', ['employees.view'])
        same = self._seat('HR Assistant', PLACER_KEYS)
        self.assertEqual(self._place(self.placer, self.people[0], subset), 200)
        self.assertEqual(self._place(self.placer, self.people[1], same), 200)

    def test_a_seat_with_no_permissions_is_always_allowed(self):
        plain = self._seat('Support Analyst', [])
        nobody = make_user('ceil_nobody@test.com', role=make_role('ceil_nobody', permission_codenames=['org_structure.edit']), employee_id='CP004')
        self.assertEqual(self._place(nobody, self.people[0], plain), 200)

    def test_a_team_managing_seat_is_not_blocked_by_the_team_flag(self):
        lead = self._seat('Team Lead', ['leave.approve'], can_manage_team=True)
        self.assertEqual(self._place(self.placer, self.people[0], lead), 200)

    def test_baseline_permissions_count_as_grantable(self):
        BaselinePermission.objects.create(permission=Permission.objects.get(codename='attendance.view'))
        seat = self._seat('Attendance Reader', ['attendance.view', 'employees.view'])
        self.assertEqual(self._place(self.placer, self.people[0], seat), 200)

    def test_the_ceiling_follows_the_placers_seat_live(self):
        payroll = self._seat('Payroll Reader', ['payroll.view'])
        self.assertEqual(self._place(self.placer, self.people[0], payroll), 403)
        own_seat = Placement.objects.get(employee=self.placer).position
        widened = _api(self.admin).put(f'/api/org-structure/positions/{own_seat.pk}/permissions/', {'codenames': PLACER_KEYS + ['payroll.view']}, format='json')
        self.assertEqual(widened.status_code, 200)
        self.assertEqual(self._place(self.placer, self.people[0], payroll), 200)

    # ── escalation attempts ───────────────────────────────────────────────────

    def test_a_seat_with_permissions_the_placer_lacks_is_refused_and_nothing_is_created(self):
        payroll = self._seat('Payroll Admin', ['payroll.view', 'payroll.edit'])
        response = _api(self.placer).post(
            f'/api/org-structure/positions/{payroll.pk}/placements/',
            {'employee': str(self.people[0].pk), 'effective_from': self.today.isoformat()}, format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn('payroll.edit', response.json()['message'])
        self.assertFalse(self._placed(self.people[0], payroll))

    def test_one_permission_too_many_in_an_otherwise_allowed_seat_is_refused(self):
        mixed = self._seat('HR And Payroll', ['employees.view', 'leave.approve', 'payroll.view'])
        self.assertEqual(self._place(self.placer, self.people[0], mixed), 403)

    def test_a_sensitive_permission_is_covered_too(self):
        workspace = self._seat('Workspace Viewer', ['employees.view_workspace'])
        self.assertEqual(self._place(self.placer, self.people[0], workspace), 403)

    def test_personal_extras_do_not_count_towards_what_may_be_granted(self):
        EmployeePermission.objects.create(employee=self.placer, permission=Permission.objects.get(codename='payroll.view'), granted_by=self.admin)
        payroll = self._seat('Payroll Reader', ['payroll.view'])
        self.assertEqual(self._place(self.placer, self.people[0], payroll), 403)

    def test_a_branch_managing_seat_needs_the_branch_flag_on_the_placers_own_seat(self):
        branch_seat = self._seat('Branch Lead', ['leave.approve'], can_manage_branch=True)
        self.assertEqual(self._place(self.placer, self.people[0], branch_seat), 403)
        branch_placer = make_user(
            'ceil_branch_placer@test.com', employee_id='CP005',
            role=make_role('ceil_branch_placer', permission_codenames=PLACER_KEYS, can_manage_branch=True),
        )
        self.assertEqual(self._place(branch_placer, self.people[0], branch_seat), 200)

    def test_a_full_access_seat_is_refused_for_everyone_who_is_not_full_access(self):
        top = self._seat('Backup Administrator', ['settings.edit'])
        self.assertEqual(self._place(self.placer, self.people[0], top), 403)
        self.assertFalse(self._placed(self.people[0], top))

    # ── full-access administrators and the initial administrator ──────────────

    def test_a_settings_edit_administrator_may_fill_any_other_seat(self):
        payroll = self._seat('Payroll Admin', ['payroll.view', 'payroll.edit'])
        branch_seat = self._seat('Branch Admin', ['leave.approve'], can_manage_branch=True)
        top = self._seat('Backup Administrator', ['settings.edit'])
        for person, seat in zip(self.people, (payroll, branch_seat, top)):
            self.assertEqual(self._place(self.admin, person, seat), 200, seat.title)

    def test_a_superuser_without_a_seat_may_fill_any_other_seat_so_the_first_admin_can_be_set_up(self):
        top = self._seat('Chief Administrator', ['settings.edit', 'payroll.edit'], can_manage_branch=True)
        self.assertEqual(self._place(self.superuser, self.people[0], top), 200)

    def test_nobody_places_themselves_even_when_the_rule_would_allow_it(self):
        low = self._seat('Records Clerk', ['employees.view'])
        other = self._seat('Anything', [])
        self.assertEqual(self._place(self.placer, self.placer, low), 403)
        self.assertEqual(self._place(self.admin, self.admin, other), 403)
        self.assertEqual(self._place(self.superuser, self.superuser, other), 403)
        self.assertFalse(self._placed(self.superuser, other))

    # ── existing placement flows ──────────────────────────────────────────────

    def test_reassigning_an_allowed_seat_still_displaces_the_previous_holder(self):
        seat = self._seat('Records Clerk', ['employees.view'])
        self.assertEqual(self._place(self.placer, self.people[0], seat, start=self.today - timedelta(days=5)), 200)
        self.assertEqual(self._place(self.placer, self.people[1], seat), 200)
        first = Placement.objects.get(employee=self.people[0], position=seat)
        self.assertEqual(first.effective_to, self.today - timedelta(days=1))

    def test_vacating_and_viewing_are_not_gated_only_granting_is(self):
        payroll = self._seat('Payroll Reader', ['payroll.view'])
        self.assertEqual(self._place(self.admin, self.people[0], payroll, start=self.today - timedelta(days=5)), 200)
        history = _api(self.placer).get(f'/api/org-structure/positions/{payroll.pk}/placements/')
        self.assertEqual(history.status_code, 200)
        ended = _api(self.placer).post(
            f'/api/org-structure/positions/{payroll.pk}/placements/end/', {'effective_to': (self.today - timedelta(days=1)).isoformat()}, format='json',
        )
        self.assertEqual(ended.status_code, 200, ended.json())

    def test_a_user_without_org_structure_edit_still_cannot_place_anyone(self):
        low = self._seat('Records Clerk', ['employees.view'])
        viewer = make_user('ceil_viewer@test.com', role=make_role('ceil_viewer', permission_codenames=['employees.view', 'org_chart.view']), employee_id='CP006')
        self.assertEqual(self._place(viewer, self.people[0], low), 403)
