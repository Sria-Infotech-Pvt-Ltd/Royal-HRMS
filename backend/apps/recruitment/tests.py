"""Regression tests for the bugs fixed in the 2026-07-22 engineering audit."""
from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.recruitment.models import Candidate, ReferralBonus


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class ReferralBonusDecimalTests(TestCase):
    """Regression test: ReferralBonusDetailView/ApproveView assigned a raw
    float(request.data['bonus_amount']) onto a DecimalField. Confirms the
    fix stores a proper Decimal instead of a float.
    """

    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        hr_role = make_role('hr', permission_codenames=['recruitment.edit', 'recruitment.view'])
        self.hr_user = make_user('hrrecruit@test.com', role=hr_role, password='TestPass123!')
        self.referrer = make_user('referrer@test.com', role=make_role('employee'), password='TestPass123!')

        self.candidate = Candidate.objects.create(
            name='Jane Candidate', email='jane@candidate.test',
            position_applied='Backend Engineer',
            referral_by=self.referrer,
        )
        self.bonus = ReferralBonus.objects.create(
            candidate=self.candidate, referrer=self.referrer,
        )
        _login(self.client, 'hrrecruit@test.com')

    def test_patch_bonus_amount_as_json_float_stores_decimal(self):
        resp = self.client.patch(
            reverse('referral-bonus-detail', kwargs={'pk': self.bonus.pk}),
            {'bonus_amount': 5000.50},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bonus.refresh_from_db()
        self.assertEqual(self.bonus.bonus_amount, Decimal('5000.50'))
        self.assertIsInstance(self.bonus.bonus_amount, Decimal)

    def test_approve_with_bonus_amount_as_json_float_stores_decimal(self):
        resp = self.client.post(
            reverse('referral-bonus-approve', kwargs={'pk': self.bonus.pk}),
            {'bonus_amount': 3333.33},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bonus.refresh_from_db()
        self.assertEqual(self.bonus.bonus_amount, Decimal('3333.33'))
        self.assertEqual(self.bonus.status, ReferralBonus.STATUS_APPROVED)

    def test_negative_bonus_amount_rejected(self):
        resp = self.client.patch(
            reverse('referral-bonus-detail', kwargs={'pk': self.bonus.pk}),
            {'bonus_amount': -100},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


class HRDecisionAssessmentAssignmentTests(TestCase):
    """Regression test: CandidateHRDecisionView.patch() referenced
    AssessmentItem.pass_score, a field removed by migration
    0006_assessment_pass_percentage_remove_item_pass_score — every approval
    of a selected candidate with a linked portal account and an active
    default assessment crashed with a FieldError partway through (after
    hr_approved was already saved and the welcome email already sent).
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr', permission_codenames=['recruitment.approve', 'recruitment.view'])
        self.hr_user = make_user('hrdecision@test.com', role=hr_role, password='TestPass123!')
        portal_user = make_user('selectedcandidate@test.com', role=None, password='TestPass123!')

        self.candidate = Candidate.objects.create(
            name='Selected Candidate', email='selectedcandidate@test.com',
            position_applied='Engineer', status=Candidate.STATUS_SELECTED,
            portal_user=portal_user,
        )

        from apps.assessments.models import Assessment, AssessmentItem
        assessment = Assessment.objects.create(
            title='Default Screening', is_active=True, is_default=True,
        )
        AssessmentItem.objects.create(
            assessment=assessment, item_type=AssessmentItem.TYPE_QUIZ,
            title='Q1', question='2+2?', option_a='3', option_b='4',
            correct_option='b',
        )
        AssessmentItem.objects.create(
            assessment=assessment, item_type=AssessmentItem.TYPE_QUIZ,
            title='Q2', question='3+3?', option_a='6', option_b='7',
            correct_option='a',
        )
        _login(self.client, 'hrdecision@test.com')

    def test_approve_selected_candidate_assigns_assessment_without_crashing(self):
        resp = self.client.patch(
            reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}),
            {'decision': 'approve'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        from apps.assessments.models import CandidateAssignment
        assignment = CandidateAssignment.objects.get(candidate=self.candidate)
        self.assertEqual(assignment.max_score, 2)

    def test_reapproving_an_already_approved_candidate_is_rejected_not_repeated(self):
        """Regression test: candidate.status never changes on this endpoint
        (stays STATUS_SELECTED — only hr_approved flips), so retrying an
        approve after it already succeeded used to silently re-match the
        same query and repeat every candidate-facing side effect (a second
        "you're approved" email, a duplicate CandidateLog entry, a second
        attempt at assessment assignment). Confirms a retry is now a no-op
        409 instead."""
        first = self.client.patch(
            reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}),
            {'decision': 'approve'}, format='json',
        )
        self.assertEqual(first.status_code, 200, first.data)

        from apps.recruitment.models import CandidateLog
        log_count_after_first = CandidateLog.objects.filter(candidate=self.candidate).count()

        second = self.client.patch(
            reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}),
            {'decision': 'approve'}, format='json',
        )
        self.assertEqual(second.status_code, 409, second.data)
        self.assertEqual(
            CandidateLog.objects.filter(candidate=self.candidate).count(),
            log_count_after_first,
            'a rejected retry must not create any new log entries (or, by the same logic, resend any email)',
        )

    def test_approval_is_atomic_a_failure_during_assessment_assignment_rolls_back_hr_approved(self):
        """Regression test: previously, candidate.hr_approved=True and the
        "HR Approved" CandidateLog entry committed independently of the
        assessment-assignment step further down, which had no try/except at
        all — a DB hiccup or a bad Assessment/AssessmentItem row there would
        500 the request *after* the approval had already been saved, with
        nothing to roll it back. Forces exactly that failure (a DB-level
        error inside CandidateAssignment.get_or_create) and confirms the
        whole approve action — including hr_approved and every CandidateLog
        entry — is rolled back together, not left half-applied."""
        from unittest.mock import patch as mock_patch

        with mock_patch(
            'apps.assessments.models.CandidateAssignment.objects.get_or_create',
            side_effect=Exception('simulated DB failure'),
        ):
            resp = self.client.patch(
                reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}),
                {'decision': 'approve'}, format='json',
            )
        self.assertEqual(resp.status_code, 500)

        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.hr_approved, 'hr_approved must roll back when a later step in the same action fails')

        from apps.recruitment.models import CandidateLog
        self.assertEqual(
            CandidateLog.objects.filter(candidate=self.candidate).count(), 0,
            'no CandidateLog entry (HR Approved / onboarding email) should survive the rollback either',
        )

        # And a genuine retry (the transient failure is gone) succeeds cleanly —
        # confirms the rollback didn't leave the candidate stuck in a bad state.
        retry = self.client.patch(
            reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}),
            {'decision': 'approve'}, format='json',
        )
        self.assertEqual(retry.status_code, 200, retry.data)
