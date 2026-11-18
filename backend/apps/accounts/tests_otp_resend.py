"""Forgot-password OTP: asking again must not cancel a code that is still on its way, and mixing up codes must say so."""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import OTPVerification

SEND = 'apps.accounts.views.auth.send_otp_email'


@override_settings(OTP_RESEND_COOLDOWN_SECONDS=60)
class OtpResendTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = make_user('otp-user@test.com', full_name='Otp User')

    def _ask(self, email='otp-user@test.com'):
        with mock.patch(SEND) as send:
            response = self.client.post(reverse('forgot-password'), {'email': email}, format='json')
        return response, send

    def _verify(self, code, email='otp-user@test.com'):
        return self.client.post(reverse('verify-otp'), {'email': email, 'otp': code}, format='json')

    def _issued_code(self, send) -> str:
        return send.call_args.args[1]

    def test_the_code_from_the_email_verifies(self):
        _, send = self._ask()
        response = self._verify(self._issued_code(send))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('reset_token', response.data['data'])

    def test_asking_again_inside_the_cooldown_keeps_the_first_code(self):
        _, first = self._ask()
        first_code = self._issued_code(first)
        response, second = self._ask()
        self.assertEqual(response.status_code, 200)
        second.assert_not_called()                       # no second email, so no second code to confuse
        self.assertEqual(OTPVerification.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self._verify(first_code).status_code, 200)   # the code the person is reading still works

    def test_the_answer_is_identical_for_unknown_emails_and_for_the_cooldown(self):
        _, _ = self._ask()
        inside, _ = self._ask()
        unknown, _ = self._ask('nobody@test.com')
        self.assertEqual((inside.status_code, inside.data['message']), (unknown.status_code, unknown.data['message']))

    def test_after_the_cooldown_a_new_code_replaces_the_old_one(self):
        _, first = self._ask()
        old_code = self._issued_code(first)
        OTPVerification.objects.filter(user=self.user).update(created_at=timezone.now() - timedelta(seconds=61))
        _, second = self._ask()
        second.assert_called_once()
        new_code = self._issued_code(second)
        self.assertEqual(OTPVerification.objects.filter(user=self.user, is_used=False).count(), 1)
        if old_code != new_code:
            response = self._verify(old_code)
            self.assertEqual(response.status_code, 400)
            self.assertIn('replaced', response.data['message'])
        self.assertEqual(self._verify(new_code).status_code, 200)

    def test_a_wrong_code_is_still_just_invalid(self):
        _, send = self._ask()
        real = self._issued_code(send)
        wrong = '000000' if real != '000000' else '111111'
        response = self._verify(wrong)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid OTP', response.data['message'])

    def test_a_failed_email_does_not_block_the_next_attempt(self):
        with mock.patch(SEND, side_effect=RuntimeError('smtp down')):
            failed = self.client.post(reverse('forgot-password'), {'email': 'otp-user@test.com'}, format='json')
        self.assertEqual(failed.status_code, 500)
        _, retry = self._ask()
        retry.assert_called_once()                       # not swallowed by the cooldown
        self.assertEqual(self._verify(self._issued_code(retry)).status_code, 200)

    def test_five_wrong_tries_lock_the_code(self):
        _, send = self._ask()
        real = self._issued_code(send)
        wrong = '000000' if real != '000000' else '111111'
        for _ in range(6):
            self._verify(wrong)
        locked = self._verify(real)
        self.assertEqual(locked.status_code, 400)
        self.assertIn('expired or maximum attempts', locked.data['message'])


class OtpStorageTests(TestCase):
    def setUp(self):
        self.user = make_user('otp-store@test.com', full_name='Otp Store')

    def test_a_new_code_is_stored_as_a_keyed_hash_never_as_the_code(self):
        otp, plain = OTPVerification.create_for_user(self.user)
        self.assertTrue(otp.otp.startswith('hmac$'))
        self.assertNotIn(plain, otp.otp)
        self.assertTrue(otp.check_otp(plain))
        self.assertFalse(otp.check_otp('000000' if plain != '000000' else '111111'))

    def test_a_code_belongs_to_one_person(self):
        other = make_user('otp-other@test.com', full_name='Other')
        otp, plain = OTPVerification.create_for_user(self.user)
        stolen = OTPVerification(user=other, otp=otp.otp)
        self.assertFalse(stolen.check_otp(plain))

    def test_a_code_issued_before_the_change_is_still_accepted(self):
        from django.contrib.auth.hashers import make_password
        legacy = OTPVerification.objects.create(user=self.user, otp=make_password('482913'), expires_at=timezone.now() + timedelta(minutes=5))
        self.assertTrue(legacy.check_otp('482913'))
        self.assertFalse(legacy.check_otp('482914'))
