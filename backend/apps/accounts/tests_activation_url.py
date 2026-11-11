"""
The emailed activation link: correct, absolute, and never malformed.

Background: invitations went out with the link `/activate/<token>/` (no website address) because the company had no portal URL, and mail
clients turned that into `http://activate/<token>/`. These tests pin the fixed behaviour: the link is built from a checked portal
address; a missing or unusable address stops the invitation BEFORE anything is changed or sent.

No real email is ever sent: the mail connection and message sending are mocked or replaced by Django's in-memory outbox.
"""
from __future__ import annotations

import re
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.mail import get_connection
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import services_employee_import_invites as invites
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Company, EmailLog, EmployeeImportInvite, PasswordResetToken
from apps.accounts.serializers import CompanySerializer
from apps.accounts.services_frontend_url import PortalUrlNotConfigured, check_portal_url, frontend_origin, frontend_url
from apps.accounts.utils import _activation_link, send_activation_invite, send_otp_email

PRODUCTION = 'https://aira.nxsys.in'
OUTBOX_CONNECTION = ('apps.accounts.utils._get_smtp_connection', lambda: (get_connection('django.core.mail.backends.locmem.EmailBackend'), 'hr@test.invalid', None))
DELAY = 'apps.accounts.tasks.send_import_invite.delay'
LINK = re.compile(r'href="([^"]*/activate/[^"]*)"')


def set_portal(value: str) -> None:
    Company.objects.all().delete()
    Company.objects.create(company_name='Test Co', portal_url=value)


class _Case(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user('act_url@test.com', role=make_role('act_url_role'), employee_id='AU001', must_change_password=True, account_activated_at=None)

    def send(self):
        with mock.patch(OUTBOX_CONNECTION[0], OUTBOX_CONNECTION[1]):
            return send_activation_invite(self.user)

    def sent_link(self) -> str:
        return LINK.search(mail.outbox[-1].alternatives[0][0] if mail.outbox[-1].alternatives else mail.outbox[-1].body).group(1)


class CorrectUrlTests(_Case):
    def test_the_production_link_is_absolute_https_on_the_production_domain(self):
        set_portal(PRODUCTION)
        token, _ = self.send()
        self.assertEqual(self.sent_link(), f'{PRODUCTION}/activate/{token.id}/')

    def test_trailing_slashes_and_case_do_not_change_the_result(self):
        for stored in (PRODUCTION + '/', PRODUCTION + '//', 'HTTPS://aira.nxsys.in'):
            set_portal(stored)
            self.assertEqual(_activation_link('T'), f'{PRODUCTION}/activate/T/', stored)

    @override_settings(DEBUG=True)                                           # http://localhost is accepted only in development
    def test_a_path_prefix_is_kept_and_a_local_test_address_is_allowed(self):
        set_portal('https://example.org/hr/')
        self.assertEqual(frontend_url('/activate/T/'), 'https://example.org/hr/activate/T/')
        set_portal('http://localhost:3000')
        self.assertEqual(frontend_url('/activate/T/'), 'http://localhost:3000/activate/T/')

    def test_the_link_points_at_the_route_the_frontend_really_has(self):
        # frontend/app/activate/[token]/page.tsx  ->  /activate/<token>   (the API it calls is GET /api/invite/<token>/)
        set_portal(PRODUCTION)
        self.assertRegex(_activation_link('abc'), r'^https://aira\.nxsys\.in/activate/abc/$')


class MissingOrMalformedConfigurationTests(_Case):
    BAD = ('http://', 'http:/', 'https://', 'https:/', 'aira.nxsys.in', 'activate', 'http://activate', 'https://activate/', 'ftp://aira.nxsys.in',
           'https://aira nxsys.in', 'https://aira.nxsys.in?x=1', 'https://aira.nxsys.in#top', '//aira.nxsys.in', 'javascript:alert(1)')

    def test_no_company_row_means_no_link_is_built(self):
        Company.objects.all().delete()
        with self.assertRaises(PortalUrlNotConfigured):
            frontend_origin()

    def test_a_blank_portal_url_means_no_link_is_built(self):
        set_portal('')
        with self.assertRaises(PortalUrlNotConfigured):
            _activation_link('T')

    def test_every_malformed_value_is_refused_and_never_turns_into_a_link(self):
        for value in self.BAD:
            set_portal(value)
            with self.assertRaises(PortalUrlNotConfigured, msg=value):
                _activation_link('T')
            with self.assertRaises(ValueError, msg=value):
                check_portal_url(value)

    @override_settings(DEBUG=False)
    def test_plain_http_is_refused_outside_local_testing(self):
        with self.assertRaises(ValueError):
            check_portal_url('http://aira.nxsys.in')

    def test_the_settings_form_refuses_the_same_values_so_they_cannot_be_saved(self):
        for value in self.BAD:
            serializer = CompanySerializer(data={'portal_url': value}, partial=True)
            serializer.is_valid()
            self.assertIn('portal_url', serializer.errors, value)
        self.assertNotIn('portal_url', (lambda s: (s.is_valid(), s.errors)[1])(CompanySerializer(data={'portal_url': PRODUCTION}, partial=True)))

    def test_without_a_portal_url_nothing_is_sent_and_the_existing_link_keeps_working(self):
        set_portal(PRODUCTION)
        old, _ = self.send()
        mail.outbox.clear()
        EmailLog.objects.all().delete()
        set_portal('')
        with self.assertRaises(PortalUrlNotConfigured):
            self.send()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailLog.objects.count(), 0)
        old.refresh_from_db()
        self.assertTrue(old.is_valid())                                  # the failed attempt did not burn the employee's current link
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user, purpose=PasswordResetToken.PURPOSE_INVITE).count(), 1)

    def test_a_bulk_import_invitation_fails_with_a_clear_reason_and_is_not_retried_automatically(self):
        set_portal('http://')
        row = EmployeeImportInvite.objects.create(user=self.user, created_by=self.user, row_number=2, batch_id='11111111-1111-1111-1111-111111111111')
        with mock.patch(OUTBOX_CONNECTION[0], OUTBOX_CONNECTION[1]):
            self.assertEqual(invites.process_invite(row.pk), 'failed')
        row.refresh_from_db()
        self.assertEqual((row.status, row.reason_code), ('failed', 'portal_url_not_configured'))
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(row.next_attempt_at)
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user).count(), 0)
        set_portal(PRODUCTION)                                           # fixed: the retry button now works and sends a correct link
        with mock.patch(DELAY):                                          # the broker is mocked: a real task would run inline and close the test's connection
            self.assertEqual(invites.retry_batch(self.user, row.batch_id)['requeued'], 1)
        with mock.patch(OUTBOX_CONNECTION[0], OUTBOX_CONNECTION[1]):
            self.assertEqual(invites.process_invite(row.pk), 'sent')
        self.assertTrue(self.sent_link().startswith(f'{PRODUCTION}/activate/'))


