"""The HR import marks a day with the same Punch Rules as live punching (no fixed hours). No database needed."""
from datetime import date, time

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceRecord
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.attendance.tests_recalculate_attendance import IN, OUT, cfg, punch

HALF, PRESENT, LATE, ABSENT = (
    AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_ABSENT,
)


def evaluate(start, end, settings):
    return AttendanceProcessorService.evaluate_times(start, end, settings)


class EvaluateTimesTests(SimpleTestCase):
    def test_a_full_day_inside_the_grace_is_present(self):
        day = evaluate(time(9, 12), time(18, 0), cfg())     # 8h48 minus 1h lunch = 7h48, above 7h40
        self.assertEqual((day['status'], day['total_working_minutes'], day['is_late']), (PRESENT, 468, False))

    def test_exactly_four_hours_on_the_clock_is_no_longer_a_full_day(self):
        # The old import rule was "240 minutes or more is Present". 09:00-13:00 is 3 h after lunch: a half day.
        self.assertEqual(evaluate(time(9, 0), time(13, 0), cfg())['status'], HALF)

    def test_late_and_short_is_a_half_day(self):
        day = evaluate(time(9, 30), time(18, 0), cfg())     # 9:30 is past the 9:20 grace; 7h30 is below 7h40
        self.assertEqual((day['status'], day['is_late']), (HALF, True))

    def test_late_but_full_hours_follows_the_forgive_late_setting(self):
        self.assertEqual(evaluate(time(10, 0), time(19, 0), cfg(forgive_late=False))['status'], LATE)
        self.assertEqual(evaluate(time(10, 0), time(19, 0), cfg(forgive_late=True))['status'], PRESENT)

    def test_the_status_follows_whatever_minimums_are_saved(self):
        for full, expected in (('8', HALF), ('7.5', PRESENT)):
            self.assertEqual(evaluate(time(9, 12), time(18, 0), cfg(full=full))['status'], expected, full)

    def test_overtime_comes_from_the_overtime_threshold(self):
        day = evaluate(time(9, 0), time(20, 0), cfg())      # 11h minus 1h lunch = 600 min; threshold 9h = 540
        self.assertEqual(day['overtime_minutes'], 60)

    def test_early_exit_is_flagged(self):
        self.assertTrue(evaluate(time(9, 0), time(15, 0), cfg())['is_early_exit'])

    def test_no_usable_out_time_is_absent_with_no_hours(self):
        for punch_out in (None, time(9, 0), time(8, 0)):
            day = evaluate(time(9, 0), punch_out, cfg())
            self.assertEqual((day['status'], day['total_working_minutes']), (ABSENT, 0), punch_out)

    def test_without_saved_settings_it_falls_back_to_the_defaults(self):
        self.assertEqual(evaluate(time(9, 0), time(17, 0), None)['status'], PRESENT)    # 8 h, no break
        self.assertEqual(evaluate(time(9, 0), time(14, 0), None)['status'], HALF)       # 5 h

    def test_an_imported_day_matches_a_punched_day_with_the_same_times(self):
        for start, end in ((time(9, 12), time(18, 0)), (time(9, 30), time(18, 0)), (time(9, 0), time(13, 0)), (time(10, 0), time(20, 0))):
            settings = cfg(forgive_late=True)
            imported = evaluate(start, end, settings)
            punched = AttendanceProcessorService._calculate(
                [punch(IN, start.hour, start.minute), punch(OUT, end.hour, end.minute)], date(2026, 11, 10), settings,
            )
            self.assertEqual(imported, punched, (start, end))
