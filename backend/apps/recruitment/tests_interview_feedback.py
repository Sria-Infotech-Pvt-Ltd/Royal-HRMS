"""
HR-led recruitment: interviewer feedback, the status flow built on it, and who is told about what.

  - an interviewer sees and acts on only the interviews assigned to them;
  - HR reads all feedback and a candidate cannot be Selected without at least one entry;
  - statuses move in a fixed order (no jump to Selected without an interview);
  - the interviewer receives the scheduling email, and candidate emails come from the acting HR user (Reply-To + contact).
"""
from __future__ import annotations

import datetime
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.recruitment.models import Candidate, CandidateEmail, CandidateLog, InterviewFeedback
from apps.recruitment.views.shared import (
    _fire_interview_date_emails_if_needed, _send_candidate_email, _send_interview_scheduled_email_general, _send_interview_scheduled_emails,
)

SHARED_SEND = 'apps.recruitment.views.shared.send_template_email'
GOOD = {'rating': 4, 'recommendation': 'recommend', 'comments': 'Strong on fundamentals and communicates clearly.'}


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class _FeedbackFixtures(TestCase):
    def setUp(self):
        cache.clear()
        self.hr = make_user('fb_hr@test.com', employee_id='FB001', full_name='Hema HR',
                            role=make_role('fb_hr', permission_codenames=['recruitment.view', 'recruitment.edit']))
        self.interviewer = make_user('fb_int1@test.com', employee_id='FB002', full_name='Ivan Interviewer', role=make_role('fb_plain'))
        self.other_interviewer = make_user('fb_int2@test.com', employee_id='FB003', full_name='Olga Other', role=make_role('fb_plain2'))
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        self.candidate = self._candidate('mine', self.interviewer, tomorrow)
        self.others_candidate = self._candidate('theirs', self.other_interviewer, tomorrow)

    def _candidate(self, tag: str, interviewer: User, day, status=Candidate.STATUS_INTERVIEW_SCHEDULED) -> Candidate:
        return Candidate.objects.create(
            name=f'Cand {tag}', email=f'fb_{tag}@test.com', phone='9000000000', position_applied='Engineer', status=status,
            interviewer=interviewer, interview_date=day, interview_time=datetime.time(11, 0), interview_mode=Candidate.MODE_VIDEO_CALL,
            meeting_link='https://meet.example.com/abc',
        )

    def _submit(self, user: User, candidate: Candidate, body: dict | None = None):
        return _client(user).put(reverse('my-interview-feedback', args=[candidate.pk]), body or GOOD, format='json')


class InterviewerAccessTests(_FeedbackFixtures):
    def test_an_interviewer_sees_only_their_assigned_interviews(self):
        rows = _client(self.interviewer).get(reverse('my-interviews')).json()['data']['results']
        self.assertEqual([row['id'] for row in rows], [self.candidate.pk])

    def test_the_interview_shows_the_schedule_but_no_contact_details(self):
        row = _client(self.interviewer).get(reverse('my-interviews')).json()['data']['results'][0]
        self.assertEqual((row['candidate_name'], row['position_applied']), ('Cand mine', 'Engineer'))
        self.assertIn('interview_time', row)
        self.assertNotIn('email', row)
        self.assertNotIn('phone', row)
        self.assertNotIn('9000000000', str(row))

    def test_someone_who_is_nobodys_interviewer_sees_an_empty_list(self):
        self.assertEqual(_client(self.hr).get(reverse('my-interviews')).json()['data']['results'], [])

    def test_an_interviewer_cannot_read_or_submit_feedback_for_someone_elses_candidate(self):
        url = reverse('my-interview-feedback', args=[self.others_candidate.pk])
        self.assertEqual(_client(self.interviewer).get(url).status_code, 404)
        self.assertEqual(self._submit(self.interviewer, self.others_candidate).status_code, 404)
        self.assertFalse(InterviewFeedback.objects.exists())

    def test_an_interviewer_cannot_use_the_hr_feedback_or_candidate_endpoints(self):
        self.assertEqual(_client(self.interviewer).get(reverse('candidate-feedback', args=[self.candidate.pk])).status_code, 403)
        self.assertEqual(_client(self.interviewer).get(reverse('candidate-list-create')).status_code, 403)

    def test_a_deactivated_interviewers_assignment_is_not_reachable_by_anyone_else(self):
        self.assertEqual(self._submit(self.other_interviewer, self.candidate).status_code, 404)


