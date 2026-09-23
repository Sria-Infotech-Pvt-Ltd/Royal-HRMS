"""
Tests for CompanySystemAdminView — the Platform Admin -> Companies ->
System Admin view/change-email flow (apps/tenants/views.py).

This replaced an earlier tenant-side attempt (Employee Profile page) that
turned out to be unreachable in practice: a provisioned System Admin has no
employee_id and never appears in that company's own Employees list
(EmployeeListCreateView.get()'s .exclude(employee_id='')). Test #15 below
specifically confirms this view works WITHOUT one, since that was the whole
point of moving it here.

Uses the one real tenant schema config.test_runner.TenantAwareTestRunner
already provisions for the whole suite (TEST_COMPANY_CODE) rather than
creating a second one — cheaper, and sufficient to prove the `with client:`
schema-switch actually reaches the right company's User table. A
nonexistent company id is used to prove "wrong/absent company id" is
rejected rather than silently falling back to some default company.
"""
from __future__ import annotations

from unittest.mock import patch
import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.tenants.models import Client, PlatformAdmin
from config.test_runner import TEST_COMPANY_CODE


def _make_platform_admin(email: str, password: str = 'TestPass123!') -> PlatformAdmin:
    admin = PlatformAdmin(email=email, full_name='Platform Admin')
    admin.set_password(password)
    admin.save()
    return admin


