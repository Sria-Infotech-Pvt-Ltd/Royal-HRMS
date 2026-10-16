"""
Phase B — monthly statement, month-end expiry, month-aware validation,
approval recheck, annual-lump exclusion, year-end carry-forward and cache
refresh for leave types on the Monthly credit schedule.

Service-level tests fix "today" to 15 June of the current year (Jan-May
closed, June open, Jul-Dec future) by patching services_monthly_statement._today,
so they don't depend on the real date. Requests' created_at is set where
in-time vs late booking matters. The API tests use the real date and a
built-in leave type (custom leave types can't be applied for through the
API yet — a pre-existing serializer limitation, reported separately).
"""
from __future__ import annotations

import calendar
import datetime
import threading
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.hrms.models import (
    CREDIT_TXN_EXPIRY, REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING, REQ_REJECTED,
    LeaveBalance, LeaveCreditTransaction, LeavePolicy, LeaveRequest,
)
from apps.hrms.services_leave_credit import LeaveCreditError, apply_adjustment, reverse_transaction, set_monthly_credit
from apps.hrms.services_monthly_statement import (
    build_statement, request_shortfall, sync_after_request_change, sync_expiries, unused_for_carry_forward,
)
from apps.hrms.tests_leave_credits import PASSWORD, YEAR, _Fixtures, _key
from config.test_runner import TEST_COMPANY_CODE

TODAY = datetime.date(YEAR, 6, 15)
D = Decimal


def _aware(day: datetime.date):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(10, 0)))


def _weekday(year: int, month: int, day: int, weekday: int | None = None) -> datetime.date:
    """First Mon-Fri date on/after the given day (or the first given weekday)."""
    d = datetime.date(year, month, day)
    while d.weekday() >= 5 or (weekday is not None and d.weekday() != weekday):
        d += datetime.timedelta(days=1)
    return d


def _boundary_month(after: int) -> int:
    """A month > `after` whose last day is Mon-Thu, so it and the next day are weekdays."""
    for m in range(after + 1, 12):
        if calendar.weekday(YEAR, m, calendar.monthrange(YEAR, m)[1]) <= 3:
            return m
    raise AssertionError('no suitable month boundary this year')


class _MonthlyBase(_Fixtures):
    PATCH_TODAY = True

    def setUp(self):
        if self.PATCH_TODAY:
            patcher = mock.patch('apps.hrms.services_monthly_statement._today', return_value=TODAY)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.make_fixtures()
        self.pink = LeavePolicy.objects.create(
            leave_type='pink', leave_type_label='Pink Leave', annual_days=D('0'), is_active=True,
            credit_schedule='monthly', monthly_carry_forward=False, monthly_rules_from=datetime.date(YEAR, 1, 1),
        )
        self.cl = LeavePolicy.objects.create(
            leave_type='cl_monthly', leave_type_label='CL Monthly', annual_days=D('12'), is_active=True,
            credit_schedule='monthly', monthly_carry_forward=True, monthly_rules_from=datetime.date(YEAR, 1, 1),
        )
        cache.clear()

    def credit(self, value, month, policy=None, employee=None):
        policy = policy or self.pink
        return set_monthly_credit(employee=employee or self.employee, leave_type=policy.leave_type, year=YEAR,
                                  month=month, value=str(value), actor=self.admin)

    def req(self, day, *, policy=None, end=None, days='1', status=REQ_APPROVED, booked=None, employee=None):
        from apps.hrms.views.leave import _deduct_balance_safe
        policy = policy or self.pink
        r = LeaveRequest.objects.create(
            employee=employee or self.employee, leave_type=policy.leave_type, start_date=day, end_date=end or day,
            total_days=D(days), reason='Personal work', status=status,
        )
        if booked:
            LeaveRequest.objects.filter(pk=r.pk).update(created_at=_aware(booked))
            r.refresh_from_db()
        if status == REQ_APPROVED:
            _deduct_balance_safe(r)
        return r

    def bal(self, policy=None, year=YEAR):
        return LeaveBalance.objects.get(employee=self.employee, leave_type=(policy or self.pink).leave_type, year=year)

    def expiries(self, policy=None):
        """month -> net expired (months netting to 0 omitted)."""
        out = {}
        for month, amount in LeaveCreditTransaction.objects.filter(
            employee=self.employee, leave_type=(policy or self.pink).leave_type, txn_type=CREDIT_TXN_EXPIRY,
        ).values_list('month', 'amount'):
            out[month] = out.get(month, D('0')) - amount
        return {m: v for m, v in out.items() if v}


