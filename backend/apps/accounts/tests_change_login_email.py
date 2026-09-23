"""
Tests for EmployeeChangeLoginEmailView — the admin-triggered "change a
System Admin's login email" action added alongside the existing Reset
Password button on the Employee Profile page.

Mirrors the fixture/assertion conventions already established in
EmployeeResetPasswordTests (apps/accounts/tests.py): SMTP left unconfigured
drives the "notification failed" branch (no network call — _get_smtp_
connection() raises RuntimeError on its own), a mocked SMTP backend drives
the "notification sent" branch. The security-relevant change itself (new
email, unchanged password, unchanged role, audit log) is always asserted
directly against the database, independent of whether either notification
email actually went out.
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, Role, User
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


class EmployeeChangeLoginEmailTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # settings.edit is the org-wide "true admin" permission this
        # endpoint is gated on — matches system_admin's real seeded role
        # (accounts.migrations.0002_seed_roles_permissions) in shape, not
        # by name, since the view resolves the target by capability too.
        self.admin_role = make_role('sysadmin_test', permission_codenames=['settings.edit'])
        self.admin = make_user(
            'admin.old@test.com', role=self.admin_role, password='TestPass123!',
            employee_id='EMPADMIN01', full_name='Company Admin',
        )

        # A second settings.edit holder — the one allowed to perform the
        # change on the first admin's account (self-service via this
        # endpoint is allowed; nothing here specifically requires "self").
        self.other_admin = make_user(
            'other.admin@test.com', role=self.admin_role, password='TestPass123!',
            employee_id='EMPADMIN02', full_name='Second Admin',
        )

        # A regular employee — must never be reachable through this endpoint.
        self.employee_role = make_role('employee_test_cle', permission_codenames=['employees.edit'])
        self.employee = make_user(
            'regular@test.com', role=self.employee_role, password='TestPass123!',
            employee_id='EMPREG001', full_name='Regular Employee',
        )

        # A pre-existing account whose email will collide with the "new"
        # email in the duplicate-rejection test.
        make_user(
            'taken@test.com', role=self.employee_role, password='TestPass123!',
            employee_id='EMPTAKEN1', full_name='Existing Owner',
        )

    def _url(self, employee_id: str):
        return reverse('employee-change-login-email', kwargs={'employee_id': employee_id})

    # ── Authorization ──────────────────────────────────────────────────

    def test_unauthorized_user_cannot_change_system_admin_email(self):
        _login(self.client, 'regular@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'new.admin@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, 'admin.old@test.com')

    def test_settings_edit_holder_cannot_target_a_regular_employee(self):
        # This endpoint only ever changes a System Admin's own email —
        # regular-employee email editing stays unavailable everywhere,
        # matching EmployeeDetailView.put() never accepting an email field.
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.employee.employee_id), {'new_email': 'new.email@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'regular@test.com')

    # ── Validation ──────────────────────────────────────────────────────

    def test_invalid_email_format_rejected(self):
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'not-an-email'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, 'admin.old@test.com')

    def test_duplicate_email_rejected(self):
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'taken@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, 'admin.old@test.com')

    def test_same_email_rejected_as_noop(self):
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'admin.old@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    # ── Successful change: user updated in place, password/role untouched ──

    def test_successful_change_updates_existing_user_in_place(self):
        old_pk = self.admin.pk
        old_password_hash = self.admin.password
        old_role_id = self.admin.role_id
        user_count_before = User.objects.count()

        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'admin.new@test.com'}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['email'], 'admin.new@test.com')

        self.admin.refresh_from_db()
        # Same row, not a new one.
        self.assertEqual(self.admin.pk, old_pk)
        self.assertEqual(User.objects.count(), user_count_before)
        self.assertEqual(self.admin.email, 'admin.new@test.com')
        # Password and role are byte-for-byte untouched.
        self.assertEqual(self.admin.password, old_password_hash)
        self.assertEqual(self.admin.role_id, old_role_id)
        self.assertTrue(self.admin.check_password('TestPass123!'))

    def test_old_email_no_longer_logs_in_new_email_does(self):
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'admin.new@test.com'}, format='json',
        )

        fresh_client = APIClient()
        old_login = fresh_client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'admin.old@test.com', 'password': 'TestPass123!'},
            format='json',
        )
        self.assertNotEqual(old_login.status_code, 200)

        new_login = fresh_client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'admin.new@test.com', 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(new_login.status_code, 200, new_login.data)

    def test_audit_log_records_old_and_new_email(self):
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'admin.new@test.com'}, format='json',
        )

        log = AuditLog.objects.filter(
            action='system_admin_email_changed', object_id=str(self.admin.id),
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changes['email'], {'from': 'admin.old@test.com', 'to': 'admin.new@test.com'})
        # No password/token material anywhere in the audit payload.
        self.assertNotIn('password', str(log.changes).lower())

    # ── Email notifications ──────────────────────────────────────────────

    def test_change_succeeds_even_when_notification_emails_fail(self):
        # No SMTPSettings configured — same "delivery failure is reported,
        # not fatal" convention as EmployeeResetPasswordTests.
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'admin.new@test.com'}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['data']['new_email_sent'])
        self.assertFalse(resp.data['data']['old_email_sent'])
        self.assertIn('could not', resp.data['message'])

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, 'admin.new@test.com')

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_both_notifications_sent_when_smtp_configured(self, mock_send):
        from apps.accounts.models import SMTPSettings
        SMTPSettings.objects.create(
            name='Change Email Test SMTP', host='smtp.example.com', port=587,
            username='test@example.com', password='irrelevant',
            from_email='test@example.com', is_active=True,
        )
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.post(
            self._url(self.admin.employee_id), {'new_email': 'admin.new@test.com'}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['new_email_sent'])
        self.assertTrue(resp.data['data']['old_email_sent'])
        self.assertEqual(mock_send.call_count, 2)

        # Neither email body may contain a password — this is an
        # email-change notification, never a credentials email.
        for call in mock_send.call_args_list:
            for message in call.args[0]:
                self.assertNotIn('Temporary Password', message.body)
                combined_alt = ' '.join(alt for alt, _ in message.alternatives)
                self.assertNotIn('Temporary Password', combined_alt)

    # ── Regression: unrelated flows still work exactly as before ─────────

    def test_generic_employee_edit_still_ignores_email_field(self):
        # EmployeeDetailView.put() must keep silently ignoring an 'email'
        # key — this feature must never leak into the generic edit path.
        _login(self.client, 'other.admin@test.com', password='TestPass123!')
        resp = self.client.put(
            reverse('employee-detail', kwargs={'employee_id': self.employee.employee_id}),
            {'email': 'sneaky@test.com', 'department': self.employee.department or ''},
            format='json',
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'regular@test.com')

    def test_role_with_settings_edit_is_resolved_by_capability_not_name(self):
        # The view's "is this target a system admin" check reads
        # role.role_permissions for settings.edit — confirm a
        # differently-named role with that same permission is still
        # treated as an eligible target (matches how _branch_admin_role()
        # and applyLeaderRole() elsewhere in this codebase already resolve
        # roles by capability, not literal name).
        self.assertTrue(
            Role.objects.get(name='sysadmin_test')
            .role_permissions.filter(permission__codename='settings.edit').exists()
        )
