"""Regression tests for the bugs fixed in the 2026-07-22 engineering audit."""
from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
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


class HRDecisionTests(TestCase):
    """CandidateHRDecisionView.patch() — approving a selected candidate with
    a linked portal account. Previously named HRDecisionAssessmentAssignmentTests
    and included default-assessment auto-assignment coverage; that behavior
    was removed (assessments are opt-in per hire now, not automatic — see
    the assessment-removal work across onboarding_approval.py,
    views_hire_complete.py, employees_list.py and this view), so the tests
    that exercised it are gone too. The reapprove-is-a-no-op regression
    below is unrelated to assessments and still applies."""

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
        _login(self.client, 'hrdecision@test.com')

    def test_approve_selected_candidate_succeeds(self):
        resp = self.client.patch(
            reverse('candidate-hr-decision', kwargs={'pk': self.candidate.pk}),
            {'decision': 'approve'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_reapproving_an_already_approved_candidate_is_rejected_not_repeated(self):
        """Regression test: candidate.status never changes on this endpoint
        (stays STATUS_SELECTED — only hr_approved flips), so retrying an
        approve after it already succeeded used to silently re-match the
        same query and repeat every candidate-facing side effect (a second
        "you're approved" email, a duplicate CandidateLog entry). Confirms a
        retry is now a no-op 409 instead."""
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


class CandidatePortalOnboardingTests(TestCase):
    """Selected interview candidates use the self-service onboarding path."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        recruiter_role = make_role(
            'portal_recruiter',
            permission_codenames=['recruitment.edit'],
        )
        self.recruiter = make_user(
            'portal-recruiter@test.com', role=recruiter_role,
        )
        self.candidate = Candidate.objects.create(
            name='Interview Candidate', email='interview.candidate@test.com',
            position_applied='QA Engineer', status=Candidate.STATUS_SELECTED,
        )
        _login(self.client, self.recruiter.email)

    def test_selected_candidate_receives_self_service_onboarding_account(self):
        response = self.client.post(
            reverse('candidate-send-portal-login', kwargs={'pk': self.candidate.pk}),
            {}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.candidate.refresh_from_db()
        portal_user = self.candidate.portal_user
        self.assertIsNotNone(portal_user)
        self.assertTrue(portal_user.requires_self_service_onboarding)
        self.assertEqual(portal_user.onboarding_status, User.ONBOARDING_PENDING)
        self.assertTrue(portal_user.must_change_password)


class CandidateCreateValidationTests(TestCase):
    """Covers CandidateCreateSerializer's field validation and the
    interview-slot conflict check — neither had any prior test coverage."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('recruiter_test', permission_codenames=['recruitment.create', 'settings.edit'])
        self.user = make_user('recruiter@test.com', role=role, password='TestPass123!')
        _login(self.client, 'recruiter@test.com')

        from apps.branch.models import Branch, City, State
        state, _ = State.objects.get_or_create(name='Telangana')
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch, _ = Branch.objects.get_or_create(
            branch_code='RCT', defaults={'branch_name': 'Recruitment Test Branch', 'city': city, 'state': state},
        )
        self.interviewer = make_user('interviewer@test.com', role=make_role('interviewer_test'), password='TestPass123!')

    def _create(self, **overrides):
        import datetime
        payload = {
            'name': 'Priya Sharma', 'email': 'priya.sharma@test.com',
            'phone': '+919876543210', 'position_applied': 'Backend Engineer',
            'branch': self.branch.id,
        }
        payload.update(overrides)
        return self.client.post(reverse('candidate-list-create'), payload, format='json')

    def test_valid_candidate_created(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_name_with_digits_rejected(self):
        resp = self._create(name='Priya123')
        self.assertEqual(resp.status_code, 400)

    def test_name_with_symbols_rejected(self):
        resp = self._create(name='Priya@Sharma')
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_email_rejected(self):
        first = self._create()
        self.assertEqual(first.status_code, 201, first.data)
        second = self._create(name='Another Person')
        self.assertEqual(second.status_code, 400)
        self.assertIn('already exists', second.data['message'])

    def test_malformed_phone_rejected(self):
        resp = self._create(phone='98-76-CALL-ME')
        self.assertEqual(resp.status_code, 400)

    def test_phone_too_short_rejected(self):
        resp = self._create(phone='12345')
        self.assertEqual(resp.status_code, 400)

    def test_position_with_digits_rejected(self):
        resp = self._create(position_applied='Engineer2')
        self.assertEqual(resp.status_code, 400)

    def test_past_interview_date_rejected(self):
        import datetime
        resp = self._create(interview_date=(datetime.date.today() - datetime.timedelta(days=1)).isoformat())
        self.assertEqual(resp.status_code, 400)

    def test_notes_over_2000_chars_rejected(self):
        resp = self._create(notes='x' * 2001)
        self.assertEqual(resp.status_code, 400)

    def test_double_booked_interviewer_rejected(self):
        import datetime
        interview_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        first = self._create(
            interview_date=interview_date, interview_time='10:00:00', interviewer=self.interviewer.id,
        )
        self.assertEqual(first.status_code, 201, first.data)
        second = self._create(
            name='Second Candidate', email='second@test.com',
            interview_date=interview_date, interview_time='10:00:00', interviewer=self.interviewer.id,
        )
        self.assertEqual(second.status_code, 400)
        self.assertIn('already interviewing', second.data['message'])

    def test_same_interviewer_different_time_is_allowed(self):
        import datetime
        interview_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        first = self._create(
            interview_date=interview_date, interview_time='10:00:00', interviewer=self.interviewer.id,
        )
        self.assertEqual(first.status_code, 201, first.data)
        second = self._create(
            name='Second Candidate', email='second@test.com',
            interview_date=interview_date, interview_time='11:00:00', interviewer=self.interviewer.id,
        )
        self.assertEqual(second.status_code, 201, second.data)


class CandidateListViewRegressionTests(TestCase):
    """Regression test for CandidateListCreateView.get's NameError:
    'CandidateStatusView' is not defined — caught live via the dev server
    log, not by an existing test. candidates_core.py referenced a class
    defined in the sibling candidate_status.py module without importing it;
    worked by accident whenever views/__init__.py's `from .candidate_status
    import *` had already run and left the name in sys.modules' shared
    state for some code paths, but not for a direct, fresh request."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('recruiter_list_test', permission_codenames=['recruitment.view'])
        self.user = make_user('recruiter-list@test.com', role=role, password='TestPass123!')
        _login(self.client, 'recruiter-list@test.com')

    def test_candidate_list_returns_status_choices_without_crashing(self):
        resp = self.client.get(reverse('candidate-list-create'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('status_choices', resp.data['data'])
        self.assertTrue(len(resp.data['data']['status_choices']) > 0)