class MonthEndExpiryTests(_MonthlyBase, TestCase):
    def test_unused_monthly_credit_expires_and_rerun_is_idempotent(self):
        self.credit(1, 3)
        self.credit(1, 4)
        self.credit(1, 7)                                                  # future month: not expired
        self.req(_weekday(YEAR, 4, 8), booked=datetime.date(YEAR, 4, 1))  # April's credit used in time
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(self.expiries(), {3: D('1')})
        bal = self.bal()
        self.assertEqual((bal.total_days, bal.used_days), (D('2'), D('1')))
        rows = LeaveCreditTransaction.objects.filter(txn_type=CREDIT_TXN_EXPIRY).count()
        sync_expiries(self.employee, self.pink, YEAR)                       # reruns add nothing
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(LeaveCreditTransaction.objects.filter(txn_type=CREDIT_TXN_EXPIRY).count(), rows)
        stmt = build_statement(self.employee, self.pink, YEAR)
        self.assertTrue(stmt.reconciled)
        self.assertEqual(stmt.months[2].expired, D('1'))
        self.assertEqual(stmt.months[6].credit_left, D('1'))               # July credit only usable in July

    def test_only_monthly_credit_expires_never_adjustments_or_opening(self):
        self.credit(2, 2)
        apply_adjustment(employee=self.employee, leave_type='pink', year=YEAR, amount='3', reason='Opening',
                         actor=self.admin, idempotency_key=_key())
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(self.expiries(), {2: D('2')})
        self.assertEqual(self.bal().total_days, D('3'))
        stmt = build_statement(self.employee, self.pink, YEAR)
        self.assertEqual((stmt.opening, stmt.adjustments, stmt.months[-1].closing), (D('3'), D('3'), D('3')))
        self.assertTrue(stmt.reconciled)

    def test_carry_forward_monthly_policy_never_expires(self):
        self.credit(1, 2, policy=self.cl)
        self.credit(1, 3, policy=self.cl)
        sync_expiries(self.employee, self.cl, YEAR)
        self.assertEqual(self.expiries(self.cl), {})
        stmt = build_statement(self.employee, self.cl, YEAR)
        self.assertEqual(stmt.months[3].carried_in, stmt.opening + D('2'))  # April carried Feb + Mar in
        self.assertTrue(stmt.reconciled)

    def test_policy_change_is_not_retroactive(self):
        self.pink.monthly_rules_from = datetime.date(YEAR, 5, 1)
        self.pink.save(update_fields=['monthly_rules_from'])
        self.credit(1, 3)
        self.credit(1, 5)
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(self.expiries(), {5: D('1')})                    # March untouched

    def test_policy_update_sets_rules_from_next_month_only_on_rule_change(self):
        from apps.hrms.serializers import LeavePolicyUpdateSerializer
        ser = LeavePolicyUpdateSerializer(self.casual, data={'credit_schedule': 'monthly'}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        self.casual.refresh_from_db()
        self.assertEqual(self.casual.monthly_rules_from, datetime.date(YEAR, 7, 1))
        self.casual.monthly_rules_from = datetime.date(YEAR, 2, 1)
        self.casual.save(update_fields=['monthly_rules_from'])
        ser = LeavePolicyUpdateSerializer(self.casual, data={'annual_days': '12'}, partial=True)  # unrelated edit
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        self.casual.refresh_from_db()
        self.assertEqual(self.casual.monthly_rules_from, datetime.date(YEAR, 2, 1))

    def test_past_month_credit_edit_recalculates_expiry(self):
        self.credit(2, 3)                                                   # March closed: expires at once
        self.assertEqual(self.expiries(), {3: D('2')})
        self.credit(1, 3)                                                   # reduce: expiry reopened then 1 re-expired
        self.assertEqual(self.expiries(), {3: D('1')})
        self.assertEqual(self.bal().total_days, D('0'))
        self.credit(3, 3)                                                   # raise: the extra also expires
        self.assertEqual(self.expiries(), {3: D('3')})
        self.assertEqual(self.bal().total_days, D('0'))
        self.assertGreaterEqual(LeaveCreditTransaction.objects.filter(txn_type=CREDIT_TXN_EXPIRY).count(), 3)
        self.assertTrue(build_statement(self.employee, self.pink, YEAR).reconciled)

    def test_expiry_rows_cannot_be_reversed_by_hand(self):
        self.credit(1, 3)
        txn = LeaveCreditTransaction.objects.get(txn_type=CREDIT_TXN_EXPIRY)
        with self.assertRaises(LeaveCreditError):
            reverse_transaction(employee=self.employee, txn_id=txn.id, reason='x', actor=self.admin, idempotency_key=_key())

    def test_annual_policies_are_never_expired(self):
        set_monthly_credit(employee=self.employee, leave_type='casual', year=YEAR, month=3, value='2', actor=self.admin)
        self.assertEqual(sync_expiries(self.employee, self.casual, YEAR), D('0'))
        self.assertEqual(self.expiries(self.casual), {})


class PendingProtectionTests(_MonthlyBase, TestCase):
    def test_pending_at_close_is_protected_then_expires_on_rejection(self):
        self.credit(1, 5)
        r = self.req(_weekday(YEAR, 5, 12), status=REQ_PENDING, booked=datetime.date(YEAR, 5, 2))
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(self.expiries(), {})                              # protected
        r.status = REQ_REJECTED
        r.save(update_fields=['status'])
        sync_after_request_change(r)
        self.assertEqual(self.expiries(), {5: D('1')})

    def test_late_booking_never_revives_expired_credit(self):
        self.credit(1, 4)
        self.assertEqual(self.expiries(), {4: D('1')})
        self.req(_weekday(YEAR, 4, 20), status=REQ_PENDING, booked=TODAY)  # backdated, booked after April closed
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(self.expiries(), {4: D('1')})
        self.assertEqual(build_statement(self.employee, self.pink, YEAR).shortfall, D('1'))

    def test_approval_of_protected_pending_keeps_expiry_unchanged(self):
        from apps.hrms.views.leave import _deduct_balance_safe
        self.credit(1, 5)
        r = self.req(_weekday(YEAR, 5, 12), status=REQ_PENDING, booked=datetime.date(YEAR, 5, 2))
        sync_expiries(self.employee, self.pink, YEAR)
        r.status = REQ_APPROVED
        r.save(update_fields=['status'])
        _deduct_balance_safe(r)
        sync_expiries(self.employee, self.pink, YEAR)
        self.assertEqual(self.expiries(), {})
        self.assertTrue(build_statement(self.employee, self.pink, YEAR).reconciled)


class MonthlyValidationTests(_MonthlyBase, TestCase):
    def shortfall(self, start, end=None, days='1', policy=None):
        return request_shortfall(self.employee, policy or self.pink, YEAR, start=start, end=end or start,
                                 duration='full_day', total_days=D(days))

    def test_future_month_uses_only_that_months_recorded_credit(self):
        self.credit(1, 8)
        self.assertEqual(self.shortfall(_weekday(YEAR, 8, 10)), D('0'))
        self.assertEqual(self.shortfall(_weekday(YEAR, 9, 10)), D('1'))   # no September credit recorded
        mon = _weekday(YEAR, 8, 10, weekday=0)
        self.assertEqual(self.shortfall(mon, mon + datetime.timedelta(days=1), days='2'), D('1'))

    def test_pending_requests_count_against_the_month(self):
        self.credit(1, 8)
        self.req(_weekday(YEAR, 8, 3), status=REQ_PENDING)
        self.assertEqual(self.shortfall(_weekday(YEAR, 8, 17)), D('1'))

    def test_request_spanning_two_months(self):
        m = _boundary_month(after=6)
        last = datetime.date(YEAR, m, calendar.monthrange(YEAR, m)[1])
        first = last + datetime.timedelta(days=1)
        self.credit(1, m)
        self.credit(1, m + 1)
        self.assertEqual(self.shortfall(last, first, days='2'), D('0'))
        self.credit(0, m + 1)
        self.assertEqual(self.shortfall(last, first, days='2'), D('1'))   # next month's day is no longer covered

    def test_non_expiring_pool_covers_any_month(self):
        apply_adjustment(employee=self.employee, leave_type='pink', year=YEAR, amount='2', reason='Opening',
                         actor=self.admin, idempotency_key=_key())
        mon = _weekday(YEAR, 9, 7, weekday=0)
        self.assertEqual(self.shortfall(mon, mon + datetime.timedelta(days=1), days='2'), D('0'))
        self.assertEqual(self.shortfall(mon, mon + datetime.timedelta(days=2), days='3'), D('1'))

    def test_carry_forward_type_runs_cumulatively(self):
        self.credit(1, 7, policy=self.cl)
        self.credit(1, 8, policy=self.cl)
        aug = _weekday(YEAR, 8, 10, weekday=0)
        jul = _weekday(YEAR, 7, 13, weekday=0)
        self.assertEqual(self.shortfall(aug, aug + datetime.timedelta(days=1), days='2', policy=self.cl), D('0'))
        self.assertEqual(self.shortfall(jul, jul + datetime.timedelta(days=1), days='2', policy=self.cl), D('1'))


class AnnualLumpExclusionTests(_MonthlyBase, TestCase):
    def test_joining_backfill_and_credit_all_give_monthly_types_no_lump(self):
        from apps.accounts.factories import make_role, make_user
        from apps.hrms.views.leave import _allocate_leaves_for_employee, _allocate_new_policy_for_existing_employees
        joiner = make_user('mb.joiner@test.com', role=make_role('credit_staff'), employee_id='MBJ01',
                           full_name='Joiner', branch='Hyderabad Credits', date_of_joining=datetime.date(YEAR, 1, 1))
        _allocate_leaves_for_employee(joiner, datetime.date(YEAR, 1, 1))
        self.assertEqual(LeaveBalance.objects.get(employee=joiner, leave_type='cl_monthly', year=YEAR).total_days, D('0'))
        self.assertEqual(LeaveBalance.objects.get(employee=joiner, leave_type='casual', year=YEAR).total_days, D('12'))
        LeaveBalance.objects.filter(employee=joiner, leave_type='cl_monthly').delete()
        _allocate_new_policy_for_existing_employees(self.cl)
        self.assertEqual(LeaveBalance.objects.get(employee=joiner, leave_type='cl_monthly', year=YEAR).total_days, D('0'))

        client = APIClient()
        client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': self.admin.email,
                                       'password': PASSWORD}, format='json')
        LeaveBalance.objects.filter(employee=joiner, leave_type__in=('cl_monthly', 'earned')).delete()
        joiner.onboarding_status = joiner.ONBOARDING_COMPLETE
        joiner.save(update_fields=['onboarding_status'])
        resp = client.post(reverse('leave-balance-credit'), {'year': YEAR, 'employee_id': 'MBJ01'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(LeaveBalance.objects.get(employee=joiner, leave_type='cl_monthly', year=YEAR).total_days, D('0'))
        self.assertEqual(LeaveBalance.objects.get(employee=joiner, leave_type='earned', year=YEAR).total_days, D('15'))


class YearBoundaryTests(_MonthlyBase, TestCase):
    def setUp(self):
        super().setUp()
        prev = YEAR - 1
        self.pink.monthly_rules_from = datetime.date(prev, 1, 1)
        self.pink.can_carry_forward = True
        self.pink.carry_forward_type = 'limited'
        self.pink.max_carry_forward_days = 5
        self.pink.carry_forward_mode = 'manual'
        self.pink.monthly_carry_forward = True        # December credit recorded before the switch
        self.pink.save()
        LeaveBalance.objects.create(employee=self.employee, leave_type='pink', year=prev,
                                    total_days=D('0'), used_days=D('0'), carried_forward=D('0'))
        apply_adjustment(employee=self.employee, leave_type='pink', year=prev, amount='2', reason='Opening',
                         actor=self.admin, idempotency_key=_key())
        set_monthly_credit(employee=self.employee, leave_type='pink', year=prev, month=12, value='1', actor=self.admin)
        self.pink.monthly_carry_forward = False       # now no-carry: December's credit is due to expire
        self.pink.save(update_fields=['monthly_carry_forward'])
        self.client = APIClient()
        self.client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': self.admin.email,
                                            'password': PASSWORD}, format='json')

    def test_preview_excludes_due_expiry_and_run_records_it_first(self):
        prev = YEAR - 1
        bal = self.bal(year=prev)
        self.assertEqual(bal.total_days, D('3'))
        self.assertEqual(unused_for_carry_forward(self.employee, self.pink, bal), D('2'))
        resp = self.client.post(reverse('carry-forward-run'), {'from_year': prev, 'to_year': YEAR}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.bal(year=prev).total_days, D('2'))                   # December expiry recorded
        new = self.bal(year=YEAR)
        self.assertEqual((new.total_days, new.carried_forward), (D('2'), D('2')))  # carry only, no lump

    def test_annual_policy_carry_forward_unchanged(self):
        prev = YEAR - 1
        self.casual.can_carry_forward = True
        self.casual.carry_forward_mode = 'manual'
        self.casual.max_carry_forward_days = 3
        self.casual.save()
        LeaveBalance.objects.create(employee=self.other_hyd, leave_type='casual', year=prev,
                                    total_days=D('12'), used_days=D('4'))
        self.client.post(reverse('carry-forward-run'), {'from_year': prev, 'to_year': YEAR}, format='json')
        new = LeaveBalance.objects.get(employee=self.other_hyd, leave_type='casual', year=YEAR)
        self.assertEqual((new.total_days, new.carried_forward), (D('15'), D('3')))  # 12 annual + capped 3



