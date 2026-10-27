"""Extra permissions granted to ONE employee: additive to the baseline and the seat, enforced everywhere access is
decided (has_perm, the token's permission list, "everyone who has X" queries), and editable only by full-access users."""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, BaselinePermission, EmployeePermission, Permission, User
from core.access import users_with_permission
from core.permissions import effective_permission_codenames, has_perm


def _permission(codename: str) -> Permission:
    module, _, action = codename.partition('.')
    return Permission.objects.get_or_create(codename=codename, defaults={'module': module, 'action': action})[0]


class EmployeeExtraPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        BaselinePermission.objects.all().delete()
        self.client = APIClient()
        self.admin = make_user('ep-admin@test.com', role=make_role('ep_admin', permission_codenames=['settings.edit', 'settings.view']))
        self.viewer = make_user('ep-viewer@test.com', role=make_role('ep_viewer', permission_codenames=['settings.view']))
        self.person = make_user('ep-person@test.com', role=make_role('ep_person', permission_codenames=['leave.view']))
        for codename in ('payroll.view', 'attendance.view', 'settings.edit'):
            _permission(codename)

    def _grant(self, codename: str) -> None:
        EmployeePermission.objects.create(employee=self.person, permission=_permission(codename))

    def _put(self, user, codenames):
        self.client.force_authenticate(user=user)
        return self.client.put(reverse('employee-permissions', args=[self.person.pk]), {'codenames': codenames}, format='json')

    def test_extra_permission_grants_access_and_is_in_the_token_list(self):
        self.assertFalse(has_perm(self.person, 'payroll.view'))
        self._grant('payroll.view')
        self.assertTrue(has_perm(self.person, 'payroll.view'))
        self.assertIn('payroll.view', effective_permission_codenames(self.person))

    def test_extra_permission_is_additive_to_the_seat(self):
        self._grant('payroll.view')
        self.assertTrue(has_perm(self.person, 'leave.view'))

    def test_extra_permission_only_applies_to_that_person(self):
        self._grant('payroll.view')
        self.assertFalse(has_perm(self.viewer, 'payroll.view'))

    def test_users_with_permission_includes_personal_grants(self):
        self._grant('payroll.view')
        holders = User.objects.filter(users_with_permission('payroll.view'))
        self.assertIn(self.person, holders)
        self.assertNotIn(self.viewer, holders)

    def test_put_grants_and_removes_extras_and_ends_the_session(self):
        with patch('apps.accounts.views.employee_permissions.force_relogin') as relogin:
            resp = self._put(self.admin, ['payroll.view', 'attendance.view'])
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['data']['extra'], ['attendance.view', 'payroll.view'])
            relogin.assert_called_once_with([self.person.pk])

        resp = self._put(self.admin, ['attendance.view'])
        self.assertEqual(resp.data['data']['extra'], ['attendance.view'])
        self.assertFalse(has_perm(self.person, 'payroll.view'))
        self.assertTrue(AuditLog.objects.filter(action='employee_permissions_update', object_id=str(self.person.pk)).exists())

    def test_put_without_a_change_does_not_end_the_session(self):
        with patch('apps.accounts.views.employee_permissions.force_relogin') as relogin:
            self._put(self.admin, [])
            relogin.assert_not_called()

    def test_only_full_access_users_can_change_extras(self):
        self.assertEqual(self._put(self.viewer, ['payroll.view']).status_code, 403)
        self.assertEqual(self._put(self.person, ['payroll.view']).status_code, 403)
        self.assertFalse(EmployeePermission.objects.exists())

    def test_unknown_permission_is_rejected(self):
        self.assertEqual(self._put(self.admin, ['nope.nothing']).status_code, 400)

    def test_full_access_cannot_be_granted_to_one_person(self):
        self.assertEqual(self._put(self.admin, ['settings.edit']).status_code, 400)
        self.assertFalse(has_perm(self.person, 'settings.edit', full_access_bypass=False))

    def test_get_shows_baseline_seat_and_extras(self):
        BaselinePermission.objects.create(permission=_permission('attendance.view'))
        self._grant('payroll.view')
        self.client.force_authenticate(user=self.viewer)
        resp = self.client.get(reverse('employee-permissions', args=[self.person.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['baseline'], ['attendance.view'])
        self.assertEqual(data['extra'], ['payroll.view'])
        self.assertIn('leave.view', data['seat']['codenames'])

    def test_get_requires_settings_view(self):
        self.client.force_authenticate(user=self.person)
        self.assertEqual(self.client.get(reverse('employee-permissions', args=[self.person.pk])).status_code, 403)
