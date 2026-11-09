"""
When an account becomes Active.

"Active" needs the employee's onboarding complete AND `account_activated_at` set AND the pending-activation flag cleared
(password set + first login). `account_activated_at` must be stamped when activation completes, whichever route the
password was set through:

  - the activation (invite) link,
  - the forced password change at first login,
  - a forgot-password reset token (the UAT case: a new account that set its password this way stayed "Awaiting
    activation" for good because nothing stamped the date).

A forgot-password reset for an employee who is already active must change nothing about their lifecycle.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import OnboardingEvent, PasswordResetToken, User
from apps.accounts.services_onboarding import is_onboarding
from apps.accounts.views.shared import _employee_dict

TEMPORARY_PASSWORD = 'Temp#Pass2026a'
NEW_PASSWORD = 'Chosen#Pass2026b'


def _new_account(email: str, **extra) -> User:
    """A completed hire that has not activated: onboarding complete, activation pending, no activation date."""
    return make_user(
        email, employee_id=extra.pop('employee_id', 'ACT001'), full_name='Newly Hired', password=TEMPORARY_PASSWORD,
        onboarding_status=User.ONBOARDING_COMPLETE, activation_pending=True, account_activated_at=None, **extra,
    )


def _reset_password(token: PasswordResetToken, password: str = NEW_PASSWORD):
    body = {'reset_token': str(token.id), 'new_password': password, 'confirm_password': password}
    return APIClient().post(reverse('reset-password'), body, format='json')


def _login(email: str, password: str):
    return APIClient().post(reverse('login'), {'email': email, 'password': password}, format='json')


class _ActivationCase(TestCase):
    def setUp(self):
        cache.clear()

    def _status(self, user: User) -> str:
        user.refresh_from_db()
        return _employee_dict(user)['status']

    def _token(self, user: User, purpose: str) -> PasswordResetToken:
        return PasswordResetToken.create_for_user(user, purpose=purpose, validity_hours=24)


class ActivationRoutesTests(_ActivationCase):
    def test_the_invite_link_stamps_the_date_and_active_follows_the_first_login(self):
        user = _new_account('act_invite@test.com')
        self.assertEqual(_reset_password(self._token(user, PasswordResetToken.PURPOSE_INVITE)).status_code, 200)
        user.refresh_from_db()
        self.assertIsNotNone(user.account_activated_at)
        self.assertEqual(self._status(user), 'onboarding')            # password set, but no first login yet

        self.assertEqual(_login(user.email, NEW_PASSWORD).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.activation_pending)
        self.assertEqual(self._status(user), 'active')

    def test_the_forced_password_change_at_first_login_activates_the_account(self):
        user = _new_account('act_forced@test.com', must_change_password=True)
        client = APIClient()
        self.assertEqual(client.post(reverse('login'), {'email': user.email, 'password': TEMPORARY_PASSWORD}, format='json').status_code, 200)
        change = client.post(reverse('change-password'), {
            'old_password': TEMPORARY_PASSWORD, 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD,
        }, format='json')
        self.assertEqual(change.status_code, 200, change.json())
        user.refresh_from_db()
        self.assertIsNotNone(user.account_activated_at)
        self.assertFalse(user.activation_pending)
        self.assertEqual(self._status(user), 'active')

    def test_a_new_account_that_sets_its_password_through_a_reset_token_becomes_active_after_first_login(self):
        """The UAT case: the account was created, the person used forgot-password instead of the activation link."""
        user = _new_account('act_reset@test.com')
        self.assertEqual(_reset_password(self._token(user, PasswordResetToken.PURPOSE_RESET)).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.activation_pending)                       # not Active merely because a password exists
        self.assertIsNone(user.account_activated_at)
        self.assertEqual(self._status(user), 'onboarding')

        self.assertEqual(_login(user.email, NEW_PASSWORD).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.activation_pending)
        self.assertIsNotNone(user.account_activated_at)                # stamped when the activation completed
        self.assertTrue(user.is_onboarded())
        self.assertEqual(self._status(user), 'active')
        self.assertEqual(OnboardingEvent.objects.filter(employee=user, event=OnboardingEvent.ACTIVATED).count(), 1)

    def test_active_is_not_shown_until_the_activation_conditions_are_met(self):
        incomplete = make_user('act_incomplete@test.com', employee_id='ACT002', onboarding_status=User.ONBOARDING_PENDING,
                               activation_pending=False, account_activated_at=None)
        no_date = make_user('act_nodate@test.com', employee_id='ACT003', onboarding_status=User.ONBOARDING_COMPLETE,
                            activation_pending=False, account_activated_at=None)
        pending = make_user('act_pending@test.com', employee_id='ACT004', onboarding_status=User.ONBOARDING_COMPLETE,
                            activation_pending=True, account_activated_at=timezone.now())
        complete = make_user('act_complete@test.com', employee_id='ACT005', onboarding_status=User.ONBOARDING_COMPLETE,
                             activation_pending=False)
        self.assertEqual([self._status(u) for u in (incomplete, no_date, pending, complete)],
                         ['onboarding', 'onboarding', 'onboarding', 'active'])
        self.assertTrue(is_onboarding(pending))


class AlreadyActiveEmployeeResetTests(_ActivationCase):
    def test_a_forgot_password_reset_changes_nothing_about_the_lifecycle(self):
        activated = timezone.now() - datetime.timedelta(days=90)
        user = make_user('act_existing@test.com', employee_id='ACT010', password=TEMPORARY_PASSWORD,
                         onboarding_status=User.ONBOARDING_COMPLETE, activation_pending=False, account_activated_at=activated)
        events_before = OnboardingEvent.objects.filter(employee=user).count()

        self.assertEqual(_reset_password(self._token(user, PasswordResetToken.PURPOSE_RESET)).status_code, 200)
        self.assertEqual(_login(user.email, NEW_PASSWORD).status_code, 200)

        user.refresh_from_db()
        self.assertEqual(user.account_activated_at, activated)         # the original date, not a new one
        self.assertFalse(user.activation_pending)
        self.assertEqual(self._status(user), 'active')
        self.assertEqual(OnboardingEvent.objects.filter(employee=user).count(), events_before)   # no lifecycle events
