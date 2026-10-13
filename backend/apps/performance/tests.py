"""Regression tests for the Performance & Appraisals module — this app had
zero test coverage before this pass. Covers review-cycle date validation,
the single-active-cycle rule, and the self-review -> manager-review state
machine's ordering/lock rules.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.performance.models import PerformanceReview, ReviewCycle


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class ReviewCycleValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('perf_admin_test', permission_codenames=['performance.manage_cycles'])
        self.admin = make_user('perfadmin@test.com', role=role, password='TestPass123!')
        _login(self.client, 'perfadmin@test.com')

    def _payload(self, **overrides):
        payload = {
            'name': 'Q4 2026',
            'period_start': '2026-10-01', 'period_end': '2026-12-31',
            'self_review_due': '2026-12-15', 'manager_review_due': '2026-12-20',
        }
        payload.update(overrides)
        return payload

    def test_valid_cycle_created(self):
        resp = self.client.post(reverse('review-cycle-list'), self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_period_end_before_start_rejected(self):
        resp = self.client.post(reverse('review-cycle-list'), self._payload(
            period_start='2026-12-31', period_end='2026-10-01',
        ), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_period_end_equal_to_start_rejected(self):
        resp = self.client.post(reverse('review-cycle-list'), self._payload(
            period_start='2026-10-01', period_end='2026-10-01',
        ), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_self_review_due_after_period_end_rejected(self):
        resp = self.client.post(reverse('review-cycle-list'), self._payload(
            self_review_due='2027-01-15',
        ), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_manager_review_due_before_self_review_due_rejected(self):
        resp = self.client.post(reverse('review-cycle-list'), self._payload(
            self_review_due='2026-12-15', manager_review_due='2026-12-10',
        ), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_denied_without_permission(self):
        no_perm = make_user('noperm_perf@test.com', role=make_role('employee_perf_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.post(reverse('review-cycle-list'), self._payload(), format='json')
        self.assertEqual(resp.status_code, 403)

    def test_only_one_active_cycle_allowed(self):
        first = ReviewCycle.objects.create(
            name='Q3 2026', period_start=datetime.date(2026, 7, 1), period_end=datetime.date(2026, 9, 30),
            self_review_due=datetime.date(2026, 9, 15), manager_review_due=datetime.date(2026, 9, 20),
            status='active', created_by=self.admin,
        )
        second = ReviewCycle.objects.create(
            name='Q4 2026', period_start=datetime.date(2026, 10, 1), period_end=datetime.date(2026, 12, 31),
            self_review_due=datetime.date(2026, 12, 15), manager_review_due=datetime.date(2026, 12, 20),
            status='draft', created_by=self.admin,
        )
        resp = self.client.patch(reverse('review-cycle-detail', args=[second.id]), {'status': 'active'}, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertIn(first.name, resp.data['message'])

    def test_invalid_status_transition_rejected(self):
        cycle = ReviewCycle.objects.create(
            name='Q1 2027', period_start=datetime.date(2027, 1, 1), period_end=datetime.date(2027, 3, 31),
            self_review_due=datetime.date(2027, 3, 15), manager_review_due=datetime.date(2027, 3, 20),
            status='draft', created_by=self.admin,
        )
        resp = self.client.patch(reverse('review-cycle-detail', args=[cycle.id]), {'status': 'bogus'}, format='json')
        self.assertEqual(resp.status_code, 400)


class ReviewSubmissionFlowTests(TestCase):
    """Covers the self-review -> manager-review state machine: ordering
    (manager can't act first), locking (can't resubmit/re-edit after
    submission), and permission scoping (only the real reporting manager,
    or an HR user with performance.manage_cycles, can act on someone
    else's review)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        manager_role = make_role('perf_manager_test', can_manage_team=True)
        self.manager = make_user('perfmgr@test.com', role=manager_role, password='TestPass123!')
        self.employee = make_user(
            'perfemp@test.com', role=make_role('perf_employee_test'), password='TestPass123!',
            reporting_manager=self.manager,
        )
        self.cycle = ReviewCycle.objects.create(
            name='Active Cycle', period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 3, 31),
            self_review_due=datetime.date(2026, 3, 15), manager_review_due=datetime.date(2026, 3, 20),
            status='active', created_by=self.manager,
        )

    def test_employee_can_save_and_submit_self_review(self):
        _login(self.client, 'perfemp@test.com')
        save_resp = self.client.patch(reverse('my-review'), {'key_strengths': 'Delivery focus'}, format='json')
        self.assertEqual(save_resp.status_code, 200, save_resp.data)
        submit_resp = self.client.post(reverse('submit-my-review'))
        self.assertEqual(submit_resp.status_code, 200, submit_resp.data)

    def test_self_review_cannot_be_edited_after_submission(self):
        _login(self.client, 'perfemp@test.com')
        self.client.post(reverse('submit-my-review'))
        resp = self.client.patch(reverse('my-review'), {'key_strengths': 'Changed my mind'}, format='json')
        self.assertEqual(resp.status_code, 409)

    def test_self_review_cannot_be_submitted_twice(self):
        _login(self.client, 'perfemp@test.com')
        first = self.client.post(reverse('submit-my-review'))
        self.assertEqual(first.status_code, 200)
        second = self.client.post(reverse('submit-my-review'))
        self.assertEqual(second.status_code, 409)

    def test_manager_cannot_act_before_self_review_submitted(self):
        review = PerformanceReview.objects.create(employee=self.employee, cycle=self.cycle, manager=self.manager)
        _login(self.client, 'perfmgr@test.com')
        patch_resp = self.client.patch(reverse('manager-review-detail', args=[review.id]), {'manager_rating': '4'}, format='json')
        self.assertEqual(patch_resp.status_code, 409)
        submit_resp = self.client.post(reverse('submit-manager-review', args=[review.id]))
        self.assertEqual(submit_resp.status_code, 409)

    def test_manager_can_act_after_self_review_submitted(self):
        review = PerformanceReview.objects.create(
            employee=self.employee, cycle=self.cycle, manager=self.manager,
            self_submitted_at=datetime.datetime.now(datetime.timezone.utc),
        )
        _login(self.client, 'perfmgr@test.com')
        patch_resp = self.client.patch(reverse('manager-review-detail', args=[review.id]), {
            'manager_rating': '4', 'manager_notes': 'Solid quarter',
            'manager_development_plan': 'Mentor two juniors', 'manager_next_checkin': '2026-12-01',
        }, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        submit_resp = self.client.post(reverse('submit-manager-review', args=[review.id]))
        self.assertEqual(submit_resp.status_code, 200, submit_resp.data)

    def test_manager_review_cannot_be_submitted_twice(self):
        review = PerformanceReview.objects.create(
            employee=self.employee, cycle=self.cycle, manager=self.manager,
            self_submitted_at=datetime.datetime.now(datetime.timezone.utc),
        )
        _login(self.client, 'perfmgr@test.com')
        self.client.patch(reverse('manager-review-detail', args=[review.id]), {
            'manager_rating': '4', 'manager_notes': 'Solid quarter',
            'manager_development_plan': 'Mentor two juniors', 'manager_next_checkin': '2026-12-01',
        }, format='json')
        first = self.client.post(reverse('submit-manager-review', args=[review.id]))
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.post(reverse('submit-manager-review', args=[review.id]))
        self.assertEqual(second.status_code, 409)

    def test_non_manager_cannot_act_on_someone_elses_review(self):
        review = PerformanceReview.objects.create(
            employee=self.employee, cycle=self.cycle, manager=self.manager,
            self_submitted_at=datetime.datetime.now(datetime.timezone.utc),
        )
        stranger = make_user('stranger_perf@test.com', role=make_role('stranger_perf_role'), password='TestPass123!')
        self.client.force_authenticate(user=stranger)
        resp = self.client.patch(reverse('manager-review-detail', args=[review.id]), {'manager_rating': '5'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_hr_with_manage_cycles_can_act_on_any_review(self):
        review = PerformanceReview.objects.create(
            employee=self.employee, cycle=self.cycle, manager=self.manager,
            self_submitted_at=datetime.datetime.now(datetime.timezone.utc),
        )
        hr_role = make_role('perf_hr_test', permission_codenames=['performance.manage_cycles'])
        hr_user = make_user('perfhr@test.com', role=hr_role, password='TestPass123!')
        self.client.force_authenticate(user=hr_user)
        resp = self.client.patch(reverse('manager-review-detail', args=[review.id]), {'manager_rating': '5'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class GoalValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.employee = make_user('goalemp@test.com', role=make_role('goal_employee_test'), password='TestPass123!')
        ReviewCycle.objects.create(
            name='Active Cycle', period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 3, 31),
            self_review_due=datetime.date(2026, 3, 15), manager_review_due=datetime.date(2026, 3, 20),
            status='active', created_by=self.employee,
        )
        _login(self.client, 'goalemp@test.com')

    def test_valid_goal_created(self):
        resp = self.client.post(reverse('my-goals'), {'title': 'Improve reliability'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_blank_title_rejected(self):
        resp = self.client.post(reverse('my-goals'), {'title': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_goal_created_without_active_cycle_rejected(self):
        ReviewCycle.objects.all().update(status='closed')
        resp = self.client.post(reverse('my-goals'), {'title': 'Some goal'}, format='json')
        self.assertEqual(resp.status_code, 409)


class AppraisalWorkflowTests(TestCase):
    """Return-to-employee, results hidden until published, one-step HR
    publish, and the acknowledgement comment."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.manager = make_user('wfmgr@test.com', role=make_role('wf_manager_test', can_manage_team=True), password='TestPass123!')
        self.employee = make_user('wfemp@test.com', role=make_role('wf_employee_test'), password='TestPass123!',
                                  reporting_manager=self.manager, employee_id='WF1')
        self.hr = make_user('wfhr@test.com', role=make_role('wf_hr_test', permission_codenames=['performance.manage_cycles']),
                            password='TestPass123!')
        self.cycle = ReviewCycle.objects.create(
            name='Workflow Cycle', period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 12, 31),
            self_review_due=datetime.date(2026, 11, 15), manager_review_due=datetime.date(2026, 11, 30),
            status='active', created_by=self.manager,
        )
        self.review = PerformanceReview.objects.create(
            employee=self.employee, cycle=self.cycle, manager=self.manager,
            self_submitted_at=datetime.datetime.now(datetime.timezone.utc), status='self_review',
        )

    def _as(self, user):
        self.client.force_authenticate(user=user)

    def _manager_submit(self):
        self._as(self.manager)
        self.client.patch(reverse('manager-review-detail', args=[self.review.id]), {
            'manager_rating': '4', 'manager_notes': 'Strong', 'manager_development_plan': 'Lead a project',
            'manager_next_checkin': '2026-12-01',
        }, format='json')
        return self.client.post(reverse('submit-manager-review', args=[self.review.id]))

    def test_return_requires_reason_and_reopens_the_self_review(self):
        self._as(self.manager)
        url = reverse('return-review', args=[self.review.id])
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 400)
        resp = self.client.post(url, {'reason': 'Add evidence'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.review.refresh_from_db()
        self.assertIsNone(self.review.self_submitted_at)
        self.assertEqual(self.review.status, 'returned')
        # the employee can edit and resubmit again
        self._as(self.employee)
        self.assertEqual(self.client.patch(reverse('my-review'), {'key_strengths': 'More evidence'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(reverse('submit-my-review')).status_code, 200)

    def test_employee_cannot_return_a_review(self):
        self._as(self.employee)
        resp = self.client.post(reverse('return-review', args=[self.review.id]), {'reason': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_cannot_return_after_manager_submitted(self):
        self.assertEqual(self._manager_submit().status_code, 200)
        resp = self.client.post(reverse('return-review', args=[self.review.id]), {'reason': 'late'}, format='json')
        self.assertEqual(resp.status_code, 409)

    def test_reporting_manager_must_supply_plan_and_checkin(self):
        self._as(self.manager)
        self.client.patch(reverse('manager-review-detail', args=[self.review.id]),
                          {'manager_rating': '4', 'manager_notes': 'ok'}, format='json')
        resp = self.client.post(reverse('submit-manager-review', args=[self.review.id]))
        self.assertEqual(resp.status_code, 400)

    def test_manager_and_hr_results_are_hidden_from_employee_until_published(self):
        self.assertEqual(self._manager_submit().status_code, 200)
        self._as(self.employee)
        before = self.client.get(reverse('my-review')).data['data']
        for field in ('manager_rating', 'manager_notes', 'manager_development_plan', 'final_rating', 'calibration_note'):
            self.assertEqual(before[field], '', field)
        self._as(self.hr)
        self.assertEqual(self.client.post(reverse('publish-review', args=[self.review.id]),
                                          {'final_rating': '5', 'note': 'Exceeded'}, format='json').status_code, 200)
        self._as(self.employee)
        after = self.client.get(reverse('my-review')).data['data']
        self.assertEqual(after['manager_rating'], '4')
        self.assertEqual(after['final_rating'], '5')

    def test_publish_needs_rating_and_note_and_hr_permission(self):
        self.assertEqual(self._manager_submit().status_code, 200)
        url = reverse('publish-review', args=[self.review.id])
        self._as(self.manager)
        self.assertEqual(self.client.post(url, {'final_rating': '5', 'note': 'x'}, format='json').status_code, 403)
        self._as(self.hr)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 409)               # not calibrated, nothing supplied
        self.assertEqual(self.client.post(url, {'final_rating': '5'}, format='json').status_code, 400)  # rating without note
        self.assertEqual(self.client.post(url, {'final_rating': '9', 'note': 'x'}, format='json').status_code, 400)

    def test_acknowledge_stores_the_comment(self):
        self.assertEqual(self._manager_submit().status_code, 200)
        self._as(self.hr)
        self.client.post(reverse('publish-review', args=[self.review.id]), {'final_rating': '5', 'note': 'Great'}, format='json')
        self._as(self.employee)
        resp = self.client.post(reverse('acknowledge-review', args=[self.review.id]), {'comment': 'Thanks'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['acknowledgement_comment'], 'Thanks')
        self.assertEqual(resp.data['data']['status'], 'completed')

    def test_team_list_creates_missing_rows_for_direct_reports_only(self):
        other = make_user('wfother@test.com', role=make_role('wf_employee_test'), password='TestPass123!', employee_id='WF2')
        PerformanceReview.objects.filter(employee=self.employee).delete()
        self._as(self.manager)
        rows = self.client.get(reverse('team-review-list')).data['data']
        self.assertEqual([str(r['employee']) for r in rows], [str(self.employee.id)])
        self.assertFalse(PerformanceReview.objects.filter(employee=other).exists())

    def test_goals_endpoint_is_limited_to_the_reporting_manager_or_hr(self):
        url = reverse('review-goals', args=[self.review.id])
        self._as(self.manager)
        self.assertEqual(self.client.get(url).status_code, 200)
        self._as(self.hr)
        self.assertEqual(self.client.get(url).status_code, 200)
        stranger = make_user('wfstranger@test.com', role=make_role('wf_stranger_role'), password='TestPass123!')
        self._as(stranger)
        self.assertEqual(self.client.get(url).status_code, 403)


class FeedbackRequestTests(TestCase):
    """Who can be asked for feedback, and the respond/decline flow."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('fb_employee_test')
        self.boss = make_user('fbboss@test.com', role=role, password='TestPass123!', employee_id='FB0')
        self.me = make_user('fbme@test.com', role=role, password='TestPass123!', employee_id='FB1', reporting_manager=self.boss)
        self.peer = make_user('fbpeer@test.com', role=role, password='TestPass123!', employee_id='FB2', reporting_manager=self.boss)
        self.report = make_user('fbrep@test.com', role=role, password='TestPass123!', employee_id='FB3', reporting_manager=self.me)
        self.stranger = make_user('fbstr@test.com', role=role, password='TestPass123!', employee_id='FB4')

    def _as(self, user):
        self.client.force_authenticate(user=user)

    def _ask(self, recipient, topic='How did the launch go?'):
        return self.client.post(reverse('feedback-request-list'), {'recipient': str(recipient.id), 'topic': topic}, format='json')

    def test_colleagues_are_manager_peers_and_reports_only(self):
        self._as(self.me)
        rows = self.client.get(reverse('feedback-colleagues')).data['data']
        self.assertEqual({r['employee_id'] for r in rows}, {'FB0', 'FB2', 'FB3'})
        self.assertEqual(rows[0]['relation'], 'Reporting manager')

    def test_cannot_ask_someone_outside_the_working_circle_or_yourself(self):
        self._as(self.me)
        self.assertEqual(self._ask(self.stranger).status_code, 403)
        self.assertEqual(self._ask(self.me).status_code, 403)

    def test_topic_is_required_and_duplicates_are_blocked(self):
        self._as(self.me)
        self.assertEqual(self._ask(self.boss, topic='  ').status_code, 400)
        self.assertEqual(self._ask(self.boss).status_code, 201)
        self.assertEqual(self._ask(self.boss).status_code, 409)

    def test_only_the_recipient_can_respond_and_only_once(self):
        self._as(self.me)
        rid = self._ask(self.boss).data['data']['id']
        url = reverse('feedback-request-respond', args=[rid])
        self.assertEqual(self.client.post(url, {'response': 'x'}, format='json').status_code, 403)   # requester
        self._as(self.boss)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 400)                  # empty
        done = self.client.post(url, {'response': 'Great launch'}, format='json')
        self.assertEqual(done.data['data']['status'], 'provided')
        self.assertEqual(self.client.post(url, {'response': 'again'}, format='json').status_code, 409)

    def test_recipient_can_decline_and_lists_are_scoped(self):
        self._as(self.me)
        rid = self._ask(self.peer).data['data']['id']
        self._as(self.peer)
        self.assertEqual(self.client.post(reverse('feedback-request-respond', args=[rid]), {'decline': True}, format='json').data['data']['status'], 'declined')
        self.assertEqual(len(self.client.get(reverse('feedback-request-list') + '?scope=for-me').data['data']['results']), 1)
        self.assertEqual(len(self.client.get(reverse('feedback-request-list')).data['data']['results']), 0)   # mine: none made
