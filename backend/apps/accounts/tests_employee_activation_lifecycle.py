"""
The complete employee lifecycle after a bulk import, with the real fields at every step.

Three different things are tracked, and they are NOT the same status:

  1. Is the account usable?        User.password (unusable until set), User.account_activated_at, User.activation_pending,
                                   User.is_active (False means DISABLED by an administrator, not "not activated yet")
  2. Has onboarding been done?     User.onboarding_status: pending -> (draft) -> submitted -> complete (or rejected)
                                   User.requires_self_service_onboarding: the employee must fill in the onboarding form
  3. Has HR approved it?           the approval (OnboardingApprovalView) moves submitted -> complete

Imported employees start as: password unusable, account_activated_at empty, onboarding_status pending, requires_self_service_onboarding
True. No email is ever sent: the mail connection is Django's in-memory outbox and Celery's broker is mocked.
"""
from __future__ import annotations

import base64
import json
import re
from unittest import mock

from django.core import mail
from django.core.mail import get_connection
from rest_framework.test import APIClient

from apps.accounts import services_employee_import_invites as invites
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Company, PasswordResetToken, User
from apps.accounts.services_lifecycle_status import ACCOUNT_ACTIVE, ACCOUNT_INVITATION_PENDING, lifecycle_summary
from apps.accounts.tests_employee_bulk_import import _ImportCase

DELAY = 'apps.accounts.tasks.send_import_invite.delay'
SMTP = 'apps.accounts.utils._get_smtp_connection'
PASSWORD = 'Fresh-Pass-1'
LINK = re.compile(r'/activate/([0-9a-f-]{36})/')


def smtp_to_outbox():
    return (get_connection('django.core.mail.backends.locmem.EmailBackend'), 'hr@test.invalid', None)


def jwt_claims(client: APIClient) -> dict:
    part = client.cookies['royal_access_token'].value.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))


def proxy_sends_to_onboarding(claims: dict) -> bool:
    """The rule in frontend/proxy.ts: onboarding is forced while the flag is set and the status is not complete (admins are exempt)."""
    return (claims.get('requires_self_service_onboarding') is True and claims.get('onboarding_status', 'complete') != 'complete'
            and not claims.get('is_superuser') and not claims.get('can_manage_branch'))