class ScheduledTaskTests(_MonthlyBase, TestCase):
    """The real Celery task bodies (run per tenant via run_for_all_tenants)."""

    def _due_march_expiry(self):
        # credit recorded while carry-forward was on, then switched off: expiry due, unrecorded
        self.pink.monthly_carry_forward = True
        self.pink.save(update_fields=['monthly_carry_forward'])
        self.credit(1, 3)
        self.pink.monthly_carry_forward = False
        self.pink.save(update_fields=['monthly_carry_forward'])

    def test_daily_expiry_task_records_due_expiry_once(self):
        from apps.hrms.tasks import sync_monthly_leave_expiry
        self._due_march_expiry()
        sync_monthly_leave_expiry()
        self.assertEqual(self.expiries(), {3: D('1')})
        sync_monthly_leave_expiry()                                         # next day: nothing new
        self.assertEqual(LeaveCreditTransaction.objects.filter(txn_type=CREDIT_TXN_EXPIRY).count(), 1)
        self.assertEqual(self.bal().total_days, D('0'))

    def test_annual_reset_expires_december_before_carrying_and_gives_no_lump(self):
        from apps.hrms.tasks import reset_annual_leave_balances
        prev = YEAR - 1
        self.pink.monthly_rules_from = datetime.date(prev, 1, 1)
        self.pink.can_carry_forward = True
        self.pink.carry_forward_type = 'unlimited'
        self.pink.carry_forward_mode = 'automatic'
        self.pink.monthly_carry_forward = True
        self.pink.save()
        LeaveBalance.objects.create(employee=self.employee, leave_type='pink', year=prev,
                                    total_days=D('0'), used_days=D('0'), carried_forward=D('0'))
        apply_adjustment(employee=self.employee, leave_type='pink', year=prev, amount='2', reason='Opening',
                         actor=self.admin, idempotency_key=_key())
        set_monthly_credit(employee=self.employee, leave_type='pink', year=prev, month=12, value='1', actor=self.admin)
        self.pink.monthly_carry_forward = False
        self.pink.save(update_fields=['monthly_carry_forward'])
        reset_annual_leave_balances()
        self.assertEqual(self.bal(year=prev).total_days, D('2'))           # December expiry recorded first
        new = self.bal(year=YEAR)
        self.assertEqual((new.total_days, new.carried_forward), (D('2'), D('2')))   # no annual lump

