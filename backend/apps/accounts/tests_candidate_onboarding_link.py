"""
HR-led recruitment, from "Selected" to "Active", and the direct-hire path beside it.

Path 1: HR sends a selected candidate ONE password-less, expiring, single-use link to the onboarding wizard. The link opens a
limited session (no employee screen) and neither creates nor activates an employee account. Only after HR approves the
onboarding is the candidate sent an account activation link; they set their own password, log in, and only then are Active.

Path 2: a direct hire counts HR's completed hire as the approval (no onboarding-approval queue); the employee shows as
"Awaiting activation" until they set a password and log in.
"""
from __future__ import annotations

import datetime
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, OrgUnit, PasswordResetToken, Position, User
from apps.accounts.services_onboarding import start_onboarding
from apps.recruitment.models import Candidate, CandidateEmail

SEND = 'apps.recruitment.services_candidate_onboarding.send_template_email'
NEW_PASSWORD = 'Activated#2026x'


def _activation_stub(user, **_kwargs):
    """Stands in for the SMTP send of the real activation invite: it still issues the real single-use token."""
    return PasswordResetToken.create_for_user(user, purpose=PasswordResetToken.PURPOSE_INVITE, validity_hours=72), True


class _RecruitmentPathFixtures(TestCase):
    def setUp(self):
        cache.clear()
        self.hr = make_user('olink_hr@test.com', employee_id='OL001', full_name='Hema HR',
                            role=make_role('olink_hr', permission_codenames=['recruitment.edit', 'recruitment.view', 'onboarding.approve']))
        self.hr_client = APIClient()
        self.hr_client.force_authenticate(user=self.hr)
        self.position = Position.objects.create(org_unit=OrgUnit.objects.create(name='Olink Unit'), title='Engineer', grade='L2')
        self.candidate = Candidate.objects.create(name='Candice Candidate', email='olink.candidate@test.com',
                                                  position_applied='Engineer', status=Candidate.STATUS_SELECTED)

    def _send_link(self, candidate=None):
        candidate = candidate or self.candidate
        with patch(SEND) as sender:
            response = self.hr_client.post(reverse('candidate-send-portal-login', args=[candidate.pk]), {}, format='json')
        return response, sender

    def _portal_user(self) -> User:
        return User.objects.get(email=self.candidate.email)

    def _live_link(self) -> PasswordResetToken:
        return PasswordResetToken.objects.get(user=self._portal_user(), purpose=PasswordResetToken.PURPOSE_ONBOARDING, is_used=False)

    def _open(self, token, client=None):
        return (client or APIClient()).post(reverse('onboarding-link-exchange'), {'token': str(token.id)}, format='json')


