"""
Permission-denial paths in the recruitment views.

`_DENIED` was used by five view modules (candidate_portal, candidate_review_email, candidate_status, referrals and the
shared portal-revoke helper) but was never defined or imported there, so every refusal raised a NameError (HTTP 500) instead
of answering 403. These tests drive each denial path and prove it (1) answers 403 with the standard message, (2) performs no
action - no mail sent, no audit/log rows, no new users - and (3) leaves every candidate, bonus and portal account unchanged.
"""
from __future__ import annotations

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User
from apps.recruitment.models import Candidate, CandidateEmail, CandidateLog, ReferralBonus

DENIED_MESSAGE = 'You do not have permission to perform this action.'
PASSWORD = 'TestPass123!'
USER_BRANCH = 'Denial Test Branch'


def _snapshot() -> dict:
    """Everything a denied request must leave untouched."""
    return {
        'candidates': list(Candidate.objects.order_by('pk').values()),
        'bonuses': list(ReferralBonus.objects.order_by('pk').values()),
        'users': list(User.objects.order_by('pk').values_list('pk', 'is_active', 'password', 'email')),
        'audit_logs': AuditLog.objects.count(),
        'candidate_logs': CandidateLog.objects.count(),
        'candidate_emails': CandidateEmail.objects.count(),
    }


class _DenialFixtures(TestCase):
    def setUp(self):
        cache.clear()
        self.nobody = make_user('denial_nobody@test.com', role=make_role('denial_plain'), password=PASSWORD)
        # Holds the recruitment keys but NOT approve, and is bound to a branch the candidate is not in.
        self.branch_bound = make_user(
            'denial_branch@test.com', branch=USER_BRANCH, password=PASSWORD,
            role=make_role('denial_branch_role', permission_codenames=['recruitment.view', 'recruitment.edit']),
        )
        self.referrer = make_user('denial_referrer@test.com', role=make_role('denial_referrer_role'), password=PASSWORD)
        portal_user = make_user('denial_portal@test.com', role=make_role('denial_portal_role'), password=PASSWORD)
        self.candidate = Candidate.objects.create(
            name='Denial Candidate', email='denial.candidate@test.com', position_applied='Engineer',
            status=Candidate.STATUS_SELECTED, portal_user=portal_user, portal_credentials_sent=True,
            referral_by=self.referrer,
        )  # no branch: outside the branch-bound user's branch
        self.bonus = ReferralBonus.objects.create(candidate=self.candidate, referrer=self.referrer)

    def _call(self, user, method: str, url_name: str, kwargs: dict, body: dict | None = None):
        client = APIClient()
        client.force_authenticate(user=user)
        url = reverse(url_name, kwargs=kwargs)
        return getattr(client, method)(url, body or {}, format='json')

    def _assert_denied(self, user, method: str, url_name: str, kwargs: dict, body: dict | None = None):
        before, outbox_before = _snapshot(), len(mail.outbox)
        response = self._call(user, method, url_name, kwargs, body)
        label = f'{method.upper()} {url_name}'
        self.assertEqual(response.status_code, 403, f'{label}: {getattr(response, "data", None)}')
        self.assertEqual(response.json()['status'], 'error', label)
        self.assertEqual(response.json()['message'], DENIED_MESSAGE, label)
        self.assertEqual(_snapshot(), before, f'{label}: a denied request changed data')
        self.assertEqual(len(mail.outbox), outbox_before, f'{label}: a denied request sent mail')