class ActivationFlowTests(_Case):
    def setUp(self):
        super().setUp()
        set_portal(PRODUCTION)
        self.client = APIClient()

    def token_from_link(self) -> str:
        return self.sent_link().rstrip('/').rsplit('/', 1)[1]

    def test_a_valid_link_is_recognised(self):
        self.send()
        response = self.client.get(reverse('invite-check', args=[self.token_from_link()]))
        self.assertEqual((response.status_code, response.data['data']['email']), (200, self.user.email))

    def test_an_unknown_or_expired_link_is_refused(self):
        self.assertEqual(self.client.get(reverse('invite-check', args=['00000000-0000-0000-0000-000000000000'])).status_code, 404)
        token, _ = self.send()
        PasswordResetToken.objects.filter(pk=token.pk).update(expires_at=token.created_at)
        self.assertEqual(self.client.get(reverse('invite-check', args=[token.id])).status_code, 410)

    def test_setting_a_password_activates_the_account_and_the_employee_can_log_in(self):
        self.send()
        token = self.token_from_link()
        response = self.client.post('/api/reset-password/', {'reset_token': token, 'new_password': 'Fresh-Pass-1', 'confirm_password': 'Fresh-Pass-1'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.account_activated_at)
        self.assertTrue(self.user.check_password('Fresh-Pass-1'))
        self.assertEqual(self.client.post('/api/login/', {'email': self.user.email, 'password': 'Fresh-Pass-1'}, format='json').status_code, 200)

    def test_the_link_cannot_be_used_twice_and_a_second_password_is_not_accepted(self):
        self.send()
        token = self.token_from_link()
        body = {'reset_token': token, 'new_password': 'Fresh-Pass-1', 'confirm_password': 'Fresh-Pass-1'}
        self.assertEqual(self.client.post('/api/reset-password/', body, format='json').status_code, 200)
        again = self.client.post('/api/reset-password/', {**body, 'new_password': 'Other-Pass-2', 'confirm_password': 'Other-Pass-2'}, format='json')
        self.assertEqual(again.status_code, 400)
        self.assertEqual(self.client.get(reverse('invite-check', args=[token])).status_code, 410)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Fresh-Pass-1'))

    def test_a_weak_password_is_refused_and_the_link_stays_usable(self):
        self.send()
        token = self.token_from_link()
        self.assertEqual(self.client.post('/api/reset-password/', {'reset_token': token, 'new_password': '123', 'confirm_password': '123'}, format='json').status_code, 400)
        self.assertEqual(self.client.get(reverse('invite-check', args=[token])).status_code, 200)


class ForgotPasswordTests(_Case):
    """The forgot-password flow emails a 6-digit code, not a link, so it has no website address to get wrong. This pins that fact."""

    def test_the_password_reset_email_contains_a_code_and_no_link(self):
        with mock.patch(OUTBOX_CONNECTION[0], OUTBOX_CONNECTION[1]):
            send_otp_email(self.user.email, '123456', 'Test User')
        html = mail.outbox[-1].alternatives[0][0] if mail.outbox[-1].alternatives else mail.outbox[-1].body
        self.assertIn('123456', html)
        self.assertNotRegex(html, r'href="[^"#]*"')
        self.assertNotIn('http://activate', html)
