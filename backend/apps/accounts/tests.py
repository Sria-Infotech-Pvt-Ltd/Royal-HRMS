from __future__ import annotations

import re
from datetime import date, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule, AuditLog, EmployeeApprovalOverride, OTPVerification, User
from apps.accounts.serializers import ForgotPasswordSerializer
from apps.accounts.views import COO_ROLE_NAME
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    # company_code is a required LoginSerializer field — it's what tells
    # LoginView which tenant schema to authenticate against. TEST_COMPANY_CODE
    # is the one test tenant config/test_runner.TenantAwareTestRunner
    # provisions for the whole run (see that module's own docstring).
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


class HtmlToTextCredentialEmailTests(SimpleTestCase):
    """
    Regression test for the "Invalid credentials" support issue: an
    employee copies Company Code / Login Email / Temporary Password from
    the credential email and pastes them into login, and sometimes gets
    "Invalid credentials" despite pasting correctly.

    Root cause: _html_to_text() (the plain-text MIME alternative every
    credential email attaches alongside its HTML part) stripped tags with
    no replacement whitespace. The employee-creation and admin-reset email
    bodies build the password/URL lines as directly-adjacent literals with
    no space between '<br>' and the next '<strong>' — e.g.
    '...{temp_password}<br><strong>Login URL:...' — so the plain-text part
    rendered as '...{temp_password}Login URL: https://...', gluing the
    literal word "Login" onto the end of the real password. Any mail
    client/gateway that shows or lets the recipient copy from the
    plain-text part (rather than the HTML part) then yields a password
    that can never pass check_password(), regardless of a byte-perfect
    copy-paste on the employee's end. No database is needed to test this
    — it is a pure string transformation.
    """

    def test_br_and_closing_tags_become_newlines_not_nothing(self):
        from apps.accounts.utils import _html_to_text
        self.assertEqual(_html_to_text('A<br>B'), 'A\nB')
        self.assertEqual(_html_to_text('<p>A</p><p>B</p>'), 'A\nB')

    def test_password_is_not_glued_to_adjacent_label_in_plaintext_part(self):
        from apps.accounts.utils import _html_to_text
        temp_password = 'aB3xK9mQ7Zwp'
        login_url = 'https://royalhrms.com/login'
        # Exact shape of the real credential-email bodies (employee-creation
        # welcome email and admin-reset email in views.py).
        body = (
            f'<strong>Temporary Password:</strong> {temp_password}<br>'
            f'<strong>Login URL:</strong> <a href="{login_url}">{login_url}</a>'
        )
        text = _html_to_text(body)
        self.assertIn(temp_password, text)
        self.assertNotIn(temp_password + 'Login', text)
        # The password must appear as its own separated token, not fused
        # to any neighbouring word on either side.
        self.assertRegex(text, rf'(?<![A-Za-z0-9]){re.escape(temp_password)}(?![A-Za-z0-9])')


class LoginFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        self.role = make_role('employee')
        self.user = make_user('employee@test.com', role=self.role, password='CorrectPass123!')

    def test_valid_login_succeeds_and_sets_cookies(self):
        resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'employee@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('royal_access_token', resp.cookies)
        self.assertIn('royal_refresh_token', resp.cookies)
        self.assertTrue(resp.cookies['royal_access_token']['httponly'])
        self.assertEqual(resp.cookies['royal_access_token']['samesite'], 'Lax')
        self.assertTrue(
            AuditLog.objects.filter(user=self.user, action='login').exists()
        )

    def test_wrong_password_does_not_authenticate(self):
        resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'employee@test.com', 'password': 'WrongPassword!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 1)

    def test_account_locks_after_max_failed_attempts(self):
        for _ in range(5):
            self.client.post(
                reverse('login'),
                {'company_code': TEST_COMPANY_CODE, 'email': 'employee@test.com', 'password': 'WrongPassword!'},
                format='json',
            )
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.locked_until)
        self.assertTrue(self.user.is_locked())

        # Even the correct password must be rejected while locked.
        resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'employee@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'employee@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_login_resets_failed_attempts_on_success(self):
        self.user.failed_login_attempts = 3
        self.user.save(update_fields=['failed_login_attempts'])
        resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'employee@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)


