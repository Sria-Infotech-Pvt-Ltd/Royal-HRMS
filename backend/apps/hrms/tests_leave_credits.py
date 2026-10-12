"""
Phase 1 — employee-wise leave credit management.

Covers the shared service (signed deltas, locking, idempotency, reversals,
used/pending floor), the API's permission scoping, yearly/monthly summary
reconciliation, the working-day monthly split, and real concurrency.
"""
from __future__ import annotations

import datetime
import threading
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.hrms.models import (
    REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING,
    Holiday, LeaveBalance, LeaveCreditTransaction, LeavePolicy, LeaveRequest,
)
from apps.hrms.services_leave_credit import (
    LeaveCreditConflict, LeaveCreditError, apply_adjustment, monthly_summary,
    reverse_transaction, yearly_summary,
)
from config.test_runner import TEST_COMPANY_CODE

PASSWORD = 'TestPass123!'
HYD = 'Hyderabad Credits'
MUM = 'Mumbai Credits'
YEAR = timezone.localdate().year


def _key() -> str:
    return uuid.uuid4().hex


class _Fixtures:
    def make_fixtures(self):
        cache.clear()
        self.casual = LeavePolicy.objects.create(leave_type='casual', annual_days=Decimal('12'), is_active=True)
        self.earned = LeavePolicy.objects.create(leave_type='earned', annual_days=Decimal('15'), is_active=True)

        hr_role = make_role('credit_branch_hr', permission_codenames=['leave.approve', 'employees.view'])
        self.hr_hyd = make_user('credit.hr.hyd@test.com', role=hr_role, employee_id='CRHRH01', full_name='HR Hyd', branch=HYD)
        self.hr_mum = make_user('credit.hr.mum@test.com', role=hr_role, employee_id='CRHRM01', full_name='HR Mum', branch=MUM)
        self.admin = make_user(
            'credit.admin@test.com', role=make_role('credit_admin', permission_codenames=['settings.edit', 'leave.approve']),
            employee_id='CRADM01', full_name='Admin', branch=HYD,
        )
        manager_role = make_role('credit_manager', permission_codenames=['leave.approve'], can_manage_team=True)
        self.manager = make_user('credit.mgr@test.com', role=manager_role, employee_id='CRMGR01', full_name='Manager', branch=HYD)
        staff = make_role('credit_staff')
        self.employee = make_user(
            'credit.emp@test.com', role=staff, employee_id='CREMP01', full_name='Employee', branch=HYD,
            reporting_manager=self.manager,
        )
        self.other_hyd = make_user('credit.other@test.com', role=staff, employee_id='CREMP02', full_name='Other', branch=HYD)
        self.emp_mum = make_user('credit.mumemp@test.com', role=staff, employee_id='CREMP03', full_name='Mum Emp', branch=MUM)
        self.balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=YEAR,
            total_days=Decimal('12'), used_days=Decimal('2'), carried_forward=Decimal('1'),
        )

    def adjust(self, amount, **kw):
        kw.setdefault('employee', self.employee)
        kw.setdefault('leave_type', 'casual')
        kw.setdefault('year', YEAR)
        kw.setdefault('reason', 'Test reason')
        kw.setdefault('actor', self.hr_hyd)
        kw.setdefault('idempotency_key', _key())
        return apply_adjustment(amount=amount, **kw)

    def pending_request(self, days, status=REQ_PENDING, employee=None, start=None):
        start = start or datetime.date(YEAR, 6, 1)
        return LeaveRequest.objects.create(
            employee=employee or self.employee, leave_type='casual', start_date=start,
            end_date=start + datetime.timedelta(days=int(days) - 1), total_days=Decimal(str(days)),
            reason='x', status=status,
        )


