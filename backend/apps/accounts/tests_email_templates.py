"""Regression tests for Email Template CRUD — no prior test coverage
exercised name format, template_type existence, built-in template
protection (name-lock + delete-block), or name-uniqueness on rename.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmailTemplate, EmailTemplateCategory


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class EmailTemplateValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('template_admin_test', permission_codenames=['settings.edit'])
        self.admin = make_user('tplAdmin@test.com', role=role, password='TestPass123!')
        _login(self.client, 'tplAdmin@test.com')
        self.category, _ = EmailTemplateCategory.objects.get_or_create(
            name='onboarding', defaults={'display_name': 'Onboarding'},
        )

    def _payload(self, **overrides):
        payload = {
            'name': 'welcome_email', 'display_name': 'Welcome Email',
            'template_type': 'onboarding', 'subject': 'Welcome, {{first_name}}!',
            'body': '<p>Hello {{first_name}}, welcome aboard.</p>',
        }
        payload.update(overrides)
        return payload

    def test_valid_template_created(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_name_with_uppercase_rejected(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(name='Welcome_Email'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_name_with_spaces_rejected(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(name='welcome email'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_name_starting_with_digit_rejected(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(name='1welcome'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unknown_template_type_rejected(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(template_type='not_a_real_category'), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_blank_subject_rejected(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(subject='   '), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_blank_body_rejected(self):
        resp = self.client.post(reverse('email-template-list'), self._payload(body=''), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_name_rejected_on_rename(self):
        first = self.client.post(reverse('email-template-list'), self._payload(name='template_a'), format='json')
        second = self.client.post(reverse('email-template-list'), self._payload(name='template_b'), format='json')
        self.assertEqual(second.status_code, 201, second.data)
        resp = self.client.put(
            reverse('email-template-detail', args=[second.data['data']['id']]),
            self._payload(name='template_a'), format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_denied_without_settings_edit(self):
        no_perm = make_user('notpladmin@test.com', role=make_role('no_tpl_perm_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.post(reverse('email-template-list'), self._payload(), format='json')
        self.assertEqual(resp.status_code, 403)


class BuiltinTemplateProtectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('template_admin_test2', permission_codenames=['settings.edit'])
        self.admin = make_user('tplAdmin2@test.com', role=role, password='TestPass123!')
        _login(self.client, 'tplAdmin2@test.com')
        self.category, _ = EmailTemplateCategory.objects.get_or_create(
            name='security', defaults={'display_name': 'Security'},
        )
        self.builtin = EmailTemplate.objects.create(
            name='password_reset', display_name='Password Reset', template_type='security',
            subject='Reset your password', body='<p>Click here to reset.</p>', is_builtin=True,
        )

    def test_builtin_template_cannot_be_deleted(self):
        resp = self.client.delete(reverse('email-template-detail', args=[self.builtin.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(EmailTemplate.objects.filter(pk=self.builtin.pk).exists())

    def test_builtin_template_name_cannot_be_changed(self):
        resp = self.client.put(reverse('email-template-detail', args=[self.builtin.pk]), {
            'name': 'renamed_reset', 'display_name': 'Password Reset', 'template_type': 'security',
            'subject': 'Reset your password', 'body': '<p>Click here to reset.</p>',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_builtin_template_other_fields_can_still_be_edited(self):
        resp = self.client.patch(
            reverse('email-template-detail', args=[self.builtin.pk]),
            {'subject': 'Updated subject line'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.builtin.refresh_from_db()
        self.assertEqual(self.builtin.subject, 'Updated subject line')

    def test_builtin_template_can_be_deactivated_instead_of_deleted(self):
        resp = self.client.patch(
            reverse('email-template-detail', args=[self.builtin.pk]),
            {'is_active': False}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.builtin.refresh_from_db()
        self.assertFalse(self.builtin.is_active)

    def test_non_builtin_template_can_be_deleted(self):
        custom = EmailTemplate.objects.create(
            name='custom_template', display_name='Custom', template_type='security',
            subject='Subject', body='Body', is_builtin=False,
        )
        resp = self.client.delete(reverse('email-template-detail', args=[custom.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(EmailTemplate.objects.filter(pk=custom.pk).exists())