class SubmittingFeedbackTests(_FeedbackFixtures):
    def test_an_interviewer_submits_structured_feedback(self):
        response = self._submit(self.interviewer, self.candidate)
        self.assertEqual(response.status_code, 201, response.json())
        entry = InterviewFeedback.objects.get(candidate=self.candidate)
        self.assertEqual((entry.rating, entry.recommendation, entry.interviewer_id), (4, 'recommend', self.interviewer.pk))
        self.assertEqual(entry.interviewer_name, 'Ivan Interviewer')
        self.assertEqual(response.json()['data']['my_feedback']['rating'], 4)

    def test_the_first_feedback_moves_the_candidate_to_interview_done(self):
        self._submit(self.interviewer, self.candidate)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.STATUS_INTERVIEW_DONE)
        self.assertTrue(CandidateLog.objects.filter(candidate=self.candidate, title='Interview feedback submitted').exists())

    def test_submitting_again_updates_the_same_entry(self):
        self._submit(self.interviewer, self.candidate)
        again = self._submit(self.interviewer, self.candidate, {**GOOD, 'rating': 2, 'recommendation': 'not_recommend'})
        self.assertEqual(again.status_code, 200)
        self.assertEqual(InterviewFeedback.objects.filter(candidate=self.candidate).count(), 1)
        self.assertEqual(InterviewFeedback.objects.get(candidate=self.candidate).rating, 2)

    def test_rating_recommendation_and_comments_are_each_required(self):
        for field, bad in (('rating', 0), ('rating', 6), ('rating', 'x'), ('recommendation', 'maybe'), ('recommendation', ''), ('comments', 'short'), ('comments', '')):
            response = self._submit(self.interviewer, self.candidate, {**GOOD, field: bad})
            self.assertEqual(response.status_code, 400, (field, bad))
            self.assertIn(field, response.json()['data'])
        self.assertFalse(InterviewFeedback.objects.exists())

    def test_feedback_is_closed_once_hr_has_decided(self):
        for decided in (Candidate.STATUS_SELECTED, Candidate.STATUS_REJECTED, Candidate.STATUS_CONVERTED):
            Candidate.objects.filter(pk=self.candidate.pk).update(status=decided)
            self.assertEqual(self._submit(self.interviewer, self.candidate).status_code, 409, decided)

    def test_feedback_cannot_be_given_before_an_interview_is_scheduled(self):
        Candidate.objects.filter(pk=self.candidate.pk).update(status=Candidate.STATUS_PENDING)
        self.assertEqual(self._submit(self.interviewer, self.candidate).status_code, 409)


class HrReadsFeedbackTests(_FeedbackFixtures):
    def test_hr_sees_every_interviewers_feedback_with_a_summary(self):
        second = self._candidate('x', self.other_interviewer, datetime.date.today())
        InterviewFeedback.objects.create(candidate=second, interviewer=self.other_interviewer, interviewer_name='Olga Other', **GOOD)
        self._submit(self.interviewer, self.candidate)
        InterviewFeedback.objects.create(candidate=self.candidate, interviewer=self.other_interviewer, interviewer_name='Olga Other',
                                         rating=2, recommendation='hold', comments='Mixed signals on system design.')
        data = _client(self.hr).get(reverse('candidate-feedback', args=[self.candidate.pk])).json()['data']
        self.assertEqual({row['interviewer'] for row in data['feedback']}, {'Ivan Interviewer', 'Olga Other'})
        self.assertEqual(data['summary'], {'count': 2, 'average_rating': 3.0, 'recommend': 1, 'undecided': 1, 'not_recommend': 0})

    def test_hr_without_recruitment_view_cannot_read_it(self):
        plain = make_user('fb_plain@test.com', employee_id='FB009', role=make_role('fb_nothing'))
        self.assertEqual(_client(plain).get(reverse('candidate-feedback', args=[self.candidate.pk])).status_code, 403)