class ApprovalAndCacheApiTests(_MonthlyBase, TestCase):
    """Real date (no patch): applying needs a future month in the current year."""
    PATCH_TODAY = False

    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        if today.month >= 11:
            self.skipTest('needs a future month in the current year')
        self.month = today.month + 1
        self.sick = LeavePolicy.objects.create(
            leave_type='sick', annual_days=D('0'), is_active=True, credit_schedule='monthly',
            monthly_carry_forward=False, monthly_rules_from=datetime.date(YEAR, 1, 1),
        )
        self.employee.onboarding_status = self.employee.ONBOARDING_COMPLETE
        self.employee.assessment_status = 'complete'
        self.employee.save(update_fields=['onboarding_status', 'assessment_status'])
        cache.clear()
        self.client = APIClient()

    def _login(self, user):
        resp = self.client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email,
                                                   'password': PASSWORD}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _apply(self, start, end=None, leave_type='sick'):
        return self.client.post(reverse('leave-request-list'), {
            'leave_type': leave_type, 'start_date': start.isoformat(), 'end_date': (end or start).isoformat(),
            'duration': 'full_day', 'reason': 'Personal work at home',
        }, format='json')

    def _approve_fully(self, req_id, action='approve'):
        """Act at whichever stage the request is in (L1 manager, then L2 branch HR)."""
        resp = None
        for _ in range(2):
            req = LeaveRequest.objects.get(pk=req_id)
            if req.status not in (REQ_PENDING, REQ_L2_PENDING):
                break
            self._login(self.manager if req.status == REQ_PENDING else self.hr_hyd)
            resp = self.client.post(reverse('leave-request-approve', kwargs={'request_id': req_id}),
                                    {'action': action}, format='json')
            if resp.status_code != 200 or action == 'reject':
                break
        return resp

    def test_apply_checked_against_the_month_and_approval_rechecks(self):
        self.credit(1, self.month, policy=self.sick)
        self._login(self.employee)
        self.assertEqual(self._apply(_weekday(YEAR, self.month, 20)).status_code, 201)
        resp = self._apply(_weekday(YEAR, self.month, 21))                  # month's only credit already pending
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('monthly leave entitlement', resp.data['message'])
        req = LeaveRequest.objects.get(employee=self.employee, leave_type='sick')
        # meanwhile another day of that month is approved elsewhere and uses the credit
        self.req(_weekday(YEAR, self.month, 6), policy=self.sick, status=REQ_APPROVED)
        resp = self._approve_fully(req.id)
        self.assertEqual(resp.status_code, 409, resp.data)
        req.refresh_from_db()
        self.assertNotEqual(req.status, REQ_APPROVED)
        self.assertEqual(self.bal(self.sick).used_days, D('1'))              # only the other day

    def test_convert_to_lop_option_respected(self):
        self.sick.convert_to_lop = True
        self.sick.save(update_fields=['convert_to_lop'])
        cache.clear()
        self.credit(1, self.month, policy=self.sick)
        self._login(self.employee)
        tue = _weekday(YEAR, self.month, 10, weekday=1)
        resp = self._apply(tue, tue + datetime.timedelta(days=1))
        self.assertEqual(resp.status_code, 201, resp.data)
        req = LeaveRequest.objects.get(employee=self.employee, leave_type='sick')
        self.assertEqual((req.total_days, req.lop_days), (D('2'), D('1')))

    def test_cancel_and_reject_clear_the_dashboard_cache(self):
        self.credit(2, self.month, policy=self.sick)
        key = f'dashboard:employee:leave_balance:{self.employee.id}:{YEAR}'
        self._login(self.employee)
        self.assertEqual(self._apply(_weekday(YEAR, self.month, 10)).status_code, 201)
        req = LeaveRequest.objects.get(employee=self.employee, leave_type='sick')
        cache.set(key, {'stale': True}, 300)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(reverse('leave-request-detail', kwargs={'request_id': req.id}), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(cache.get(key))

        self._login(self.employee)
        self.assertEqual(self._apply(_weekday(YEAR, self.month, 20)).status_code, 201)
        req = LeaveRequest.objects.get(employee=self.employee, leave_type='sick', status__in=(REQ_PENDING, REQ_L2_PENDING))
        cache.set(key, {'stale': True}, 300)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._approve_fully(req.id, action='reject').status_code, 200)
        self.assertIsNone(cache.get(key))

    def test_custom_leave_types_can_be_applied_for(self):
        """Regression: custom (non built-in) leave types were rejected by the serializer."""
        self.credit(1, self.month, policy=self.pink)
        self._login(self.employee)
        resp = self._apply(_weekday(YEAR, self.month, 10), leave_type='pink')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(LeaveRequest.objects.get(employee=self.employee, leave_type='pink').total_days, D('1'))
        self.pink.is_active = False
        self.pink.save(update_fields=['is_active'])
        resp = self._apply(_weekday(YEAR, self.month, 20), leave_type='pink')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid leave type', resp.data['message'])
        self.assertEqual(self._apply(_weekday(YEAR, self.month, 20), leave_type='no_such_type').status_code, 400)

    def test_annual_policy_approval_clears_cache_and_deducts_as_before(self):
        key = f'dashboard:employee:leave_balance:{self.employee.id}:{YEAR}'
        self._login(self.employee)
        day = _weekday(YEAR, self.month, 10)
        self.assertEqual(self._apply(day, leave_type='casual').status_code, 201)
        req = LeaveRequest.objects.get(employee=self.employee, leave_type='casual')
        cache.set(key, {'stale': True}, 300)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self._approve_fully(req.id).status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, REQ_APPROVED)
        self.assertIsNone(cache.get(key))
        self.assertEqual(LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=YEAR).used_days,
                         D('2') + req.total_days)


