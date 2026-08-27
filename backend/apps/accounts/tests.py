from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, Department, Designation, OTPVerification, User
from apps.accounts.serializers import ForgotPasswordSerializer


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class LoginFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        self.role = make_role('employee')
        self.user = make_user('employee@test.com', role=self.role, password='CorrectPass123!')

    def test_valid_login_succeeds_and_sets_cookies(self):
        resp = self.client.post(
            reverse('login'),
            {'email': 'employee@test.com', 'password': 'CorrectPass123!'},
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
            {'email': 'employee@test.com', 'password': 'WrongPassword!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 1)

    def test_account_locks_after_max_failed_attempts(self):
        for _ in range(5):
            self.client.post(
                reverse('login'),
                {'email': 'employee@test.com', 'password': 'WrongPassword!'},
                format='json',
            )
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.locked_until)
        self.assertTrue(self.user.is_locked())

        # Even the correct password must be rejected while locked.
        resp = self.client.post(
            reverse('login'),
            {'email': 'employee@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self.client.post(
            reverse('login'),
            {'email': 'employee@test.com', 'password': 'CorrectPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_login_resets_failed_attempts_on_success(self):
        self.user.failed_login_attempts = 3
        self.user.save(update_fields=['failed_login_attempts'])
        resp = self.client.post(
            reverse('login'),
            {'email': 'employee@test.com', 'password': 'CorrectPass123!'},
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
            {'email': 'refresh@test.com', 'password': 'CorrectPass123!'},
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
            reverse('forgot-password'), {'email': 'nobody-registered@test.com'}, format='json',
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
            {'email': 'reset@test.com', 'otp': plain_otp},
            format='json',
        )
        self.assertEqual(verify_resp.status_code, 200)
        reset_token = verify_resp.data['data']['reset_token']

        reset_resp = self.client.post(
            reverse('reset-password'),
            {
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
                {'email': 'reset@test.com', 'otp': '000000'},
                format='json',
            )
        resp = self.client.post(
            reverse('verify-otp'),
            {'email': 'reset@test.com', 'otp': plain_otp},
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
            {'email': 'change@test.com', 'password': 'OldPass123!'},
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

        # OnboardingApprovalView now validates department/designation against
        # the master tables (see Piece A) — real rows required for a 200.
        dept = Department.objects.create(name='Engineering', is_active=True)
        Designation.objects.create(name='Software Engineer', department=dept, is_active=True)

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
