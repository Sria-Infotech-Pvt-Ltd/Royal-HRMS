"""
Regression tests: attendance/absence/LOP calculations must be clipped to
[max(period_start, date_of_joining), min(period_end, last_working_day, today)],
not run over the whole calendar month regardless of when the employee
actually joined or left.

Bug: a mid-month joiner (DOJ 27th) saw "Days Absent 19 of 19 working days",
"19 LOP pending", 0% attendance, with every day from the 1st to the 26th
marked "A" — days before they had even joined. The HR Attendance List had
the same issue ("new joiners flagged Absent").

Covers the three cases the ticket's acceptance criteria name explicitly:
a mid-month joiner, a leaver (no LOP after their last working day), and
the unaffected full-month case.
"""
from __future__ import annotations

import uuid
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.attendance.models import AttendanceRecord
from apps.attendance.services_attendance import STATUS_NOT_JOINED, STATUS_PENDING, AttendanceDashboardService
from apps.attendance.services_hr import get_attendance_list
from apps.hrms.models_separation_v2 import AlumniRecord


class MidMonthJoinerClippingTests(TestCase):
    """Acceptance case 1: a mid-month joiner's working days are counted
    only from DOJ, with 0 LOP for days before they joined."""

    def setUp(self):
        self.employee = make_user(
            'doj-joiner@test.com', employee_id='DOJCLIP01',
            date_of_joining=date(2026, 10, 27),
        )

    def test_get_stats_excludes_days_before_doj(self):
        stats = AttendanceDashboardService.get_stats(self.employee, 2026, 10)
        # Only the 27th-31st (5 days) can possibly count, never the 1st-26th.
        self.assertLessEqual(stats['working_days'], 5)
        self.assertLessEqual(stats['lop_pending'], 5)

    def test_get_monthly_summary_excludes_days_before_doj(self):
        summary = AttendanceDashboardService.get_monthly_summary(self.employee, 2026, 10)
        self.assertLessEqual(summary['working_days'], 5)
        self.assertLessEqual(summary['days_absent'], 5)

    def test_calendar_marks_pre_doj_days_not_employed_not_absent(self):
        calendar = AttendanceDashboardService.get_calendar(self.employee, 2026, 10)
        days = calendar['days']
        # The 1st (long before DOJ) must never be "Absent".
        if 1 in days:
            self.assertEqual(days[1]['status'], 'Not joined')
            self.assertNotEqual(days[1]['status'], 'Absent')
        if 26 in days:
            self.assertEqual(days[26]['status'], 'Not joined')

    def test_hr_attendance_list_does_not_flag_new_joiner_as_absent_before_doj(self):
        rows = get_attendance_list({'date': date(2026, 10, 15), 'branch': '', 'department': ''})
        row = next(r for r in rows if r['employee_id'] == self.employee.employee_id)
        self.assertEqual(row['status_key'], AttendanceRecord.STATUS_NOT_EMPLOYED)
        self.assertNotEqual(row['status_key'], AttendanceRecord.STATUS_ABSENT)

    def test_hr_attendance_list_absent_filter_excludes_pre_doj_employee(self):
        rows = get_attendance_list({
            'date': date(2026, 10, 15), 'branch': '', 'department': '', 'status': 'absent',
        })
        ids = [r['employee_id'] for r in rows]
        self.assertNotIn(self.employee.employee_id, ids)


class LeaverClippingTests(TestCase):
    """Acceptance case 2: a leaver gets no LOP after their last working day."""

    def setUp(self):
        # AlumniRecord is normally only created alongside is_active=False
        # (see its own docstring), which would exclude this employee from
        # get_attendance_list's base queryset entirely before the new LWD
        # check ever runs -- kept active here specifically to exercise that
        # check's own correctness, independent of whether today's real
        # invariant (every AlumniRecord implies is_active=False) holds.
        self.employee = make_user(
            'doj-leaver@test.com', employee_id='DOJCLIP02',
            date_of_joining=date(2026, 1, 1), is_active=True,
        )
        AlumniRecord.objects.create(
            id=uuid.uuid4(), employee=self.employee, last_working_day=date(2026, 10, 10),
        )

    def test_days_after_last_working_day_are_not_absent(self):
        calendar = AttendanceDashboardService.get_calendar(self.employee, 2026, 10)
        days = calendar['days']
        # A day after the last working day is blank (like a future day), never Absent.
        if 20 in days:
            self.assertNotEqual(days[20]['status'], 'Absent')

    def test_get_stats_excludes_days_after_last_working_day(self):
        stats = AttendanceDashboardService.get_stats(self.employee, 2026, 10)
        # Only the 1st-10th (10 days) can possibly count.
        self.assertLessEqual(stats['working_days'], 10)

    def test_hr_attendance_list_marks_leaver_not_employed_after_lwd(self):
        rows = get_attendance_list({'date': date(2026, 10, 20), 'branch': '', 'department': ''})
        row = next(r for r in rows if r['employee_id'] == self.employee.employee_id)
        self.assertEqual(row['status_key'], AttendanceRecord.STATUS_NOT_EMPLOYED)


class FullMonthEmployeeUnaffectedTests(TestCase):
    """Acceptance case 3: an employee who was employed for the whole month
    is completely unaffected by the DOJ/LWD clipping."""

    def setUp(self):
        self.employee = make_user(
            'doj-fullmonth@test.com', employee_id='DOJCLIP03',
            date_of_joining=date(2020, 1, 1),
        )

    def test_calendar_has_no_not_employed_days(self):
        calendar = AttendanceDashboardService.get_calendar(self.employee, 2026, 10)
        statuses = {d['status'] for d in calendar['days'].values()}
        self.assertNotIn('Not joined', statuses)

    def test_hr_attendance_list_status_is_never_not_employed(self):
        rows = get_attendance_list({'date': date(2026, 10, 15), 'branch': '', 'department': ''})
        row = next(r for r in rows if r['employee_id'] == self.employee.employee_id)
        self.assertNotEqual(row['status_key'], AttendanceRecord.STATUS_NOT_EMPLOYED)


class TodayShiftCutoffTests(TestCase):
    """Today stays Pending (not Absent) until the shift has ended; _classify_day is a pure function, so it is tested
    directly instead of depending on the wall-clock time the suite runs at."""

    def _classify(self, cur, today, **kwargs):
        return AttendanceDashboardService._classify_day(
            cur=cur, rec=None, holiday_dates=set(), off_dates=set(), leave_dates=set(), today=today, **kwargs,
        )

    def test_today_before_shift_end_is_pending_not_absent(self):
        today = date(2026, 10, 15)
        key = self._classify(today, today, shift_ended_today=False)
        self.assertEqual(key, STATUS_PENDING)
        self.assertNotEqual(key, AttendanceRecord.STATUS_ABSENT)

    def test_today_after_shift_end_falls_back_to_absent(self):
        today = date(2026, 10, 15)
        self.assertEqual(self._classify(today, today, shift_ended_today=True), AttendanceRecord.STATUS_ABSENT)

    def test_past_day_is_absent_regardless_of_shift_end(self):
        key = self._classify(date(2026, 10, 1), date(2026, 10, 15), shift_ended_today=False)
        self.assertEqual(key, AttendanceRecord.STATUS_ABSENT)

    def test_pre_doj_day_is_not_joined(self):
        key = self._classify(date(2026, 10, 5), date(2026, 10, 15), eff_start=date(2026, 10, 27))
        self.assertEqual(key, STATUS_NOT_JOINED)
