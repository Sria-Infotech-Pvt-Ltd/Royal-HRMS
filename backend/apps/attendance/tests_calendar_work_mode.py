"""The calendar tells the page which days were worked from home (no database needed)."""
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceRecord
from apps.attendance.services_attendance import AttendanceDashboardService

TODAY = date(2026, 11, 17)


def record(status, work_mode):
    return SimpleNamespace(
        status=status, clock_in_display='13:04', clock_out_display=None, total_hours_display='-',
        total_working_minutes=0, note='', work_mode=work_mode,
    )


def build(day_number, rec=None, **kwargs):
    records = {date(2026, 11, day_number): rec} if rec else {}
    return AttendanceDashboardService._build_day(day_number, 2026, 11, records, set(), set(), set(), TODAY, **kwargs)


class CalendarWorkModeTests(SimpleTestCase):
    def test_a_late_day_worked_from_home_carries_work_mode_wfh_and_keeps_its_status(self):
        day = build(16, record(AttendanceRecord.STATUS_LATE, AttendanceRecord.WORK_MODE_WFH))
        self.assertEqual(day['work_mode'], 'wfh')
        self.assertEqual(day['status'], 'Late')      # work mode is separate from the status

    def test_an_office_day_carries_work_mode_office(self):
        day = build(17, record(AttendanceRecord.STATUS_PRESENT, AttendanceRecord.WORK_MODE_OFFICE))
        self.assertEqual(day['work_mode'], 'office')

    def test_a_day_with_no_record_has_no_work_mode(self):
        day = build(12)                               # a past day with nothing recorded is shown as Absent
        self.assertIsNone(day['work_mode'])
        self.assertEqual(day['status'], 'Absent')

    def test_the_other_day_fields_are_unchanged(self):
        day = build(16, record(AttendanceRecord.STATUS_LATE, AttendanceRecord.WORK_MODE_WFH))
        self.assertEqual(day['clockIn'], '13:04')
        self.assertEqual({'date', 'status', 'color', 'clockIn', 'clockOut', 'hours', 'note', 'holiday_name', 'canRegularize',
                          'regularization_required', 'work_mode'}, set(day))
