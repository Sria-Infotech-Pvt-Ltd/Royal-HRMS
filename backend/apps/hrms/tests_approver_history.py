"""An approver's Approved / Rejected lists must show the requests they were the approver of. The approval QUEUE (waiting for me) still drops a
request the moment it is decided; the Approvals page LIST adds the ones assigned to me in any status."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Q
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule, User
from apps.hrms.models import LeaveBalance, LeavePolicy, LeaveRequest
from apps.hrms.views.leave_shared import _approval_scope_filter

TODAY = timezone.localdate()


def _future_monday(weeks_ahead: int = 3) -> datetime.date:
    base = TODAY + datetime.timedelta(weeks=weeks_ahead)
    return base + datetime.timedelta(days=(7 - base.weekday()) % 7 or 7)


class ApproverHistoryTests(TestCase):
    def setUp(self):
        cache.clear()
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE,
            defaults={'l1_approver_kind': ApprovalWorkflowRule.APPROVER_REPORTING_MANAGER, 'l2_approver_kind': ApprovalWorkflowRule.APPROVER_HR},
        )
        LeavePolicy.objects.update_or_create(
            leave_type='casual', defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0'), 'is_active': True, 'convert_to_lop': False,
                                           'allow_negative_balance': False, 'minimum_notice_period': 0, 'allow_probation_leave': True},
        )
        self.hr = make_user('hist-hr@test.com', role=make_role('hist_hr', permission_codenames=['leave.approve', 'wfh.approve', 'leave.view']), branch='Mulugu')
        self.manager = make_user('hist-mgr@test.com', role=make_role('hist_mgr', permission_codenames=['leave.approve', 'wfh.approve'], can_manage_team=True), branch='Mulugu')
        self.other_manager = make_user('hist-other@test.com', role=make_role('hist_other', permission_codenames=['leave.approve', 'wfh.approve'], can_manage_team=True), branch='Mulugu')
        self.employee = make_user('hist-emp@test.com', employee_id='EMPHI001', role=make_role('hist_emp'), branch='Mulugu', reporting_manager=self.manager)
        self.employee.hr = self.hr
        self.employee.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        self.employee.save(update_fields=['hr', 'employment_status'])
        self.monday = _future_monday()
        LeaveBalance.objects.create(employee=self.employee, leave_type='casual', year=self.monday.year, total_days=Decimal('6.0'), used_days=Decimal('0'))

    def _as(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _team_ids(self, user, endpoint, **params) -> set[str]:
        response = self._as(user).get(reverse(endpoint), {'scope': 'team', 'page_size': 100, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id'] for row in response.data['data']['results']}

    def _leave(self, day_offset=0):
        start = self.monday + datetime.timedelta(days=7 * day_offset)
        response = self._as(self.employee).post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': start.isoformat(), 'end_date': start.isoformat(), 'reason': 'Family function at home',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['data']['id']

    def _decide(self, user, request_id, action, route='leave-request-approve'):
        return self._as(user).post(reverse(route, kwargs={'request_id': request_id}), {'action': action}, format='json')

    def test_a_manager_and_hr_still_see_a_leave_request_after_approving_it_under_approved(self):
        request_id = self._leave()
        self.assertIn(request_id, self._team_ids(self.manager, 'leave-request-list', status='pending'))
        self.assertEqual(self._decide(self.manager, request_id, 'approve').status_code, 200)
        self.assertEqual(self._decide(self.hr, request_id, 'approve').status_code, 200)
        self.assertIn(request_id, self._team_ids(self.manager, 'leave-request-list', status='approved'))
        self.assertIn(request_id, self._team_ids(self.hr, 'leave-request-list', status='approved'))
        self.assertNotIn(request_id, self._team_ids(self.manager, 'leave-request-list', status='pending'))

    def test_a_rejected_request_stays_visible_under_rejected_to_the_approver_who_had_it(self):
        request_id = self._leave()
        self._decide(self.manager, request_id, 'reject')
        self.assertIn(request_id, self._team_ids(self.manager, 'leave-request-list', status='rejected'))

    def test_somebody_who_was_never_the_approver_does_not_see_it(self):
        request_id = self._leave()
        self._decide(self.manager, request_id, 'approve')
        self._decide(self.hr, request_id, 'approve')
        self.assertNotIn(request_id, self._team_ids(self.other_manager, 'leave-request-list', status='approved'))
        self.assertNotIn(request_id, self._team_ids(self.other_manager, 'leave-request-list'))

    def test_an_approver_never_sees_their_own_request_in_the_team_list(self):
        LeaveBalance.objects.create(employee=self.manager, leave_type='casual', year=self.monday.year, total_days=Decimal('6.0'), used_days=Decimal('0'))
        mine = self._as(self.manager).post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': self.monday.isoformat(), 'end_date': self.monday.isoformat(), 'reason': 'My own family function',
        }, format='json')
        if mine.status_code == 201:
            self.assertNotIn(mine.data['data']['id'], self._team_ids(self.manager, 'leave-request-list'))

    def test_the_approval_queue_itself_still_drops_a_decided_request(self):
        request_id = self._leave()
        self._decide(self.manager, request_id, 'approve')
        self._decide(self.hr, request_id, 'approve')
        queue = LeaveRequest.objects.filter(_approval_scope_filter(self.manager))
        self.assertFalse(queue.filter(pk=request_id).exists(), 'counts, search and voice still read only what is waiting')

    def test_work_from_home_lists_work_the_same_way(self):
        today = TODAY
        body = {'start_date': (today + datetime.timedelta(days=2)).isoformat(), 'end_date': (today + datetime.timedelta(days=3)).isoformat(),
                'reason': 'Internet repair at home', 'location_label': 'Home', 'latitude': 17.385044, 'longitude': 78.486671}
        created = self._as(self.employee).post(reverse('wfh-request-list'), body, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        request_id = created.data['data']['id']
        self._decide(self.manager, request_id, 'approve', 'wfh-request-approve')
        self._decide(self.hr, request_id, 'approve', 'wfh-request-approve')
        self.assertIn(request_id, self._team_ids(self.manager, 'wfh-request-list', status='approved'))
        self.assertIn(request_id, self._team_ids(self.hr, 'wfh-request-list', status='approved'))
        self.assertNotIn(request_id, self._team_ids(self.other_manager, 'wfh-request-list', status='approved'))
        # and the employee's own list, which is what decides the punch mode, has it too
        own = self._as(self.employee).get(reverse('wfh-request-list'), {'status': 'approved', 'page_size': 5})
        self.assertIn(request_id, {row['id'] for row in own.data['data']['results']})
