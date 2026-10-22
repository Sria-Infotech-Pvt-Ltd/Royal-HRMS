"""
Changing what a position (or everyone) may do must end the sessions of the people affected, so they pick up the new
permissions at their next login instead of acting on the old set for the life of their refresh token.

Permissions are copied into the login token (see apps.accounts.tokens), while backend has_perm() checks already read
the database fresh. Blacklisting the affected people's outstanding tokens is what keeps the two in step.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories import make_permission, make_role, make_user
from apps.accounts.models import OrgUnit, Placement, Position


class PermissionChangeForcesLogoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('seatadmin@test.com', role=make_role('settings_admin_test', permission_codenames=['settings.edit']))
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        for codename in ('employees.edit_own_profile', 'leave.view'):
            make_permission(codename)

        unit = OrgUnit.objects.create(name='Logout Test Unit')
        self.seat = Position.objects.create(org_unit=unit, title='Analyst', grade='L2')
        self.holder = make_user('seat-holder@test.com')
        Placement.objects.create(position=self.seat, employee=self.holder, effective_from=date.today() - timedelta(days=1))
        self.url = reverse('position-permissions', args=[self.seat.pk])

    def _token_for(self, user):
        return RefreshToken.for_user(user)

    def _is_blacklisted(self, token) -> bool:
        return BlacklistedToken.objects.filter(token__jti=str(token['jti'])).exists()

    def test_changing_a_positions_permissions_blacklists_the_holders_tokens(self):
        token = self._token_for(self.holder)
        self.assertFalse(self._is_blacklisted(token))

        resp = self.client.put(self.url, {'codenames': ['employees.edit_own_profile']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertTrue(self._is_blacklisted(token))

    def test_saving_the_same_permissions_again_does_not_log_anyone_out(self):
        self.client.put(self.url, {'codenames': ['leave.view']}, format='json')
        token = self._token_for(self.holder)

        resp = self.client.put(self.url, {'codenames': ['leave.view']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertFalse(self._is_blacklisted(token))

    def test_inactive_holders_tokens_are_not_blacklisted_needlessly(self):
        inactive = make_user('inactive-holder@test.com')
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])
        Placement.objects.filter(employee=self.holder).update(employee=inactive)
        token = self._token_for(inactive)

        self.client.put(self.url, {'codenames': ['leave.view']}, format='json')

        self.assertFalse(self._is_blacklisted(token))

    def test_other_positions_holders_are_unaffected(self):
        other_unit = OrgUnit.objects.create(name='Other Logout Unit')
        other_seat = Position.objects.create(org_unit=other_unit, title='Clerk', grade='L1')
        other_person = make_user('other-holder@test.com')
        Placement.objects.create(position=other_seat, employee=other_person, effective_from=date.today() - timedelta(days=1))
        token = self._token_for(other_person)

        self.client.put(self.url, {'codenames': ['leave.view']}, format='json')

        self.assertFalse(self._is_blacklisted(token))

    def test_changing_the_baseline_logs_everyone_out(self):
        token = self._token_for(self.holder)

        resp = self.client.put(reverse('baseline-permissions'), {'codenames': ['leave.view']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertTrue(self._is_blacklisted(token))
