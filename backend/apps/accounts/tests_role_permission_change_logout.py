"""
Regression test: updating a Role's permissions must force-logout every
active user currently holding that role (blacklist their outstanding
refresh tokens) — permissions are baked into the JWT at login and
deliberately not re-derived on the silent 15-minute refresh
(see FreshClaimsTokenRefreshSerializer's own docstring), so without this,
an already-logged-in user keeps acting on the OLD permission set for up
to the refresh token's full 7-day lifetime after an admin changes what
their role can do.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.factories import make_role, make_user


class RolePermissionChangeForcesLogoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin_role = make_role('settings_admin_test', permission_codenames=['settings.edit'])
        self.admin = make_user('roleadmin@test.com', role=self.admin_role, password='TestPass123!')
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.target_role = make_role('employee_logout_test')
        self.target_user = make_user('affected-employee@test.com', role=self.target_role)
        # Only inactive users should be spared — not exercised here, but
        # kept in mind: is_active=True is the default from make_user.

    def _refresh_token_for(self, user):
        return RefreshToken.for_user(user)

    def test_updating_role_permissions_blacklists_active_users_tokens(self):
        token = self._refresh_token_for(self.target_user)
        self.assertFalse(BlacklistedToken.objects.filter(token__jti=str(token['jti'])).exists())

        resp = self.client.put(reverse('role-detail', args=[self.target_role.id]), {
            'name': self.target_role.name,
            'display_name': self.target_role.display_name,
            'can_manage_team': False,
            'can_manage_branch': False,
            'permission_codenames': ['employees.edit_own_profile'],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertTrue(BlacklistedToken.objects.filter(token__jti=str(token['jti'])).exists())

    def test_inactive_users_tokens_are_not_blacklisted_needlessly(self):
        inactive_user = make_user('inactive-employee@test.com', role=self.target_role)
        inactive_user.is_active = False
        inactive_user.save(update_fields=['is_active'])
        token = self._refresh_token_for(inactive_user)

        resp = self.client.put(reverse('role-detail', args=[self.target_role.id]), {
            'name': self.target_role.name,
            'display_name': self.target_role.display_name,
            'can_manage_team': False,
            'can_manage_branch': False,
            'permission_codenames': [],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertFalse(BlacklistedToken.objects.filter(token__jti=str(token['jti'])).exists())

    def test_other_roles_tokens_are_unaffected(self):
        other_role = make_role('other_role_logout_test')
        other_user = make_user('other-role-employee@test.com', role=other_role)
        token = self._refresh_token_for(other_user)

        resp = self.client.put(reverse('role-detail', args=[self.target_role.id]), {
            'name': self.target_role.name,
            'display_name': self.target_role.display_name,
            'can_manage_team': False,
            'can_manage_branch': False,
            'permission_codenames': [],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertFalse(BlacklistedToken.objects.filter(token__jti=str(token['jti'])).exists())
