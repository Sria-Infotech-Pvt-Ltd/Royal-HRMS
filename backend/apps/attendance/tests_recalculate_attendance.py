"""Recalculating existing days with the current settings: the decision logic (no database needed)."""
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.attendance.management.commands.recalculate_attendance_status import _month_range, _period
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.services_recalculate import RecalcPlan, _is_calculated_note, plan_record_change

DAY = date(2026, 11, 10)


def cfg(full='7.67', half='4', break_minutes=60, grace=20, forgive_late=False):
    return SimpleNamespace(
        working_hours=SimpleNamespace(
            shift_start=time(9, 0), shift_end=time(18, 0), grace_period_minutes=grace, break_duration_minutes=break_minutes,
        ),
        punch_rules=SimpleNamespace(min_hours_full_day=Decimal(full), min_hours_half_day=Decimal(half), early_exit_grace_minutes=30),
        overtime_rules=SimpleNamespace(ot_threshold_hours=Decimal('9')),
        late_mark_rules=SimpleNamespace(forgive_late_when_full_hours=forgive_late),
    )


def punch(kind, ist_hour, ist_minute):
    """A punch at an IST wall-clock time (IST is UTC+5:30), stored in UTC like the real ones."""
    ist = datetime(2026, 11, 10, ist_hour, ist_minute)
    utc = ist.replace(tzinfo=dt_timezone.utc) - timedelta(hours=5, minutes=30)
    return SimpleNamespace(punch_type=kind, punched_at=utc)


def record(status, minutes, is_late=False, note='', is_early_exit=False):
    return SimpleNamespace(
        date=DAY, status=status, total_working_minutes=minutes, overtime_minutes=0,
        is_late=is_late, is_early_exit=is_early_exit, note=note,
    )


IN, OUT = AttendancePunch.PUNCH_IN, AttendancePunch.PUNCH_OUT
HALF, PRESENT, LATE = AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE


class PlanRecordChangeTests(SimpleTestCase):
    def test_seven_point_eight_hours_becomes_full_day_under_the_new_minimum(self):
        # 09:12 to 18:00 minus a 1 h lunch = 7 h 48 min (468): inside the 20 min grace, and above 7 h 40 min (460).
        changes = plan_record_change(record(HALF, 468), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg())
        self.assertEqual(changes, {'status': PRESENT})

    def test_the_same_day_stays_half_day_under_the_old_eight_hour_minimum(self):
        self.assertIsNone(plan_record_change(record(HALF, 468), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg(full='8')))

    def test_a_stricter_minimum_can_also_turn_a_full_day_into_a_half_day(self):
        changes = plan_record_change(record(PRESENT, 468), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg(full='8'))
        self.assertEqual(changes, {'status': HALF})

    def test_a_short_day_stays_half_day_not_absent(self):
        # Leaving at 12:00 is an early exit, so the stored record already carries that flag.
        self.assertIsNone(plan_record_change(record(HALF, 120, is_early_exit=True), [punch(IN, 9, 0), punch(OUT, 12, 0)], cfg()))

    def test_a_day_with_no_punches_is_left_alone(self):
        self.assertIsNone(plan_record_change(record(HALF, 0), [], cfg()))

    def test_a_day_still_clocked_in_is_left_alone(self):
        self.assertIsNone(plan_record_change(record(PRESENT, 0), [punch(IN, 9, 0)], cfg()))
        self.assertIsNone(plan_record_change(record(PRESENT, 0), [punch(IN, 9, 0), punch(OUT, 13, 0), punch(IN, 14, 0)], cfg()))

    def test_a_note_written_by_a_person_is_kept(self):
        changes = plan_record_change(
            record(HALF, 468, note='Approved by HR'), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg(),
        )
        self.assertEqual(changes, {'status': PRESENT})

    def test_a_note_written_by_the_calculation_is_refreshed(self):
        # 09:30 is past the 09:20 grace (late); 09:30 to 19:00 minus lunch = 8 h 30 min, a full day. Late is forgiven here.
        changes = plan_record_change(
            record(LATE, 510, is_late=True, note='Grace exceeded'),
            [punch(IN, 9, 30), punch(OUT, 19, 0)], cfg(forgive_late=True),
        )
        self.assertEqual(changes['status'], PRESENT)
        self.assertIn('full hours completed', changes['note'])


class SupportingFunctionTests(SimpleTestCase):
    def test_calculated_notes_are_recognised(self):
        for note in ('', 'Grace exceeded', 'Late arrival', 'Grace exceeded - full hours completed, not counted as a late mark'):
            self.assertTrue(_is_calculated_note(note), note)
        self.assertFalse(_is_calculated_note('Approved by HR'))

    def test_the_plan_counts_skips_by_reason(self):
        plan = RecalcPlan()
        plan.skip('edited by hand')
        plan.skip('edited by hand')
        self.assertEqual(plan.skipped, {'edited by hand': 2})

    def test_month_range_for_a_past_month_covers_the_whole_month(self):
        with mock.patch('apps.attendance.management.commands.recalculate_attendance_status.timezone.localdate', return_value=date(2026, 11, 16)):
            self.assertEqual(_month_range('2026-10'), (date(2026, 10, 1), date(2026, 10, 31)))
            self.assertEqual(_month_range(''), (date(2026, 11, 1), date(2026, 11, 16)))

    def test_month_range_rejects_bad_input_and_future_months(self):
        with mock.patch('apps.attendance.management.commands.recalculate_attendance_status.timezone.localdate', return_value=date(2026, 11, 16)):
            for bad in ('November', '2026-13', '2027-01'):
                with self.assertRaises(CommandError):
                    _month_range(bad)

    def test_from_month_covers_every_month_up_to_the_end_month(self):
        with mock.patch('apps.attendance.management.commands.recalculate_attendance_status.timezone.localdate', return_value=date(2026, 11, 16)):
            self.assertEqual(_period('2026-04', ''), (date(2026, 4, 1), date(2026, 11, 16)))
            self.assertEqual(_period('2026-04', '2026-09'), (date(2026, 4, 1), date(2026, 9, 30)))
            self.assertEqual(_period('', '2026-10'), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_from_month_after_the_end_month_is_refused(self):
        with mock.patch('apps.attendance.management.commands.recalculate_attendance_status.timezone.localdate', return_value=date(2026, 11, 16)):
            with self.assertRaises(CommandError):
                _period('2026-11', '2026-09')
