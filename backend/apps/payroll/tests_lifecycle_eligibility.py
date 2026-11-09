"""
Payroll eligibility and proration around joining and leaving. The existing onboarding / bank-data gate is unchanged (it is
asserted here too); on top of it:
  * joining after the cycle ends, or no joining date, means not paid;
  * a last working day (approved separation) BEFORE the cycle starts means not paid;
  * a last working day inside the cycle means paid up to and including that day;
  * joining on the first day of the cycle is paid in full, joining mid-cycle is prorated from the joining date.
Accounts are not deactivated automatically at the last working day, so the separation date is what stops payment.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import User
from apps.hrms.models import SEP_APPROVED, SEP_PENDING, SeparationRequest
from apps.payroll.engine.legacy import (
    _approved_last_working_days, _eligible_employees_qs, _proration_end, _proration_start, _proration_windows,
)

D = datetime.date
CYCLE = SimpleNamespace(cycle_start=D(2026, 11, 1), cycle_end=D(2026, 11, 30), branch=None)
REQUEST_DATE = D(2026, 9, 1)


def _employee(name: str, number: int, joined, **extra) -> User:
    extra.setdefault('onboarding_status', User.ONBOARDING_COMPLETE)
    return make_user(f'pl_{name}@test.com', employee_id=f'PL{number:03d}', branch='Payroll Lifecycle Branch', date_of_joining=joined, **extra)


def _leave(employee: User, last_day: D, status=SEP_APPROVED) -> None:
    SeparationRequest.objects.create(
        employee=employee, separation_type='resignation', request_date=REQUEST_DATE, proposed_last_working_day=last_day, status=status,
    )


class PayrollLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        e = _employee
        cls.full = e('full', 1, D(2025, 1, 1))
        cls.first_day = e('first', 2, D(2026, 11, 1))
        cls.mid_join = e('mid', 3, D(2026, 11, 16))
        cls.last_day_join = e('lastj', 4, D(2026, 11, 30))
        cls.after_join = e('after', 5, D(2026, 12, 1))
        cls.blank = e('blank', 6, None)
        cls.leaves_mid = e('leavemid', 7, D(2025, 1, 1))
        _leave(cls.leaves_mid, D(2026, 11, 14))
        cls.leaves_on_start = e('leavestart', 8, D(2025, 1, 1))
        _leave(cls.leaves_on_start, D(2026, 11, 1))
        cls.leaves_on_end = e('leaveend', 9, D(2025, 1, 1))
        _leave(cls.leaves_on_end, D(2026, 11, 30))
        cls.leaves_after = e('leaveafter', 10, D(2025, 1, 1))
        _leave(cls.leaves_after, D(2026, 12, 15))
        cls.left_before = e('leftbefore', 11, D(2025, 1, 1))
        _leave(cls.left_before, D(2026, 10, 31))
        cls.pending_leave = e('pending', 12, D(2025, 1, 1))
        _leave(cls.pending_leave, D(2026, 10, 31), status=SEP_PENDING)
        cls.join_and_leave = e('joinleave', 13, D(2026, 11, 10))
        _leave(cls.join_and_leave, D(2026, 11, 20))
        cls.not_onboarded = e('notonboarded', 14, D(2025, 1, 1), onboarding_status=User.ONBOARDING_PENDING)
        cls.everyone = [v for v in vars(cls).values() if isinstance(v, User)]

    def _eligible_ids(self) -> set:
        return set(_eligible_employees_qs(CYCLE).values_list('employee_id', flat=True))

    def test_who_is_paid_for_the_cycle(self):
        ids = self._eligible_ids()
        paid = [self.full, self.first_day, self.mid_join, self.last_day_join, self.leaves_mid, self.leaves_on_start,
                self.leaves_on_end, self.leaves_after, self.pending_leave, self.join_and_leave]
        for employee in paid:
            self.assertIn(employee.employee_id, ids, employee.email)
        for employee in (self.after_join, self.blank, self.left_before, self.not_onboarded):
            self.assertNotIn(employee.employee_id, ids, employee.email)

    def test_existing_onboarding_gate_is_unchanged(self):
        self.assertNotIn(self.not_onboarded.employee_id, self._eligible_ids())
        self.assertEqual(self.not_onboarded.date_of_joining, D(2025, 1, 1))   # joined long ago: only onboarding excludes them

    def test_a_pending_separation_does_not_stop_pay(self):
        self.assertIn(self.pending_leave.employee_id, self._eligible_ids())

    def test_the_last_working_day_counts_even_if_the_account_is_still_active(self):
        self.assertTrue(self.left_before.is_active)
        self.assertNotIn(self.left_before.employee_id, self._eligible_ids())

    def test_windows_and_fractions_for_every_case(self):
        employees = [self.full, self.first_day, self.mid_join, self.last_day_join, self.leaves_mid, self.leaves_on_start,
                     self.leaves_on_end, self.leaves_after, self.join_and_leave]
        last_days = _approved_last_working_days([e.id for e in employees])
        windows, factors = _proration_windows(employees, CYCLE, {}, last_days)
        expected = {
            self.full: (D(2026, 11, 1), D(2026, 11, 30), Decimal(30)),
            self.first_day: (D(2026, 11, 1), D(2026, 11, 30), Decimal(30)),          # joined on the first day: the whole cycle
            self.mid_join: (D(2026, 11, 16), D(2026, 11, 30), Decimal(15)),          # joined mid-cycle: from the joining date
            self.last_day_join: (D(2026, 11, 30), D(2026, 11, 30), Decimal(1)),
            self.leaves_mid: (D(2026, 11, 1), D(2026, 11, 14), Decimal(14)),         # last working day mid-cycle: up to that day
            self.leaves_on_start: (D(2026, 11, 1), D(2026, 11, 1), Decimal(1)),
            self.leaves_on_end: (D(2026, 11, 1), D(2026, 11, 30), Decimal(30)),
            self.leaves_after: (D(2026, 11, 1), D(2026, 11, 30), Decimal(30)),       # last day after the cycle: the whole cycle
            self.join_and_leave: (D(2026, 11, 10), D(2026, 11, 20), Decimal(11)),
        }
        for employee, (start, end, days) in expected.items():
            self.assertEqual(windows[employee.id], (start, end), employee.email)
            self.assertEqual(factors[employee.id], days / Decimal(30), employee.email)

    def test_nothing_is_owed_for_a_cycle_entirely_before_joining_or_after_leaving(self):
        windows, factors = _proration_windows([self.after_join, self.left_before], CYCLE, {},
                                              _approved_last_working_days([self.left_before.id]))
        self.assertEqual(factors[self.after_join.id], Decimal(0))      # joins the day after the cycle ends
        self.assertEqual(factors[self.left_before.id], Decimal(0))     # left the day before it starts
        self.assertGreater(windows[self.after_join.id][0], CYCLE.cycle_end)

    def test_proration_start_and_end_helpers(self):
        self.assertEqual(_proration_start(self.first_day, CYCLE), CYCLE.cycle_start)
        self.assertEqual(_proration_start(self.mid_join, CYCLE), D(2026, 11, 16))
        self.assertEqual(_proration_end(self.full, CYCLE, CYCLE.cycle_start), CYCLE.cycle_end)
        self.assertEqual(_proration_end(self.full, CYCLE, CYCLE.cycle_start, last_working_day=D(2026, 11, 14)), D(2026, 11, 14))
        self.assertEqual(_proration_end(self.full, CYCLE, CYCLE.cycle_start, last_working_day=D(2026, 12, 14)), CYCLE.cycle_end)

    def test_a_deactivated_account_is_still_bounded_by_its_last_attendance_and_never_past_its_last_working_day(self):
        inactive = SimpleNamespace(is_active=False)
        dates = [D(2026, 11, 3), D(2026, 11, 10)]
        self.assertEqual(_proration_end(inactive, CYCLE, CYCLE.cycle_start, attendance_dates=dates), D(2026, 11, 10))
        self.assertEqual(_proration_end(inactive, CYCLE, CYCLE.cycle_start, last_working_day=D(2026, 11, 8), attendance_dates=dates), D(2026, 11, 8))
        self.assertEqual(_proration_end(inactive, CYCLE, CYCLE.cycle_start), CYCLE.cycle_start)   # no attendance: zero days

    def test_the_latest_approved_last_working_day_wins_and_unapproved_ones_are_ignored(self):
        _leave(self.full, D(2026, 11, 5))
        _leave(self.full, D(2026, 11, 25))
        _leave(self.full, D(2026, 11, 2), status=SEP_PENDING)
        self.assertEqual(_approved_last_working_days([self.full.id])[self.full.id], D(2026, 11, 25))
