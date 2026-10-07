"""
Phase 6A — tests for the leave ledger, comp-off earning, the
leave_status_for hook, holiday calendar migration/lookup, and the
LeaveType FK/choices defect fix (Task A.3).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.hrms.models import DURATION_FULL, REQ_APPROVED, LeaveBalance, LeavePolicy, LeaveRequest
from apps.hrms.models_leave_ledger import LeaveTransaction, LeaveType
from apps.hrms.services_comp_off import CompOffError, expire_comp_off_lots, grant_comp_off
from apps.hrms.services_leave_ledger import create_transaction, is_unpaid_lwp, recompute_balance_cache
from apps.hrms.services_leave_status import leave_status_for


class LeaveTypeDefectFixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_leave_types')

    def test_custom_leave_policy_type_can_get_a_balance_row(self):
        LeavePolicy.objects.create(leave_type='marriage', leave_type_label='Marriage Leave', annual_days=5)
        employee = make_user('customleaveemp@test.com', password='TestPass123!')

        balance = LeaveBalance.objects.create(employee=employee, leave_type='marriage', year=2026, total_days=5)
        self.assertEqual(balance.leave_type, 'marriage')

    def test_custom_leave_policy_type_can_get_a_request_row(self):
        employee = make_user('customleaveemp2@test.com', password='TestPass123!')
        request = LeaveRequest.objects.create(
            employee=employee, leave_type='marriage', duration=DURATION_FULL,
            start_date=date(2026, 5, 1), end_date=date(2026, 5, 1), total_days=Decimal('1'),
            reason='test', status=REQ_APPROVED,
        )
        self.assertEqual(request.leave_type, 'marriage')

    def test_is_unpaid_lwp_matches_seeded_lwp_type(self):
        self.assertTrue(is_unpaid_lwp('lwp'))
        self.assertFalse(is_unpaid_lwp('casual'))

    def test_is_unpaid_lwp_falls_back_to_literal_for_unseeded_code(self):
        self.assertFalse(is_unpaid_lwp('totally_unseeded_code'))


class LeaveLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_leave_types')

    def setUp(self):
        self.employee = make_user('ledgeremp@test.com', password='TestPass123!')
        self.casual = LeaveType.objects.get(code='casual')

    def test_opening_and_accrual_build_total_days(self):
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_OPENING, quantity=Decimal('12'), effective_date=date(2026, 1, 1))
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_ACCRUAL, quantity=Decimal('1'), effective_date=date(2026, 2, 1))

        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=2026)
        self.assertEqual(balance.total_days, Decimal('13.0'))
        self.assertEqual(balance.used_days, Decimal('0.0'))

    def test_availed_increases_used_days(self):
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_OPENING, quantity=Decimal('12'), effective_date=date(2026, 1, 1))
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_AVAILED, quantity=Decimal('-2'), effective_date=date(2026, 3, 1))

        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=2026)
        self.assertEqual(balance.total_days, Decimal('12.0'))
        self.assertEqual(balance.used_days, Decimal('2.0'))

    def test_availed_reversal_reduces_used_days(self):
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_AVAILED, quantity=Decimal('-2'), effective_date=date(2026, 3, 1))
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_AVAILED_REVERSAL, quantity=Decimal('2'), effective_date=date(2026, 3, 5))

        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=2026)
        self.assertEqual(balance.used_days, Decimal('0.0'))

    def test_carry_forward_in_tracked_separately_with_expiry(self):
        create_transaction(
            self.employee, self.casual, txn_type=LeaveTransaction.TXN_CARRY_FORWARD_IN, quantity=Decimal('3'),
            effective_date=date(2026, 1, 1), expiry_date=date(2026, 3, 31),
        )
        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=2026)
        self.assertEqual(balance.carried_forward, Decimal('3.0'))
        self.assertEqual(balance.carry_forward_expiry_date, date(2026, 3, 31))

    def test_lapse_reduces_total_days(self):
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_OPENING, quantity=Decimal('12'), effective_date=date(2026, 1, 1))
        create_transaction(self.employee, self.casual, txn_type=LeaveTransaction.TXN_LAPSE, quantity=Decimal('-2'), effective_date=date(2026, 12, 31))

        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=2026)
        self.assertEqual(balance.total_days, Decimal('10.0'))


class CompOffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_leave_types')

    def setUp(self):
        self.employee = make_user('compoffemp@test.com', password='TestPass123!')

    def test_full_day_grant_from_eight_hours(self):
        txn = grant_comp_off(self.employee, work_date=date(2026, 1, 4), hours_worked=8)
        self.assertEqual(txn.quantity, Decimal('1'))
        self.assertEqual(txn.expiry_date, date(2026, 1, 4) + timedelta(days=60))

    def test_half_day_grant_from_four_hours(self):
        txn = grant_comp_off(self.employee, work_date=date(2026, 1, 4), hours_worked=4)
        self.assertEqual(txn.quantity, Decimal('0.5'))

    def test_insufficient_hours_rejected(self):
        with self.assertRaises(CompOffError):
            grant_comp_off(self.employee, work_date=date(2026, 1, 4), hours_worked=2)

    def test_expired_lot_creates_reversal(self):
        grant_comp_off(self.employee, work_date=date(2020, 1, 1), hours_worked=8, expiry_days=1)
        result = expire_comp_off_lots(as_of=date(2020, 1, 5))

        self.assertEqual(result['expired'], 1)
        comp_off_type = LeaveType.objects.get(code='comp_off')
        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='comp_off', year=2020)
        self.assertEqual(balance.total_days, Decimal('0.0'))

    def test_expiring_twice_does_not_double_expire(self):
        grant_comp_off(self.employee, work_date=date(2020, 1, 1), hours_worked=8, expiry_days=1)
        expire_comp_off_lots(as_of=date(2020, 1, 5))
        result2 = expire_comp_off_lots(as_of=date(2020, 1, 10))
        self.assertEqual(result2['expired'], 0)


class LeaveStatusForTests(TestCase):
    def setUp(self):
        self.employee = make_user('leavestatusemp@test.com', password='TestPass123!')

    def test_no_leave_returns_none(self):
        self.assertIsNone(leave_status_for(self.employee, date(2026, 1, 1)))

    def test_approved_full_day_paid_leave(self):
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', duration=DURATION_FULL,
            start_date=date(2026, 2, 1), end_date=date(2026, 2, 1), total_days=Decimal('1'),
            reason='test', status=REQ_APPROVED, is_lwp=False,
        )
        result = leave_status_for(self.employee, date(2026, 2, 1))
        self.assertEqual(result['portion'], 'full')
        self.assertTrue(result['is_paid'])
        self.assertEqual(result['leave_type_code'], 'casual')

    def test_approved_lwp_is_unpaid(self):
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='lwp', duration=DURATION_FULL,
            start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), total_days=Decimal('1'),
            reason='test', status=REQ_APPROVED, is_lwp=True,
        )
        result = leave_status_for(self.employee, date(2026, 3, 1))
        self.assertFalse(result['is_paid'])

    def test_pending_request_is_ignored(self):
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', duration=DURATION_FULL,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 1), total_days=Decimal('1'),
            reason='test', status='pending',
        )
        self.assertIsNone(leave_status_for(self.employee, date(2026, 4, 1)))


class HolidayCalendarMigrationTests(TestCase):
    def setUp(self):
        from apps.hrms.models import Holiday
        Holiday.objects.create(name='New Year', date=date(2027, 1, 1), holiday_type='national', branch=None)

    def test_migration_creates_company_wide_calendar_entry(self):
        from apps.hrms.models_holiday_calendar import HolidayCalendar, HolidayCalendarEntry

        call_command('migrate_holidays_to_calendars')

        calendar = HolidayCalendar.objects.get(code='COMPANY_WIDE_2027')
        self.assertTrue(HolidayCalendarEntry.objects.filter(calendar=calendar, date=date(2027, 1, 1), name='New Year').exists())

    def test_verification_command_reports_zero_mismatches(self):
        from io import StringIO

        call_command('migrate_holidays_to_calendars')
        out = StringIO()
        call_command('verify_holiday_calendar_migration', stdout=out)
        self.assertIn('Mismatches=0', out.getvalue())

    def test_is_holiday_for_employee_resolves_company_wide(self):
        from apps.hrms.services_holiday_calendar import is_holiday_for_employee

        call_command('migrate_holidays_to_calendars')
        employee = make_user('holidayemp@test.com', password='TestPass123!')
        entry = is_holiday_for_employee(employee, date(2027, 1, 1))
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, 'New Year')

    def test_is_holiday_for_employee_none_on_non_holiday(self):
        from apps.hrms.services_holiday_calendar import is_holiday_for_employee

        call_command('migrate_holidays_to_calendars')
        employee = make_user('holidayemp2@test.com', password='TestPass123!')
        self.assertIsNone(is_holiday_for_employee(employee, date(2027, 1, 2)))