class DashboardStatementTests(_MonthlyBase, TestCase):
    def test_statement_for_monthly_types_reconciles(self):
        self.credit(1, 3)
        self.credit(1, 4)
        self.req(_weekday(YEAR, 4, 8), booked=datetime.date(YEAR, 4, 1))
        sync_expiries(self.employee, self.pink, YEAR)
        self.employee.onboarding_status = self.employee.ONBOARDING_COMPLETE
        self.employee.assessment_status = 'complete'
        self.employee.save(update_fields=['onboarding_status', 'assessment_status'])
        client = APIClient()
        client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': self.employee.email,
                                       'password': PASSWORD}, format='json')
        data = client.get('/api/dashboard/employee/leave-balances/', {'year': YEAR}).data['data']
        rows = {b['leave_type']: b for b in data['balances']}
        stmt = rows['pink']['statement']
        self.assertTrue(stmt['reconciled'])
        march = next(m for m in stmt['months'] if m['month'] == 3)
        self.assertEqual((march['credit'], march['expired'], march['closing']), (1.0, 1.0, 0.0))
        april = next(m for m in stmt['months'] if m['month'] == 4)
        self.assertEqual((april['credit'], april['used'], april['expired']), (1.0, 1.0, 0.0))
        self.assertIsNone(rows['casual']['statement'])                      # annual types: no statement


