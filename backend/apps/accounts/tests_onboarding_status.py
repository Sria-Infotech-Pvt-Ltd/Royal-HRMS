"""
Onboarding status: a new hire shows as Onboarding until they have set a password AND logged in once, and the admin can see
(and act on) everything that happened meanwhile.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

import apps.accounts.tests_hire_wizard as wizard
from apps.accounts import services_onboarding as onboarding
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OnboardingEvent, PasswordResetToken, User
from apps.accounts.services_headcount import get_headcount

def _events(user):
    return list(OnboardingEvent.objects.filter(employee=user).order_by('created_at').values_list('event', flat=True))


class OnboardingTestBase(TestCase):
    def setUp(self):
        cache.clear()
        # Own patchers, stopped one by one: patch.stopall() would also stop patches other test classes started.
        smtp_patcher = patch('apps.accounts.utils._get_smtp_connection', return_value=(None, 'noreply@test.com', None))
        build_patcher = patch('apps.accounts.utils._build_message')
        self.smtp = smtp_patcher.start()
        self.build = build_patcher.start()
        self.addCleanup(smtp_patcher.stop)
        self.addCleanup(build_patcher.stop)
        self.build.return_value.send.return_value = None
        role = make_role('onb_admin', permission_codenames=['employees.reset_password', 'employees.edit', 'employees.view'])
        self.admin = make_user('onb-admin@test.com', role=role, password='TestPass123!')
        self.hire = make_user('onb-hire@test.com', employee_id='EMPON001', password='Placeholder1!', must_change_password=True)
        self.hire.onboarding_status = User.ONBOARDING_COMPLETE
        self.hire.save(update_fields=['onboarding_status'])
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _start(self):
        return onboarding.start_onboarding(self.hire, actor=self.admin)

    def _history(self):
        resp = self.client.get(reverse('employee-onboarding-history', args=[self.hire.id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['data']

    def _activate_via_link(self):
        token = onboarding.latest_invite(self.hire)
        APIClient().get(reverse('invite-check', args=[token.id]))
        resp = APIClient().post(reverse('reset-password'), {
            'reset_token': str(token.id), 'new_password': 'RealPassw0rd!', 'confirm_password': 'RealPassw0rd!',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _login(self, password='RealPassw0rd!'):
        return APIClient().post(reverse('login'), {'email': self.hire.email, 'password': password}, format='json')


class StatusTests(OnboardingTestBase):
    def test_a_newly_invited_employee_is_onboarding_not_active(self):
        self._start()
        self.hire.refresh_from_db()
        self.assertTrue(onboarding.is_onboarding(self.hire))
        rows = self.client.get(reverse('employee-list-create') + '?search=EMPON001').data['data']['results']
        self.assertEqual(rows[0]['status'], 'onboarding')

    def test_the_onboarding_filter_finds_them_and_the_active_filter_does_not(self):
        self._start()
        onboarding_rows = self.client.get(reverse('employee-list-create') + '?status=onboarding&search=EMPON001').data['data']['results']
        active_rows = self.client.get(reverse('employee-list-create') + '?status=active&search=EMPON001').data['data']['results']
        self.assertEqual([row['id'] for row in onboarding_rows], ['EMPON001'])
        self.assertEqual(active_rows, [])

    def test_headcount_counts_them_as_onboarding_not_active(self):
        before = get_headcount()
        self._start()
        after = get_headcount()
        self.assertEqual(after['onboarding'], before['onboarding'] + 1)
        self.assertEqual(after['active'], before['active'] - 1 if before['active'] else 0)

    def test_an_established_employee_is_unaffected_by_an_admin_password_reset(self):
        # must_change_password is set by an admin reset too; only activation_pending decides Onboarding.
        self.hire.must_change_password = True
        self.hire.save(update_fields=['must_change_password'])
        self.assertFalse(onboarding.is_onboarding(self.hire))


class ActivationTests(OnboardingTestBase):
    def test_status_becomes_active_only_after_password_set_and_first_login(self):
        self._start()
        self._activate_via_link()
        self.hire.refresh_from_db()
        self.assertTrue(self.hire.activation_pending, 'password set alone must not activate')
        self.assertEqual(self._login().status_code, 200)
        self.hire.refresh_from_db()
        self.assertFalse(self.hire.activation_pending)
        self.assertFalse(onboarding.is_onboarding(self.hire))

    def test_history_records_every_step_in_order(self):
        self._start()
        self._activate_via_link()
        self._login()
        self.assertEqual(
            _events(self.hire),
            ['initiated', 'email_sent', 'link_opened', 'password_set', 'first_login', 'activated'],
        )
        labels = [item['label'] for item in self._history()['timeline']]
        self.assertIn('Status changed to Active', labels)

    def test_login_first_then_forced_password_change_also_activates(self):
        self._start()
        self.hire.set_password('TempPassw0rd!')
        self.hire.save(update_fields=['password'])
        self.assertEqual(self._login('TempPassw0rd!').status_code, 200)
        self.hire.refresh_from_db()
        self.assertTrue(self.hire.activation_pending)
        client = APIClient()
        client.force_authenticate(user=self.hire)
        resp = client.post(reverse('change-password'), {
            'old_password': 'TempPassw0rd!', 'new_password': 'RealPassw0rd!', 'confirm_password': 'RealPassw0rd!',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.hire.refresh_from_db()
        self.assertFalse(self.hire.activation_pending)

    def test_a_failed_login_attempt_does_not_count_as_first_login(self):
        self._start()
        self._activate_via_link()
        self._login('WrongPassword1!')
        self.assertNotIn('first_login', _events(self.hire))
        self.hire.refresh_from_db()
        self.assertTrue(self.hire.activation_pending)


class FailedEmailAndResendTests(OnboardingTestBase):
    def _fail_next_send(self, reason='550 5.1.1 mailbox unavailable'):
        self.build.return_value.send.side_effect = Exception(reason)

    def test_a_failed_send_is_recorded_with_the_reason_and_shown_as_the_state(self):
        self._fail_next_send()
        self.assertFalse(self._start())
        data = self._history()
        self.assertEqual(data['state']['code'], 'email_failed')
        self.assertEqual(data['state']['message'], 'Onboarding email failed. Please resend.')
        failed = next(item for item in data['timeline'] if item['event'] == 'email_failed')
        self.assertIn('mailbox unavailable', failed['detail'])
        self.assertTrue(data['state']['can_resend'])

    def test_resend_after_a_failure_works_and_is_logged_with_who_did_it(self):
        self._fail_next_send()
        self._start()
        self.build.return_value.send.side_effect = None
        resp = self.client.post(reverse('employee-resend-invite', args=[self.hire.id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        entry = next(item for item in resp.data['data']['timeline'] if item['event'] == 'email_resent')
        self.assertEqual(entry['actor_name'], self.admin.full_name or self.admin.email)
        self.assertEqual(resp.data['data']['state']['code'], 'not_logged_in')

    def test_a_resend_that_fails_again_says_so_and_stays_resendable(self):
        self._fail_next_send()
        self._start()
        resp = self.client.post(reverse('employee-resend-invite', args=[self.hire.id]))
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(_events(self.hire).count('email_failed'), 2)

    @override_settings(ONBOARDING_RESEND_MAX_PER_HOUR=2)
    def test_resends_are_rate_limited_per_hour(self):
        self._start()
        url = reverse('employee-resend-invite', args=[self.hire.id])
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 200)
        blocked = self.client.post(url)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn('last hour', blocked.data['message'])
        # Once the older resends age out of the window it works again.
        OnboardingEvent.objects.filter(employee=self.hire, event='email_resent').update(created_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_resend_is_not_offered_once_the_password_is_set(self):
        self._start()
        self._activate_via_link()
        data = self._history()
        self.assertEqual(data['state']['code'], 'awaiting_login')
        self.assertFalse(data['state']['can_resend'])


class ExpiredLinkTests(OnboardingTestBase):
    def test_an_expired_link_shows_link_expired_and_can_be_resent(self):
        self._start()
        PasswordResetToken.objects.filter(user=self.hire).update(expires_at=timezone.now() - timedelta(minutes=1))
        data = self._history()
        self.assertEqual(data['state']['code'], 'link_expired')
        self.assertIn('Link expired', data['state']['message'])
        self.assertTrue(data['state']['can_resend'])
        old = onboarding.latest_invite(self.hire)
        resp = APIClient().get(reverse('invite-check', args=[old.id]))
        self.assertEqual(resp.status_code, 410)
        self.assertEqual(self.client.post(reverse('employee-resend-invite', args=[self.hire.id])).status_code, 200)
        self.assertTrue(onboarding.latest_invite(self.hire).is_valid())


class CorrectEmailTests(OnboardingTestBase):
    def test_a_wrong_address_can_be_corrected_and_the_invite_goes_to_the_new_one(self):
        self._start()
        resp = self.client.post(reverse('employee-resend-invite', args=[self.hire.id]), {'email': 'fixed@test.com'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.hire.refresh_from_db()
        self.assertEqual(self.hire.email, 'fixed@test.com')
        self.assertIn('email_corrected', _events(self.hire))
        self.assertEqual(self.build.call_args.kwargs['to'], ['fixed@test.com'])

    def test_an_address_already_used_by_someone_else_is_refused(self):
        self._start()
        resp = self.client.post(reverse('employee-resend-invite', args=[self.hire.id]), {'email': self.admin.email}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.hire.refresh_from_db()
        self.assertEqual(self.hire.email, 'onb-hire@test.com')

    def test_a_malformed_address_is_refused(self):
        self._start()
        resp = self.client.post(reverse('employee-resend-invite', args=[self.hire.id]), {'email': 'not-an-email'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_the_address_cannot_be_changed_through_this_for_someone_not_onboarding(self):
        self.hire.must_change_password = True
        self.hire.save(update_fields=['must_change_password'])
        resp = self.client.post(reverse('employee-resend-invite', args=[self.hire.id]), {'email': 'other@test.com'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.hire.refresh_from_db()
        self.assertEqual(self.hire.email, 'onb-hire@test.com')


class PermissionTests(OnboardingTestBase):
    def test_history_needs_account_management_permission(self):
        plain = make_user('onb-plain@test.com', role=make_role('onb_plain'), password='TestPass123!')
        client = APIClient()
        client.force_authenticate(user=plain)
        self.assertEqual(client.get(reverse('employee-onboarding-history', args=[self.hire.id])).status_code, 403)
        self.assertEqual(client.post(reverse('employee-resend-invite', args=[self.hire.id])).status_code, 403)


class MigrationBackfillTests(TestCase):
    def test_someone_who_was_sent_an_invite_and_never_used_it_is_marked_onboarding(self):
        import importlib

        from django.apps import apps

        user = make_user('onb-backfill@test.com', employee_id='EMPON009', must_change_password=True)
        PasswordResetToken.objects.create(
            user=user, purpose=PasswordResetToken.PURPOSE_INVITE, expires_at=timezone.now() + timedelta(hours=5),
        )
        untouched = make_user('onb-backfill2@test.com', employee_id='EMPON010', must_change_password=True)
        importlib.import_module('apps.accounts.migrations.0206_onboarding_events_activation_pending').mark_users_with_unused_invites(apps, None)
        user.refresh_from_db()
        untouched.refresh_from_db()
        self.assertTrue(user.activation_pending)
        self.assertFalse(untouched.activation_pending)


class HireStartsOnboardingTests(wizard.HireWizardTestCase):
    def _hire(self):
        action = self._create_draft()
        self._set_employment_type(action, 'Permanent')
        self._patch(action, self._valid_full_draft())
        self._upload_all_required_docs(action)
        return self._complete(action)

    def test_completing_a_hire_leaves_the_person_onboarding_with_the_email_logged(self):
        with patch('apps.accounts.utils.send_activation_invite') as send:
            resp = self._hire()
        self.assertEqual(resp.status_code, 201, resp.data)
        employee = User.objects.get(employee_id=resp.data['data']['reserved_employee_id'])
        self.assertTrue(employee.activation_pending)
        self.assertTrue(onboarding.is_onboarding(employee))
        self.assertEqual(_events(employee), ['initiated', 'email_sent'])
        send.assert_called_once()

    def test_a_failing_mail_server_does_not_fail_the_hire_and_is_visible_afterwards(self):
        with patch('apps.accounts.utils.send_activation_invite', side_effect=Exception('Connection refused')):
            resp = self._hire()
        self.assertEqual(resp.status_code, 201, resp.data)
        employee = User.objects.get(employee_id=resp.data['data']['reserved_employee_id'])
        self.assertEqual(_events(employee), ['initiated', 'email_failed'])
        self.assertEqual(onboarding.current_state(employee)['code'], 'email_failed')
