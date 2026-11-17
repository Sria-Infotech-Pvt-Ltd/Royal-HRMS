"""Half day at or below the half-day limit; above it but short of a full day is Present with "hours not completed" (no database)."""
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceRecord
from apps.attendance.serializers_settings import PunchRulesWriteSerializer
from apps.attendance.services_attendance import (
    AttendanceDashboardService, AttendanceProcessorService, _calendar_short_minutes, _short_display,
)
from apps.attendance.tests_recalculate_attendance import cfg

HALF, PRESENT, LATE, ABSENT = (
    AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_ABSENT,
)
FULL, HALF_LIMIT = 460, 240      # cfg(): full-day minimum 7.67 h (460 min), half-day limit 4 h (240 min)


def resolve(net_minutes, *, settings=None, late=False, open_session=False, complete=True):
    return AttendanceProcessorService._resolve_status(net_minutes, late, settings or cfg(), open_session, complete)


def result(net_minutes, settings=None, first_in='09:00', complete=True, open_session=False):
    """_result_from_totals for a day whose worked minutes after the break are `net_minutes` (the break is 60 min)."""
    from datetime import time
    hour, minute = map(int, first_in.split(':'))
    return AttendanceProcessorService._result_from_totals(
        time(hour, minute), None if open_session else time(18, 0), net_minutes + 60, open_session, complete, settings or cfg(),
    )


class StatusBoundaryTests(SimpleTestCase):
    def test_at_or_below_the_half_day_limit_is_a_half_day(self):
        for minutes in (1, 120, HALF_LIMIT):
            self.assertEqual(resolve(minutes), HALF, minutes)

    def test_one_minute_above_the_limit_is_present_not_a_half_day(self):
        self.assertEqual(resolve(HALF_LIMIT + 1), PRESENT)
        self.assertEqual(resolve(FULL - 1), PRESENT)

    def test_the_full_day_minimum_and_above_is_present(self):
        for minutes in (FULL, FULL + 1, 600):
            self.assertEqual(resolve(minutes), PRESENT, minutes)

    def test_a_late_arrival_in_the_short_zone_stays_late(self):
        self.assertEqual(resolve(300, late=True), LATE)

    def test_nobody_who_clocked_in_and_out_is_marked_absent(self):
        self.assertEqual(resolve(0), HALF)
        self.assertEqual(resolve(0, complete=False), ABSENT)

    def test_a_day_still_clocked_in_is_present_whatever_the_hours_so_far(self):
        self.assertEqual(resolve(0, open_session=True, complete=False), PRESENT)
        self.assertEqual(resolve(0, open_session=True, complete=False, late=True), LATE)

    def test_with_short_days_as_half_days_on_everything_below_a_full_day_is_a_half_day(self):
        settings = cfg(short_as_half=True)
        for minutes in (1, HALF_LIMIT, HALF_LIMIT + 1, FULL - 1):
            self.assertEqual(resolve(minutes, settings=settings), HALF, minutes)
        self.assertEqual(resolve(FULL, settings=settings), PRESENT)

    def test_a_missing_setting_object_uses_the_defaults(self):
        self.assertEqual(AttendanceProcessorService._punch_thresholds(None), (480, 240, False))
        self.assertEqual(AttendanceProcessorService._punch_thresholds(SimpleNamespace()), (480, 240, False))

    def test_an_older_settings_object_without_the_switch_means_off(self):
        old = SimpleNamespace(punch_rules=SimpleNamespace(min_hours_full_day='8', min_hours_half_day='4'))
        self.assertEqual(AttendanceProcessorService._punch_thresholds(old), (480, 240, False))


class ShortMinutesTests(SimpleTestCase):
    def test_the_shortfall_is_minutes_below_the_full_day_minimum(self):
        self.assertEqual(result(468)['short_minutes'], 0)
        self.assertEqual(result(450)['short_minutes'], 10)
        self.assertEqual(result(300)['short_minutes'], 160)

    def test_a_half_day_also_records_its_shortfall(self):
        day = result(180)
        self.assertEqual((day['status'], day['short_minutes']), (HALF, 280))

    def test_a_day_still_clocked_in_has_no_shortfall(self):
        self.assertEqual(result(0, first_in='11:54', complete=False, open_session=True)['short_minutes'], 0)

    def test_the_shortfall_follows_the_saved_full_day_minimum(self):
        self.assertEqual(result(450, settings=cfg(full='8'))['short_minutes'], 30)
        self.assertEqual(result(450, settings=cfg(full='7'))['short_minutes'], 0)

    def test_days_that_are_not_worked_days_reset_the_shortfall(self):
        self.assertEqual(AttendanceProcessorService._no_punch_record(date(2026, 11, 10), cfg())['short_minutes'], 0)


class CalendarShortHoursTests(SimpleTestCase):
    @staticmethod
    def day(status, short_minutes):
        rec = SimpleNamespace(
            status=status, clock_in_display='09:12', clock_out_display='18:00', total_hours_display='7h 48m',
            total_working_minutes=468, note='', work_mode='office', short_minutes=short_minutes,
        )
        return AttendanceDashboardService._build_day(10, 2026, 11, {date(2026, 11, 10): rec}, set(), set(), set(), date(2026, 11, 17))

    def test_a_present_day_short_of_a_full_day_carries_its_shortfall_text(self):
        day = self.day(PRESENT, 80)
        self.assertEqual((day['status'], day['short_minutes'], day['short_display']), ('Present', 80, '1h 20m'))

    def test_a_late_day_carries_it_too(self):
        self.assertEqual(self.day(LATE, 40)['short_display'], '40m')

    def test_a_half_day_or_a_completed_day_carries_none(self):
        self.assertIsNone(self.day(HALF, 280)['short_display'])
        self.assertIsNone(self.day(PRESENT, 0)['short_display'])

    def test_the_text_helpers(self):
        self.assertEqual([_short_display(m) for m in (0, 5, 60, 80)], [None, '5m', '1h 00m', '1h 20m'])
        self.assertEqual(_calendar_short_minutes(PRESENT, None), 0)
        self.assertEqual(_calendar_short_minutes(PRESENT, SimpleNamespace()), 0)       # a record from before the field existed


class SettingsSerializerTests(SimpleTestCase):
    base = {'min_hours_full_day': '8.00', 'min_hours_half_day': '4.00', 'early_exit_grace_minutes': 30}

    def test_the_switch_defaults_to_off_and_accepts_on(self):
        for extra, expected in (({}, False), ({'short_hours_as_half_day': True}, True), ({'short_hours_as_half_day': False}, False)):
            serializer = PunchRulesWriteSerializer(data={**self.base, **extra})
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data['short_hours_as_half_day'], expected)

    def test_the_half_day_limit_must_still_be_below_the_full_day_minimum(self):
        serializer = PunchRulesWriteSerializer(data={**self.base, 'min_hours_half_day': '8.00'})
        self.assertFalse(serializer.is_valid())