class LeaveCreditServiceTests(_Fixtures, TestCase):
    def setUp(self):
        self.make_fixtures()

    def _balance(self):
        self.balance.refresh_from_db()
        return self.balance

    def test_positive_and_negative_adjustments_change_total_only(self):
        txn, created = self.adjust('3')
        self.assertTrue(created)
        self.assertEqual((txn.total_before, txn.total_after), (Decimal('12'), Decimal('15')))
        self.adjust('-1.5')
        b = self._balance()
        self.assertEqual(b.total_days, Decimal('13.5'))
        self.assertEqual(b.used_days, Decimal('2'))
        self.assertEqual(LeaveCreditTransaction.objects.filter(employee=self.employee).count(), 2)
        self.assertEqual(AuditLog.objects.filter(action='leave_credit_adjusted').count(), 2)

    def test_reason_is_mandatory(self):
        for reason in ('', '   ', None):
            with self.subTest(reason=reason), self.assertRaises(LeaveCreditError):
                self.adjust('1', reason=reason)
        self.assertEqual(self._balance().total_days, Decimal('12'))

    def test_invalid_amounts_rejected(self):
        for amount in ('0', 'abc', '1.25', '400', None, 'NaN'):
            with self.subTest(amount=amount), self.assertRaises(LeaveCreditError):
                self.adjust(amount)
        self.assertFalse(LeaveCreditTransaction.objects.exists())

    def test_future_year_and_loss_of_pay_rejected(self):
        with self.assertRaises(LeaveCreditError):
            self.adjust('1', year=YEAR + 1)
        with self.assertRaises(LeaveCreditError):
            self.adjust('1', leave_type='lwp')

    def test_cannot_drop_below_used_plus_pending(self):
        self.pending_request(3)
        self.pending_request(1, status=REQ_L2_PENDING, start=datetime.date(YEAR, 7, 1))
        with self.assertRaises(LeaveCreditError):
            self.adjust('-6.5')  # 12 - 6.5 = 5.5 < 2 used + 4 pending
        self.adjust('-6')        # exactly 6 left
        self.assertEqual(self._balance().total_days, Decimal('6'))

    def test_cannot_go_below_zero_even_when_negative_balance_allowed(self):
        self.casual.allow_negative_balance = True
        self.casual.save()
        self.adjust('-11')  # below used, allowed by policy
        with self.assertRaises(LeaveCreditError):
            self.adjust('-2')

    def test_same_key_is_applied_once(self):
        key = _key()
        _, first = self.adjust('2', idempotency_key=key)
        txn, second = self.adjust('2', idempotency_key=key)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(self._balance().total_days, Decimal('14'))
        self.assertEqual(LeaveCreditTransaction.objects.count(), 1)

    def test_same_key_different_request_conflicts(self):
        key = _key()
        self.adjust('2', idempotency_key=key)
        with self.assertRaises(LeaveCreditConflict):
            self.adjust('3', idempotency_key=key)
        self.assertEqual(self._balance().total_days, Decimal('14'))

    def test_missing_current_year_row_is_created_once(self):
        self.adjust('3', leave_type='earned')
        self.adjust('1', leave_type='earned')
        rows = LeaveBalance.objects.filter(employee=self.employee, leave_type='earned', year=YEAR)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().total_days, Decimal('4'))
        self.assertEqual(rows.get().used_days, Decimal('0'))

    def test_missing_row_rules(self):
        with self.assertRaises(LeaveCreditError):
            self.adjust('-1', leave_type='earned')
        with self.assertRaises(LeaveCreditError):
            self.adjust('1', leave_type='earned', year=YEAR - 1)
        self.earned.is_active = False
        self.earned.save()
        with self.assertRaises(LeaveCreditError):
            self.adjust('1', leave_type='earned')
        self.assertFalse(LeaveBalance.objects.filter(employee=self.employee, leave_type='earned').exists())

    def test_reversal_is_compensating_and_keeps_history(self):
        original, _ = self.adjust('4')
        reversal, created = reverse_transaction(
            employee=self.employee, txn_id=original.id, reason='Entered by mistake',
            actor=self.hr_hyd, idempotency_key=_key(),
        )
        self.assertTrue(created)
        self.assertEqual(reversal.amount, Decimal('-4'))
        self.assertEqual(reversal.reverses_id, original.id)
        self.assertEqual(self._balance().total_days, Decimal('12'))
        self.assertTrue(LeaveCreditTransaction.objects.filter(pk=original.pk).exists())
        self.assertEqual(AuditLog.objects.filter(action='leave_credit_reversed').count(), 1)

    def test_reversal_rules(self):
        original, _ = self.adjust('4')
        key = _key()
        reversal, _ = reverse_transaction(employee=self.employee, txn_id=original.id, reason='r', actor=self.hr_hyd, idempotency_key=key)
        _, replay = reverse_transaction(employee=self.employee, txn_id=original.id, reason='r', actor=self.hr_hyd, idempotency_key=key)
        self.assertFalse(replay)
        with self.assertRaises(LeaveCreditError):
            reverse_transaction(employee=self.employee, txn_id=original.id, reason='r', actor=self.hr_hyd, idempotency_key=_key())
        with self.assertRaises(LeaveCreditError):
            reverse_transaction(employee=self.employee, txn_id=reversal.id, reason='r', actor=self.hr_hyd, idempotency_key=_key())
        self.assertEqual(self._balance().total_days, Decimal('12'))

    def test_reversing_a_credit_respects_used_plus_pending(self):
        original, _ = self.adjust('5')   # 17
        self.pending_request(14)          # used 2 + pending 14 = 16
        with self.assertRaises(LeaveCreditError):
            reverse_transaction(employee=self.employee, txn_id=original.id, reason='r', actor=self.hr_hyd, idempotency_key=_key())

    def test_stale_balance_object_never_overwrites_concurrent_deduction(self):
        from apps.hrms.views.leave import _deduct_balance_safe
        stale = LeaveBalance.objects.get(pk=self.balance.pk)  # read before the approval below
        approved = self.pending_request(3, status=REQ_APPROVED)
        _deduct_balance_safe(approved)
        self.adjust('1')
        stale.refresh_from_db()
        self.assertEqual((stale.total_days, stale.used_days), (Decimal('13'), Decimal('5')))