class TokenRefreshTests(TestCase):
    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        self.role = make_role('employee')
        self.user = make_user('refresh@test.com', role=self.role, password='CorrectPass123!')
        login_resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'refresh@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.refresh_cookie = login_resp.cookies['royal_refresh_token'].value

    def test_refresh_with_valid_cookie_issues_new_access_cookie(self):
        self.client.cookies['royal_refresh_token'] = self.refresh_cookie
        resp = self.client.post(reverse('token-refresh'), {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('royal_access_token', resp.cookies)

    def test_refresh_without_cookie_is_rejected(self):
        # setUp's login already left a refresh cookie on self.client — use a
        # bare client so this actually exercises the no-cookie-present path.
        bare_client = APIClient()
        resp = bare_client.post(reverse('token-refresh'), {}, format='json')
        self.assertEqual(resp.status_code, 401)


class PasswordResetFlowTests(TestCase):
    """Covers ForgotPassword -> VerifyOTP -> ResetPassword end to end.

    Email sending is skipped (no SMTPSettings configured), so we read the
    OTP straight from the DB the same way `send_otp_email` would be given it.
    """

    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        self.role = make_role('employee')
        self.user = make_user('reset@test.com', role=self.role, password='OldPass123!')

    def test_forgot_password_does_not_reveal_account_existence(self):
        """Regression test: validate_email() used to raise a ValidationError
        for unknown/inactive emails, which fails the field BEFORE the view's
        own "same response either way" branch can run — so an unknown email
        got a distinct 400 while a known one got a 200. Both must now pass
        field validation identically; only serializer.context differs.
        """
        known = ForgotPasswordSerializer(data={'email': 'reset@test.com'})
        unknown = ForgotPasswordSerializer(data={'email': 'nobody-registered@test.com'})

        self.assertTrue(known.is_valid())
        self.assertTrue(unknown.is_valid())
        self.assertIn('user', known.context)
        self.assertNotIn('user', unknown.context)

    def test_forgot_password_view_returns_identical_response_for_unknown_email(self):
        # The known-user path additionally tries to send a real OTP email,
        # which needs an active SMTPSettings row this test intentionally
        # doesn't create — so only the unknown-user (no-op) path is checked
        # against the API here; the serializer-level test above covers both.
        resp = self.client.post(
            reverse('forgot-password'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'nobody-registered@test.com'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data['message'],
            'OTP sent to your email address. It is valid for 10 minutes.',
        )

    def test_full_reset_round_trip(self):
        otp_obj, plain_otp = OTPVerification.create_for_user(self.user)

        verify_resp = self.client.post(
            reverse('verify-otp'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'reset@test.com', 'otp': plain_otp},
            format='json',
        )
        self.assertEqual(verify_resp.status_code, 200)
        reset_token = verify_resp.data['data']['reset_token']

        reset_resp = self.client.post(
            reverse('reset-password'),
            {
                'company_code': TEST_COMPANY_CODE,
                'reset_token': reset_token,
                'new_password': 'BrandNewPass123!',
                'confirm_password': 'BrandNewPass123!',
            },
            format='json',
        )
        self.assertEqual(reset_resp.status_code, 200)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPass123!'))
        self.assertFalse(self.user.must_change_password)

        # Token must be single-use.
        replay_resp = self.client.post(
            reverse('reset-password'),
            {
                'company_code': TEST_COMPANY_CODE,
                'reset_token': reset_token,
                'new_password': 'AnotherPass123!',
                'confirm_password': 'AnotherPass123!',
            },
            format='json',
        )
        self.assertEqual(replay_resp.status_code, 400)

    def test_otp_brute_force_is_capped_by_attempts(self):
        otp_obj, plain_otp = OTPVerification.create_for_user(self.user)
        for _ in range(5):
            self.client.post(
                reverse('verify-otp'),
                {'company_code': TEST_COMPANY_CODE, 'email': 'reset@test.com', 'otp': '000000'},
                format='json',
            )
        resp = self.client.post(
            reverse('verify-otp'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'reset@test.com', 'otp': plain_otp},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('maximum attempts', resp.data['message'].lower())


class ChangePasswordTests(TestCase):
    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        self.role = make_role('employee')
        self.user = make_user('change@test.com', role=self.role, password='OldPass123!')
        login_resp = self.client.post(
            reverse('login'),
            {'company_code': TEST_COMPANY_CODE, 'email': 'change@test.com', 'password': 'OldPass123!'},
            format='json',
        )
        self.access_cookie = login_resp.cookies['royal_access_token'].value
        self.refresh_cookie = login_resp.cookies['royal_refresh_token'].value

    def test_change_password_blacklists_old_refresh_token(self):
        self.client.cookies['royal_access_token'] = self.access_cookie
        self.client.cookies['royal_refresh_token'] = self.refresh_cookie

        resp = self.client.post(
            reverse('change-password'),
            {
                'old_password': 'OldPass123!',
                'new_password': 'NewPass123!',
                'confirm_password': 'NewPass123!',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

        # The refresh token issued at login must no longer work.
        refresh_client = APIClient()
        refresh_client.cookies['royal_refresh_token'] = self.refresh_cookie
        refresh_resp = refresh_client.post(reverse('token-refresh'), {}, format='json')
        self.assertEqual(refresh_resp.status_code, 401)


class OnboardingApprovalReferralBonusTests(TestCase):
    """Regression test: approving a referred candidate's onboarding must
    create their ReferralBonus record. The only code that used to do this
    lived in recruitment's CandidateStatusView.patch(), guarded by
    `new_status == STATUS_CONVERTED` — but that view's own status whitelist
    excludes STATUS_CONVERTED, so the check could never be True. Candidates
    are only ever actually converted here, in OnboardingApprovalView, which
    never created the bonus record at all.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        make_role('employee')  # OnboardingApprovalView looks this up by name
        hr_role = make_role('hr', permission_codenames=['onboarding.approve'])
        self.hr_user = make_user('hronboard@test.com', role=hr_role, password='TestPass123!')

        self.referrer = make_user('referrer2@test.com', role=make_role('employee'), password='TestPass123!')

        from apps.recruitment.models import Candidate, ReferralBonus
        self.Candidate = Candidate
        self.ReferralBonus = ReferralBonus

        self.new_hire = make_user(
            'newhire@test.com', role=None, password='TestPass123!',
            onboarding_status=User.ONBOARDING_SUBMITTED,
        )
        self.candidate = Candidate.objects.create(
            name='New Hire', email='newhire@test.com', position_applied='Engineer',
            referral_by=self.referrer, portal_user=self.new_hire,
        )
        _login(self.client, 'hronboard@test.com')

    def test_approving_onboarding_creates_referral_bonus(self):
        resp = self.client.post(
            reverse('onboarding-approve', kwargs={'user_id': str(self.new_hire.pk)}),
            {'decision': 'approve', 'department': 'Engineering', 'designation': 'Software Engineer'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            self.ReferralBonus.objects.filter(candidate=self.candidate, referrer=self.referrer).exists()
        )

    def test_approving_onboarding_without_referral_creates_no_bonus(self):
        self.candidate.referral_by = None
        self.candidate.save(update_fields=['referral_by'])

        resp = self.client.post(
            reverse('onboarding-approve', kwargs={'user_id': str(self.new_hire.pk)}),
            {'decision': 'approve', 'department': 'Engineering', 'designation': 'Software Engineer'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(self.ReferralBonus.objects.filter(candidate=self.candidate).exists())


class EmployeeResetPasswordTests(TestCase):
    """Covers the new admin-triggered Reset Password button on the Employee
    Profile page (EmployeeResetPasswordView).

    Two email outcomes are both exercised for real, not just assumed:
    - SMTP left unconfigured (same convention as PasswordResetFlowTests
      above) drives the "email delivery failed" branch — no network call
      happens, _get_smtp_connection() raises RuntimeError on its own.
    - A mocked SMTP backend drives the "email sent successfully" branch
      without an actual network call.
    In both cases the security-relevant change itself (new password,
    forced change on next login, unlocked account, audit log) is asserted
    directly against the database, and the response body is asserted to
    never contain the generated password.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr', permission_codenames=['employees.edit'])
        self.hr_user = make_user(
            'hrreset@test.com', role=hr_role, password='TestPass123!',
            employee_id='EMPHR001', full_name='HR Admin',
        )
        employee_role = make_role('employee')
        self.employee = make_user(
            'target@test.com', role=employee_role, password='OldPass123!',
            employee_id='EMPTARGET1', full_name='Target Employee',
            failed_login_attempts=2,
        )

    def _reset_url(self, employee_id: str | None = None):
        return reverse(
            'employee-reset-password',
            kwargs={'employee_id': employee_id or self.employee.employee_id},
        )

    def test_permission_denied_without_employees_edit(self):
        no_perm_role = make_role('reset_test_no_perm')
        make_user('noperm@test.com', role=no_perm_role, password='TestPass123!')
        _login(self.client, 'noperm@test.com', password='TestPass123!')

        resp = self.client.post(self._reset_url(), {}, format='json')
        self.assertEqual(resp.status_code, 403)

        # Confirm nothing changed — a denied request must be a true no-op.
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password('OldPass123!'))

    def test_reset_changes_password_and_forces_change_even_if_email_fails(self):
        old_hash = self.employee.password
        _login(self.client, 'hrreset@test.com', password='TestPass123!')

        resp = self.client.post(self._reset_url(), {}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['data']['email_sent'])
        self.assertIn('could not be sent', resp.data['message'])
        # The generated temp password must never appear anywhere in the response.
        self.assertNotIn('password', resp.data['data'])

        self.employee.refresh_from_db()
        self.assertNotEqual(self.employee.password, old_hash)
        self.assertFalse(self.employee.check_password('OldPass123!'))
        self.assertTrue(self.employee.must_change_password)
        self.assertEqual(self.employee.failed_login_attempts, 0)
        self.assertIsNone(self.employee.locked_until)
        self.assertTrue(
            AuditLog.objects.filter(
                action='employee_password_reset', object_id=str(self.employee.id),
            ).exists()
        )

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_reset_reports_email_sent_when_smtp_succeeds(self, mock_send):
        from apps.accounts.models import SMTPSettings
        SMTPSettings.objects.create(
            name='Reset Test SMTP', host='smtp.example.com', port=587,
            username='test@example.com', password='irrelevant',
            from_email='test@example.com', is_active=True,
        )
        _login(self.client, 'hrreset@test.com', password='TestPass123!')

        resp = self.client.post(self._reset_url(), {}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['email_sent'])
        self.assertIn('New credentials sent', resp.data['message'])
        self.assertNotIn('password', resp.data['data'])
        mock_send.assert_called_once()

        self.employee.refresh_from_db()
        self.assertTrue(self.employee.must_change_password)

    def test_admin_cannot_reset_own_password(self):
        _login(self.client, 'hrreset@test.com', password='TestPass123!')
        resp = self.client.post(self._reset_url(self.hr_user.employee_id), {}, format='json')
        self.assertEqual(resp.status_code, 400)

        self.hr_user.refresh_from_db()
        self.assertTrue(self.hr_user.check_password('TestPass123!'))


class EmployeeCodeGenerationTests(TestCase):
    """New Employee ID format: prefix + date-of-joining (DDMM) + name
    initials, with a numeric-suffix collision strategy — replaces the old
    pure sequence-number format for NEW employees only. Exercises
    EmployeeCodeSettings.generate_employee_id() directly with the exact
    argument shapes each of the three real call sites passes (a string date
    from EmployeeListCreateView.post(), a date object from
    OnboardingApprovalView/EmployeeBulkImportView), since all three already
    funnel through this one shared method with no call-site-specific logic.
    """

    def setUp(self):
        from apps.accounts.models import EmployeeCodeSettings
        EmployeeCodeSettings.objects.update_or_create(
            pk=1, defaults={'prefix': 'RSS', 'padding': 5, 'next_sequence': 1},
        )
        role = make_role('employee_codegen_test')
        self.existing = make_user(
            'existing@test.com', role=role, employee_id='RSS00001', full_name='Pre Existing',
        )

    def test_ddmm_and_initials_two_word_name(self):
        from apps.accounts.models import EmployeeCodeSettings
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Teerdaveni', last_name='Gedela', date_of_joining=date(2026, 8, 3),
        )
        self.assertEqual(emp_id, 'RSS0308TG')

    def test_date_of_joining_passed_as_string_matches_date_object(self):
        # EmployeeListCreateView.post() passes date_of_joining as a raw
        # 'YYYY-MM-DD' string (pre-validated via strptime), unlike the other
        # two call sites which already have a real date object.
        from apps.accounts.models import EmployeeCodeSettings
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Ravi', last_name='Kumar', date_of_joining='2026-09-15',
        )
        self.assertEqual(emp_id, 'RSS1509RK')

    def test_date_of_joining_defaults_to_today_when_missing(self):
        from apps.accounts.models import EmployeeCodeSettings
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='No', last_name='Date', date_of_joining=None,
        )
        self.assertEqual(emp_id, f'RSS{date.today().strftime("%d%m")}ND')

    def test_single_word_name_repeats_first_initial(self):
        from apps.accounts.models import EmployeeCodeSettings
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Madonna', last_name='', date_of_joining=date(2026, 1, 20),
        )
        self.assertEqual(emp_id, 'RSS2001MM')

    def test_both_names_blank_falls_back_to_xx(self):
        from apps.accounts.models import EmployeeCodeSettings
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='', last_name='', date_of_joining=date(2026, 1, 20),
        )
        self.assertEqual(emp_id, 'RSS2001XX')

    def test_multi_word_onboarding_approval_style_split(self):
        # Mirrors OnboardingApprovalView.post()'s exact existing split:
        # full_name.split(' ', 1) -> first_name = first word, last_name =
        # everything after. Only the first letter of each is used, same
        # rule as every other call site — not re-parsed into a "real"
        # surname, matching "preserve existing name fields" from the brief.
        from apps.accounts.models import EmployeeCodeSettings
        full_name = 'Mary Jane Smith'
        parts = full_name.split(' ', 1)
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '',
            date_of_joining=date(2026, 4, 12),
        )
        self.assertEqual(emp_id, 'RSS1204MJ')  # 'J' from "Jane Smith", not "Smith"

    def test_prefix_is_configurable(self):
        from apps.accounts.models import EmployeeCodeSettings
        EmployeeCodeSettings.objects.filter(pk=1).update(prefix='ACM')
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Ravi', last_name='Kumar', date_of_joining=date(2026, 9, 15),
        )
        self.assertEqual(emp_id, 'ACM1509RK')

    def test_next_sequence_is_not_incremented(self):
        from apps.accounts.models import EmployeeCodeSettings
        before = EmployeeCodeSettings.objects.get(pk=1).next_sequence
        EmployeeCodeSettings.generate_employee_id(
            first_name='Ravi', last_name='Kumar', date_of_joining=date(2026, 9, 15),
        )
        after = EmployeeCodeSettings.objects.get(pk=1).next_sequence
        self.assertEqual(before, after)

    def test_collision_appends_suffix(self):
        from apps.accounts.models import EmployeeCodeSettings
        employee_role = make_role('employee_codegen_collision')
        make_user(
            'ravi1@test.com', role=employee_role, employee_id='RSS0308RK', full_name='Ravi Kumar',
        )
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Rahul', last_name='Kumar', date_of_joining=date(2026, 8, 3),
        )
        self.assertEqual(emp_id, 'RSS0308RK2')

    def test_collision_increments_suffix_past_first_duplicate(self):
        from apps.accounts.models import EmployeeCodeSettings
        employee_role = make_role('employee_codegen_collision2')
        make_user('a@test.com', role=employee_role, employee_id='RSS0308RK', full_name='A')
        make_user('b@test.com', role=employee_role, employee_id='RSS0308RK2', full_name='B')
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Rahul', last_name='Kumar', date_of_joining=date(2026, 8, 3),
        )
        self.assertEqual(emp_id, 'RSS0308RK3')

    def test_no_collision_when_initials_differ(self):
        from apps.accounts.models import EmployeeCodeSettings
        employee_role = make_role('employee_codegen_no_collision')
        make_user(
            'ravi2@test.com', role=employee_role, employee_id='RSS0308RK', full_name='Ravi Kumar',
        )
        emp_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Anita', last_name='Shah', date_of_joining=date(2026, 8, 3),
        )
        self.assertEqual(emp_id, 'RSS0308AS')

    def test_existing_employee_id_unaffected_by_new_generation(self):
        from apps.accounts.models import EmployeeCodeSettings
        EmployeeCodeSettings.generate_employee_id(
            first_name='Ravi', last_name='Kumar', date_of_joining=date(2026, 9, 15),
        )
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.employee_id, 'RSS00001')


