"""
Regression tests for the new-hire account-activation invite flow (replaces
plaintext temp-password emails — see apps.accounts.utils.send_activation_invite,
views.auth.InviteCheckView, views_reset_password.ResendInviteView).
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import PasswordResetToken
from apps.accounts.utils import send_activation_invite


class ActivationInviteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.role = make_role('employee_invite_test')
        self.user = make_user('invited@test.com', role=self.role, must_change_password=True)

    @patch('apps.accounts.utils._build_message')
    @patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
    def test_send_activation_invite_creates_a_valid_invite_token(self, _mock_conn, mock_build):
        mock_build.return_value.send.return_value = None
        token = send_activation_invite(self.user)
        self.assertEqual(token.purpose, PasswordResetToken.PURPOSE_INVITE)
        self.assertEqual(token.status, PasswordResetToken.STATUS_SENT)
        self.assertTrue(token.is_valid())

    @patch('apps.accounts.utils._build_message')
    @patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
    def test_check_endpoint_marks_opened_once(self, _mock_conn, mock_build):
        mock_build.return_value.send.return_value = None
        token = send_activation_invite(self.user)
        client = APIClient()

        resp = client.get(reverse('invite-check', args=[token.id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['email'], self.user.email)

        token.refresh_from_db()
        self.assertEqual(token.status, PasswordResetToken.STATUS_OPENED)
        first_opened_at = token.opened_at

        # Opening again must not bump opened_at a second time.
        client.get(reverse('invite-check', args=[token.id]))
        token.refresh_from_db()
        self.assertEqual(token.opened_at, first_opened_at)

    @patch('apps.accounts.utils._build_message')
    @patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
    def test_setting_password_activates_the_account(self, _mock_conn, mock_build):
        mock_build.return_value.send.return_value = None
        token = send_activation_invite(self.user)
        client = APIClient()

        resp = client.post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': 'RealPassw0rd!', 'confirm_password': 'RealPassw0rd!',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)

        token.refresh_from_db()
        self.assertEqual(token.status, PasswordResetToken.STATUS_ACTIVATED)

        # The same link must not work a second time.
        resp2 = client.post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': 'AnotherPassw0rd!', 'confirm_password': 'AnotherPassw0rd!',
        }, format='json')
        self.assertEqual(resp2.status_code, 400)

    def test_expired_invite_is_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        token = PasswordResetToken.objects.create(
            user=self.user, purpose=PasswordResetToken.PURPOSE_INVITE,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        client = APIClient()
        resp = client.get(reverse('invite-check', args=[token.id]))
        self.assertEqual(resp.status_code, 410)

    @patch('apps.accounts.utils._build_message')
    @patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
    def test_resend_invalidates_the_previous_link(self, _mock_conn, mock_build):
        mock_build.return_value.send.return_value = None
        admin_role = make_role('admin_invite_test', permission_codenames=['employees.reset_password'])
        admin = make_user('admin-invite@test.com', role=admin_role, password='TestPass123!')

        old_token = send_activation_invite(self.user)

        client = APIClient()
        client.force_authenticate(user=admin)
        resp = client.post(reverse('employee-resend-invite', args=[self.user.id]))
        self.assertEqual(resp.status_code, 200, resp.data)

        old_token.refresh_from_db()
        self.assertTrue(old_token.is_used)

        new_token = PasswordResetToken.objects.filter(
            user=self.user, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False,
        ).first()
        self.assertIsNotNone(new_token)
        self.assertNotEqual(new_token.id, old_token.id)

    def test_resend_denied_once_already_activated(self):
        self.user.must_change_password = False
        self.user.save(update_fields=['must_change_password'])

        admin_role = make_role('admin_invite_test2', permission_codenames=['employees.reset_password'])
        admin = make_user('admin-invite2@test.com', role=admin_role, password='TestPass123!')
        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.post(reverse('employee-resend-invite', args=[self.user.id]))
        self.assertEqual(resp.status_code, 400)

    @patch('apps.accounts.utils._build_message')
    @patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
    def test_invite_status_endpoint_reflects_lifecycle(self, _mock_conn, mock_build):
        mock_build.return_value.send.return_value = None
        admin_role = make_role('admin_invite_test3', permission_codenames=['employees.reset_password'])
        admin = make_user('admin-invite3@test.com', role=admin_role, password='TestPass123!')
        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.get(reverse('employee-invite-status', args=[self.user.id]))
        self.assertEqual(resp.data['data']['invite_status'], None)

        token = send_activation_invite(self.user)
        resp = client.get(reverse('employee-invite-status', args=[self.user.id]))
        self.assertEqual(resp.data['data']['invite_status'], 'sent')

        public_client = APIClient()
        public_client.get(reverse('invite-check', args=[token.id]))
        resp = client.get(reverse('employee-invite-status', args=[self.user.id]))
        self.assertEqual(resp.data['data']['invite_status'], 'opened')

        public_client.post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': 'RealPassw0rd!', 'confirm_password': 'RealPassw0rd!',
        }, format='json')
        resp = client.get(reverse('employee-invite-status', args=[self.user.id]))
        self.assertEqual(resp.data['data']['invite_status'], 'activated')