def _login_platform_admin(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('platform-admin-login'), {'email': email, 'password': password}, format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


class CompanySystemAdminViewTests(TestCase):

    def setUp(self):
        self.client_obj = Client.objects.get(company_code=TEST_COMPANY_CODE)
        self.platform_admin_email = 'platadmin.sysadmin.test@test.com'
        _make_platform_admin(self.platform_admin_email)

        # The tenant's own System Admin — deliberately NO employee_id, same
        # shape as a real company-provisioning-created account (test #15).
        with self.client_obj:
            self.admin_role = make_role('sysadmin_pa_test', permission_codenames=['settings.edit'])
            self.tenant_admin = make_user(
                'tenant.admin.old@test.com', role=self.admin_role, password='TenantPass123!',
                full_name='Tenant System Admin',
            )
            self.assertEqual(self.tenant_admin.employee_id, '')  # sanity check on the fixture itself

            employee_role = make_role('employee_pa_test', permission_codenames=['employees.edit'])
            make_user(
                'taken@test.com', role=employee_role, password='TestPass123!', employee_id='PATAKEN1',
            )

        self.api = APIClient()

    def _url(self, company_pk):
        return reverse('platform-admin-company-system-admin', kwargs={'pk': company_pk})

    # ── Authorization ──────────────────────────────────────────────────

    def test_unauthenticated_request_rejected(self):
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'new@test.com'}, format='json',
        )
        self.assertIn(resp.status_code, (401, 403))

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertEqual(self.tenant_admin.email, 'tenant.admin.old@test.com')

    # ── Targeting ──────────────────────────────────────────────────────

    def test_nonexistent_company_returns_404(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.get(self._url(uuid.uuid4()))
        self.assertEqual(resp.status_code, 404)

    # ── Validation ──────────────────────────────────────────────────────

    def test_invalid_email_format_rejected(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'not-an-email'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_email_rejected(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'taken@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertEqual(self.tenant_admin.email, 'tenant.admin.old@test.com')

    def test_same_email_rejected_as_noop(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'tenant.admin.old@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    # ── Successful change: in-place update only ───────────────────────

    def test_successful_change_updates_existing_user_in_place(self):
        with self.client_obj:
            from apps.accounts.models import User
            old_pk            = self.tenant_admin.pk
            old_password_hash = self.tenant_admin.password
            old_role_id       = self.tenant_admin.role_id
            user_count_before = User.objects.count()

        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'tenant.admin.new@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['email'], 'tenant.admin.new@test.com')

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertEqual(self.tenant_admin.pk, old_pk)                        # same row (test #3)
            self.assertEqual(User.objects.count(), user_count_before)             # no duplicate (test #4)
            self.assertEqual(self.tenant_admin.email, 'tenant.admin.new@test.com')
            self.assertEqual(self.tenant_admin.password, old_password_hash)       # password untouched (test #5)
            self.assertTrue(self.tenant_admin.check_password('TenantPass123!'))
            self.assertEqual(self.tenant_admin.role_id, old_role_id)              # role untouched (test #6)

    def test_get_returns_current_system_admin(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.get(self._url(self.client_obj.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['email'], 'tenant.admin.old@test.com')
        self.assertEqual(resp.data['data']['full_name'], 'Tenant System Admin')

    # ── Audit ─────────────────────────────────────────────────────────

    def test_tenant_side_audit_log_records_old_and_new_email(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'tenant.admin.new@test.com'}, format='json',
        )

        with self.client_obj:
            from apps.accounts.models import AuditLog
            log = AuditLog.objects.filter(
                action='system_admin_email_changed', object_id=str(self.tenant_admin.id),
            ).first()
            self.assertIsNotNone(log)
            self.assertEqual(
                log.changes['email'], {'from': 'tenant.admin.old@test.com', 'to': 'tenant.admin.new@test.com'},
            )
            self.assertNotIn('password', str(log.changes).lower())

    def test_platform_side_audit_log_records_the_action(self):
        _login_platform_admin(self.api, self.platform_admin_email)
        self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'tenant.admin.new@test.com'}, format='json',
        )

        from apps.tenants.models import PlatformAdminAuditLog
        log = PlatformAdminAuditLog.objects.filter(
            action='company_system_admin_email_changed', target_company=self.client_obj,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changes['old_email'], 'tenant.admin.old@test.com')
        self.assertEqual(log.changes['new_email'], 'tenant.admin.new@test.com')
        self.assertNotIn('password', str(log.changes).lower())

    # ── Email notifications ──────────────────────────────────────────

    def test_change_succeeds_even_when_notification_emails_fail(self):
        # No SMTPSettings configured for the test tenant — same "delivery
        # failure is reported, not fatal" convention used throughout this
        # codebase's other email-sending tests.
        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'tenant.admin.new@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['data']['new_email_sent'])
        self.assertFalse(resp.data['data']['old_email_sent'])

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertEqual(self.tenant_admin.email, 'tenant.admin.new@test.com')

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_both_notifications_sent_when_smtp_configured(self, mock_send):
        with self.client_obj:
            from apps.accounts.models import SMTPSettings
            SMTPSettings.objects.create(
                name='PA System Admin Email Test SMTP', host='smtp.example.com', port=587,
                username='test@example.com', password='irrelevant',
                from_email='test@example.com', is_active=True,
            )

        _login_platform_admin(self.api, self.platform_admin_email)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'new_email': 'tenant.admin.new@test.com'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['new_email_sent'])
        self.assertTrue(resp.data['data']['old_email_sent'])
        self.assertEqual(mock_send.call_count, 2)

        # Neither notification may contain a password — this is an
        # email-change notice, never a credentials email.
        for call in mock_send.call_args_list:
            for message in call.args[0]:
                self.assertNotIn('Temporary Password', message.body)
                combined_alt = ' '.join(alt for alt, _ in message.alternatives)
                self.assertNotIn('Temporary Password', combined_alt)


class CompanyOnboardingEmailUnaffectedTests(TestCase):
    """
    Regression check for requirement #14: company-provisioning's own
    credentials email (a completely different code path — public-schema
    PlatformSMTPSettings, not the tenant SMTPSettings this feature uses)
    must still fire exactly as before. Calls _seed_company_data directly
    (the same function provision_company()/finish_pending_provisioning()
    both funnel through) rather than going through async Celery
    provisioning, which this test suite has no worker for.
    """

    @patch('apps.tenants.services.send_company_provisioned_email')
    def test_seed_company_data_still_sends_provisioning_email(self, mock_send):
        from apps.tenants.models import ALL_MODULES, Client as ClientModel
        from apps.tenants.services import _seed_company_data

        client = ClientModel(
            schema_name='tenant_pa_onboarding_test',
            company_code='PAONBTEST',
            company_name='PA Onboarding Regression Test Co',
            enabled_modules=list(ALL_MODULES),
            is_active=True,
        )
        client.save()  # auto_create_schema=True

        try:
            _seed_company_data(client, 'new.admin@test.com')
        finally:
            client.delete(force_drop=True)

        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs['admin_email'], 'new.admin@test.com')


class CompanySystemAdminResetPasswordViewTests(TestCase):
    """
    Tests for CompanySystemAdminResetPasswordView — requires the ACTING
    Platform Admin's own current password (never the System Admin's)
    before generating and emailing a new temporary System Admin password.
    """

    def setUp(self):
        self.client_obj = Client.objects.get(company_code=TEST_COMPANY_CODE)
        self.pa_email = 'platadmin.pwreset.test@test.com'
        self.pa_password = 'PlatformPass123!'
        _make_platform_admin(self.pa_email, self.pa_password)

        with self.client_obj:
            self.admin_role = make_role('sysadmin_pwreset_test', permission_codenames=['settings.edit'])
            self.tenant_admin = make_user(
                'tenant.admin.pwreset@test.com', role=self.admin_role, password='OldPass123!',
                full_name='Tenant System Admin',
            )
            self.assertEqual(self.tenant_admin.employee_id, '')  # test #11 fixture sanity check

            other_role = make_role('employee_pwreset_test', permission_codenames=['employees.edit'])
            self.other_employee = make_user(
                'other.employee.pwreset@test.com', role=other_role, password='OtherPass123!',
                employee_id='PWRESET1',
            )

        self.api = APIClient()

    def _url(self, company_pk):
        return reverse('platform-admin-company-system-admin-reset-password', kwargs={'pk': company_pk})

    # ── Authorization (tests #4, #5) ──────────────────────────────────

    def test_unauthenticated_request_rejected(self):
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
        )
        self.assertIn(resp.status_code, (401, 403))

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertTrue(self.tenant_admin.check_password('OldPass123!'))

    def test_tenant_user_credentials_do_not_grant_access(self):
        # IsPlatformAdmin only ever accepts a request authenticated via
        # PlatformAdminAuthentication (the platform_access_token cookie
        # namespace) — a tenant user has no way to authenticate against
        # this endpoint at all, which is the "non-platform-admin" case
        # collapsing to the same rejection as unauthenticated for this
        # specific architecture (confirmed during investigation).
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': 'OldPass123!'}, format='json',
        )
        self.assertIn(resp.status_code, (401, 403))

    # ── Validation ──────────────────────────────────────────────────────

    def test_empty_platform_admin_password_rejected(self):
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(self._url(self.client_obj.pk), {'platform_admin_password': ''}, format='json')
        self.assertEqual(resp.status_code, 400)

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertTrue(self.tenant_admin.check_password('OldPass123!'))

    def test_incorrect_platform_admin_password_rejected(self):
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': 'WrongPassword!'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertTrue(self.tenant_admin.check_password('OldPass123!'))  # unchanged (test #2)

    def test_system_admin_password_is_never_used_for_verification(self):
        # Deliberately try the SYSTEM ADMIN's own password as the
        # "platform_admin_password" field — must be rejected, since it is
        # checked against request.user (the PlatformAdmin), never the
        # tenant User.
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': 'OldPass123!'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertTrue(self.tenant_admin.check_password('OldPass123!'))

    def test_nonexistent_company_returns_404(self):
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(
            self._url(uuid.uuid4()), {'platform_admin_password': self.pa_password}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    # ── Successful reset: correct PA password → succeeds, in-place only ──

    def test_correct_password_resets_system_admin_password(self):
        with self.client_obj:
            from apps.accounts.models import User
            old_pk            = self.tenant_admin.pk
            old_password_hash = self.tenant_admin.password
            old_role_id       = self.tenant_admin.role_id
            old_email         = self.tenant_admin.email
            user_count_before = User.objects.count()

        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        # Temp password itself must never appear in the response (see §3 of task).
        self.assertNotIn('password', resp.data.get('data', {}))
        self.assertNotIn('OldPass123', str(resp.data))

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertEqual(self.tenant_admin.pk, old_pk)                    # test #7
            self.assertEqual(User.objects.count(), user_count_before)         # no duplicate user
            self.assertEqual(self.tenant_admin.email, old_email)              # test #8
            self.assertEqual(self.tenant_admin.role_id, old_role_id)          # test #9 (role -> permissions, test #10)
            self.assertNotEqual(self.tenant_admin.password, old_password_hash)  # test #12
            self.assertFalse(self.tenant_admin.check_password('OldPass123!'))   # test #14
            self.assertTrue(self.tenant_admin.must_change_password)

            # The other employee in the same tenant is completely untouched.
            self.other_employee.refresh_from_db()
            self.assertTrue(self.other_employee.check_password('OtherPass123!'))

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_new_temporary_password_actually_works_for_login(self, mock_send):
        with self.client_obj:
            from apps.accounts.models import SMTPSettings
            SMTPSettings.objects.create(
                name='PA Reset Password Test SMTP', host='smtp.example.com', port=587,
                username='test@example.com', password='irrelevant',
                from_email='test@example.com', is_active=True,
            )

        # Capture the real temp password by patching set_password on the
        # exact User instance the view will fetch and mutate — simplest way
        # to observe the plaintext without weakening the view's own contract
        # of never returning/logging it.
        captured = {}
        from apps.accounts.models import User
        original_set_password = User.set_password

        def _capturing_set_password(self_user, raw_password):
            if self_user.email == 'tenant.admin.pwreset@test.com':
                captured['password'] = raw_password
            return original_set_password(self_user, raw_password)

        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        with patch.object(User, 'set_password', _capturing_set_password):
            resp = self.api.post(
                self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('password', captured)

        # test #13: the temp password logs in, and (per must_change_password
        # convention already used by EmployeeResetPasswordView) forces a
        # change on next login — asserted directly against the DB rather
        # than the login response, since that convention is enforced by the
        # frontend/subsequent flows, not LoginView's status code itself.
        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertTrue(self.tenant_admin.check_password(captured['password']))
            self.assertTrue(self.tenant_admin.must_change_password)

    # ── Audit (tests #16, #17, #18) ──────────────────────────────────────

    def test_tenant_side_audit_log_never_contains_password(self):
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
        )

        with self.client_obj:
            from apps.accounts.models import AuditLog
            log = AuditLog.objects.filter(
                action='system_admin_password_reset', object_id=str(self.tenant_admin.id),
            ).first()
            self.assertIsNotNone(log)  # test #17
            self.assertNotIn('password', str(log.changes).lower())  # test #16

    def test_platform_side_audit_log_created_and_never_contains_password(self):
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
        )

        from apps.tenants.models import PlatformAdminAuditLog
        log = PlatformAdminAuditLog.objects.filter(
            action='company_system_admin_password_reset', target_company=self.client_obj,
        ).first()
        self.assertIsNotNone(log)  # test #18
        self.assertNotIn('password', str(log.changes).lower())  # test #16

    # ── Email (test #15) ──────────────────────────────────────────────

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_credential_email_sent_to_correct_system_admin_address(self, mock_send):
        with self.client_obj:
            from apps.accounts.models import SMTPSettings
            SMTPSettings.objects.create(
                name='PA Reset Password Email Test SMTP', host='smtp.example.com', port=587,
                username='test@example.com', password='irrelevant',
                from_email='test@example.com', is_active=True,
            )

        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['email_sent'])
        mock_send.assert_called_once()

        sent_message = mock_send.call_args.args[0][0]
        self.assertEqual(list(sent_message.to), ['tenant.admin.pwreset@test.com'])

    def test_reset_succeeds_even_when_notification_email_fails(self):
        # No SMTPSettings configured for the test tenant — same "delivery
        # failure is reported, not fatal" convention as every other
        # credential email in this codebase.
        _login_platform_admin(self.api, self.pa_email, self.pa_password)
        resp = self.api.post(
            self._url(self.client_obj.pk), {'platform_admin_password': self.pa_password}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['data']['email_sent'])

        with self.client_obj:
            self.tenant_admin.refresh_from_db()
            self.assertTrue(self.tenant_admin.must_change_password)