class LeaveCreditSummaryTests(_Fixtures, TestCase):
    def setUp(self):
        self.make_fixtures()

    def test_yearly_summary_reconciles_to_balance(self):
        self.adjust('3')
        self.adjust('-1')
        self.pending_request(2)
        row = next(r for r in yearly_summary(self.employee, YEAR) if r['leave_type'] == 'casual')
        self.balance.refresh_from_db()
        self.assertEqual(row['manual_adjustments'], 2.0)
        self.assertEqual(row['carried_forward'], 1.0)
        self.assertEqual(row['opening_or_allocated'], 11.0)
        self.assertEqual(row['opening_or_allocated'] + row['carried_forward'] + row['manual_adjustments'], row['total_credits'])
        self.assertEqual(row['total_credits'], float(self.balance.total_days))
        self.assertEqual(row['remaining'], float(self.balance.total_days - self.balance.used_days))
        self.assertEqual(row['pending'], 2.0)
        self.assertEqual(row['available_after_pending'], row['remaining'] - 2.0)

    def _expected_split(self, start, end):
        from apps.hrms.views.leave import _calc_working_days
        first_end = datetime.date(start.year, start.month + 1, 1) - datetime.timedelta(days=1)
        w1 = Decimal(str(_calc_working_days(start, first_end, 'full_day', self.casual, self.employee)))
        w2 = Decimal(str(_calc_working_days(first_end + datetime.timedelta(days=1), end, 'full_day', self.casual, self.employee)))
        return w1, w2

    def test_multi_month_leave_split_by_working_days_with_holiday(self):
        start, end = datetime.date(YEAR, 1, 26), datetime.date(YEAR, 2, 6)
        # A holiday on the first weekday of February reduces February's working days.
        feb_day = next(d for d in (datetime.date(YEAR, 2, n) for n in range(1, 7)) if d.weekday() < 5)
        Holiday.objects.create(name='Credit Test Holiday', date=feb_day)
        cache.clear()
        w1, w2 = self._expected_split(start, end)
        self.assertGreater(w1, 0)
        self.assertGreater(w2, 0)
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', start_date=start, end_date=end,
            total_days=w1 + w2, reason='x', status=REQ_APPROVED,
        )
        self.balance.used_days = Decimal('2') + w1 + w2
        self.balance.save()

        data = monthly_summary(self.employee, 'casual', YEAR)
        months = {m['month']: m for m in data['months']}
        self.assertEqual(months[1]['used'], float(w1))
        self.assertEqual(months[2]['used'], float(w2))
        self.assertEqual(data['used_not_itemised'], 2.0)  # opening used with no requests behind it
        itemised = sum(m['used'] for m in data['months']) + data['used_in_next_year_months'] + data['used_not_itemised']
        self.assertAlmostEqual(itemised, data['total_used'])
        self.assertEqual(data['approximated_requests'], 0)

    def test_lop_part_is_not_counted_as_used(self):
        start = datetime.date(YEAR, 3, 2)
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', start_date=start, end_date=start,
            total_days=Decimal('1'), lop_days=Decimal('1'), reason='x', status=REQ_APPROVED,
        )
        data = monthly_summary(self.employee, 'casual', YEAR)
        self.assertEqual(data['months'][2]['used'], 0.0)

    def test_cross_year_leave_counts_against_start_year(self):
        prev = YEAR - 1
        balance = LeaveBalance.objects.create(employee=self.employee, leave_type='earned', year=prev, total_days=Decimal('15'))
        start, end = datetime.date(prev, 12, 29), datetime.date(YEAR, 1, 9)
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='earned', start_date=start, end_date=end,
            total_days=Decimal('8'), reason='x', status=REQ_APPROVED,
        )
        balance.used_days = Decimal('8')
        balance.save()
        data = monthly_summary(self.employee, 'earned', prev)
        self.assertGreater(data['used_in_next_year_months'], 0)
        total = sum(m['used'] for m in data['months']) + data['used_in_next_year_months'] + data['used_not_itemised']
        self.assertAlmostEqual(total, 8.0)
        self.assertAlmostEqual(data['used_not_itemised'], 0.0)

    def test_monthly_credits_match_yearly_adjustments(self):
        self.adjust('3')
        self.adjust('-0.5')
        data = monthly_summary(self.employee, 'casual', YEAR)
        row = next(r for r in yearly_summary(self.employee, YEAR) if r['leave_type'] == 'casual')
        self.assertEqual(data['total_credit_adjustments'], row['manual_adjustments'])
        this_month = timezone.localtime().month
        self.assertEqual(data['months'][this_month - 1]['credit_adjustments'], 2.5)