@patch('apps.recruitment.views.candidate_status._send_candidate_email', return_value=CandidateEmail.STATUS_SENT)
class StatusFlowTests(_FeedbackFixtures):
    def _move(self, candidate: Candidate, status_value: str):
        return _client(self.hr).patch(reverse('candidate-status', args=[candidate.pk]), {'status': status_value}, format='json')

    def test_selected_needs_at_least_one_interviewer_feedback(self, _mail):
        Candidate.objects.filter(pk=self.candidate.pk).update(status=Candidate.STATUS_INTERVIEW_DONE)
        refused = self._move(self.candidate, Candidate.STATUS_SELECTED)
        self.assertEqual(refused.status_code, 400)
        self.assertIn('feedback', refused.json()['message'])
        InterviewFeedback.objects.create(candidate=self.candidate, interviewer=self.interviewer, interviewer_name='Ivan', **GOOD)
        self.assertEqual(self._move(self.candidate, Candidate.STATUS_SELECTED).status_code, 200)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, Candidate.STATUS_SELECTED)

    def test_a_candidate_cannot_jump_to_selected_without_an_interview(self, _mail):
        for before in (Candidate.STATUS_PENDING, Candidate.STATUS_SCREENING, Candidate.STATUS_INTERVIEW_SCHEDULED):
            Candidate.objects.filter(pk=self.candidate.pk).update(status=before)
            InterviewFeedback.objects.get_or_create(candidate=self.candidate, interviewer=self.interviewer, defaults={'interviewer_name': 'I', **GOOD})
            response = self._move(self.candidate, Candidate.STATUS_SELECTED)
            self.assertEqual(response.status_code, 400, before)
            self.assertIn('Interview Done', response.json()['message'])

    def test_the_allowed_steps_in_order(self, _mail):
        for before, after in ((Candidate.STATUS_PENDING, Candidate.STATUS_SCREENING), (Candidate.STATUS_SCREENING, Candidate.STATUS_INTERVIEW_SCHEDULED),
                              (Candidate.STATUS_INTERVIEW_SCHEDULED, Candidate.STATUS_INTERVIEW_DONE)):
            Candidate.objects.filter(pk=self.candidate.pk).update(status=before)
            self.assertEqual(self._move(self.candidate, after).status_code, 200, (before, after))

    def test_a_candidate_can_be_rejected_at_any_stage_before_conversion(self, _mail):
        for before in (Candidate.STATUS_PENDING, Candidate.STATUS_SCREENING, Candidate.STATUS_INTERVIEW_SCHEDULED, Candidate.STATUS_INTERVIEW_DONE, Candidate.STATUS_SELECTED):
            Candidate.objects.filter(pk=self.candidate.pk).update(status=before)
            self.assertEqual(self._move(self.candidate, Candidate.STATUS_REJECTED).status_code, 200, before)

    def test_backward_and_repeated_moves_are_refused(self, _mail):
        Candidate.objects.filter(pk=self.candidate.pk).update(status=Candidate.STATUS_SELECTED)
        self.assertEqual(self._move(self.candidate, Candidate.STATUS_INTERVIEW_DONE).status_code, 400)
        self.assertEqual(self._move(self.candidate, Candidate.STATUS_SELECTED).status_code, 400)
        Candidate.objects.filter(pk=self.candidate.pk).update(status=Candidate.STATUS_REJECTED)
        self.assertEqual(self._move(self.candidate, Candidate.STATUS_PENDING).status_code, 400)

    def test_a_converted_candidate_cannot_be_moved(self, _mail):
        Candidate.objects.filter(pk=self.candidate.pk).update(status=Candidate.STATUS_CONVERTED)
        self.assertEqual(self._move(self.candidate, Candidate.STATUS_REJECTED).status_code, 400)


