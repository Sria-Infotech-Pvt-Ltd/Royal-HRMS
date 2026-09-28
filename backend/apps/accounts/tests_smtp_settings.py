"""Regression tests for SMTP Settings CRUD and activation — no prior test
coverage exercised this at all. Covers field validation (port range,
blank host/username, malformed from/bcc email), name-uniqueness on both
create and rename, permission gating (settings.edit only), and the
single-active-config invariant on activation.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import SMTPSettings


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class SMTPSettingsValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('smtp_admin_test', permission_codenames=['settings.edit'])
        self.admin = make_user('smtpadmin@test.com', role=role, password='TestPass123!')
        _login(self.client, 'smtpadmin@test.com')

    def _payload(self, **overrides):
        payload = {
            'name': 'Primary SMTP', 'host': 'smtp.example.com', 'port': 587,
            'username': 'user@example.com', 'password': 'secret123',
            'from_email': 'noreply@example.com',
        }
        payload.update(overrides)
        return payload

    def test_valid_config_created(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_blank_host_rejected(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(host='   '), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_port_zero_rejected(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(port=0), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_port_over_65535_rejected(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(port=70000), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_blank_username_rejected(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(username='  '), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_malformed_from_email_rejected(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(from_email='not-an-email'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_malformed_bcc_email_rejected(self):
        resp = self.client.post(reverse('smtp-list'), self._payload(bcc_email='also-not-valid'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_name_rejected_on_create(self):
        # SMTPSettingsSerializer.validate() checks name uniqueness itself
        # (case-insensitive) before the view ever attempts the insert — 400,
        # not 409. The view's IntegrityError->409 catch only exists as a
        # fallback for a genuine race between two concurrent submissions,
        # which this single-request test doesn't exercise.
        first = self.client.post(reverse('smtp-list'), self._payload(), format='json')
        self.assertEqual(first.status_code, 201, first.data)
        second = self.client.post(reverse('smtp-list'), self._payload(host='smtp2.example.com'), format='json')
        self.assertEqual(second.status_code, 400)

    def test_duplicate_name_rejected_on_rename(self):
        first = self.client.post(reverse('smtp-list'), self._payload(name='Config A'), format='json')
        second = self.client.post(reverse('smtp-list'), self._payload(name='Config B'), format='json')
        self.assertEqual(second.status_code, 201, second.data)
        resp = self.client.patch(
            reverse('smtp-detail', args=[second.data['data']['id']]), {'name': 'Config A'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_server_type_config_saves_without_host_or_username(self):
        # Regression: the frontend never sends host/username/port/password for
        # smtp_type=server (only local-mode fields), but the serializer used
        # to mark host/username required unconditionally (no blank=True on
        # the model fields) — every "server" config silently failed with a
        # 400 the frontend rendered as a generic, easy-to-miss toast.
        resp = self.client.post(reverse('smtp-list'), {
            'name': 'Dedicated Mail Server', 'smtp_type': 'server',
            'from_email': 'noreply@example.com',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_local_type_still_requires_host_and_username(self):
        resp = self.client.post(reverse('smtp-list'), {
            'name': 'Local Missing Fields', 'smtp_type': 'local',
            'from_email': 'noreply@example.com', 'password': 'secret123',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('host', resp.data.get('data', resp.data) if isinstance(resp.data, dict) else {})

    def test_create_denied_without_settings_edit(self):
        no_perm = make_user('nosmtpperm@test.com', role=make_role('no_smtp_perm_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.post(reverse('smtp-list'), self._payload(), format='json')
        self.assertEqual(resp.status_code, 403)


class SMTPActivationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('smtp_admin_test2', permission_codenames=['settings.edit'])
        self.admin = make_user('smtpadmin2@test.com', role=role, password='TestPass123!')
        _login(self.client, 'smtpadmin2@test.com')

        self.config_a = SMTPSettings.objects.create(
            name='Config A', host='a.example.com', port=587, username='a@example.com',
            password='secretA', from_email='a@example.com', is_active=True,
        )
        self.config_b = SMTPSettings.objects.create(
            name='Config B', host='b.example.com', port=587, username='b@example.com',
            password='secretB', from_email='b@example.com', is_active=False,
        )

    def test_activating_one_config_deactivates_the_other(self):
        resp = self.client.post(reverse('smtp-activate', args=[self.config_b.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.config_a.refresh_from_db()
        self.config_b.refresh_from_db()
        self.assertFalse(self.config_a.is_active)
        self.assertTrue(self.config_b.is_active)

    def test_only_one_config_ever_active_after_multiple_switches(self):
        self.client.post(reverse('smtp-activate', args=[self.config_b.pk]))
        self.client.post(reverse('smtp-activate', args=[self.config_a.pk]))
        active_count = SMTPSettings.objects.filter(is_active=True).count()
        self.assertEqual(active_count, 1)

    def test_deleting_the_active_config_warns_nothing_is_active(self):
        resp = self.client.delete(reverse('smtp-detail', args=[self.config_a.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('No SMTP config is currently active', resp.data['message'])