class ActivationLifecycleTests(_ImportCase):
    def setUp(self):
        super().setUp()
        Company.objects.create(company_name='Test Co', portal_url='https://aira.nxsys.in')
        self.approver = make_user('life_hr@test.com', role=make_role('life_hr', permission_codenames=['employees.view', 'employees.create', 'onboarding.approve']),
                                  employee_id='LH001', branch=self.hyd.branch_name)
        with mock.patch(DELAY), mock.patch(SMTP, smtp_to_outbox):       # the import may try the invitation at once: it goes to the in-memory outbox
            response = self.commit(self.hr, [self.row(1)])
        self.assertEqual(response.status_code, 201, response.data)
        self.employee = User.objects.get(email='asha1@import.test')
        self.invite = self.employee.import_invites.get()

    def send_invitation(self) -> str:
        """The activation link from the invitation email. Sends the invitation first if the import left it waiting."""
        self.invite.refresh_from_db()
        if self.invite.status == 'pending':
            with mock.patch(SMTP, smtp_to_outbox):
                invites.process_invite(self.invite.pk)
            self.invite.refresh_from_db()
        self.assertEqual((self.invite.status, self.invite.reason_code), ('sent', ''))
        return LINK.search(mail.outbox[-1].alternatives[0][0]).group(1)

    def activate(self, token: str, password: str = PASSWORD):
        return APIClient().post('/api/reset-password/', {'reset_token': token, 'new_password': password, 'confirm_password': password}, format='json')

    def login(self, password: str = PASSWORD):
        client = APIClient()
        return client, client.post('/api/login/', {'email': self.employee.email, 'password': password}, format='json')

    def refresh(self) -> User:
        self.employee.refresh_from_db()
        return self.employee

    # ── 1. right after the import ────────────────────────────────────────────────────────────────────────────────────────

    def test_the_imported_account_is_pending_activation_and_cannot_be_used_yet(self):
        user = self.refresh()
        self.assertFalse(user.has_usable_password())                                  # no password exists: nobody can sign in
        self.assertIsNone(user.account_activated_at)                                  # never activated
        self.assertEqual(user.onboarding_status, User.ONBOARDING_PENDING)             # onboarding not done
        self.assertTrue(user.requires_self_service_onboarding)                        # the employee must fill the onboarding form
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.is_active)                                               # NOT "deactivated": False here would mean Disabled
        summary = lifecycle_summary(user)
        self.assertEqual((summary['account_status'], summary['onboarding_stage']), (ACCOUNT_INVITATION_PENDING, 'not_started'))

    def test_login_is_blocked_before_a_password_is_created(self):
        for guess in ('Fresh-Pass-1', 'password', self.employee.email.split('@')[0]):
            _client, response = self.login(guess)
            self.assertIn(response.status_code, (400, 401), guess)
        self.assertNotIn('royal_access_token', _client.cookies)

    def test_sending_the_invitation_does_not_activate_anything(self):
        token = self.send_invitation()
        user = self.refresh()
        self.assertIsNone(user.account_activated_at)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(PasswordResetToken.objects.get(id=token).is_valid())
        self.assertEqual(self.login()[1].status_code, 401)                            # the link alone is not a login

    # ── 2. setting the password ──────────────────────────────────────────────────────────────────────────────────────────

    def test_setting_the_password_activates_the_account_but_not_onboarding(self):
        token = self.send_invitation()
        self.assertEqual(self.activate(token).status_code, 200)
        user = self.refresh()
        self.assertTrue(user.check_password(PASSWORD))
        self.assertIsNotNone(user.account_activated_at)                               # activated
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.is_active)
        self.assertEqual(user.onboarding_status, User.ONBOARDING_PENDING)             # still NOT onboarded
        self.assertTrue(user.requires_self_service_onboarding)                        # preserved
        self.assertTrue(PasswordResetToken.objects.get(id=token).is_used)             # the link is spent
        summary = lifecycle_summary(user)
        self.assertEqual((summary['account_status'], summary['onboarding_stage']), (ACCOUNT_ACTIVE, 'not_started'))
        self.assertFalse(user.is_onboarded())                                         # "Active" account, but not an onboarded employee

    def test_the_link_cannot_be_used_twice(self):
        token = self.send_invitation()
        self.assertEqual(self.activate(token).status_code, 200)
        second = self.activate(token, 'Other-Pass-2')
        self.assertEqual(second.status_code, 400)
        self.assertTrue(self.refresh().check_password(PASSWORD))                      # the second password was not accepted
        self.assertEqual(APIClient().get(f'/api/invite/{token}/').status_code, 410)

    def test_login_is_allowed_after_the_password_is_created(self):
        self.activate(self.send_invitation())
        client, response = self.login()
        self.assertEqual(response.status_code, 200, response.data)
        user_payload = response.data['data']['user']
        self.assertEqual((user_payload['onboarding_status'], user_payload['requires_self_service_onboarding']), ('pending', True))
        self.assertTrue(proxy_sends_to_onboarding(jwt_claims(client)))                # the frontend sends them to /onboarding, not the dashboard
        self.assertEqual(self.login('wrong-password')[1].status_code, 401)

    # ── 3. onboarding and HR approval ────────────────────────────────────────────────────────────────────────────────────

    def test_before_hr_approval_onboarding_stays_pending_and_cannot_be_approved(self):
        self.activate(self.send_invitation())
        client, _ = self.login()
        self.assertEqual(self.refresh().onboarding_status, 'pending')
        refusal = self.client_for(self.approver).post(f'/api/onboarding/approvals/{self.employee.pk}/', {'decision': 'approve'}, format='json')
        self.assertEqual(refusal.status_code, 400)                                    # nothing was submitted, so there is nothing to approve
        self.assertEqual(self.refresh().onboarding_status, 'pending')
        self.assertEqual(client.post('/api/onboarding/', {}, format='json').status_code, 400)   # an empty form cannot be submitted either
        self.assertEqual(self.refresh().onboarding_status, 'pending')

    def test_an_employee_cannot_approve_their_own_onboarding(self):
        self.activate(self.send_invitation())
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
        client, _ = self.login()
        self.assertEqual(client.post(f'/api/onboarding/approvals/{self.employee.pk}/', {'decision': 'approve'}, format='json').status_code, 403)
        self.assertEqual(self.refresh().onboarding_status, 'submitted')

    def test_after_hr_approval_onboarding_is_complete_and_the_dashboard_is_reachable(self):
        self.activate(self.send_invitation())
        # The onboarding form itself (required fields, documents) is exercised by the onboarding tests and the end-to-end run;
        # here the submitted state is set directly so that THIS test is only about activation and approval.
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
        self.assertEqual(lifecycle_summary(self.refresh())['onboarding_stage'], 'awaiting_review')
        response = self.client_for(self.approver).post(f'/api/onboarding/approvals/{self.employee.pk}/', {'decision': 'approve', 'remarks': 'ok'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        user = self.refresh()
        self.assertEqual(user.onboarding_status, User.ONBOARDING_COMPLETE)
        self.assertTrue(user.is_onboarded())                                          # complete AND activated
        summary = lifecycle_summary(user)
        self.assertEqual((summary['account_status'], summary['onboarding_stage']), (ACCOUNT_ACTIVE, 'completed'))
        client, login = self.login()
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.data['data']['user']['onboarding_status'], 'complete')
        self.assertFalse(proxy_sends_to_onboarding(jwt_claims(client)))               # no longer forced to /onboarding: the dashboard opens
        self.assertEqual(client.get('/api/notifications/unread-count/').status_code, 200)   # and its API works for this employee
        self.assertEqual(client.patch('/api/onboarding/step/0/', {'father_name': 'x'}, format='json').status_code, 403)   # approved data is locked

    def test_a_disabled_account_is_a_separate_state_from_a_pending_one(self):
        self.activate(self.send_invitation())
        User.objects.filter(pk=self.employee.pk).update(is_active=False)
        self.assertEqual(lifecycle_summary(self.refresh())['account_status'], 'disabled')
        self.assertEqual(self.login()[1].status_code, 403)                            # is_active=False is "deactivated", not "not activated yet"


class SuperuserApprovalTests(_ImportCase):
    """A superuser (the main admin) can see and approve a submitted onboarding, whether or not the employee has set a password yet."""

    def setUp(self):
        super().setUp()
        Company.objects.create(company_name='Test Co', portal_url='https://aira.nxsys.in')
        with mock.patch(DELAY), mock.patch(SMTP, smtp_to_outbox):
            self.assertEqual(self.commit(self.hr, [self.row(1)]).status_code, 201)
        self.employee = User.objects.get(email='asha1@import.test')

    def test_the_superuser_sees_a_submitted_onboarding_in_the_approvals_list(self):
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
        response = self.client_for(self.admin).get('/api/onboarding/approvals/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(self.employee.email, str(response.data))

    def test_the_superuser_can_approve_even_if_the_employee_has_not_set_a_password_yet(self):
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client_for(self.admin).post(f'/api/onboarding/approvals/{self.employee.pk}/', {'decision': 'approve'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.onboarding_status, User.ONBOARDING_COMPLETE)
        self.assertIsNone(self.employee.account_activated_at)          # approval alone does not activate: the password link does

    def test_nothing_can_be_approved_before_the_employee_submits(self):
        response = self.client_for(self.admin).post(f'/api/onboarding/approvals/{self.employee.pk}/', {'decision': 'approve'}, format='json')
        self.assertEqual((response.status_code, self.employee.onboarding_status), (400, 'pending'))
        self.assertIn('not submitted', response.data['message'])