class InterviewAndCandidateEmailTests(_FeedbackFixtures):
    def _calls(self, sender):
        return {call.kwargs['recipient_email']: call.kwargs for call in sender.call_args_list}

    def test_the_interviewer_receives_the_scheduling_email_with_the_hr_contact(self):
        with patch(SHARED_SEND) as sender:
            _send_interview_scheduled_email_general(self.candidate, self.hr)
        calls = self._calls(sender)
        self.assertEqual(set(calls), {self.candidate.email, self.interviewer.email})
        interviewer_mail = calls[self.interviewer.email]
        self.assertEqual(interviewer_mail['template_name'], 'interview_scheduled_interviewer')
        self.assertEqual(interviewer_mail['context']['interviewer_name'], 'Ivan Interviewer')
        self.assertEqual(interviewer_mail['reply_to'], 'fb_hr@test.com')
        self.assertEqual(calls[self.candidate.email]['reply_to'], 'fb_hr@test.com')
        self.assertEqual(calls[self.candidate.email]['hr_contact'], ('Hema HR', 'fb_hr@test.com'))

    def test_a_referred_candidates_interview_also_notifies_the_interviewer(self):
        Candidate.objects.filter(pk=self.candidate.pk).update(referral_by=self.hr)
        candidate = Candidate.objects.select_related('interviewer', 'referral_by').get(pk=self.candidate.pk)
        with patch(SHARED_SEND) as sender:
            _send_interview_scheduled_emails(candidate, self.hr)
        self.assertIn(self.interviewer.email, self._calls(sender))

    def test_no_interviewer_means_no_interviewer_email(self):
        Candidate.objects.filter(pk=self.candidate.pk).update(interviewer=None)
        candidate = Candidate.objects.get(pk=self.candidate.pk)
        with patch(SHARED_SEND) as sender:
            _send_interview_scheduled_email_general(candidate, self.hr)
        self.assertEqual(set(self._calls(sender)), {candidate.email})

    def test_the_interview_template_for_interviewers_exists(self):
        from apps.accounts.models import EmailTemplate
        names = set(EmailTemplate.objects.filter(name__in=['interview_scheduled_interviewer', 'candidate_onboarding_link']).values_list('name', flat=True))
        self.assertEqual(names, {'interview_scheduled_interviewer', 'candidate_onboarding_link'})

    def test_candidate_status_emails_come_from_the_acting_hr_user(self):
        with patch(SHARED_SEND) as sender:
            _send_candidate_email(self.candidate, 'candidate_selected', self.hr)
        kwargs = sender.call_args.kwargs
        self.assertEqual(kwargs['reply_to'], 'fb_hr@test.com')
        self.assertEqual(kwargs['hr_contact'], ('Hema HR', 'fb_hr@test.com'))

    def test_a_newly_assigned_interviewer_is_told_even_when_the_time_did_not_change(self):
        candidate = self.candidate
        with patch('apps.recruitment.tasks.send_interview_scheduled_emails_task.apply_async') as queue, self.captureOnCommitCallbacks(execute=True):
            _fire_interview_date_emails_if_needed(candidate, candidate.interview_date, candidate.interview_time, candidate.meeting_link,
                                                  actor=self.hr, old_interviewer_id=self.other_interviewer.pk)
        queue.assert_called_once()
        self.assertEqual(queue.call_args.kwargs['args'], [candidate.pk, self.hr.pk])

    def test_nothing_is_sent_when_nothing_about_the_interview_changed(self):
        candidate = self.candidate
        with patch('apps.recruitment.tasks.send_interview_scheduled_emails_task.apply_async') as queue, self.captureOnCommitCallbacks(execute=True):
            _fire_interview_date_emails_if_needed(candidate, candidate.interview_date, candidate.interview_time, candidate.meeting_link,
                                                  actor=self.hr, old_interviewer_id=candidate.interviewer_id)
        queue.assert_not_called()
