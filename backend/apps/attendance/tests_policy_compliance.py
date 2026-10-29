"""
Company policy rules in attendance processing and payroll:

- Missing Clock Out → Attendance Settings → Missing Clock Out (Incomplete by
  default, or Half Day / Absent); no punch at all stays Absent; the HR
  Un-punches list still finds the day; payroll counts the resulting status.
- Late marks → "every N" (unchanged) or "N allowed, LOP for each after"
  (per calendar month).
- Permitted early leaves per month: leaving within the Early Exit Grace still
  counts as a full day that many times a month, earliest days first, and a
  correction to an earlier day re-checks later days.
"""
from __future__ import annotations

import datetime
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    AttendanceLateMarkRules, AttendancePunch, AttendancePunchRules, AttendanceRecord, AttendanceSettings,
    AttendanceWorkingHours,
)
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.attendance.services_hr_audit import get_unpunch_count, get_unpunches
from apps.attendance.services_policy import late_mark_lop_days, missing_punch_status
from apps.attendance.services_unpunch import detect_and_mark_unpunches
from apps.payroll.tests_salary_components import SalaryFixtureMixin
from apps.payroll.views.cycles import process_payroll_cycle

IST = ZoneInfo('Asia/Kolkata')
BRANCH = 'Policy Branch'


def _at(day: date, hh: int, mm: int = 0) -> datetime.datetime:
    return datetime.datetime(day.year, day.month, day.day, hh, mm, tzinfo=IST)


class PolicyFixture(TestCase):
    """Ris-like settings: 09:30–18:30, grace 10, break 45, full day 8 h, half day 4 h."""

    def setUp(self):
        cache.clear()
        self.settings_row = AttendanceSettings.objects.create(is_active=True)
        AttendanceWorkingHours.objects.create(
            settings=self.settings_row, shift_start=time(9, 30), shift_end=time(18, 30),
            grace_period_minutes=10, missing_punch_grace_minutes=10, break_duration_minutes=45,
        )
        self.rules = AttendancePunchRules.objects.create(
            settings=self.settings_row, min_hours_full_day=Decimal('8.00'), min_hours_half_day=Decimal('4.00'),
            early_exit_grace_minutes=30,
        )
        self.late_rules = AttendanceLateMarkRules.objects.create(
            settings=self.settings_row, late_marks_per_lop=5, lop_deduction_unit='half_day',
        )
        self.emp = make_user('policy.emp@test.com', role=make_role('policy_staff'), employee_id='POL001',
                             full_name='Policy Emp', branch=BRANCH)

    def configure(self, **fields):
        AttendancePunchRules.objects.filter(pk=self.rules.pk).update(**fields)
        cache.clear()

    def punch(self, day, hh, mm, kind):
        AttendancePunch.objects.create(employee=self.emp, punch_type=kind, punched_at=_at(day, hh, mm))

    def work(self, day, start=(9, 30), end=(18, 30)):
        self.punch(day, *start, AttendancePunch.PUNCH_IN)
        if end:
            self.punch(day, *end, AttendancePunch.PUNCH_OUT)
        return AttendanceProcessorService.process_day(self.emp, day)


# ── 1. Missing Clock Out ─────────────────────────────────────────────────────

