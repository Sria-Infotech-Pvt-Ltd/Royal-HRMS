"""The calendar tells the page which days were worked from home (no database needed)."""
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceRecord
from apps.attendance.serializers_my_attendance import CalendarSerializer
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
                          'regularization_required', 'work_mode', 'short_minutes', 'short_display', 'is_late', 'late_forgiven', 'late_after'}, set(day))


class CalendarApiResponseTests(SimpleTestCase):
    """What the page actually receives: the calendar goes through CalendarSerializer, which drops any field it does not list."""

    @staticmethod
    def api_days(rec):
        day = AttendanceDashboardService._build_day(16, 2026, 11, {date(2026, 11, 16): rec}, set(), set(), set(), TODAY)
        return CalendarSerializer({'days': {16: day}}).data['days']

    def test_the_work_mode_and_the_shortfall_reach_the_page(self):
        rec = record(AttendanceRecord.STATUS_PRESENT, AttendanceRecord.WORK_MODE_WFH)
        rec.short_minutes = 80
        day = self.api_days(rec)['16']
        self.assertEqual(day['work_mode'], 'wfh')
        self.assertEqual((day['short_minutes'], day['short_display']), (80, '1h 20m'))

    def test_a_day_without_a_shortfall_or_record_still_serialises(self):
        day = self.api_days(record(AttendanceRecord.STATUS_PRESENT, AttendanceRecord.WORK_MODE_OFFICE))['16']
        self.assertEqual((day['work_mode'], day['short_minutes'], day['short_display']), ('office', 0, None))

    def test_the_api_day_has_every_field_the_page_reads(self):
        day = self.api_days(record(AttendanceRecord.STATUS_LATE, AttendanceRecord.WORK_MODE_WFH))['16']
        self.assertTrue({'status', 'clockIn', 'clockOut', 'hours', 'work_mode', 'short_minutes', 'short_display'} <= set(day))