class ConcurrentExpiryTests(_MonthlyBase, TransactionTestCase):
    def tearDown(self):
        for conn in connections.all():
            conn.close()

    def test_concurrent_syncs_record_expiry_once(self):
        # credit recorded while carry-forward was on, then switched off: expiry due, not yet recorded
        self.pink.monthly_carry_forward = True
        self.pink.save(update_fields=['monthly_carry_forward'])
        self.credit(1, 3)
        self.pink.monthly_carry_forward = False
        self.pink.save(update_fields=['monthly_carry_forward'])
        results = []

        def run():
            from apps.tenants.models import Client
            connection.set_tenant(Client.objects.get(company_code=TEST_COMPANY_CODE))
            try:
                policy = LeavePolicy.objects.get(leave_type='pink')
                results.append(sync_expiries(self.employee, policy, YEAR))
            except Exception as exc:  # noqa: BLE001 — asserted below
                results.append(exc)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertFalse([r for r in results if isinstance(r, Exception)], results)
        self.assertEqual(sorted(results), [D('-1'), D('0'), D('0'), D('0')])
        self.assertEqual(LeaveCreditTransaction.objects.filter(txn_type=CREDIT_TXN_EXPIRY).count(), 1)
        self.assertEqual(self.bal().total_days, D('0'))


