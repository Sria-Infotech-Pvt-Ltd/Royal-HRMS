"""The whole leave request journey, as an employee and her approvers would live it: apply -> L1 (reporting manager) -> L2 (HR) -> balance.

Covers what the older single-level tests do not: the two-level order, reject and cancel giving the days back, overlapping dates, and the
case that surprised a real employee: no balance row at all for the leave type ("0 days available")."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule, User
from apps.hrms.models import LeaveBalance, LeavePolicy, LeaveRequest


def _future_monday(weeks_ahead: int = 3) -> datetime.date:
    base = datetime.date.today() + datetime.timedelta(weeks=weeks_ahead)
    return base + datetime.timedelta(days=(7 - base.weekday()) % 7 or 7)


class TwoLevelLeaveFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE,
            defaults={'l1_approver_kind': ApprovalWorkflowRule.APPROVER_REPORTING_MANAGER, 'l2_approver_kind': ApprovalWorkflowRule.APPROVER_HR},
        )
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0'), 'is_active': True, 'convert_to_lop': False,
                      'allow_negative_balance': False, 'minimum_notice_period': 0, 'allow_probation_leave': True},
        )
        self.hr = make_user('flow-hr@test.com', role=make_role('flow_hr', permission_codenames=['leave.approve', 'leave.view']), branch='Mulugu')
        self.manager = make_user('flow-mgr@test.com', role=make_role('flow_mgr', permission_codenames=['leave.approve'], can_manage_team=True), branch='Mulugu')
        self.employee = make_user('flow-emp@test.com', role=make_role('flow_emp'), branch='Mulugu', reporting_manager=self.manager)
        self.employee.hr = self.hr
        self.employee.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        self.employee.save(update_fields=['hr', 'employment_status'])
        self.monday = _future_monday()
        self.balance = LeaveBalance.objects.create(employee=self.employee, leave_type='casual', year=self.monday.year, total_days=Decimal('4.0'), used_days=Decimal('0'))

    def _as(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _apply(self, start=None, days=1, reason='Sister is getting married', user=None):
        start = start or self.monday
        end = start + datetime.timedelta(days=days - 1)
        return self._as(user or self.employee).post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': start.isoformat(), 'end_date': end.isoformat(), 'reason': reason,
        }, format='json')

    def _decide(self, user, request_id, action):
        return self._as(user).post(reverse('leave-request-approve', kwargs={'request_id': request_id}), {'action': action}, format='json')

    def _used(self):
        self.balance.refresh_from_db()
        return self.balance.used_days

    def test_a_request_goes_manager_then_hr_and_only_the_final_approval_uses_the_days(self):
        created = self._apply()
        self.assertEqual(created.status_code, 201, created.data)
        request_id = created.data['data']['id']
        self.assertEqual(created.data['data']['status'], 'pending')
        self.assertEqual(self._used(), Decimal('0'))

        l1 = self._decide(self.manager, request_id, 'approve')
        self.assertEqual(l1.status_code, 200, l1.data)
        self.assertEqual(l1.data['data']['status'], 'l2_pending')
        self.assertEqual(self._used(), Decimal('0'), 'the days are not used until the last level approves')

        l2 = self._decide(self.hr, request_id, 'approve')
        self.assertEqual(l2.status_code, 200, l2.data)
        self.assertEqual(l2.data['data']['status'], 'approved')
        self.assertEqual(self._used(), Decimal('1.0'))

    def test_hr_cannot_jump_ahead_of_the_manager_and_the_manager_cannot_do_the_hr_step(self):
        request_id = self._apply().data['data']['id']
        self.assertEqual(self._decide(self.hr, request_id, 'approve').status_code, 403)       # level 1 belongs to the reporting manager
        self.assertEqual(self._decide(self.manager, request_id, 'approve').status_code, 200)
        self.assertEqual(self._decide(self.manager, request_id, 'approve').status_code, 403)   # level 2 belongs to HR
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, 'l2_pending')

    def test_a_rejection_at_either_level_ends_it_and_gives_the_days_back(self):
        first = self._apply(days=2).data['data']['id']
        self.assertEqual(self._decide(self.manager, first, 'reject').status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(pk=first).status, 'rejected')
        second = self._apply(start=self.monday + datetime.timedelta(days=7), days=2).data['data']['id']
        self._decide(self.manager, second, 'approve')
        self.assertEqual(self._decide(self.hr, second, 'reject').status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(pk=second).status, 'rejected')
        self.assertEqual(self._used(), Decimal('0'))
        self.assertEqual(self._apply(start=self.monday + datetime.timedelta(days=14), days=4).status_code, 201, 'the whole balance is free again')

    def test_a_decided_request_cannot_be_decided_again(self):
        request_id = self._apply().data['data']['id']
        self._decide(self.manager, request_id, 'approve')
        self._decide(self.hr, request_id, 'approve')
        again = self._decide(self.hr, request_id, 'approve')
        self.assertEqual(again.status_code, 400)
        self.assertEqual(self._used(), Decimal('1.0'), 'never taken twice')

    def test_the_employee_can_cancel_a_waiting_request_but_not_a_finished_one_and_nobody_else_can(self):
        waiting = self._apply().data['data']['id']
        url = reverse('leave-request-detail', kwargs={'request_id': waiting})
        self.assertEqual(self._as(self.manager).patch(url, {}, format='json').status_code, 403)
        cancelled = self._as(self.employee).patch(url, {}, format='json')
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.assertEqual(LeaveRequest.objects.get(pk=waiting).status, 'cancelled')
        self.assertEqual(self._as(self.employee).patch(url, {}, format='json').status_code, 400)

        done = self._apply(start=self.monday + datetime.timedelta(days=7)).data['data']['id']
        self._decide(self.manager, done, 'approve')
        self._decide(self.hr, done, 'approve')
        self.assertEqual(self._as(self.employee).patch(reverse('leave-request-detail', kwargs={'request_id': done}), {}, format='json').status_code, 400)

    def test_you_cannot_apply_twice_for_the_same_days_nor_beyond_your_balance(self):
        self.assertEqual(self._apply().status_code, 201)
        overlap = self._apply()
        self.assertEqual(overlap.status_code, 400)
        self.assertIn('already have a leave request', overlap.data['message'])
        too_many = self._apply(start=self.monday + datetime.timedelta(days=14), days=5)
        self.assertEqual(too_many.status_code, 400)
        self.assertIn('Insufficient balance', too_many.data['message'])

    def test_the_balance_screen_shows_days_held_by_waiting_requests(self):
        self._apply(days=2)
        rows = self._as(self.employee).get(reverse('leave-balance'), {'year': self.monday.year}).json()['data']
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        casual = next(row for row in rows if row['leave_type'] == 'casual')
        self.assertEqual((casual['pending_days'], casual['available_days']), (2.0, 2.0))

    def test_an_employee_with_no_balance_row_is_told_zero_days_and_refused(self):
        """The reported case: a person added without leave balances sees '0 days available' and the server says to contact HR; they cannot apply until HR credits them."""
        newcomer = make_user('flow-new@test.com', employee_id='EMPFLW009', role=make_role('flow_emp'), branch='Mulugu', reporting_manager=self.manager)
        newcomer.hr = self.hr
        newcomer.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        newcomer.save(update_fields=['hr', 'employment_status'])
        self.assertFalse(LeaveBalance.objects.filter(employee=newcomer).exists())
        refused = self._apply(user=newcomer)
        self.assertEqual(refused.status_code, 400)
        self.assertIn('No leave balance found for casual', refused.data['message'])
        self.assertIn('Contact HR', refused.data['message'])
        credit_url = reverse('leave-balance-credit')
        body = {'year': self.monday.year, 'employee_id': newcomer.employee_id}
        # Credit Rules -> Credit only reaches people whose onboarding is complete: while it is pending, nothing is credited.
        self.assertEqual(self._as(self.hr).post(credit_url, body, format='json').data['data']['credited'], 0)
        self.assertEqual(self._apply(user=newcomer).status_code, 400)
        # Once their onboarding is complete, HR's credit gives them the balance, and the same request now works.
        newcomer.onboarding_status = User.ONBOARDING_COMPLETE
        newcomer.save(update_fields=['onboarding_status'])
        credit = self._as(self.hr).post(credit_url, body, format='json')
        self.assertEqual(credit.status_code, 200, credit.data)
        self.assertGreaterEqual(credit.data['data']['credited'], 1)
        second = self._apply(user=newcomer)
        self.assertEqual(second.status_code, 201, second.data)
