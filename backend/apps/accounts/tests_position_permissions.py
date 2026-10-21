"""Access follows the seat: permissions held through a Position (step 1 of removing Roles)."""
from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, OrgUnit, Permission, Placement, Position, PositionPermission
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

    def test_person_with_no_role_at_all_still_gets_seat_access(self):
        self._place(date.today())
        self.person.role = None
        self.person.save()
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

    def test_role_permissions_still_work_alongside_seats(self):
        role = make_role('legacy_role_seat_test', permission_codenames=['leave.view'])
        self.person.role = role
        self.person.save()
        self._place(date.today())
        self.assertTrue(has_perm(self.person, 'leave.view'))
        self.assertTrue(has_perm(self.person, 'payroll.view'))
        self.assertEqual(effective_permission_codenames(self.person), ['leave.view', 'payroll.view'])

    def test_settings_edit_on_a_seat_is_full_access(self):
        PositionPermission.objects.create(position=self.seat, permission=_permission('settings.edit'))
        self._place(date.today())
        self.assertTrue(has_perm(self.person, 'employees.edit'))


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


class MigrateRolesToPositionsCommandTests(TestCase):
    def setUp(self):
        unit = OrgUnit.objects.create(name='Command Seat Test')
        self.seat = Position.objects.create(org_unit=unit, title='HR Partner', grade='L3')
        role = make_role('hr_cmd_seat_test', permission_codenames=['employees.view', 'employees.edit'])
        role.can_manage_team = True
        role.save()
        self.holder = make_user('holder-cmd@test.com', role=role, employee_id='CMD1')
        Placement.objects.create(position=self.seat, employee=self.holder, effective_from=date.today() - timedelta(days=1))
        self.unseated = make_user('unseated-cmd@test.com', role=role, employee_id='CMD2')

    def _run(self, *args):
        out = StringIO()
        call_command('migrate_roles_to_positions', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing_and_flags_people_without_a_seat(self):
        output = self._run()
        self.assertIn('DRY RUN', output)
        self.assertIn('NO SEAT: CMD2', output)
        self.assertFalse(self.seat.position_permissions.exists())

    def test_apply_copies_role_permissions_and_flags_onto_the_seat_and_is_idempotent(self):
        self._run('--apply')
        self.seat.refresh_from_db()
        self.assertEqual(
            sorted(self.seat.position_permissions.values_list('permission__codename', flat=True)),
            ['employees.edit', 'employees.view'],
        )
        self.assertTrue(self.seat.can_manage_team)
        self.assertIn('0 seats', self._run('--apply'))
