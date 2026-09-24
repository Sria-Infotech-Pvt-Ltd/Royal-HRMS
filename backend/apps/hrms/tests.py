"""Critical-flow and regression tests for the HRMS app (leave + expenses).

This app had zero test coverage before the 2026-07-22 engineering audit.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule
from apps.hrms.models import CarryForwardLog, Expense, LeaveBalance, LeavePolicy
from apps.hrms.tasks import expire_unused_carry_forward


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


def _future_monday(weeks_ahead: int = 2) -> datetime.date:
    """A Monday safely in the future — avoids both 'backdated leave' rejection
    and any ambiguity about weekly-off/holiday configuration on other days.
    """
    base = datetime.date.today() + datetime.timedelta(weeks=weeks_ahead)
    return base + datetime.timedelta(days=(7 - base.weekday()) % 7 or 7)


class LeaveBalanceAdjustDecimalTests(TestCase):
    """Regression test: patching only one of total_days/used_days left the
    in-memory LeaveBalance with one Decimal field and one raw-float field.
    The very next line (LeaveBalanceSerializer.get_available_days) subtracts
    them and threw a TypeError.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr', permission_codenames=['leave.approve'])
        self.hr_user = make_user('hrleave@test.com', role=hr_role, password='TestPass123!')
        self.employee = make_user('leaveemp@test.com', role=make_role('employee'), password='TestPass123!')
        self.balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('12.0'), used_days=Decimal('2.0'),
        )
        _login(self.client, 'hrleave@test.com')

    def test_patching_only_total_days_does_not_crash(self):
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'total_days': 15.5},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('15.5'))
        self.assertEqual(resp.data['data']['available_days'], 13.5)

    def test_patching_only_used_days_does_not_crash(self):
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'used_days': 3.5},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('3.5'))

    def test_negative_total_days_rejected(self):
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'total_days': -5},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_employee_cannot_adjust_own_balance(self):
        _login(self.client, 'leaveemp@test.com')
        # Grant the employee leave.approve to isolate the self-adjustment
        # check specifically, rather than the permission check.
        self.employee.role.role_permissions.filter(permission__codename='leave.approve')
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'total_days': 100},
            format='json',
        )
        self.assertIn(resp.status_code, (403, 404))


