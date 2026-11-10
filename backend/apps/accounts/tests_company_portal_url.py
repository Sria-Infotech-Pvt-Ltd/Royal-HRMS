"""
The Employee Portal URL setting: saved and read through the Company Settings API, validated, and used by the invitation service.

No email is sent: the mail connection is Django's in-memory outbox.
"""
from __future__ import annotations

import re
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.mail import get_connection
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, Company, PasswordResetToken
from apps.accounts.services_frontend_url import PortalUrlNotConfigured
from apps.accounts.utils import send_activation_invite

URL = '/api/settings/company/'
PRODUCTION = 'https://aira.nxsys.in'
SMTP = 'apps.accounts.utils._get_smtp_connection'


def outbox_connection():
    return (get_connection('django.core.mail.backends.locmem.EmailBackend'), 'hr@test.invalid', None)


class CompanyPortalUrlApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(company_name='Test Co')
        self.admin = make_user('portal_admin@test.com', employee_id='PA001', is_superuser=True)
        self.editor = make_user('portal_editor@test.com', employee_id='PE001', role=make_role('portal_editor', permission_codenames=['settings.edit']))
        self.viewer = make_user('portal_viewer@test.com', employee_id='PV001', role=make_role('portal_viewer', permission_codenames=['settings.view']))

    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def save(self, value, user=None):
        # is_draft: the settings page's "Save draft" path. A full save also validates every other company field (PAN, address...),
        # which this fixture company does not have; the portal URL check itself runs on both paths.
        return self.client_for(user or self.admin).patch(URL, {'portal_url': value, 'is_draft': 'true'}, format='json')

    # ── saving and retrieving ────────────────────────────────────────────────────────────────────────────────────────────

    def test_an_administrator_can_save_and_read_back_the_portal_url(self):
        response = self.save(PRODUCTION)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['data']['portal_url'], PRODUCTION)
        self.company.refresh_from_db()
        self.assertEqual(self.company.portal_url, PRODUCTION)
        read = self.client_for(self.viewer).get(URL)
        self.assertEqual(read.data['data']['portal_url'], PRODUCTION)

    def test_a_trailing_slash_is_removed_when_saving(self):
        self.assertEqual(self.save(PRODUCTION + '/').data['data']['portal_url'], PRODUCTION)

    def test_the_change_is_audited(self):
        self.save(PRODUCTION)
        self.assertTrue(AuditLog.objects.filter(module='company', action='update', user=self.admin).exists())

    def test_only_someone_with_settings_edit_can_change_it(self):
        self.assertEqual(self.save(PRODUCTION, self.editor).status_code, 200)
        self.assertEqual(self.save('https://other.example.org', self.viewer).status_code, 403)
        self.company.refresh_from_db()
        self.assertEqual(self.company.portal_url, PRODUCTION)                    # the viewer's attempt changed nothing

    def test_it_is_saved_on_the_one_company_record(self):
        self.save(PRODUCTION)
        self.assertEqual(Company.objects.count(), 1)                              # this system has a single company; no second record appears

    # ── validation ───────────────────────────────────────────────────────────────────────────────────────────────────────

    def test_malformed_values_are_refused_with_a_clear_message_and_nothing_is_saved(self):
        self.save(PRODUCTION)
        for bad in ('http://', 'http:/', 'https://', 'aira.nxsys.in', 'activate', 'http://activate', 'ftp://aira.nxsys.in', 'https://aira nxsys.in',
                    'https://aira.nxsys.in?x=1', 'javascript:alert(1)'):
            response = self.save(bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertTrue(response.data['message'], bad)
            self.company.refresh_from_db()
            self.assertEqual(self.company.portal_url, PRODUCTION, bad)           # still the good value

    def test_plain_http_is_refused_outside_local_development(self):
        with self.settings(DEBUG=False):
            response = self.save('http://aira.nxsys.in')
        self.assertEqual(response.status_code, 400)
        self.assertIn('https', response.data['message'])

    def test_localhost_over_http_is_allowed_only_in_development(self):
        with self.settings(DEBUG=True):
            self.assertEqual(self.save('http://localhost:3000').status_code, 200)
        with self.settings(DEBUG=False):
            self.assertEqual(self.save('http://localhost:3000').status_code, 400)

    # ── use by the invitation service ───────────────────────────────────────────────────────────────────────────────────

    def test_the_invitation_link_uses_the_saved_value_in_the_required_format(self):
        self.save(PRODUCTION)
        user = make_user('portal_invitee@test.com', employee_id='PI001', account_activated_at=None)
        with mock.patch(SMTP, outbox_connection):
            token, _ = send_activation_invite(user)
        link = re.search(r'href="([^"]*/activate/[^"]*)"', mail.outbox[-1].alternatives[0][0]).group(1)
        self.assertEqual(link, f'{PRODUCTION}/activate/{token.id}/')

    def test_clearing_the_value_stops_invitations_with_a_clear_message_and_creates_no_token(self):
        self.save(PRODUCTION)
        self.assertEqual(self.save('').status_code, 200)
        user = make_user('portal_invitee2@test.com', employee_id='PI002', account_activated_at=None)
        with mock.patch(SMTP, outbox_connection):
            with self.assertRaises(PortalUrlNotConfigured) as caught:
                send_activation_invite(user)
        self.assertIn('Company settings', str(caught.exception))                 # tells the administrator where to fix it
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(PasswordResetToken.objects.filter(user=user).count(), 0)   # no unusable token was created