class LeaveCreditApiPermissionTests(_Fixtures, TestCase):
    def setUp(self):
        self.make_fixtures()
        self.client = APIClient()

    def _login(self, user):
        resp = self.client.post(
            reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email, 'password': PASSWORD}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def _post_adjust(self, employee, amount='1', **extra):
        payload = {'leave_type': 'casual', 'year': YEAR, 'amount': amount, 'reason': 'Bonus day', 'idempotency_key': _key(), **extra}
        return self.client.post(reverse('leave-credit-adjust', kwargs={'employee_id': employee.employee_id}), payload, format='json')

    def _get(self, employee):
        return self.client.get(reverse('leave-credit-overview', kwargs={'employee_id': employee.employee_id}), {'year': YEAR})

    def test_branch_hr_manages_own_branch(self):
        self._login(self.hr_hyd)
        self.assertEqual(self._get(self.employee).status_code, 200)
        resp = self._post_adjust(self.employee)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('13'))

    def test_branch_hr_cannot_touch_other_branch(self):
        LeaveBalance.objects.create(employee=self.emp_mum, leave_type='casual', year=YEAR, total_days=Decimal('12'))
        self._login(self.hr_hyd)
        self.assertEqual(self._get(self.emp_mum).status_code, 404)
        self.assertEqual(self._post_adjust(self.emp_mum).status_code, 404)
        self.assertFalse(LeaveCreditTransaction.objects.filter(employee=self.emp_mum).exists())

    def test_admin_with_settings_edit_can_manage_any_branch(self):
        LeaveBalance.objects.create(employee=self.emp_mum, leave_type='casual', year=YEAR, total_days=Decimal('12'))
        self._login(self.admin)
        self.assertEqual(self._post_adjust(self.emp_mum).status_code, 201)

    def test_manager_only_for_direct_reports(self):
        LeaveBalance.objects.create(employee=self.other_hyd, leave_type='casual', year=YEAR, total_days=Decimal('12'))
        self._login(self.manager)
        self.assertEqual(self._post_adjust(self.employee).status_code, 201)
        self.assertEqual(self._get(self.other_hyd).status_code, 404)
        self.assertEqual(self._post_adjust(self.other_hyd).status_code, 404)

    def test_self_adjustment_blocked(self):
        LeaveBalance.objects.create(employee=self.hr_hyd, leave_type='casual', year=YEAR, total_days=Decimal('12'))
        self._login(self.hr_hyd)
        self.assertEqual(self._post_adjust(self.hr_hyd).status_code, 404)

    def test_roles_without_leave_approve_blocked(self):
        self._login(self.other_hyd)
        self.assertEqual(self._get(self.employee).status_code, 403)
        self.assertEqual(self._post_adjust(self.employee).status_code, 403)

    def test_validation_errors_and_duplicates_over_api(self):
        self._login(self.hr_hyd)
        self.assertEqual(self._post_adjust(self.employee, reason='').status_code, 400)
        self.assertEqual(self._post_adjust(self.employee, amount='0').status_code, 400)
        key = _key()
        first = self._post_adjust(self.employee, idempotency_key=key)
        again = self._post_adjust(self.employee, idempotency_key=key)
        other = self._post_adjust(self.employee, amount='2', idempotency_key=key)
        self.assertEqual((first.status_code, again.status_code, other.status_code), (201, 200, 409))
        self.assertTrue(again.data['data']['duplicate'])
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('13'))

    def test_reverse_endpoint_and_overview_payload(self):
        self._login(self.hr_hyd)
        created = self._post_adjust(self.employee, amount='2').data['data']['transaction']
        resp = self.client.post(
            reverse('leave-credit-reverse', kwargs={'employee_id': self.employee.employee_id, 'txn_id': created['id']}),
            {'reason': 'Mistake', 'idempotency_key': _key()}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        data = self._get(self.employee).data['data']
        self.assertEqual(data['leave_type'], 'casual')
        self.assertEqual(len(data['transactions']), 2)
        original = next(t for t in data['transactions'] if t['id'] == created['id'])
        self.assertFalse(original['can_reverse'])
        self.assertIsNotNone(original['reversed_by'])
        self.assertEqual(data['monthly']['leave_type'], 'casual')
        self.assertIn('casual', [t['value'] for t in data['assignable_leave_types']])

    def test_cannot_reverse_another_employees_transaction(self):
        LeaveBalance.objects.create(employee=self.other_hyd, leave_type='casual', year=YEAR, total_days=Decimal('12'))
        theirs, _ = self.adjust('1', employee=self.other_hyd)
        self._login(self.hr_hyd)
        resp = self.client.post(
            reverse('leave-credit-reverse', kwargs={'employee_id': self.employee.employee_id, 'txn_id': theirs.id}),
            {'reason': 'x', 'idempotency_key': _key()}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_legacy_adjust_endpoint_scoping_unchanged(self):
        self._login(self.manager)
        url = reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
        other_balance = LeaveBalance.objects.create(employee=self.other_hyd, leave_type='casual', year=YEAR, total_days=Decimal('12'))
        self.assertEqual(
            self.client.get(reverse('leave-balance-adjust', kwargs={'balance_id': other_balance.pk})).status_code, 404,
        )


class LeaveCreditConcurrencyTests(_Fixtures, TransactionTestCase):
    """Real commits and separate DB connections per thread, to exercise row locking."""

    def setUp(self):
        self.make_fixtures()

    def tearDown(self):
        for conn in connections.all():
            conn.close()

    def _in_thread(self, fn, results):
        def run():
            from apps.tenants.models import Client
            connection.set_tenant(Client.objects.get(company_code=TEST_COMPANY_CODE))
            try:
                results.append(fn())
            except Exception as exc:  # noqa: BLE001 — collected and asserted on below
                results.append(exc)
            finally:
                connections.close_all()
        return threading.Thread(target=run)

    def test_duplicate_submissions_race_applies_once(self):
        key, results = _key(), []
        threads = [self._in_thread(lambda: self.adjust('2', idempotency_key=key), results) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertFalse([r for r in results if isinstance(r, Exception)], results)
        self.assertEqual(sum(1 for _, created in results if created), 1)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('14'))
        self.assertEqual(LeaveCreditTransaction.objects.count(), 1)

    def test_adjustments_and_approvals_interleaved_lose_nothing(self):
        from apps.hrms.views.leave import _deduct_balance_safe
        approved = [
            self.pending_request(1, status=REQ_APPROVED, start=datetime.date(YEAR, 3, d)) for d in range(2, 6)
        ]
        results, threads = [], []
        for req in approved:
            threads.append(self._in_thread(lambda r=req: _deduct_balance_safe(r), results))
            threads.append(self._in_thread(lambda: self.adjust('1'), results))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertFalse([r for r in results if isinstance(r, Exception)], results)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('16'))  # 12 + 4 credits
        self.assertEqual(self.balance.used_days, Decimal('6'))    # 2 + 4 approvals
