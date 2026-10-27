"""
Bug fix — ESS attendance calendar/stats/summary wrongly marked days before
date_of_joining as Absent, and marked "today" Absent before the employee's
shift had even ended.

SimpleTestCase + mocking, same pattern tests_query_efficiency.py already uses
for this module (this shared test DB has no provisioned tenant schema, so a
real TestCase round trip through the ORM can't run here) — these tests hit
the pure classification/window functions directly: _classify_day,
effective_attendance_window, shift_end_has_passed.
"""
from __future__ import annotations

from datetime import date, datetime, time
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceRecord
from apps.attendance.services_attendance import (
    STATUS_NOT_JOINED,
    STATUS_PENDING,
    AttendanceDashboardService,
    effective_attendance_window,
    shift_end_has_passed,
)

_IST = ZoneInfo('Asia/Kolkata')
_classify = AttendanceDashboardService._classify_day


class ClassifyDayNotJoinedTests(SimpleTestCase):
    """Mid-month joiner: days before date_of_joining are 'Not joined', not Absent."""

    def test_day_before_joining_is_not_joined(self):
        key = _classify(
            cur=date(2026, 10, 5), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 15), eff_end=date(2026, 10, 31),
            shift_ended_today=True,
        )
        self.assertEqual(key, STATUS_NOT_JOINED)

    def test_joining_day_itself_is_not_not_joined(self):
        key = _classify(
            cur=date(2026, 10, 15), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 15), eff_end=date(2026, 10, 31),
            shift_ended_today=True,
        )
        self.assertEqual(key, AttendanceRecord.STATUS_ABSENT)

    def test_day_after_approved_exit_is_blank(self):
        key = _classify(
            cur=date(2026, 10, 20), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 1), eff_end=date(2026, 10, 18),
            shift_ended_today=True,
        )
        self.assertIsNone(key)


class ClassifyDayPendingTodayTests(SimpleTestCase):
    """'Today' isn't marked Absent until the shift has ended."""

    def test_today_before_shift_end_is_pending(self):
        key = _classify(
            cur=date(2026, 10, 26), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 15), eff_end=date(2026, 10, 31),
            shift_ended_today=False,
        )
        self.assertEqual(key, STATUS_PENDING)

    def test_today_after_shift_end_with_no_punch_is_absent(self):
        key = _classify(
            cur=date(2026, 10, 26), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 15), eff_end=date(2026, 10, 31),
            shift_ended_today=True,
        )
        self.assertEqual(key, AttendanceRecord.STATUS_ABSENT)

    def test_today_with_an_existing_record_ignores_pending(self):
        rec = MagicMock()
        rec.status = AttendanceRecord.STATUS_PRESENT
        key = _classify(
            cur=date(2026, 10, 26), rec=rec, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 15), eff_end=date(2026, 10, 31),
            shift_ended_today=False,
        )
        self.assertEqual(key, AttendanceRecord.STATUS_PRESENT)


class ClassifyDayFullMonthEmployeeUnchangedTests(SimpleTestCase):
    """An employee with no join-date gap this month classifies exactly as before."""

    def test_full_month_employee_absent_day_unchanged(self):
        key = _classify(
            cur=date(2026, 10, 5), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 1), eff_end=date(2026, 10, 31),
            shift_ended_today=True,
        )
        self.assertEqual(key, AttendanceRecord.STATUS_ABSENT)

    def test_full_month_employee_without_window_args_unchanged(self):
        """eff_start/eff_end omitted entirely (defaults) behaves exactly as
        the pre-fix signature did — the three new kwargs are additive."""
        key = _classify(
            cur=date(2026, 10, 5), rec=None, holiday_dates=set(), off_dates=set(),
            leave_dates=set(), today=date(2026, 10, 26),
        )
        self.assertEqual(key, AttendanceRecord.STATUS_ABSENT)

    def test_holiday_still_wins_inside_the_employment_window(self):
        key = _classify(
            cur=date(2026, 10, 20), rec=None, holiday_dates={date(2026, 10, 20)},
            off_dates=set(), leave_dates=set(), today=date(2026, 10, 26),
            eff_start=date(2026, 10, 1), eff_end=date(2026, 10, 31),
            shift_ended_today=True,
        )
        self.assertEqual(key, AttendanceRecord.STATUS_HOLIDAY)


class EffectiveAttendanceWindowTests(SimpleTestCase):
    def test_clamps_start_to_date_of_joining(self):
        employee = MagicMock(date_of_joining=date(2026, 10, 15))
        with patch('apps.hrms.models.SeparationRequest.objects') as mock_mgr:
            mock_mgr.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
            start, end = effective_attendance_window(employee, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(start, date(2026, 10, 15))
        self.assertEqual(end, date(2026, 10, 31))

    def test_no_date_of_joining_keeps_range_start(self):
        employee = MagicMock(date_of_joining=None)
        with patch('apps.hrms.models.SeparationRequest.objects') as mock_mgr:
            mock_mgr.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = None
            start, end = effective_attendance_window(employee, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(start, date(2026, 10, 1))
        self.assertEqual(end, date(2026, 10, 31))

    def test_clamps_end_to_approved_last_working_day(self):
        employee = MagicMock(date_of_joining=None)
        with patch('apps.hrms.models.SeparationRequest.objects') as mock_mgr:
            mock_mgr.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = date(2026, 10, 18)
            start, end = effective_attendance_window(employee, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(start, date(2026, 10, 1))
        self.assertEqual(end, date(2026, 10, 18))


class ShiftEndHasPassedTests(SimpleTestCase):
    def test_before_shift_end_returns_false(self):
        cfg = MagicMock()
        cfg.working_hours.shift_end = time(18, 0)
        now = datetime(2026, 10, 26, 10, 0, tzinfo=_IST)  # 10:00 IST
        self.assertFalse(shift_end_has_passed(cfg, now=now))

    def test_after_shift_end_returns_true(self):
        cfg = MagicMock()
        cfg.working_hours.shift_end = time(18, 0)
        now = datetime(2026, 10, 26, 19, 0, tzinfo=_IST)  # 19:00 IST
        self.assertTrue(shift_end_has_passed(cfg, now=now))

    def test_no_settings_falls_back_to_default_shift_end(self):
        now_before = datetime(2026, 10, 26, 10, 0, tzinfo=_IST)
        now_after = datetime(2026, 10, 26, 19, 0, tzinfo=_IST)
        self.assertFalse(shift_end_has_passed(None, now=now_before))
        self.assertTrue(shift_end_has_passed(None, now=now_after))