class LeaveRequestFlowTests(TestCase):
    """End-to-end: submit -> L1 approve -> balance deducted."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        manager_role = make_role(
            'manager__team_lead', permission_codenames=['leave.approve'], can_manage_team=True,
        )
        employee_role = make_role('employee')
        self.manager = make_user('leavemgr@test.com', role=manager_role, password='TestPass123!')
        self.employee = make_user(
            'applicant@test.com', role=employee_role, password='TestPass123!',
            reporting_manager=self.manager,
        )

        # A migration already seeds a default rule for 'leave' — update it in
        # place rather than colliding with the unique workflow_type constraint.
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE,
            defaults={
                'l1_approver_role': manager_role,
                'l2_approver_role': None,
            },
        )
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0'), 'is_active': True},
        )
        self.leave_date = _future_monday()
        LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=self.leave_date.year,
            total_days=Decimal('12.0'), used_days=Decimal('0'),
        )
        _login(self.client, 'applicant@test.com')

    def test_submit_leave_request_happy_path(self):
        resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual',
                'duration': 'full_day',
                'start_date': self.leave_date.isoformat(),
                'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['status'], 'pending')

    def test_insufficient_balance_is_rejected(self):
        resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual',
                'duration': 'full_day',
                'start_date': self.leave_date.isoformat(),
                'end_date': (self.leave_date + datetime.timedelta(days=29)).isoformat(),
                'reason': 'A long trip abroad.',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Insufficient balance', resp.data['message'])

    def test_manager_approval_deducts_balance(self):
        create_resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual', 'duration': 'full_day',
                'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        request_id = create_resp.data['data']['id']

        mgr_client = APIClient()
        _login(mgr_client, 'leavemgr@test.com')
        approve_resp = mgr_client.post(
            reverse('leave-request-approve', kwargs={'request_id': request_id}),
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(approve_resp.status_code, 200, approve_resp.data)
        self.assertEqual(approve_resp.data['data']['status'], 'approved')

        balance = LeaveBalance.objects.get(
            employee=self.employee, leave_type='casual', year=self.leave_date.year,
        )
        self.assertEqual(balance.used_days, Decimal('1.0'))

    def test_non_designated_approver_is_rejected(self):
        create_resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual', 'duration': 'full_day',
                'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        request_id = create_resp.data['data']['id']

        make_user(
            'othermgr@test.com', role=make_role('manager__team_lead'), password='TestPass123!',
        )
        other_client = APIClient()
        _login(other_client, 'othermgr@test.com')
        resp = other_client.post(
            reverse('leave-request-approve', kwargs={'request_id': request_id}),
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_cannot_approve_own_leave_request(self):
        # Give the applicant leave.approve too, to isolate the self-approval
        # check rather than the permission check.
        create_resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual', 'duration': 'full_day',
                'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        request_id = create_resp.data['data']['id']
        self.employee.role = make_role('employee_with_approve', permission_codenames=['leave.approve'])
        self.employee.save(update_fields=['role'])

        resp = self.client.post(
            reverse('leave-request-approve', kwargs={'request_id': request_id}),
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn('cannot approve', resp.data['message'].lower())


class LeaveRequestPolicyValidationTests(TestCase):
    """Covers the field- and policy-level rules in LeaveRequestCreateSerializer
    and _validate_leave_policy that had no prior test coverage — reason
    length, date ordering, overlap with an existing leave/WFH request,
    backdated/future-date limits, min/max duration, and attachment_required."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        employee_role = make_role('employee_policy_test')
        self.employee = make_user('policyemp@test.com', role=employee_role, password='TestPass123!')
        self.leave_date = _future_monday()
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0'), 'is_active': True},
        )
        LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=self.leave_date.year,
            total_days=Decimal('12.0'), used_days=Decimal('0'),
        )
        _login(self.client, 'policyemp@test.com')

    def _apply(self, **overrides):
        payload = {
            'leave_type': 'casual', 'duration': 'full_day',
            'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
            'reason': 'Personal work to attend to.',
        }
        payload.update(overrides)
        return self.client.post(reverse('leave-request-list'), payload, format='json')

    def test_reason_under_10_chars_rejected(self):
        resp = self._apply(reason='Sick')
        self.assertEqual(resp.status_code, 400)

    def test_end_date_before_start_date_rejected(self):
        resp = self._apply(end_date=(self.leave_date - datetime.timedelta(days=1)).isoformat())
        self.assertEqual(resp.status_code, 400)

    def test_overlapping_leave_request_rejected(self):
        first = self._apply()
        self.assertEqual(first.status_code, 201, first.data)
        second = self._apply()
        self.assertEqual(second.status_code, 400)
        self.assertIn('already have a leave request', second.data['message'])

    def test_overlapping_wfh_request_rejected(self):
        from apps.hrms.models import REQ_PENDING, WorkFromHomeRequest
        WorkFromHomeRequest.objects.create(
            employee=self.employee, start_date=self.leave_date, end_date=self.leave_date,
            status=REQ_PENDING, latitude=Decimal('17.4483'), longitude=Decimal('78.3915'),
        )
        resp = self._apply()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('work-from-home', resp.data['message'])

    def test_backdated_leave_rejected_when_policy_disallows(self):
        LeavePolicy.objects.filter(leave_type='casual').update(allow_backdated_leave=False)
        past_date = datetime.date.today() - datetime.timedelta(days=2)
        resp = self._apply(start_date=past_date.isoformat(), end_date=past_date.isoformat())
        self.assertEqual(resp.status_code, 400)
        self.assertIn('backdated', resp.data['message'].lower())

    def test_backdated_leave_allowed_within_policy_limit(self):
        LeavePolicy.objects.filter(leave_type='casual').update(
            allow_backdated_leave=True, maximum_backdated_days=5,
        )
        past_date = datetime.date.today() - datetime.timedelta(days=2)
        resp = self._apply(start_date=past_date.isoformat(), end_date=past_date.isoformat())
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_backdated_leave_rejected_beyond_max_backdated_days(self):
        LeavePolicy.objects.filter(leave_type='casual').update(
            allow_backdated_leave=True, maximum_backdated_days=1,
        )
        past_date = datetime.date.today() - datetime.timedelta(days=5)
        resp = self._apply(start_date=past_date.isoformat(), end_date=past_date.isoformat())
        self.assertEqual(resp.status_code, 400)

    def test_future_leave_rejected_when_policy_disallows(self):
        LeavePolicy.objects.filter(leave_type='casual').update(allow_future_leave=False)
        resp = self._apply()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('future-dated', resp.data['message'].lower())

    def test_future_leave_rejected_beyond_maximum_future_days(self):
        LeavePolicy.objects.filter(leave_type='casual').update(
            allow_future_leave=True, maximum_future_days=3,
        )
        # self.leave_date is ~2 weeks out — well past a 3-day cap.
        resp = self._apply()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('advance', resp.data['message'].lower())

    def test_below_minimum_leave_duration_rejected(self):
        LeavePolicy.objects.filter(leave_type='casual').update(minimum_leave_duration=Decimal('2.0'))
        resp = self._apply()  # single day
        self.assertEqual(resp.status_code, 400)
        self.assertIn('minimum', resp.data['message'].lower())

    def test_above_maximum_leave_duration_rejected(self):
        LeavePolicy.objects.filter(leave_type='casual').update(maximum_leave_duration=1)
        resp = self._apply(end_date=(self.leave_date + datetime.timedelta(days=3)).isoformat())
        self.assertEqual(resp.status_code, 400)
        self.assertIn('maximum', resp.data['message'].lower())

    def test_missing_required_attachment_rejected(self):
        LeavePolicy.objects.filter(leave_type='casual').update(attachment_required=True)
        resp = self._apply()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('attachment', resp.data['message'].lower())

    def test_half_day_rejected_when_policy_disallows(self):
        LeavePolicy.objects.filter(leave_type='casual').update(allow_half_day=False)
        resp = self._apply(duration='half_morning')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('half-day', resp.data['message'].lower())