class ProfileLeaveStatsTests(_MonthlyBase, TestCase):
    """Employee Profile → Leave: /leave/stats/?employee_id= carries the monthly statement."""

    def setUp(self):
        super().setUp()
        self.credit(1, 3)                                                  # March: unused -> expires
        self.credit(1, 4)
        self.req(_weekday(YEAR, 4, 8), booked=datetime.date(YEAR, 4, 1))  # April credit used in time
        sync_expiries(self.employee, self.pink, YEAR)                       # what the daily task does
        self.client = APIClient()

    def _login(self, user):
        resp = self.client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email,
                                                   'password': PASSWORD}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _stats(self, year=YEAR, employee_id='CREMP01'):
        params = {'year': year}
        if employee_id:
            params['employee_id'] = employee_id
        resp = self.client.get(reverse('leave-stats'), params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return {b['leave_type']: b for b in resp.data['data']['balances']}

    def test_monthly_and_annual_types_side_by_side(self):
        self._login(self.hr_hyd)
        rows = self._stats()
        pink, casual = rows['pink'], rows['casual']
        self.assertEqual((casual['credit_schedule'], casual['statement']), ('annual', None))
        self.assertEqual((casual['total_days'], casual['used_days']), (12.0, 2.0))         # annual card unchanged
        self.assertEqual(pink['credit_schedule'], 'monthly')
        stmt = pink['statement']
        months = {m['month']: m for m in stmt['months']}
        self.assertEqual((months[3]['credit'], months[3]['expired'], months[3]['closing']), (1.0, 1.0, 0.0))
        self.assertEqual((months[4]['credit'], months[4]['used'], months[4]['expired']), (1.0, 1.0, 0.0))
        self.assertEqual((months[1]['credit'], months[1]['closing']), (0.0, 0.0))          # month with no record
        self.assertEqual(sorted(months)[:6], [1, 2, 3, 4, 5, 6])                           # Jan..June (TODAY)
        self.assertEqual((stmt['total_credited'], stmt['total_expired']), (2.0, 1.0))
        self.assertFalse(stmt['monthly_carry_forward'])
        self.assertTrue(stmt['reconciled'])
        self.assertEqual(pink['available'], pink['total_days'] - pink['used_days'])        # yearly figure kept

    def test_year_navigation_loads_that_years_records(self):
        prev = YEAR - 1
        self.pink.monthly_rules_from = datetime.date(prev, 1, 1)
        self.pink.save(update_fields=['monthly_rules_from'])
        LeaveBalance.objects.create(employee=self.employee, leave_type='pink', year=prev,
                                    total_days=D('0'), used_days=D('0'), carried_forward=D('0'))
        set_monthly_credit(employee=self.employee, leave_type='pink', year=prev, month=11, value='2', actor=self.admin)
        self._login(self.hr_hyd)
        stmt = self._stats(year=prev)['pink']['statement']
        self.assertEqual(len(stmt['months']), 12)                                          # past year: all months
        self.assertEqual({m['month']: m['credit'] for m in stmt['months'] if m['credit']}, {11: 2.0})
        self.assertEqual(self._stats()['pink']['statement']['total_credited'], 2.0)       # this year's own 2

    def test_carry_forward_type_shows_carried_in(self):
        self.credit(1, 2, policy=self.cl)
        self.credit(1, 3, policy=self.cl)
        self._login(self.hr_hyd)
        stmt = self._stats()['cl_monthly']['statement']
        months = {m['month']: m for m in stmt['months']}
        self.assertTrue(stmt['monthly_carry_forward'])
        self.assertEqual((months[3]['carried_in'], months[4]['carried_in']), (1.0, 2.0))
        self.assertTrue(all(not m['carry_off'] and m['expired'] == 0 for m in stmt['months']))

    def test_statement_respects_profile_scope(self):
        self._login(self.hr_mum)                         # other branch: no statement through this endpoint
        self.assertIsNone(self._stats()['pink']['statement'])
        self._login(self.manager)                        # manager without employees.view: no statement
        self.assertIsNone(self._stats()['pink']['statement'])
        self._login(self.admin)                          # settings.edit: all branches
        self.assertIsNotNone(self._stats()['pink']['statement'])
        self._login(self.other_hyd)                      # no permission at all
        self.assertEqual(self.client.get(reverse('leave-stats'), {'employee_id': 'CREMP01', 'year': YEAR}).status_code, 403)

    def test_employee_sees_own_statement(self):
        self._login(self.employee)
        rows = self._stats(employee_id=None)
        self.assertIsNotNone(rows['pink']['statement'])
        self.assertIsNone(rows['casual']['statement'])

    def test_schedule_comes_from_the_policy_and_is_null_without_one(self):
        LeaveBalance.objects.create(employee=self.employee, leave_type='ghost', year=YEAR,
                                    total_days=D('2'), used_days=D('0'), carried_forward=D('0'))
        self._login(self.hr_hyd)
        rows = self._stats()
        self.assertEqual({k: rows[k]['credit_schedule'] for k in ('pink', 'cl_monthly', 'casual', 'ghost') if k in rows},
                         {'pink': 'monthly', 'casual': 'annual', 'ghost': None})
        self.assertIsNone(rows['ghost']['statement'])

    def test_manage_leave_credits_rows_carry_the_policy_schedule(self):
        LeaveBalance.objects.create(employee=self.employee, leave_type='ghost', year=YEAR,
                                    total_days=D('2'), used_days=D('0'), carried_forward=D('0'))
        self._login(self.hr_hyd)
        resp = self.client.get(reverse('leave-credit-overview', kwargs={'employee_id': 'CREMP01'}), {'year': YEAR})
        self.assertEqual(resp.status_code, 200, resp.data)
        sched = {r['leave_type']: r['credit_schedule'] for r in resp.data['data']['summaries']}
        self.assertEqual((sched['pink'], sched['casual'], sched['ghost']), ('monthly', 'annual', None))
        assignable = {t['value']: t['credit_schedule'] for t in resp.data['data']['assignable_leave_types']}
        self.assertEqual((assignable['pink'], assignable['cl_monthly'], assignable['earned']), ('monthly', 'monthly', 'annual'))
        self.assertNotIn('ghost', assignable)                          # no policy -> never assignable