class MissingPunchTests(PolicyFixture):
    DAY = date(2026, 9, 1)   # a past Tuesday

    def test_status_follows_setting(self):
        cfg = SimpleNamespace(punch_rules=SimpleNamespace(missing_punch_action='mark_half_day'))
        self.assertEqual(missing_punch_status(cfg), AttendanceRecord.STATUS_HALF_DAY)
        cfg.punch_rules.missing_punch_action = 'mark_absent'
        self.assertEqual(missing_punch_status(cfg), AttendanceRecord.STATUS_ABSENT)
        cfg.punch_rules.missing_punch_action = 'require_regularization'
        self.assertEqual(missing_punch_status(cfg), AttendanceRecord.STATUS_INCOMPLETE)
        self.assertEqual(missing_punch_status(None), AttendanceRecord.STATUS_INCOMPLETE)

    def test_default_past_day_without_clock_out_is_incomplete(self):
        rec = self.work(self.DAY, end=None)
        self.assertEqual(rec.status, AttendanceRecord.STATUS_INCOMPLETE)

    def test_half_day_setting_for_past_day_without_clock_out(self):
        self.configure(missing_punch_action='mark_half_day')
        rec = self.work(self.DAY, end=None)
        self.assertEqual(rec.status, AttendanceRecord.STATUS_HALF_DAY)
        # Still listed for HR follow-up, whatever the status.
        self.assertEqual([r['employee_id'] for r in get_unpunches(self.DAY, BRANCH, '')], ['POL001'])
        self.assertEqual(get_unpunch_count(self.DAY, BRANCH, ''), 1)

    def test_no_punch_at_all_is_absent_whatever_the_setting(self):
        self.configure(missing_punch_action='mark_half_day')
        rec = AttendanceProcessorService.process_day(self.emp, self.DAY)
        self.assertEqual(rec.status, AttendanceRecord.STATUS_ABSENT)
        self.assertEqual(get_unpunch_count(self.DAY, BRANCH, ''), 0)

    def test_correction_adding_clock_out_recalculates(self):
        self.configure(missing_punch_action='mark_half_day')
        self.work(self.DAY, end=None)
        self.punch(self.DAY, 18, 30, AttendancePunch.PUNCH_OUT)   # approved correction adds the punch
        rec = AttendanceProcessorService.process_day(self.emp, self.DAY)
        self.assertEqual(rec.status, AttendanceRecord.STATUS_PRESENT)
        self.assertEqual(get_unpunch_count(self.DAY, BRANCH, ''), 0)

    def test_today_still_working_is_not_penalised(self):
        self.configure(missing_punch_action='mark_absent')
        today = date.today()
        if today.weekday() == 6:
            today -= datetime.timedelta(days=1)
        rec = self.work(today, end=None)
        self.assertIn(rec.status, (AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE))

    def test_unpunch_job_applies_setting(self):
        self.configure(missing_punch_action='mark_half_day')
        today = date.today()
        self.punch(today, 9, 30, AttendancePunch.PUNCH_IN)
        AttendanceRecord.objects.create(employee=self.emp, date=today, status=AttendanceRecord.STATUS_PRESENT,
                                        first_punch_in=time(9, 30))
        with patch('apps.attendance.services_unpunch._now_ist', return_value=time(23, 59)), \
                patch('apps.attendance.services_unpunch._notify_employees', return_value=1):
            result = detect_and_mark_unpunches(today)
        self.assertEqual(result['marked'], 1)
        self.assertEqual(AttendanceRecord.objects.get(employee=self.emp, date=today).status,
                         AttendanceRecord.STATUS_HALF_DAY)


# ── 3. Late-arrival allowance ────────────────────────────────────────────────

class LateMarkRuleTests(TestCase):
    def rules(self, n, mode, unit='half_day'):
        return SimpleNamespace(late_marks_per_lop=n, late_mark_mode=mode, lop_deduction_unit=unit)

    def days(self, month, count):
        return [date(2026, month, d) for d in range(1, count + 1)]

    def test_five_allowed_then_half_day_each(self):
        r = self.rules(5, 'after_allowance')
        self.assertEqual(late_mark_lop_days(self.days(9, 5), r), Decimal('0'))
        self.assertEqual(late_mark_lop_days(self.days(9, 6), r), Decimal('0.5'))
        self.assertEqual(late_mark_lop_days(self.days(9, 8), r), Decimal('1.5'))

    def test_allowance_resets_each_month(self):
        r = self.rules(5, 'after_allowance')
        self.assertEqual(late_mark_lop_days(self.days(9, 5) + self.days(10, 5), r), Decimal('0'))
        self.assertEqual(late_mark_lop_days(self.days(9, 6) + self.days(10, 7), r), Decimal('1.5'))

    def test_every_n_unchanged(self):
        r = self.rules(4, 'every_n')
        self.assertEqual(late_mark_lop_days(self.days(9, 7), r), Decimal('0.5'))
        self.assertEqual(late_mark_lop_days(self.days(9, 8), r), Decimal('1.0'))
        r = self.rules(3, 'every_n', 'full_day')
        self.assertEqual(late_mark_lop_days(self.days(9, 6), r), Decimal('2'))

    def test_zero_means_tracking_only(self):
        self.assertEqual(late_mark_lop_days(self.days(9, 20), self.rules(0, 'after_allowance')), Decimal('0'))
        self.assertEqual(late_mark_lop_days(self.days(9, 20), None), Decimal('0'))

    def test_missing_mode_behaves_as_every_n(self):
        r = SimpleNamespace(late_marks_per_lop=4, lop_deduction_unit='half_day')
        self.assertEqual(late_mark_lop_days(self.days(9, 8), r), Decimal('1.0'))


# ── 4 / 10. Permitted early leave ────────────────────────────────────────────