class EmployeeIdConversionDryRunTests(TestCase):
    """dry_run_employee_id_conversion — read-only preview command. Verifies
    the mapping/collision/ordering logic and, just as importantly, that it
    makes zero writes (every employee_id is byte-for-byte unchanged after
    running it)."""

    def setUp(self):
        from apps.accounts.models import EmployeeCodeSettings
        EmployeeCodeSettings.objects.update_or_create(
            pk=1, defaults={'prefix': 'RSS', 'padding': 5, 'next_sequence': 1},
        )
        role = make_role('employee_dryrun_test')
        # Deliberately created in this order: Ravi, Rahul, Rohit all share
        # date_of_joining + "R_" initials -> a 3-way collision group, whose
        # order should resolve by creation order (date_joined) since their
        # date_of_joining ties exactly.
        self.teerdaveni = make_user(
            'teerdaveni@test.com', role=role, employee_id='DEM00025',
            full_name='Teerdaveni Gedela', date_of_joining=date(2026, 8, 3),
        )
        self.ravi = make_user(
            'ravi@test.com', role=role, employee_id='DEM00030',
            full_name='Ravi Kumar', date_of_joining=date(2026, 9, 15),
        )
        self.rahul = make_user(
            'rahul@test.com', role=role, employee_id='DEM00031',
            full_name='Rahul Kumar', date_of_joining=date(2026, 9, 15),
        )
        self.rohit = make_user(
            'rohit@test.com', role=role, employee_id='DEM00032',
            full_name='Rohit Khan', date_of_joining=date(2026, 9, 15), is_active=False,
        )
        self.no_doj = make_user(
            'nodoj@test.com', role=role, employee_id='DEM00040',
            full_name='No Date Person', date_of_joining=None,
        )
        self.no_name = make_user(
            'noname@test.com', role=role, employee_id='DEM00041',
            full_name='', date_of_joining=date(2026, 1, 1),
        )

    def _run(self):
        # Calls handle_tenant() directly rather than going through
        # TenantCommand.handle() via call_command() — that wrapper closes
        # the DB connection in its finally block when it's done, which is
        # correct for a real one-shot `manage.py ...` process but destroys
        # the connection this TestCase's own transaction still needs for
        # every assertion/test after it. The test runner already keeps the
        # connection pointed at the TESTCO tenant schema for the whole
        # test, so handle_tenant() sees the same data either way.
        import io
        from apps.accounts.management.commands.dry_run_employee_id_conversion import Command
        from apps.tenants.models import Client
        from config.test_runner import TEST_COMPANY_CODE
        client = Client.objects.get(company_code=TEST_COMPANY_CODE)
        out = io.StringIO()
        Command(stdout=out).handle_tenant(client)
        return out.getvalue()

    def test_makes_zero_database_writes(self):
        before = {
            u.pk: u.employee_id for u in
            [self.teerdaveni, self.ravi, self.rahul, self.rohit, self.no_doj, self.no_name]
        }
        self._run()
        for u in [self.teerdaveni, self.ravi, self.rahul, self.rohit, self.no_doj, self.no_name]:
            u.refresh_from_db()
            self.assertEqual(u.employee_id, before[u.pk])

    def test_report_contains_expected_mapping(self):
        report = self._run()
        self.assertIn('DEM00025  ->  RSS0308TG', report)
        self.assertIn('No collision', report)

    def test_report_detects_three_way_collision_in_creation_order(self):
        report = self._run()
        # Ravi created first -> bare id; Rahul second -> suffix 2;
        # Rohit (inactive) third -> suffix 3 — proves inactive employees
        # are included in collision detection, not skipped.
        self.assertIn('DEM00030  ->  RSS1509RK', report)
        self.assertIn('DEM00031  ->  RSS1509RK2', report)
        self.assertIn('DEM00032  ->  RSS1509RK3', report)
        self.assertIn('[INACTIVE]', report)
        self.assertIn('Collision group of 3', report)

    def test_report_flags_missing_date_of_joining(self):
        report = self._run()
        self.assertIn('DEM00040', report)
        self.assertIn('missing date of joining', report)

    def test_report_flags_missing_name(self):
        report = self._run()
        self.assertIn('DEM00041', report)
        self.assertIn('missing/blank name', report)

    def test_summary_counts(self):
        # Computed relative to whatever else already exists in this tenant
        # schema (e.g. fixtures left behind by other test classes sharing
        # this --keepdb database) rather than a hardcoded absolute count,
        # so this stays correct regardless of what else is in the schema —
        # the 6 users this test's own setUp created are what's actually
        # being verified.
        other_existing = User.objects.exclude(employee_id='').exclude(
            pk__in=[
                self.teerdaveni.pk, self.ravi.pk, self.rahul.pk,
                self.rohit.pk, self.no_doj.pk, self.no_name.pk,
            ],
        ).count()
        report = self._run()
        self.assertIn(f'Total employee rows considered: {other_existing + 6}', report)
        self.assertIn('Total collision groups (2+ employees sharing DDMM+initials): 1', report)
        self.assertIn('Total employees that would receive a numeric suffix: 2', report)


