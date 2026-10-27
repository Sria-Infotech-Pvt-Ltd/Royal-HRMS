"""Access follows the seat: permissions held through a Position (step 1 of removing Roles)."""
from __future__ import annotations

from datetime import date, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, BaselinePermission, OrgUnit, Permission, Placement, Position, PositionPermission, User
from core.access import can_manage_branch, can_manage_team, excluded_from_payroll, team_managers, users_with_permission
from core.permissions import effective_permission_codenames, has_perm


def _permission(codename: str) -> Permission:
    module, _, action = codename.partition('.')
    return Permission.objects.get_or_create(codename=codename, defaults={'module': module, 'action': action or 'view'})[0]


class SeatPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = OrgUnit.objects.create(name='Finance Seat Test')
        self.seat = Position.objects.create(org_unit=self.unit, title='Payroll Lead', grade='L3')
        PositionPermission.objects.create(position=self.seat, permission=_permission('payroll.view'))
        self.bare_role = make_role('bare_seat_test', permission_codenames=[])
        self.person = make_user('seat-person@test.com', role=self.bare_role, employee_id='SEAT1')

    def _place(self, start, end=None):
        return Placement.objects.create(position=self.seat, employee=self.person, effective_from=start, effective_to=end)

    def test_no_seat_means_no_permission(self):
        self.assertFalse(has_perm(self.person, 'payroll.view'))

    def test_holder_inherits_the_seats_permission(self):
        self._place(date.today() - timedelta(days=1))
        self.assertTrue(has_perm(self.person, 'payroll.view'))
        self.assertFalse(has_perm(self.person, 'payroll.edit'))

    def test_seat_holder_with_no_other_access_still_gets_the_seats_permission(self):
        self._place(date.today())
        self.assertTrue(has_perm(self.person, 'payroll.view'))

    def test_ended_future_and_inactive_seats_grant_nothing(self):
        placement = self._place(date.today() - timedelta(days=10), date.today() - timedelta(days=1))
        self.assertFalse(has_perm(self.person, 'payroll.view'), 'ended placement')
        placement.delete()
        placement = self._place(date.today() + timedelta(days=5))
        self.assertFalse(has_perm(self.person, 'payroll.view'), 'future placement')
        placement.delete()
        self._place(date.today() - timedelta(days=1))
        Position.objects.filter(pk=self.seat.pk).update(is_active=False)
        self.assertFalse(has_perm(self.person, 'payroll.view'), 'inactive seat')

    def test_settings_edit_on_a_seat_is_not_full_access(self):
        PositionPermission.objects.create(position=self.seat, permission=_permission('settings.edit'))
        self._place(date.today())
        self.assertTrue(has_perm(self.person, 'settings.edit'))
        self.assertFalse(has_perm(self.person, 'employees.edit'))  # only a superuser has everything


class PositionPermissionsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        unit = OrgUnit.objects.create(name='API Seat Test')
        self.seat = Position.objects.create(org_unit=unit, title='Analyst', grade='L2')
        admin_role = make_role('admin_seat_api', permission_codenames=['settings.edit', 'org_chart.view'])
        self.admin = make_user('admin-seat@test.com', role=admin_role, employee_id='SEATADM')
        viewer_role = make_role('viewer_seat_api', permission_codenames=['org_chart.view'])
        self.viewer = make_user('viewer-seat@test.com', role=viewer_role, employee_id='SEATVIEW')
        for codename in ('payroll.view', 'leave.view', 'leave.approve'):
            _permission(codename)
        self.url = reverse('position-permissions', args=[self.seat.pk])

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_admin_replaces_the_seats_permissions_and_flags(self):
        client = self._client(self.admin)
        resp = client.put(self.url, {'codenames': ['payroll.view', 'leave.view'], 'can_manage_team': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['codenames'], ['leave.view', 'payroll.view'])
        resp = client.put(self.url, {'codenames': ['leave.approve']}, format='json')
        self.assertEqual(resp.data['data']['codenames'], ['leave.approve'])
        self.seat.refresh_from_db()
        self.assertTrue(self.seat.can_manage_team)
        self.assertEqual(AuditLog.objects.filter(action='position_permissions_update').count(), 2)

    def test_get_returns_the_current_permissions(self):
        PositionPermission.objects.create(position=self.seat, permission=_permission('payroll.view'))
        resp = self._client(self.viewer).get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['codenames'], ['payroll.view'])

    def test_non_admin_cannot_change_permissions(self):
        resp = self._client(self.viewer).put(self.url, {'codenames': ['payroll.view']}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self.seat.position_permissions.exists())

    def test_unknown_codename_and_bad_body_are_rejected(self):
        client = self._client(self.admin)
        self.assertEqual(client.put(self.url, {'codenames': ['no.such_permission']}, format='json').status_code, 400)
        self.assertEqual(client.put(self.url, {'codenames': 'payroll.view'}, format='json').status_code, 400)
        self.assertFalse(self.seat.position_permissions.exists())