class MissingPermissionDenialTests(_DenialFixtures):
    """The caller lacks the recruitment key the view requires."""

    def _cand(self) -> dict:
        return {'pk': self.candidate.pk}

    def test_candidate_portal_views_refuse_a_caller_without_recruitment_permission(self):
        for method, name in [('post', 'candidate-send-portal-login'), ('get', 'candidate-send-portal-login'),
                             ('post', 'candidate-resend-portal-login'), ('get', 'candidate-resend-portal-login'),
                             ('delete', 'candidate-send-portal-login'), ('delete', 'candidate-resend-portal-login')]:
            with self.subTest(method=method, view=name):
                self._assert_denied(self.nobody, method, name, self._cand())

    def test_candidate_review_email_views_refuse_a_caller_without_recruitment_permission(self):
        for method, name, kwargs in [('get', 'candidate-review', {}), ('get', 'candidate-email-logs', {}),
                                     ('get', 'candidate-stats', {}),
                                     ('post', 'candidate-send-email', self._cand())]:
            with self.subTest(method=method, view=name):
                self._assert_denied(self.nobody, method, name, kwargs, {'subject': 's', 'body': 'b'} if method == 'post' else None)

    def test_candidate_status_views_refuse_a_caller_without_recruitment_permission(self):
        cases = [('get', 'candidate-status-choices', {}, None),
                 ('patch', 'candidate-status', self._cand(), {'status': Candidate.STATUS_REJECTED}),
                 ('get', 'candidate-status', self._cand(), None), ('delete', 'candidate-status', self._cand(), None),
                 ('patch', 'candidate-hr-decision', self._cand(), {'decision': 'approved'}),
                 ('get', 'candidate-hr-decision', self._cand(), None), ('delete', 'candidate-hr-decision', self._cand(), None)]
        for method, name, kwargs, body in cases:
            with self.subTest(method=method, view=name):
                self._assert_denied(self.nobody, method, name, kwargs, body)

    def test_hr_decision_needs_the_approve_key_not_just_view_and_edit(self):
        for method in ('patch', 'delete'):
            with self.subTest(method=method):
                self._assert_denied(self.branch_bound, method, 'candidate-hr-decision', self._cand(), {'decision': 'approved'})

    def test_referral_bonus_views_refuse_a_caller_without_recruitment_edit(self):
        bonus = {'pk': self.bonus.pk}
        for method, name, body in [('patch', 'referral-bonus-detail', {'bonus_amount': 1}),
                                   ('post', 'referral-bonus-approve', {}), ('post', 'referral-bonus-pay', {})]:
            with self.subTest(method=method, view=name):
                self._assert_denied(self.nobody, method, name, bonus, body)

    def test_a_referral_bonus_can_only_be_read_by_its_referrer_or_recruitment_staff(self):
        self._assert_denied(self.nobody, 'get', 'referral-bonus-detail', {'pk': self.bonus.pk})
        own = self._call(self.referrer, 'get', 'referral-bonus-detail', {'pk': self.bonus.pk})
        self.assertEqual(own.status_code, 200, 'the referrer must still read their own bonus')


class BranchScopeDenialTests(_DenialFixtures):
    """The caller holds the key but the candidate is outside their branch."""

    def test_portal_views_refuse_a_candidate_outside_the_callers_branch(self):
        cand = {'pk': self.candidate.pk}
        for method, name in [('post', 'candidate-send-portal-login'), ('get', 'candidate-send-portal-login'),
                             ('post', 'candidate-resend-portal-login'), ('get', 'candidate-resend-portal-login'),
                             ('delete', 'candidate-send-portal-login'), ('delete', 'candidate-resend-portal-login')]:
            with self.subTest(method=method, view=name):
                self._assert_denied(self.branch_bound, method, name, cand)

    def test_status_and_decision_views_refuse_a_candidate_outside_the_callers_branch(self):
        cand = {'pk': self.candidate.pk}
        for method, name, body in [('patch', 'candidate-status', {'status': Candidate.STATUS_REJECTED}),
                                   ('get', 'candidate-status', None), ('get', 'candidate-hr-decision', None)]:
            with self.subTest(method=method, view=name):
                self._assert_denied(self.branch_bound, method, name, cand, body)

    def test_the_portal_account_stays_active_after_a_refused_revoke(self):
        self._call(self.branch_bound, 'delete', 'candidate-send-portal-login', {'pk': self.candidate.pk})
        self.candidate.refresh_from_db()
        self.candidate.portal_user.refresh_from_db()
        self.assertTrue(self.candidate.portal_credentials_sent)
        self.assertTrue(self.candidate.portal_user.is_active)