class EmployeeDetailsFieldProtectionTests(TestCase):
    """Employee ID/Name immutability, DOB/Mobile/Email edit + validation, and
    System Admin/HR Admin/Branch Admin scoping on EmployeeDetailView.put() —
    covers the Employee Details business rule: Employee ID and Employee Name
    stay permanently read-only; Date of Birth, Mobile Number, and Email
    become editable for every role already authorized via employees.edit.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        system_admin_role = make_role(
            'system_admin', permission_codenames=['employees.view', 'employees.edit', 'settings.edit'],
        )
        self.system_admin = make_user(
            'sysadmin@test.com', role=system_admin_role, password='TestPass123!',
            employee_id='EMPSYS001', full_name='Sys Admin', branch='Mumbai HQ',
        )

        hr_admin_role = make_role('hr_admin', permission_codenames=['employees.view', 'employees.edit'])
        self.hr_admin = make_user(
            'hradmin@test.com', role=hr_admin_role, password='TestPass123!',
            employee_id='EMPHRA001', full_name='HR Admin', branch='Mumbai HQ',
        )

        branch_admin_role = make_role('branch_admin', permission_codenames=['employees.view', 'employees.edit'])
        self.branch_admin = make_user(
            'branchadmin@test.com', role=branch_admin_role, password='TestPass123!',
            employee_id='EMPBRA001', full_name='Branch Admin', branch='Mumbai HQ',
        )

        no_perm_role = make_role('no_perm_role')
        self.no_perm_user = make_user(
            'noperm@test.com', role=no_perm_role, password='TestPass123!',
            employee_id='EMPNOP001', full_name='No Perm', branch='Mumbai HQ',
        )

        employee_role = make_role('employee')
        self.employee = make_user(
            'target@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPTGT001', full_name='Target Employee', branch='Mumbai HQ',
            phone='9876500001', onboarding_status=User.ONBOARDING_COMPLETE,
        )
        self.other_branch_employee = make_user(
            'otherbranch@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPOTB001', full_name='Other Branch Employee', branch='Delhi HQ',
        )
        self.someone_else = make_user(
            'someoneelse@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPSE0001', full_name='Someone Else', branch='Mumbai HQ',
        )

    def _url(self, employee_id: str | None = None):
        return reverse('employee-detail', kwargs={'employee_id': employee_id or self.employee.employee_id})

    # ── Employee ID / Employee Name immutability ───────────────────────────

    def test_employee_id_cannot_be_changed(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'employee_id': 'HACKED001'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Employee ID cannot be modified', resp.data['message'])

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, 'EMPTGT001')

    def test_employee_id_echoed_back_unchanged_is_not_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(
            self._url(), {'employee_id': self.employee.employee_id, 'phone': '9876500002'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, 'EMPTGT001')
        self.assertEqual(self.employee.phone, '9876500002')

    def test_full_name_cannot_be_changed(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'full_name': 'Hacked Name'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Employee name cannot be modified', resp.data['message'])

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'Target Employee')

    def test_full_name_immutable_regardless_of_onboarding_status(self):
        # Previously full_name was only locked once onboarding was complete —
        # confirm a not-yet-onboarded employee is protected too.
        pending_role = make_role('employee_pending', permission_codenames=[])
        pending_employee = make_user(
            'pending@test.com', role=pending_role, password='TestPass123!',
            employee_id='EMPPND001', full_name='Pending Employee', branch='Mumbai HQ',
            onboarding_status=User.ONBOARDING_PENDING,
        )
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(pending_employee.employee_id), {'full_name': 'New Name'}, format='json')
        self.assertEqual(resp.status_code, 400)
        pending_employee.refresh_from_db()
        self.assertEqual(pending_employee.full_name, 'Pending Employee')

    def test_full_name_echoed_back_unchanged_is_not_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(
            self._url(), {'full_name': self.employee.full_name, 'phone': '9876500003'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    # ── Date of Birth ───────────────────────────────────────────────────────

    def test_valid_date_of_birth_accepted(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        dob = (date.today() - timedelta(days=365 * 30)).isoformat()
        resp = self.client.put(self._url(), {'date_of_birth': dob}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(str(self.employee.profile.date_of_birth), dob)

    def test_future_date_of_birth_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        dob = (date.today() + timedelta(days=1)).isoformat()
        resp = self.client.put(self._url(), {'date_of_birth': dob}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('past', resp.data['message'])

    def test_under_18_date_of_birth_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        dob = (date.today() - timedelta(days=365 * 10)).isoformat()
        resp = self.client.put(self._url(), {'date_of_birth': dob}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('18', resp.data['message'])

    def test_over_80_date_of_birth_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        dob = (date.today() - timedelta(days=365 * 85)).isoformat()
        resp = self.client.put(self._url(), {'date_of_birth': dob}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_malformed_date_of_birth_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'date_of_birth': '30-02-2000'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('YYYY-MM-DD', resp.data['message'])

    # ── Mobile Number ───────────────────────────────────────────────────────

    def test_valid_mobile_number_accepted_regardless_of_onboarding_status(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'phone': '+91 98765 43210'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '+91 98765 43210')

    def test_invalid_mobile_number_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'phone': 'not-a-phone-number!!'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9876500001')

    def test_blank_mobile_number_allowed(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'phone': ''}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '')

    # ── Email ────────────────────────────────────────────────────────────────

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_valid_email_change_accepted_and_notifications_sent(self, mock_send):
        from apps.accounts.models import SMTPSettings
        SMTPSettings.objects.create(
            name='Test SMTP', host='smtp.example.com', port=587,
            username='test@example.com', password='irrelevant',
            from_email='test@example.com', is_active=True,
        )
        old_email = self.employee.email
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'email': 'new-address@test.com'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'new-address@test.com')
        self.assertTrue(
            AuditLog.objects.filter(
                action='employee_updated', object_id=str(self.employee.id),
                changes__email__from=old_email, changes__email__to='new-address@test.com',
            ).exists()
        )
        # Confirmation-to-new + security-alert-to-old, same as
        # CompanySystemAdminView's equivalent email-change action.
        self.assertEqual(mock_send.call_count, 2)

        # The new email must actually be usable to log in with — proves this
        # isn't a cosmetic display-only change and login isn't broken.
        new_client = APIClient()
        _login(new_client, 'new-address@test.com', password='TestPass123!')

    def test_invalid_email_format_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'email': 'not-an-email'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'target@test.com')

    def test_email_already_in_use_by_another_account_rejected(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'email': 'someoneelse@test.com'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'target@test.com')

    def test_email_unchanged_value_is_a_no_op(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        resp = self.client.put(
            self._url(), {'email': self.employee.email, 'phone': '9123456785'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            AuditLog.objects.filter(
                action='employee_updated', object_id=str(self.employee.id), changes__has_key='email',
            ).exists()
        )

    # ── Combined edit (DOB + Mobile + Email together) ──────────────────────

    def test_hr_admin_can_update_dob_mobile_and_email_together(self):
        _login(self.client, 'hradmin@test.com', password='TestPass123!')
        dob = (date.today() - timedelta(days=365 * 25)).isoformat()
        resp = self.client.put(self._url(), {
            'date_of_birth': dob, 'phone': '9123456780', 'email': 'combined@test.com',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.employee.refresh_from_db()
        self.assertEqual(str(self.employee.profile.date_of_birth), dob)
        self.assertEqual(self.employee.phone, '9123456780')
        self.assertEqual(self.employee.email, 'combined@test.com')

    # ── Permissions / scoping ───────────────────────────────────────────────

    def test_unauthorized_role_denied(self):
        _login(self.client, 'noperm@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'phone': '9123456781'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9876500001')

    def test_system_admin_can_edit_employee_in_any_branch(self):
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.put(
            self._url(self.other_branch_employee.employee_id), {'phone': '9123456782'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_branch_admin_can_edit_employee_within_own_branch(self):
        _login(self.client, 'branchadmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url(), {'phone': '9123456783'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_branch_admin_cannot_edit_employee_outside_own_branch(self):
        _login(self.client, 'branchadmin@test.com', password='TestPass123!')
        resp = self.client.put(
            self._url(self.other_branch_employee.employee_id), {'phone': '9123456784'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)
        self.other_branch_employee.refresh_from_db()
        self.assertEqual(self.other_branch_employee.phone, '')

    def test_branch_admin_cannot_smuggle_employee_id_change_alongside_other_fields(self):
        _login(self.client, 'branchadmin@test.com', password='TestPass123!')
        resp = self.client.put(
            self._url(), {'employee_id': 'BYPASS001', 'phone': '9123456786'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, 'EMPTGT001')
        self.assertEqual(self.employee.phone, '9876500001')


class EmployeeDetailsDateOfJoiningEditTests(TestCase):
    """Date of Joining is now editable through EmployeeDetailView.put() for
    any authorized editor (employees.edit + branch scope), including after
    onboarding is complete — previously locked post-onboarding the same way
    full_name/phone used to be. Reuses the exact fixtures/pattern from
    EmployeeDetailsFieldProtectionTests (self.employee is already
    ONBOARDING_COMPLETE, branch='Mumbai HQ' — the state that used to trigger
    the 409 lock)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        branch_admin_role = make_role(
            'branch_admin_doj_test', permission_codenames=['employees.view', 'employees.edit'],
        )
        self.branch_admin = make_user(
            'branchadmin.doj@test.com', role=branch_admin_role, password='TestPass123!',
            employee_id='EMPBRD001', full_name='Branch Admin', branch='Mumbai HQ',
        )

        employee_role = make_role('employee_doj_test')
        self.employee = make_user(
            'target.doj@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPTGD001', full_name='Target Employee', branch='Mumbai HQ',
            date_of_joining='2024-01-10', onboarding_status=User.ONBOARDING_COMPLETE,
        )
        self.other_branch_employee = make_user(
            'otherbranch.doj@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPOBD001', full_name='Other Branch Employee', branch='Delhi HQ',
            date_of_joining='2024-01-10', onboarding_status=User.ONBOARDING_COMPLETE,
        )
        _login(self.client, 'branchadmin.doj@test.com', password='TestPass123!')

    def _url(self, employee):
        return reverse('employee-detail', kwargs={'employee_id': employee.employee_id})

    def test_branch_admin_can_edit_doj_for_employee_in_own_branch(self):
        resp = self.client.put(self._url(self.employee), {'date_of_joining': '2024-03-15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(str(self.employee.date_of_joining), '2024-03-15')

    def test_doj_change_persisted_and_returned_by_get(self):
        put_resp = self.client.put(self._url(self.employee), {'date_of_joining': '2024-06-01'}, format='json')
        self.assertEqual(put_resp.status_code, 200, put_resp.data)

        get_resp = self.client.get(self._url(self.employee))
        self.assertEqual(get_resp.status_code, 200, get_resp.data)
        self.assertEqual(get_resp.data['data']['date_of_joining'], '2024-06-01')

    def test_malformed_doj_rejected(self):
        resp = self.client.put(self._url(self.employee), {'date_of_joining': '15-03-2024'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(str(self.employee.date_of_joining), '2024-01-10')

    def test_branch_admin_cannot_edit_doj_outside_own_branch(self):
        resp = self.client.put(
            self._url(self.other_branch_employee), {'date_of_joining': '2024-03-15'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)
        self.other_branch_employee.refresh_from_db()
        self.assertEqual(str(self.other_branch_employee.date_of_joining), '2024-01-10')

    def test_employee_id_unchanged_after_doj_edit(self):
        resp = self.client.put(self._url(self.employee), {'date_of_joining': '2024-03-15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_id, 'EMPTGD001')

    def test_employee_name_unchanged_after_doj_edit(self):
        resp = self.client.put(self._url(self.employee), {'date_of_joining': '2024-03-15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'Target Employee')

    def test_dob_mobile_email_still_editable_alongside_doj(self):
        resp = self.client.put(self._url(self.employee), {
            'date_of_joining': '2024-03-15', 'date_of_birth': '1992-07-20',
            'phone': '9876543210', 'email': 'newtarget.doj@test.com',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(str(self.employee.date_of_joining), '2024-03-15')
        self.assertEqual(str(self.employee.profile.date_of_birth), '1992-07-20')
        self.assertEqual(self.employee.phone, '9876543210')
        self.assertEqual(self.employee.email, 'newtarget.doj@test.com')

    def test_doj_change_recorded_in_audit_log(self):
        resp = self.client.put(self._url(self.employee), {'date_of_joining': '2024-03-15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entry = AuditLog.objects.filter(
            action='employee_updated', object_id=str(self.employee.id),
        ).order_by('-created_at').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.changes.get('date_of_joining'), {'from': '2024-01-10', 'to': '2024-03-15'})

    def test_unauthorized_user_cannot_edit_doj(self):
        no_perm_role = make_role('no_perm_doj_test')
        make_user(
            'noperm.doj@test.com', role=no_perm_role, password='TestPass123!',
            employee_id='EMPNPD001', full_name='No Perm', branch='Mumbai HQ',
        )
        _login(self.client, 'noperm.doj@test.com', password='TestPass123!')
        resp = self.client.put(self._url(self.employee), {'date_of_joining': '2024-03-15'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.employee.refresh_from_db()
        self.assertEqual(str(self.employee.date_of_joining), '2024-01-10')


class EmployeeApprovalMatrixBranchScopeTests(TestCase):
    """EmployeeApprovalMatrixView checked employees.view/employees.edit but
    never branch-scoped the target employee_id — unlike every comparable
    endpoint in this file (EmployeeDetailView, the DOJ edit tests above).
    Since Branch Admin's seeded role already holds employees.view/edit
    (migration 0052), this meant a Branch Admin could read/write the
    Approval Matrix override for an employee in ANY branch, not just their
    own. Fixed by adding the same _employee_out_of_branch_scope() check
    EmployeeDetailView already uses, to get()/_upsert()/delete() alike.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        sysadmin_role = make_role('sysadmin_approval_matrix_test', permission_codenames=['settings.edit'])
        self.sysadmin = make_user(
            'sysadmin.apm@test.com', role=sysadmin_role, password='TestPass123!',
            employee_id='EMPSAM001', full_name='Sys Admin', branch='Mumbai HQ',
        )

        branch_admin_role = make_role(
            'branch_admin_approval_matrix_test', permission_codenames=['employees.view', 'employees.edit'],
        )
        self.branch_admin = make_user(
            'branchadmin.apm@test.com', role=branch_admin_role, password='TestPass123!',
            employee_id='EMPBAM001', full_name='Branch Admin', branch='Mumbai HQ',
        )

        employee_role = make_role('employee_approval_matrix_test')
        self.employee = make_user(
            'target.apm@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPTAM001', full_name='Target Employee', branch='Mumbai HQ',
        )
        self.other_branch_employee = make_user(
            'otherbranch.apm@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPOAM001', full_name='Other Branch Employee', branch='Delhi HQ',
        )
        self.approver = make_user(
            'approver.apm@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPAPM001', full_name='Approver Person', branch='Mumbai HQ',
        )

    def _url(self, employee):
        return reverse('employee-approval-matrix', kwargs={'employee_id': employee.employee_id})

    # ── Branch Admin + own-branch employee: must keep working ──────────────

    def test_branch_admin_can_view_own_branch_employee_matrix(self):
        _login(self.client, 'branchadmin.apm@test.com', password='TestPass123!')
        resp = self.client.get(self._url(self.employee))
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_branch_admin_can_update_own_branch_employee_matrix(self):
        _login(self.client, 'branchadmin.apm@test.com', password='TestPass123!')
        resp = self.client.put(self._url(self.employee), {
            'workflow_type': 'leave', 'l1_override_id': self.approver.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            EmployeeApprovalOverride.objects.filter(employee=self.employee, workflow_type='leave').exists()
        )

    def test_branch_admin_can_delete_own_branch_employee_override(self):
        EmployeeApprovalOverride.objects.create(
            employee=self.employee, workflow_type='leave', l1_override=self.approver,
        )
        _login(self.client, 'branchadmin.apm@test.com', password='TestPass123!')
        resp = self.client.delete(self._url(self.employee) + '?workflow_type=leave')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            EmployeeApprovalOverride.objects.filter(employee=self.employee, workflow_type='leave').exists()
        )

    # ── Branch Admin + different-branch employee: must now be denied ───────

    def test_branch_admin_cannot_view_other_branch_employee_matrix(self):
        _login(self.client, 'branchadmin.apm@test.com', password='TestPass123!')
        resp = self.client.get(self._url(self.other_branch_employee))
        self.assertEqual(resp.status_code, 404)

    def test_branch_admin_cannot_update_other_branch_employee_matrix(self):
        _login(self.client, 'branchadmin.apm@test.com', password='TestPass123!')
        resp = self.client.put(self._url(self.other_branch_employee), {
            'workflow_type': 'leave', 'l1_override_id': self.approver.id,
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            EmployeeApprovalOverride.objects.filter(
                employee=self.other_branch_employee, workflow_type='leave',
            ).exists()
        )

    def test_branch_admin_cannot_delete_other_branch_employee_override(self):
        EmployeeApprovalOverride.objects.create(
            employee=self.other_branch_employee, workflow_type='leave', l1_override=self.approver,
        )
        _login(self.client, 'branchadmin.apm@test.com', password='TestPass123!')
        resp = self.client.delete(self._url(self.other_branch_employee) + '?workflow_type=leave')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(
            EmployeeApprovalOverride.objects.filter(
                employee=self.other_branch_employee, workflow_type='leave',
            ).exists()
        )

    # ── System Admin: unchanged, still works across every branch ───────────

    def test_system_admin_can_view_any_branch_employee_matrix(self):
        _login(self.client, 'sysadmin.apm@test.com', password='TestPass123!')
        resp = self.client.get(self._url(self.other_branch_employee))
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_system_admin_can_update_any_branch_employee_matrix(self):
        _login(self.client, 'sysadmin.apm@test.com', password='TestPass123!')
        resp = self.client.put(self._url(self.other_branch_employee), {
            'workflow_type': 'leave', 'l1_override_id': self.approver.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    # ── Existing employees.view/edit authorization: unchanged ──────────────

    def test_unauthorized_user_cannot_view_matrix(self):
        no_perm_role = make_role('no_perm_approval_matrix_test')
        make_user(
            'noperm.apm@test.com', role=no_perm_role, password='TestPass123!',
            employee_id='EMPNPM001', full_name='No Perm', branch='Mumbai HQ',
        )
        _login(self.client, 'noperm.apm@test.com', password='TestPass123!')
        resp = self.client.get(self._url(self.employee))
        self.assertEqual(resp.status_code, 403)

    def test_unauthorized_user_cannot_update_matrix(self):
        no_perm_role = make_role('no_perm_approval_matrix_edit_test')
        make_user(
            'noperm2.apm@test.com', role=no_perm_role, password='TestPass123!',
            employee_id='EMPNPM002', full_name='No Perm Edit', branch='Mumbai HQ',
        )
        _login(self.client, 'noperm2.apm@test.com', password='TestPass123!')
        resp = self.client.put(self._url(self.employee), {
            'workflow_type': 'leave', 'l1_override_id': self.approver.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)


class EmployeeReportingManagerBranchScopeTests(TestCase):
    """EmployeeReportingManagerView.patch() checked employees.edit and
    looked up the employee via _get_employee() but never called
    _employee_out_of_branch_scope() — the same gap already found and fixed
    in EmployeeApprovalMatrixView. Since Branch Admin's seeded role already
    holds employees.edit, this meant a Branch Admin could set the reporting
    manager for an employee in ANY branch via direct API call. Fixed by
    adding the same helper, same pattern as EmployeeDetailView.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        sysadmin_role = make_role('sysadmin_reporting_mgr_test', permission_codenames=['settings.edit'])
        self.sysadmin = make_user(
            'sysadmin.rm@test.com', role=sysadmin_role, password='TestPass123!',
            employee_id='EMPSRM001', full_name='Sys Admin', branch='Mumbai HQ',
        )

        branch_admin_role = make_role(
            'branch_admin_reporting_mgr_test', permission_codenames=['employees.view', 'employees.edit'],
        )
        self.branch_admin = make_user(
            'branchadmin.rm@test.com', role=branch_admin_role, password='TestPass123!',
            employee_id='EMPBRM001', full_name='Branch Admin', branch='Mumbai HQ',
        )

        employee_role = make_role('employee_reporting_mgr_test')
        self.employee = make_user(
            'target.rm@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPTRM001', full_name='Target Employee', branch='Mumbai HQ',
        )
        self.other_branch_employee = make_user(
            'otherbranch.rm@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPORM001', full_name='Other Branch Employee', branch='Delhi HQ',
        )
        self.manager = make_user(
            'manager.rm@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPMRM001', full_name='Manager Person', branch='Mumbai HQ',
        )

    def _url(self, employee):
        return reverse('employee-reporting-manager', kwargs={'employee_id': employee.employee_id})

    def test_branch_admin_can_set_reporting_manager_for_own_branch_employee(self):
        _login(self.client, 'branchadmin.rm@test.com', password='TestPass123!')
        resp = self.client.patch(
            self._url(self.employee), {'reporting_manager_id': str(self.manager.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_manager_id, self.manager.id)

    def test_branch_admin_cannot_set_reporting_manager_for_other_branch_employee(self):
        _login(self.client, 'branchadmin.rm@test.com', password='TestPass123!')
        resp = self.client.patch(
            self._url(self.other_branch_employee), {'reporting_manager_id': str(self.manager.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 404)
        self.other_branch_employee.refresh_from_db()
        self.assertIsNone(self.other_branch_employee.reporting_manager_id)

    def test_system_admin_can_set_reporting_manager_for_other_branch_employee(self):
        _login(self.client, 'sysadmin.rm@test.com', password='TestPass123!')
        resp = self.client.patch(
            self._url(self.other_branch_employee), {'reporting_manager_id': str(self.manager.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.other_branch_employee.refresh_from_db()
        self.assertEqual(self.other_branch_employee.reporting_manager_id, self.manager.id)

    def test_unauthorized_user_cannot_set_reporting_manager(self):
        no_perm_role = make_role('no_perm_reporting_mgr_test')
        make_user(
            'noperm.rm@test.com', role=no_perm_role, password='TestPass123!',
            employee_id='EMPNRM001', full_name='No Perm', branch='Mumbai HQ',
        )
        _login(self.client, 'noperm.rm@test.com', password='TestPass123!')
        resp = self.client.patch(
            self._url(self.employee), {'reporting_manager_id': str(self.manager.id)}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.reporting_manager_id)


class ManagerReportingManagerEditTests(TestCase):
    """Regression: EmployeeDetailView.put() rejected ANY edit to a Manager
    (even an unrelated field like DOB) with "Managers do not have a
    reporting manager." The frontend always includes reporting_manager_id
    in its PUT payload (null when empty, same as every other field it
    sends) — the backend's old check fired on the key merely being
    PRESENT, not on an actual value being submitted, unlike the equivalent
    check in EmployeeListCreateView.post() which only checks truthy values.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_admin_mgr_test', permission_codenames=['employees.view', 'employees.edit'])
        self.hr = make_user(
            'hrmgrtest@test.com', role=hr_role, password='TestPass123!',
            employee_id='EMPHRM001', full_name='HR Tester', branch='Mumbai HQ',
        )
        manager_role = make_role('manager_reporting_test', can_manage_team=True)
        self.other_manager = make_user(
            'othermanager@test.com', role=manager_role, password='TestPass123!',
            employee_id='EMPMGR002', full_name='Other Manager', branch='Mumbai HQ',
        )
        self.manager = make_user(
            'manager@test.com', role=manager_role, password='TestPass123!',
            employee_id='EMPMGR001', full_name='Gangadhara Reddy', branch='Mumbai HQ',
            reporting_manager=None,
        )
        employee_role = make_role('employee_reporting_test')
        self.employee = make_user(
            'emp@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPEMP001', full_name='Regular Employee', branch='Mumbai HQ',
            reporting_manager=self.other_manager,
        )
        _login(self.client, 'hrmgrtest@test.com', password='TestPass123!')

    def _url(self, employee):
        return reverse('employee-detail', kwargs={'employee_id': employee.employee_id})

    def test_manager_with_empty_reporting_manager_can_save_dob(self):
        resp = self.client.put(self._url(self.manager), {
            'reporting_manager_id': None, 'date_of_birth': '1990-05-15',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual(str(self.manager.profile.date_of_birth), '1990-05-15')
        self.assertIsNone(self.manager.reporting_manager)

    def test_manager_with_empty_reporting_manager_can_save_phone_email_address(self):
        resp = self.client.put(self._url(self.manager), {
            'reporting_manager_id': None, 'phone': '9988776655', 'email': 'newmanager@test.com',
            'current_address': 'Kondapur, Hyderabad',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.phone, '9988776655')
        self.assertEqual(self.manager.email, 'newmanager@test.com')
        self.assertIsNone(self.manager.reporting_manager)

    def test_manager_cannot_be_assigned_a_reporting_manager(self):
        resp = self.client.put(self._url(self.manager), {
            'reporting_manager_id': str(self.other_manager.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Managers do not have a reporting manager', resp.data['message'])
        self.manager.refresh_from_db()
        self.assertIsNone(self.manager.reporting_manager)

    def test_manager_reporting_manager_id_key_omitted_entirely_still_saves(self):
        resp = self.client.put(self._url(self.manager), {'phone': '9000000000'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.phone, '9000000000')

    def test_non_manager_with_valid_reporting_manager_unaffected(self):
        # Existing behavior for a regular employee must be unchanged: a real
        # reporting_manager_id still gets applied normally.
        new_manager = make_user(
            'newmgr@test.com',
            role=make_role('manager_reporting_test2', can_manage_team=True),
            employee_id='EMPMGR003', full_name='New Manager', branch='Mumbai HQ',
        )
        resp = self.client.put(self._url(self.employee), {
            'reporting_manager_id': str(new_manager.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_manager_id, new_manager.pk)

    def test_non_manager_clearing_reporting_manager_still_works(self):
        resp = self.client.put(self._url(self.employee), {'reporting_manager_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.reporting_manager)

    def test_non_manager_self_assignment_still_rejected(self):
        resp = self.client.put(self._url(self.employee), {
            'reporting_manager_id': str(self.employee.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cannot be their own reporting manager', resp.data['message'])


class ManagerCooReportingTests(TestCase):
    """A Manager (role.can_manage_team=True) is blocked from having any
    Reporting Manager in several places — deliberate, Managers ARE the
    reporting manager for others. One narrow exception now exists: a
    Manager may report to the Chief Operating Officer specifically — an
    existing, pre-created production role (name='chief_operating_officer_coo',
    can_manage_team=False) — matched via _is_coo() on that immutable role
    slug. Never relaxed to "any Manager" or "any can_manage_team role".
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        sysadmin_role = make_role('sysadmin_coo_test', permission_codenames=['settings.edit'])
        self.sysadmin = make_user(
            'sysadmin.coo@test.com', role=sysadmin_role, password='TestPass123!',
            employee_id='EMPSCO001', full_name='Sys Admin', branch='Mumbai HQ',
        )

        branch_admin_role = make_role(
            'branch_admin_coo_test', permission_codenames=['employees.view', 'employees.edit'],
        )
        self.branch_admin = make_user(
            'branchadmin.coo@test.com', role=branch_admin_role, password='TestPass123!',
            employee_id='EMPBCO001', full_name='Branch Admin', branch='Mumbai HQ',
        )

        # Mirrors the real production role exactly: can_manage_team=False.
        coo_role = make_role(COO_ROLE_NAME, can_manage_team=False)
        self.coo = make_user(
            'coo@test.com', role=coo_role, password='TestPass123!',
            employee_id='EMPCOO001', full_name='Chief Operating Officer', branch='Delhi HQ',
        )

        manager_role = make_role('manager_coo_test', can_manage_team=True)
        self.manager = make_user(
            'manager.coo@test.com', role=manager_role, password='TestPass123!',
            employee_id='EMPMCO001', full_name='Branch Manager', branch='Mumbai HQ',
        )
        self.other_branch_manager = make_user(
            'othermanager.coo@test.com', role=manager_role, password='TestPass123!',
            employee_id='EMPOMC001', full_name='Other Branch Manager', branch='Delhi HQ',
        )
        self.other_manager = make_user(
            'peer.coo@test.com', role=manager_role, password='TestPass123!',
            employee_id='EMPPMC001', full_name='Peer Manager', branch='Mumbai HQ',
        )

        employee_role = make_role('employee_coo_test')
        self.employee = make_user(
            'employee.coo@test.com', role=employee_role, password='TestPass123!',
            employee_id='EMPECO001', full_name='Regular Employee', branch='Mumbai HQ',
            reporting_manager=self.manager,
        )

    def _detail_url(self, employee):
        return reverse('employee-detail', kwargs={'employee_id': employee.employee_id})

    def _rm_url(self, employee):
        return reverse('employee-reporting-manager', kwargs={'employee_id': employee.employee_id})

    def _matrix_url(self, employee):
        return reverse('employee-approval-matrix', kwargs={'employee_id': employee.employee_id})

    # A — Manager can be assigned COO as Reporting Manager
    def test_manager_can_be_assigned_coo_via_employee_detail(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.put(self._detail_url(self.manager), {
            'reporting_manager_id': str(self.coo.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.reporting_manager_id, self.coo.pk)

    def test_manager_can_be_assigned_coo_via_reporting_manager_endpoint(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.patch(self._rm_url(self.manager), {
            'reporting_manager_id': str(self.coo.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.reporting_manager_id, self.coo.pk)

    # B — Manager cannot be assigned an ordinary Manager as Reporting Manager
    def test_manager_cannot_be_assigned_ordinary_manager(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.put(self._detail_url(self.manager), {
            'reporting_manager_id': str(self.other_manager.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Managers do not have a reporting manager', resp.data['message'])
        self.manager.refresh_from_db()
        self.assertIsNone(self.manager.reporting_manager)

    def test_manager_cannot_be_assigned_ordinary_manager_via_dedicated_endpoint(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.patch(self._rm_url(self.manager), {
            'reporting_manager_id': str(self.other_manager.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.manager.refresh_from_db()
        self.assertIsNone(self.manager.reporting_manager)

    # C — COO appears in the Reporting Manager picker regardless of branch
    def test_coo_appears_in_manager_picker_regardless_of_branch(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.get(reverse('employee-manager-list'), {'branch': 'Mumbai HQ'})
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {row['id'] for row in resp.data['data']}
        self.assertIn(str(self.coo.pk), ids)
        # Existing branch filtering for ordinary managers is untouched —
        # a manager in a different branch must still be excluded.
        self.assertNotIn(str(self.other_branch_manager.pk), ids)

    # D — Manager's employee detail response includes reporting_manager = COO
    def test_manager_detail_response_includes_coo_as_reporting_manager(self):
        self.manager.reporting_manager = self.coo
        self.manager.save(update_fields=['reporting_manager'])
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.get(self._detail_url(self.manager))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('reporting_manager', resp.data['data'])
        self.assertEqual(resp.data['data']['reporting_manager']['id'], self.coo.employee_id)

    # E — Manager Approval Matrix display shows COO, not "Not assigned"
    def test_manager_approval_matrix_displays_coo_as_l1_approver(self):
        self.manager.reporting_manager = self.coo
        self.manager.save(update_fields=['reporting_manager'])
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.get(self._matrix_url(self.manager), {'workflow_type': 'leave'})
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['data']
        self.assertEqual(row['l1_approver_id'], str(self.coo.id))
        self.assertEqual(row['l1_approver_name'], self.coo.full_name)

    # F — real approval resolution for a Manager routes to COO
    def test_manager_real_approval_resolution_routes_to_coo(self):
        self.manager.reporting_manager = self.coo
        self.manager.save(update_fields=['reporting_manager'])
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE,
            defaults={'l1_approver_role': self.manager.role},
        )
        from apps.accounts.services_approval import resolve_approval_chain
        l1, _l2 = resolve_approval_chain(self.manager, ApprovalWorkflowRule.WORKFLOW_LEAVE)
        self.assertEqual(l1, self.coo)

    # G — Branch Admin can configure a Manager in their own branch to report to COO
    def test_branch_admin_can_assign_coo_to_own_branch_manager(self):
        _login(self.client, 'branchadmin.coo@test.com', password='TestPass123!')
        resp = self.client.patch(self._rm_url(self.manager), {
            'reporting_manager_id': str(self.coo.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.reporting_manager_id, self.coo.pk)

    # H — Branch Admin cannot modify a Manager from another branch
    def test_branch_admin_cannot_assign_coo_to_other_branch_manager(self):
        _login(self.client, 'branchadmin.coo@test.com', password='TestPass123!')
        resp = self.client.patch(self._rm_url(self.other_branch_manager), {
            'reporting_manager_id': str(self.coo.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        self.other_branch_manager.refresh_from_db()
        self.assertIsNone(self.other_branch_manager.reporting_manager)

    # I — existing employee -> Manager reporting behavior unchanged
    def test_regular_employee_reporting_manager_unaffected(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.put(self._detail_url(self.employee), {
            'reporting_manager_id': str(self.other_manager.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_manager_id, self.other_manager.pk)

    # J — existing System Admin behavior unchanged (acts across branches freely)
    def test_system_admin_can_assign_coo_across_branches(self):
        _login(self.client, 'sysadmin.coo@test.com', password='TestPass123!')
        resp = self.client.patch(self._rm_url(self.other_branch_manager), {
            'reporting_manager_id': str(self.coo.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.other_branch_manager.refresh_from_db()
        self.assertEqual(self.other_branch_manager.reporting_manager_id, self.coo.pk)


class CompanyEmailWrapperFooterTests(SimpleTestCase):
    """
    Regression test for the Royal HRMS website footer link added to
    _company_email_wrapper() — the single shared wrapper every company-level
    email (onboarding welcome/Branch Admin, onboarding submitted/approved/
    rejected, password reset, OTP, SMTP test, and every other EmailTemplate-
    driven notification across the app) passes through before sending. Pure
    string function, no database needed.
    """

    def test_royalhrms_link_appears_exactly_once_and_existing_content_is_preserved(self):
        from apps.accounts.utils import _company_email_wrapper

        body = "<p>Hi <strong>Test Employee</strong>,</p><p>Your account has been created.</p>"
        old_footer_text = "royalstaffing.in &nbsp;|&nbsp; Surat, Gujarat"
        html = _company_email_wrapper(
            body, "Royal Staffing", "", "royalstaffing.in", "Surat, Gujarat",
        )

        # The new link is present, clickable, and appears exactly once.
        self.assertEqual(html.count('href="https://royalhrms.com"'), 1)
        self.assertIn("Visit Royal HRMS", html)
        self.assertIn("royalhrms.com", html)

        # Nothing about the existing header/body/footer was altered.
        self.assertIn(body, html)
        self.assertIn(old_footer_text, html)
        self.assertIn("Royal Staffing", html)

    def test_wrapper_still_renders_with_no_company_website_or_address(self):
        from apps.accounts.utils import _company_email_wrapper

        # A brand-new company with no website/address configured yet — the
        # existing fallback-to-company-name footer behavior must still work
        # alongside the new, always-present Royal HRMS link.
        html = _company_email_wrapper("<p>Body</p>", "New Co", "", "", "")
        self.assertIn("New Co", html)
        self.assertEqual(html.count('href="https://royalhrms.com"'), 1)


class EmployeeReportingRelationshipPersistenceTests(TestCase):
    """Reporting Manager / Reporting Approver / Branch HR must persist across
    save -> GET (reopen). Covers the Personal-tab PUT, the Approval Matrix's
    reporting-manager PATCH, and the Approval Matrix's Branch HR route.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        editor_role = make_role('rel_persist_editor', permission_codenames=['employees.view', 'employees.edit'])
        self.editor = make_user(
            'rel.editor@test.com', role=editor_role,
            employee_id='EMPRPE001', full_name='Rel Editor', branch='Mumbai HQ',
        )
        self.staff_role = make_role('rel_persist_staff')
        self.manager_a = self._staff('rel.mgr.a@test.com', 'EMPRPM001', 'Manager A')
        self.manager_b = self._staff('rel.mgr.b@test.com', 'EMPRPM002', 'Manager B')
        self.approver_a = self._staff('rel.apr.a@test.com', 'EMPRPA001', 'Approver A')
        self.approver_b = self._staff('rel.apr.b@test.com', 'EMPRPA002', 'Approver B')
        self.hr_a = self._staff('rel.hr.a@test.com', 'EMPRPH001', 'HR A')
        self.hr_b = self._staff('rel.hr.b@test.com', 'EMPRPH002', 'HR B')
        self.employee = make_user(
            'rel.target@test.com', role=self.staff_role, employee_id='EMPRPT001', full_name='Target Employee',
            branch='Mumbai HQ', phone='9000000001',
            reporting_manager=self.manager_a, reporting_approver=self.approver_a, hr=self.hr_a,
        )
        _login(self.client, 'rel.editor@test.com')

    def _staff(self, email, employee_id, full_name, branch='Mumbai HQ'):
        return make_user(email, role=self.staff_role, employee_id=employee_id, full_name=full_name, branch=branch)

    def _detail_url(self, employee=None):
        return reverse('employee-detail', kwargs={'employee_id': (employee or self.employee).employee_id})

    def _rm_url(self):
        return reverse('employee-reporting-manager', kwargs={'employee_id': self.employee.employee_id})

    def _hr_url(self):
        return reverse('employee-hr-assign', kwargs={'employee_id': self.employee.employee_id})

    def _get_relationships(self):
        resp = self.client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        return {k: data[k] for k in ('reporting_manager', 'reporting_approver', 'hr')}

    def test_personal_put_persists_all_three_and_reopen_shows_them(self):
        resp = self.client.put(self._detail_url(), {
            'reporting_manager_id': str(self.manager_b.pk),
            'reporting_approver_id': str(self.approver_b.pk),
            'hr_id': str(self.hr_b.pk),
            'phone': '9000000001',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        for _ in range(2):  # reopen twice — GET's auto-assign must not override explicit values
            rel = self._get_relationships()
            self.assertEqual(rel['reporting_manager']['uuid'], str(self.manager_b.pk))
            self.assertEqual(rel['reporting_manager']['name'], 'Manager B')
            self.assertEqual(rel['reporting_approver']['uuid'], str(self.approver_b.pk))
            self.assertEqual(rel['reporting_approver']['name'], 'Approver B')
            self.assertEqual(rel['hr']['uuid'], str(self.hr_b.pk))

    def test_get_uuid_round_trips_through_put_unchanged(self):
        # The frontend echoes .uuid back as *_id on its next save — must be a no-op.
        rel = self._get_relationships()
        resp = self.client.put(self._detail_url(), {
            'reporting_manager_id': rel['reporting_manager']['uuid'],
            'reporting_approver_id': rel['reporting_approver']['uuid'],
            'hr_id': rel['hr']['uuid'],
            'phone': '9000000002',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_manager_id, self.manager_a.pk)
        self.assertEqual(self.employee.reporting_approver_id, self.approver_a.pk)
        self.assertEqual(self.employee.hr_id, self.hr_a.pk)
        self.assertEqual(self.employee.phone, '9000000002')

    def test_clearing_reporting_approver_persists_as_empty(self):
        resp = self.client.put(self._detail_url(), {'reporting_approver_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        rel = self._get_relationships()
        self.assertIsNone(rel['reporting_approver']['uuid'])
        self.assertEqual(rel['reporting_manager']['uuid'], str(self.manager_a.pk))

    def test_put_without_approver_key_leaves_approver_unchanged(self):
        resp = self.client.put(self._detail_url(), {'phone': '9000000003'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_approver_id, self.approver_a.pk)

    def test_approval_matrix_manager_change_survives_unrelated_save_with_fresh_values(self):
        resp = self.client.patch(self._rm_url(), {'reporting_manager_id': str(self.manager_b.pk)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        # Fixed frontend: baseValues carries manager_b, so an unrelated save resends it.
        rel = self._get_relationships()
        resp = self.client.put(self._detail_url(), {
            'reporting_manager_id': rel['reporting_manager']['uuid'],
            'reporting_approver_id': rel['reporting_approver']['uuid'],
            'hr_id': rel['hr']['uuid'],
            'phone': '9000000004',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._get_relationships()['reporting_manager']['uuid'], str(self.manager_b.pk))

    def test_personal_put_is_last_write_wins_so_stale_client_values_revert(self):
        # Server contract behind the old frontend bug: the client must never resend a stale id.
        self.client.patch(self._rm_url(), {'reporting_manager_id': str(self.manager_b.pk)}, format='json')
        resp = self.client.put(self._detail_url(), {
            'reporting_manager_id': str(self.manager_a.pk), 'phone': '9000000005',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_manager_id, self.manager_a.pk)

    def test_hr_assign_route_put_persists_only_hr(self):
        resp = self.client.put(self._hr_url(), {'hr_id': str(self.hr_b.pk)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        rel = self._get_relationships()
        self.assertEqual(rel['hr']['uuid'], str(self.hr_b.pk))
        self.assertEqual(rel['reporting_manager']['uuid'], str(self.manager_a.pk))
        self.assertEqual(rel['reporting_approver']['uuid'], str(self.approver_a.pk))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9000000001')
        self.assertTrue(self.employee.is_active)

    def test_hr_assign_route_patch_does_not_accept_hr_id(self):
        # PATCH on this route is the activate/deactivate handler — why the
        # Approval Matrix Branch HR editor must use PUT.
        resp = self.client.patch(self._hr_url(), {'hr_id': str(self.hr_b.pk)}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.hr_id, self.hr_a.pk)

    def test_self_as_reporting_approver_rejected_and_unchanged(self):
        resp = self.client.put(self._detail_url(), {'reporting_approver_id': str(self.employee.pk)}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_approver_id, self.approver_a.pk)

    def test_inactive_reporting_approver_rejected(self):
        self.approver_b.is_active = False
        self.approver_b.save(update_fields=['is_active'])
        resp = self.client.put(self._detail_url(), {'reporting_approver_id': str(self.approver_b.pk)}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_approver_id, self.approver_a.pk)

    def test_invalid_manager_aborts_whole_save_including_approver(self):
        resp = self.client.put(self._detail_url(), {
            'reporting_manager_id': str(self.employee.pk),
            'reporting_approver_id': str(self.approver_b.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_manager_id, self.manager_a.pk)
        self.assertEqual(self.employee.reporting_approver_id, self.approver_a.pk)

    def test_branch_scoped_editor_cannot_change_other_branch_relationships(self):
        other = make_user(
            'rel.other@test.com', role=self.staff_role, employee_id='EMPRPO001',
            full_name='Other Branch', branch='Delhi HQ', reporting_approver=self.approver_a,
        )
        resp = self.client.put(self._detail_url(other), {'reporting_approver_id': str(self.approver_b.pk)}, format='json')
        self.assertEqual(resp.status_code, 404)
        other.refresh_from_db()
        self.assertEqual(other.reporting_approver_id, self.approver_a.pk)

    def test_user_without_edit_permission_cannot_change_relationships(self):
        make_user(
            'rel.viewer@test.com', role=make_role('rel_persist_viewer', permission_codenames=['employees.view']),
            employee_id='EMPRPV001', full_name='Viewer', branch='Mumbai HQ',
        )
        _login(self.client, 'rel.viewer@test.com')
        resp = self.client.put(self._detail_url(), {'reporting_approver_id': str(self.approver_b.pk)}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.reporting_approver_id, self.approver_a.pk)

