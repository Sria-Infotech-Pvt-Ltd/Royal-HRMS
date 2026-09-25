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
from apps.performance.models import Goal, PerformanceReview, ReviewCycle


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
        patch_resp = self.client.patch(reverse('manager-review-detail', args=[review.id]), {'manager_rating': '4'}, format='json')
        self.assertEqual(patch_resp.status_code, 200, patch_resp.data)
        submit_resp = self.client.post(reverse('submit-manager-review', args=[review.id]))
        self.assertEqual(submit_resp.status_code, 200, submit_resp.data)

    def test_manager_review_cannot_be_submitted_twice(self):
        review = PerformanceReview.objects.create(
            employee=self.employee, cycle=self.cycle, manager=self.manager,
            self_submitted_at=datetime.datetime.now(datetime.timezone.utc),
        )
        _login(self.client, 'perfmgr@test.com')
        first = self.client.post(reverse('submit-manager-review', args=[review.id]))
        self.assertEqual(first.status_code, 200)
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