class ExpenseSelfApprovalTests(TestCase):
    """Regression/critical-path test: an approver can never approve their
    own expense claim, even if they hold expenses.approve.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('hr', permission_codenames=['expenses.approve'])
        self.hr_user = make_user('hrexpense@test.com', role=role, password='TestPass123!')
        _login(self.client, 'hrexpense@test.com')

    def test_cannot_approve_own_expense(self):
        expense = Expense.objects.create(
            employee=self.hr_user, expense_number=1, title='Taxi',
            category='travel', amount=Decimal('500.00'),
            expense_date=datetime.date(2026, 1, 10),
        )
        resp = self.client.patch(
            reverse('expense-detail', kwargs={'expense_number': expense.expense_number}),
            {'status': 'approved'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn('cannot approve', resp.data['message'].lower())


class ExpireUnusedCarryForwardTaskTests(TestCase):
    """Regression test: LeaveBalance.carry_forward_expiry_date was set by
    both reset_annual_leave_balances and the manual CarryForwardRunView, but
    nothing ever read it back — carried-forward leave never actually expired.
    Confirms the new expire_unused_carry_forward task enforces it correctly.
    """

    def setUp(self):
        cache.clear()
        self.employee = make_user('carryforward@test.com', role=make_role('employee'), password='TestPass123!')

    def test_expired_carry_forward_is_deducted_and_cleared(self):
        balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('15.0'), used_days=Decimal('2.0'),
            carried_forward=Decimal('5.0'),
            carry_forward_expiry_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        result = expire_unused_carry_forward()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['skipped'], 0)

        balance.refresh_from_db()
        # available before expiry = 15 - 2 = 13, carried_forward = 5 -> fully reclaimable
        self.assertEqual(balance.total_days, Decimal('10.0'))
        self.assertEqual(balance.carried_forward, Decimal('0'))
        self.assertIsNone(balance.carry_forward_expiry_date)

        log = CarryForwardLog.objects.get(process_mode='expire')
        self.assertEqual(log.total_processed, 1)
        self.assertEqual(log.total_skipped, 0)
        self.assertEqual(log.total_failed, 0)

    def test_only_the_actually_available_portion_is_reclaimed(self):
        """An employee who already used more than their non-carry-forward
        allotment (available_days < carried_forward) must only lose what's
        actually available — total_days must never drop below used_days."""
        balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('12.0'), used_days=Decimal('10.0'),
            carried_forward=Decimal('5.0'),
            carry_forward_expiry_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        expire_unused_carry_forward()

        balance.refresh_from_db()
        # available = 12 - 10 = 2, carried_forward = 5 -> only 2 reclaimable
        self.assertEqual(balance.total_days, Decimal('10.0'))
        self.assertEqual(balance.used_days, Decimal('10.0'))
        self.assertEqual(balance.total_days, balance.used_days, 'must never go negative')
        self.assertEqual(balance.carried_forward, Decimal('0'))

    def test_fully_used_carry_forward_is_only_cleared_not_double_deducted(self):
        """available_days <= 0 (already fully used before expiry): nothing to
        claw back, but the expired flag must still clear so this row is not
        re-selected on every subsequent day's run."""
        balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('10.0'), used_days=Decimal('10.0'),
            carried_forward=Decimal('5.0'),
            carry_forward_expiry_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        result = expire_unused_carry_forward()
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['processed'], 0)

        balance.refresh_from_db()
        self.assertEqual(balance.total_days, Decimal('10.0'))
        self.assertEqual(balance.carried_forward, Decimal('0'))
        self.assertIsNone(balance.carry_forward_expiry_date)

    def test_not_yet_expired_carry_forward_is_left_untouched(self):
        balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('15.0'), used_days=Decimal('2.0'),
            carried_forward=Decimal('5.0'),
            carry_forward_expiry_date=datetime.date.today() + datetime.timedelta(days=30),
        )
        result = expire_unused_carry_forward()
        self.assertEqual(result['processed'], 0)
        self.assertEqual(result['skipped'], 0)

        balance.refresh_from_db()
        self.assertEqual(balance.total_days, Decimal('15.0'))
        self.assertEqual(balance.carried_forward, Decimal('5.0'))
        self.assertIsNotNone(balance.carry_forward_expiry_date)

    def test_rerunning_the_task_is_idempotent(self):
        balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('15.0'), used_days=Decimal('2.0'),
            carried_forward=Decimal('5.0'),
            carry_forward_expiry_date=datetime.date.today() - datetime.timedelta(days=1),
        )
        first = expire_unused_carry_forward()
        self.assertEqual(first['processed'], 1)

        second = expire_unused_carry_forward()
        self.assertEqual(second['processed'], 0)
        self.assertEqual(second['skipped'], 0)

        balance.refresh_from_db()
        self.assertEqual(balance.total_days, Decimal('10.0'), 'second run must not deduct again')
        self.assertEqual(CarryForwardLog.objects.filter(process_mode='expire').count(), 2)