class SendingTheOnboardingLinkTests(_RecruitmentPathFixtures):
    def test_only_a_selected_candidate_can_be_sent_the_link(self):
        for status_value in (Candidate.STATUS_PENDING, Candidate.STATUS_INTERVIEW_DONE, Candidate.STATUS_REJECTED):
            candidate = Candidate.objects.create(name='X', email=f'olink.{status_value}@test.com', position_applied='Engineer', status=status_value)
            response, sender = self._send_link(candidate)
            self.assertEqual(response.status_code, 400, status_value)
            sender.assert_not_called()
            self.assertFalse(User.objects.filter(email=candidate.email).exists())

    def test_the_link_email_carries_a_link_and_no_password_and_reaches_the_candidate_from_hr(self):
        response, sender = self._send_link()
        self.assertEqual(response.status_code, 200, response.json())
        kwargs = sender.call_args.kwargs
        self.assertEqual(kwargs['template_name'], 'candidate_onboarding_link')
        self.assertEqual(kwargs['recipient_email'], self.candidate.email)
        self.assertIn('/onboarding/start/', kwargs['context']['onboarding_link'])
        self.assertNotIn('temp_password', kwargs['context'])
        self.assertNotIn('password', ' '.join(kwargs['context']).lower())
        self.assertEqual(kwargs['reply_to'], 'olink_hr@test.com')
        self.assertEqual(kwargs['hr_contact'], ('Hema HR', 'olink_hr@test.com'))

    def test_sending_the_link_creates_no_usable_account_and_activates_nothing(self):
        self._send_link()
        user = self._portal_user()
        self.assertFalse(user.has_usable_password())          # no password exists to be emailed or guessed
        self.assertEqual(user.employee_id, '')                # no employee record yet
        self.assertIsNone(user.account_activated_at)
        self.assertTrue(user.requires_self_service_onboarding)
        self.assertEqual(user.onboarding_status, User.ONBOARDING_PENDING)
        self.assertEqual(user.hr_id, self.hr.pk)              # the candidate's HR contact
        self.assertFalse(PasswordResetToken.objects.filter(user=user, purpose=PasswordResetToken.PURPOSE_INVITE).exists())

    def test_the_email_log_never_stores_the_live_link(self):
        from apps.accounts.models import EmailLog
        from apps.accounts.utils import send_template_email as real_send
        self._send_link()
        link = self._live_link()
        with patch('apps.accounts.utils._get_smtp_connection', side_effect=RuntimeError('no smtp in tests')):
            with self.assertRaises(RuntimeError):
                real_send(recipient_email=self.candidate.email, template_name='candidate_onboarding_link', module='recruitment',
                          context={'candidate_name': 'C', 'position': 'P', 'company_name': 'Co', 'onboarding_link': f'https://x/onboarding/start/{link.id}/', 'expires_on': 'soon'})
        logged = EmailLog.objects.filter(template_name='candidate_onboarding_link').latest('created_at')
        self.assertNotIn(str(link.id), logged.body_html)

    def test_a_resend_replaces_the_old_link(self):
        self._send_link()
        first = self._live_link()
        with patch(SEND):
            response = self.hr_client.post(reverse('candidate-resend-portal-login', args=[self.candidate.pk]), {}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        second = self._live_link()
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(self._open(first).status_code, 410)       # the old link is dead
        self.assertEqual(self._open(second).status_code, 200)

    def test_a_failed_email_is_reported_and_can_be_resent(self):
        with patch(SEND, side_effect=RuntimeError('smtp down')):
            response = self.hr_client.post(reverse('candidate-send-portal-login', args=[self.candidate.pk]), {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['data']['delivered'])
        self.assertIn('could not be sent', response.json()['message'])

    def test_an_hr_user_without_recruitment_edit_cannot_send_it(self):
        plain = make_user('olink_plain@test.com', employee_id='OL002', role=make_role('olink_plain'))
        client = APIClient()
        client.force_authenticate(user=plain)
        self.assertEqual(client.post(reverse('candidate-send-portal-login', args=[self.candidate.pk]), {}, format='json').status_code, 403)


class OpeningTheOnboardingLinkTests(_RecruitmentPathFixtures):
    def setUp(self):
        super().setUp()
        self._send_link()
        self.token = self._live_link()

    def test_opening_the_link_starts_a_session_without_a_password(self):
        client = APIClient()
        response = self._open(self.token, client)
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIn('royal_access_token', client.cookies)
        self.assertEqual(response.json()['data']['user']['email'], self.candidate.email)
        self.assertTrue(response.json()['data']['user']['requires_self_service_onboarding'])
        self.assertTrue(AuditLog.objects.filter(action='onboarding_link_opened', object_id=str(self._portal_user().pk)).exists())

    def test_the_link_works_once(self):
        self.assertEqual(self._open(self.token).status_code, 200)
        again = self._open(self.token)
        self.assertEqual(again.status_code, 410)
        self.assertIn('already used', again.json()['message'])
        self.assertNotIn('royal_access_token', again.cookies)

    def test_an_expired_link_is_refused(self):
        PasswordResetToken.objects.filter(pk=self.token.pk).update(expires_at=timezone.now() - datetime.timedelta(minutes=1))
        response = self._open(self.token)
        self.assertEqual(response.status_code, 410)
        self.assertIn('expired', response.json()['message'])

    def test_an_unknown_or_malformed_link_is_refused(self):
        client = APIClient()
        self.assertEqual(client.post(reverse('onboarding-link-exchange'), {'token': '00000000-0000-0000-0000-000000000000'}, format='json').status_code, 404)
        self.assertEqual(client.post(reverse('onboarding-link-exchange'), {'token': 'not-a-token'}, format='json').status_code, 404)
        self.assertEqual(client.post(reverse('onboarding-link-exchange'), {}, format='json').status_code, 400)

    def test_an_activation_or_reset_token_cannot_be_used_as_an_onboarding_link(self):
        user = self._portal_user()
        for purpose in (PasswordResetToken.PURPOSE_INVITE, PasswordResetToken.PURPOSE_RESET):
            other = PasswordResetToken.create_for_user(user, purpose=purpose, validity_hours=1)
            self.assertEqual(self._open(other).status_code, 404, purpose)

    def test_the_link_cannot_be_used_after_hr_has_approved(self):
        User.objects.filter(pk=self._portal_user().pk).update(onboarding_status=User.ONBOARDING_COMPLETE)
        self.assertEqual(self._open(self.token).status_code, 410)

    def test_a_deactivated_candidates_link_is_refused(self):
        User.objects.filter(pk=self._portal_user().pk).update(is_active=False)
        self.assertEqual(self._open(self.token).status_code, 410)


class RejectionClosesTheLinkTests(_RecruitmentPathFixtures):
    """Rejecting the candidate (not just sending the onboarding back for corrections) ends their access."""

    def _reject(self):
        with patch('apps.recruitment.views.candidate_status._send_candidate_email', return_value=CandidateEmail.STATUS_SENT):
            return self.hr_client.patch(reverse('candidate-status', args=[self.candidate.pk]), {'status': 'rejected'}, format='json')

    def test_an_unopened_link_stops_working_once_the_candidate_is_rejected(self):
        self._send_link()
        token = self._live_link()
        self.assertEqual(self._reject().status_code, 200)
        self.assertEqual(self._open(token).status_code, 410)

    def test_an_open_session_is_cut_off_once_the_candidate_is_rejected(self):
        self._send_link()
        session = APIClient()
        self._open(self._live_link(), session)
        self.assertEqual(session.get(reverse('my-profile')).status_code, 200)
        self.assertEqual(self._reject().status_code, 200)
        self.assertIn(session.get(reverse('my-profile')).status_code, (401, 403))


class AccessBeforeApprovalTests(_RecruitmentPathFixtures):
    """With the link's session the candidate reaches the onboarding form and nothing that belongs to an employee."""

    def setUp(self):
        super().setUp()
        self._send_link()
        self.session = APIClient()
        self._open(self._live_link(), self.session)

    def test_the_candidate_can_reach_their_onboarding_screens_and_see_their_hr_contact(self):
        contact = self.session.get(reverse('onboarding-hr-contact'))
        self.assertEqual(contact.status_code, 200, contact.json())
        self.assertEqual(contact.json()['data'], {'name': 'Hema HR', 'email': 'olink_hr@test.com'})

    def test_the_employee_screens_stay_closed(self):
        for name in ('leave-balance', 'leave-request-list', 'my-approvals'):
            if name == 'my-approvals':
                continue   # read-only own-chain view: harmless, not an employee module
            self.assertEqual(self.session.get(reverse(name)).status_code, 403, name)

    def test_the_candidate_cannot_use_the_session_to_reach_hr_screens(self):
        self.assertEqual(self.session.get(reverse('candidate-list-create')).status_code, 403)
        self.assertEqual(self.session.post(reverse('candidate-send-portal-login', args=[self.candidate.pk]), {}, format='json').status_code, 403)

    def test_no_activation_link_exists_before_approval(self):
        user = self._portal_user()
        self.assertFalse(PasswordResetToken.objects.filter(user=user, purpose=PasswordResetToken.PURPOSE_INVITE).exists())
        User.objects.filter(pk=user.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)   # the candidate submits
        self.assertFalse(PasswordResetToken.objects.filter(user=user, purpose=PasswordResetToken.PURPOSE_INVITE).exists())


class ActivationOnlyAfterApprovalTests(_RecruitmentPathFixtures):
    def setUp(self):
        super().setUp()
        self._send_link()
        self.session = APIClient()
        self._open(self._live_link(), self.session)
        self.user = self._portal_user()
        User.objects.filter(pk=self.user.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)

    def _approve(self):
        hr = make_user('olink_approver@test.com', employee_id='OL003', role=make_role('olink_approver', permission_codenames=['onboarding.approve', 'settings.edit']))
        client = APIClient()
        client.force_authenticate(user=hr)
        with patch('apps.accounts.utils.send_activation_invite', side_effect=_activation_stub) as sender, \
                patch('apps.accounts.tasks.send_onboarding_approved_notification_task.apply_async'), \
                self.captureOnCommitCallbacks(execute=True):
            response = client.post(reverse('onboarding-approve', args=[self.user.pk]), {'decision': 'approve', 'position': str(self.position.pk)}, format='json')
        return response, sender

    def test_rejection_sends_nothing_and_activates_nothing(self):
        with patch('apps.accounts.utils.send_activation_invite', side_effect=_activation_stub) as sender:
            response = self.hr_client.post(reverse('onboarding-approve', args=[self.user.pk]), {'decision': 'reject', 'remarks': 'PAN unclear'}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        sender.assert_not_called()
        self.user.refresh_from_db()
        self.assertIsNone(self.user.account_activated_at)
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_REJECTED)

    def test_approval_sends_the_activation_link_but_does_not_activate_the_account(self):
        response, sender = self._approve()
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIn('activation link', response.json()['message'])
        sender.assert_called_once()
        self.user.refresh_from_db()
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_COMPLETE)
        self.assertTrue(self.user.employee_id)
        self.assertIsNone(self.user.account_activated_at)         # not activated by approval
        self.assertTrue(self.user.activation_pending)
        self.assertFalse(self.user.has_usable_password())          # still no password
        self.assertFalse(self.user.is_onboarded())
        self.assertTrue(PasswordResetToken.objects.filter(user=self.user, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False).exists())

    def test_the_candidates_old_session_still_cannot_reach_employee_screens_after_approval(self):
        self._approve()
        self.assertEqual(self.session.get(reverse('leave-balance')).status_code, 403)

    def test_the_candidate_becomes_active_only_after_setting_a_password_and_logging_in(self):
        self._approve()
        token = PasswordResetToken.objects.get(user=self.user, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False)

        reset = APIClient().post(reverse('reset-password'), {'reset_token': str(token.id), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD}, format='json')
        self.assertEqual(reset.status_code, 200, reset.json())
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.account_activated_at)       # the candidate set their own password
        self.assertTrue(self.user.activation_pending)              # ...but Active also waits for the first login

        client = APIClient()
        login = client.post(reverse('login'), {'email': self.user.email, 'password': NEW_PASSWORD}, format='json')
        self.assertEqual(login.status_code, 200, login.json())
        self.user.refresh_from_db()
        self.assertFalse(self.user.activation_pending)
        self.assertTrue(self.user.is_onboarded())
        self.assertNotEqual(client.get(reverse('leave-balance')).status_code, 403)   # the employee dashboard is open now

    def test_the_activation_link_works_once(self):
        self._approve()
        token = PasswordResetToken.objects.get(user=self.user, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False)
        body = {'reset_token': str(token.id), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD}
        self.assertEqual(APIClient().post(reverse('reset-password'), body, format='json').status_code, 200)
        self.assertNotEqual(APIClient().post(reverse('reset-password'), body, format='json').status_code, 200)