class AccessHelperTests(TestCase):
    """core.access: baseline permissions, seat flags and the "everyone who ..." conditions."""

    def setUp(self):
        cache.clear()
        unit = OrgUnit.objects.create(name='Access Helper Test')
        self.manager_seat = Position.objects.create(org_unit=unit, title='Team Lead', grade='L3', can_manage_team=True, can_manage_branch=True)
        self.system_seat = Position.objects.create(org_unit=unit, title='Service Seat', grade='L1', exclude_from_payroll=True)
        PositionPermission.objects.create(position=self.manager_seat, permission=_permission('leave.approve'))
        role = make_role('plain_access_helper', permission_codenames=[])
        self.lead = make_user('lead-access@test.com', role=role, employee_id='ACC1')
        self.service = make_user('service-access@test.com', role=role, employee_id='ACC2')
        self.nobody = make_user('nobody-access@test.com', role=role, employee_id='ACC3')
        Placement.objects.create(position=self.manager_seat, employee=self.lead, effective_from=date.today())
        Placement.objects.create(position=self.system_seat, employee=self.service, effective_from=date.today())

    def test_seat_flags_drive_scope_helpers(self):
        self.assertTrue(can_manage_team(self.lead))
        self.assertTrue(can_manage_branch(self.lead))
        self.assertFalse(can_manage_team(self.nobody))

    def test_team_managers_condition_selects_seat_holders_and_works_in_exclude(self):
        self.assertEqual(list(User.objects.filter(team_managers()).values_list('employee_id', flat=True)), ['ACC1'])
        excluded = set(User.objects.exclude(team_managers()).values_list('employee_id', flat=True))
        self.assertIn('ACC3', excluded)
        self.assertNotIn('ACC1', excluded)

    def test_users_with_permission_covers_seat_and_baseline(self):
        self.assertEqual(list(User.objects.filter(users_with_permission('leave.approve')).values_list('employee_id', flat=True)), ['ACC1'])
        BaselinePermission.objects.create(permission=_permission('leave.approve'))
        self.assertEqual(User.objects.filter(users_with_permission('leave.approve')).count(), User.objects.count())

    def test_excluded_from_payroll_follows_the_seat(self):
        self.assertEqual(list(User.objects.filter(excluded_from_payroll()).values_list('employee_id', flat=True)), ['ACC2'])


class BaselinePermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        BaselinePermission.objects.all().delete()  # the migrations seed it; start from an empty baseline
        self.person = make_user('baseline-person@test.com', role=None, employee_id='BASE1')

    def test_everyone_gets_baseline_permissions_without_a_seat(self):
        self.assertFalse(has_perm(self.person, 'leave.create'))
        BaselinePermission.objects.create(permission=_permission('leave.create'))
        self.assertTrue(has_perm(self.person, 'leave.create'))
        self.assertEqual(effective_permission_codenames(self.person), ['leave.create'])


class BaselinePermissionsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        BaselinePermission.objects.all().delete()  # the migrations seed it; start from an empty baseline
        admin_role = make_role('admin_baseline_api', permission_codenames=['settings.edit'])
        self.admin = make_user('admin-baseline@test.com', role=admin_role, employee_id='BAPI1')
        self.plain = make_user('plain-baseline@test.com', role=make_role('plain_baseline_api', permission_codenames=[]), employee_id='BAPI2')
        for codename in ('leave.create', 'attendance.view'):
            _permission(codename)
        self.url = reverse('baseline-permissions')

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_admin_replaces_the_baseline_and_everyone_gets_it(self):
        resp = self._client(self.admin).put(self.url, {'codenames': ['leave.create', 'attendance.view']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(has_perm(self.plain, 'leave.create'))
        self._client(self.admin).put(self.url, {'codenames': ['attendance.view']}, format='json')
        self.assertFalse(has_perm(self.plain, 'leave.create'))
        self.assertEqual(AuditLog.objects.filter(action='baseline_permissions_update').count(), 2)

    def test_any_signed_in_user_can_read_it(self):
        BaselinePermission.objects.create(permission=_permission('leave.create'))
        resp = self._client(self.plain).get(self.url)
        self.assertEqual(resp.data['data']['codenames'], ['leave.create'])

    def test_non_admin_cannot_change_it_and_full_access_cannot_be_baseline(self):
        self.assertEqual(self._client(self.plain).put(self.url, {'codenames': ['leave.create']}, format='json').status_code, 403)
        self.assertEqual(self._client(self.admin).put(self.url, {'codenames': ['settings.edit']}, format='json').status_code, 400)
        self.assertEqual(self._client(self.admin).put(self.url, {'codenames': ['no.such']}, format='json').status_code, 400)
        self.assertFalse(BaselinePermission.objects.exists())