class EarlyLeaveAllowanceTests(PolicyFixture):
    # September 2026: 1st Tue, 2nd Wed, 3rd Thu, 4th Fri
    D1, D2, D3 = date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)

    def test_conflict_without_allowance_is_half_day(self):
        rec = self.work(self.D1, end=(18, 0))     # 8 h 30 − 45 min break = 7 h 45
        self.assertEqual(rec.status, AttendanceRecord.STATUS_HALF_DAY)
        self.assertFalse(rec.early_leave_allowance_applied)

    def test_first_early_leave_in_month_counts_as_present(self):
        self.configure(early_leave_allowance_per_month=1)
        first = self.work(self.D1, end=(18, 0))
        second = self.work(self.D2, end=(18, 0))
        self.assertEqual((first.status, first.early_leave_allowance_applied), (AttendanceRecord.STATUS_PRESENT, True))
        self.assertEqual((second.status, second.early_leave_allowance_applied), (AttendanceRecord.STATUS_HALF_DAY, False))
        self.assertIn('Permitted early leave', first.note)

    def test_leaving_more_than_window_early_never_qualifies(self):
        self.configure(early_leave_allowance_per_month=1)
        rec = self.work(self.D1, end=(17, 55))    # 35 min early
        self.assertEqual(rec.status, AttendanceRecord.STATUS_HALF_DAY)
        self.assertTrue(rec.is_early_exit)

    def test_late_and_early_shortfall_not_forgiven(self):
        self.configure(early_leave_allowance_per_month=1)
        rec = self.work(self.D1, start=(10, 0), end=(18, 0))   # late too: only the early part is forgiven
        self.assertEqual(rec.status, AttendanceRecord.STATUS_HALF_DAY)
        self.assertFalse(rec.early_leave_allowance_applied)

    def test_late_day_whose_only_shortfall_is_early_leave_stays_late(self):
        self.configure(early_leave_allowance_per_month=1)
        rec = self.work(self.D1, start=(9, 45), end=(18, 15))  # 8 h 30 − 45 = 7 h 45; +15 early = 8 h
        self.assertEqual((rec.status, rec.early_leave_allowance_applied), (AttendanceRecord.STATUS_LATE, True))

    def test_allowance_resets_next_month(self):
        self.configure(early_leave_allowance_per_month=1)
        self.work(self.D1, end=(18, 0))
        october = self.work(date(2026, 10, 1), end=(18, 0))
        self.assertTrue(october.early_leave_allowance_applied)

    def test_correcting_earlier_day_frees_allowance_for_later_day(self):
        self.configure(early_leave_allowance_per_month=1)
        self.work(self.D1, end=(18, 0))
        later = self.work(self.D2, end=(18, 0))
        self.assertFalse(later.early_leave_allowance_applied)
        # Approved correction: D1 actually ended at 18:30.
        AttendancePunch.objects.filter(employee=self.emp, punched_at=_at(self.D1, 18, 0)).update(
            punched_at=_at(self.D1, 18, 30))
        AttendanceProcessorService.process_day(self.emp, self.D1)
        later = AttendanceRecord.objects.get(employee=self.emp, date=self.D2)
        self.assertEqual((later.status, later.early_leave_allowance_applied), (AttendanceRecord.STATUS_PRESENT, True))

    def test_allowance_of_two_rechecks_all_later_days(self):
        self.configure(early_leave_allowance_per_month=2)
        for day in (self.D1, self.D2, self.D3):
            self.work(day, end=(18, 0))
        self.assertFalse(AttendanceRecord.objects.get(employee=self.emp, date=self.D3).early_leave_allowance_applied)
        AttendancePunch.objects.filter(employee=self.emp, punched_at=_at(self.D1, 18, 0)).update(
            punched_at=_at(self.D1, 18, 30))
        AttendanceProcessorService.process_day(self.emp, self.D1)
        applied = dict(AttendanceRecord.objects.filter(employee=self.emp).values_list('date', 'early_leave_allowance_applied'))
        self.assertEqual(applied, {self.D1: False, self.D2: True, self.D3: True})

    def test_early_exit_flag_uses_configured_window(self):
        self.configure(early_exit_grace_minutes=15)
        rec = self.work(self.D1, end=(18, 10))    # 20 min early > 15
        self.assertTrue(rec.is_early_exit)


# ── Payroll uses the same outcomes ───────────────────────────────────────────

class PayrollConsistencyTests(SalaryFixtureMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.make_fixtures()
        self.assign(self.emp_a, ctc='600000', effective='2026-01-01')
        settings_row = AttendanceSettings.objects.create(is_active=True)
        self.late_rules = AttendanceLateMarkRules.objects.create(
            settings=settings_row, late_marks_per_lop=5, lop_deduction_unit='half_day',
            late_mark_mode='after_allowance',
        )
        for d in range(5, 12):   # 7 late days in January
            AttendanceRecord.objects.create(employee=self.emp_a, date=date(2026, 1, d),
                                            status=AttendanceRecord.STATUS_LATE, is_late=True)
        # A missing clock-out the setting marked Half Day.
        AttendanceRecord.objects.create(employee=self.emp_a, date=date(2026, 1, 20),
                                        status=AttendanceRecord.STATUS_HALF_DAY, first_punch_in=time(9, 30))

    def lop(self):
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        return self.payslip(jan, self.emp_a).lop_days

    def test_after_allowance_lop_plus_missing_punch_half_day(self):
        self.assertEqual(self.lop(), Decimal('1.5'))      # (7 − 5) × 0.5 + 0.5

    def test_every_n_lop_unchanged(self):
        AttendanceLateMarkRules.objects.filter(pk=self.late_rules.pk).update(late_mark_mode='every_n', late_marks_per_lop=4)
        self.assertEqual(self.lop(), Decimal('1.0'))      # 7 // 4 × 0.5 + 0.5