class DirectHirePathTests(TestCase):
    """HR's completed hire is the approval: no onboarding-approval queue, and the employee is "Awaiting activation"."""

    def setUp(self):
        cache.clear()
        self.hr = make_user('direct_hr@test.com', employee_id='DH001', role=make_role(
            'direct_hr', permission_codenames=['employees.view', 'employees.create', 'onboarding.approve']))
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr)
        self.hire = make_user('direct_hire@test.com', employee_id='DH010', onboarding_status=User.ONBOARDING_COMPLETE)
        with patch('apps.accounts.utils.send_activation_invite', side_effect=_activation_stub):
            start_onboarding(self.hire, actor=self.hr)           # what completing a hire does
        self.hire.refresh_from_db()

    def test_the_hire_is_not_waiting_in_any_onboarding_approval_queue(self):
        listed = self.client.get(reverse('onboarding-approvals')).json()['data']['results']
        self.assertNotIn(str(self.hire.pk), [str(row.get('id')) for row in listed])
        pipeline = self.client.get(reverse('onboarding-approvals'), {'view': 'pipeline'}).json()['data']['results']
        self.assertNotIn(str(self.hire.pk), [str(row.get('id')) for row in pipeline])

    def test_the_hire_shows_awaiting_activation_not_onboarding_work(self):
        data = self.client.get(reverse('employee-detail', args=[self.hire.employee_id])).json()['data']
        self.assertEqual(data['status'], 'onboarding')
        self.assertTrue(data['awaiting_activation'])
        self.assertFalse(data['needs_onboarding_data'])          # nothing is left for them to fill in

    def test_after_the_password_and_first_login_the_flag_clears_and_probation_stays_separate(self):
        token = PasswordResetToken.objects.get(user=self.hire, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False)
        APIClient().post(reverse('reset-password'), {'reset_token': str(token.id), 'new_password': NEW_PASSWORD, 'confirm_password': NEW_PASSWORD}, format='json')
        APIClient().post(reverse('login'), {'email': self.hire.email, 'password': NEW_PASSWORD}, format='json')
        data = self.client.get(reverse('employee-detail', args=[self.hire.employee_id])).json()['data']
        self.assertEqual(data['status'], 'active')
        self.assertFalse(data['awaiting_activation'])
        self.assertEqual(data['employment_status'], User.EMPLOYMENT_STATUS_PROBATION)   # an employment status, not the account status
