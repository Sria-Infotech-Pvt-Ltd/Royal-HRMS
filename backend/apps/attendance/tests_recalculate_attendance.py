"""Recalculating existing days with the current settings: the decision logic (no database needed)."""
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.attendance.management.commands.recalculate_attendance_status import _month_range, _period
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.services_recalculate import (
    SOURCE_IMPORT, SOURCE_PUNCHES, RecalcPlan, _is_calculated_note, _plan_one, plan_imported_change, plan_record_change,
)

DAY = date(2026, 11, 10)


def cfg(full='7.67', half='4', break_minutes=60, grace=20, forgive_late=False, short_as_half=False):
    return SimpleNamespace(
        working_hours=SimpleNamespace(
            shift_start=time(9, 0), shift_end=time(18, 0), grace_period_minutes=grace, break_duration_minutes=break_minutes,
        ),
        punch_rules=SimpleNamespace(
            min_hours_full_day=Decimal(full), min_hours_half_day=Decimal(half), early_exit_grace_minutes=30,
            short_hours_as_half_day=short_as_half,
        ),
        overtime_rules=SimpleNamespace(ot_threshold_hours=Decimal('9')),
        late_mark_rules=SimpleNamespace(forgive_late_when_full_hours=forgive_late),
    )


def punch(kind, ist_hour, ist_minute):
    """A punch at an IST wall-clock time (IST is UTC+5:30), stored in UTC like the real ones."""
    ist = datetime(2026, 11, 10, ist_hour, ist_minute)
    utc = ist.replace(tzinfo=dt_timezone.utc) - timedelta(hours=5, minutes=30)
    return SimpleNamespace(punch_type=kind, punched_at=utc)


def record(status, minutes, is_late=False, note='', is_early_exit=False, first_in=None, last_out=None, short_minutes=0):
    return SimpleNamespace(
        pk='record-1', employee=SimpleNamespace(employee_id='E1', full_name='Test Person'),
        date=DAY, status=status, total_working_minutes=minutes, overtime_minutes=0,
        is_late=is_late, is_early_exit=is_early_exit, note=note, first_punch_in=first_in, last_punch_out=last_out,
        short_minutes=short_minutes,
    )


IN, OUT = AttendancePunch.PUNCH_IN, AttendancePunch.PUNCH_OUT
HALF, PRESENT, LATE = AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE


class PlanRecordChangeTests(SimpleTestCase):
    def test_seven_point_eight_hours_becomes_full_day_under_the_new_minimum(self):
        # 09:12 to 18:00 minus a 1 h lunch = 7 h 48 min (468): inside the 20 min grace, and above 7 h 40 min (460).
        changes = plan_record_change(record(HALF, 468), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg())
        self.assertEqual(changes, {'status': PRESENT})

    def test_under_an_eight_hour_minimum_the_same_day_becomes_present_with_hours_not_completed(self):
        # 7h48 is above the 4 h half-day limit but short of 8 h: Present, 12 minutes short (not a Half Day any more).
        changes = plan_record_change(record(HALF, 468), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg(full='8'))
        self.assertEqual(changes, {'status': PRESENT, 'short_minutes': 12})

    def test_with_short_days_as_half_days_switched_on_the_old_rule_still_applies(self):
        self.assertIsNone(plan_record_change(record(HALF, 468, short_minutes=12), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg(full='8', short_as_half=True)))
        changes = plan_record_change(record(PRESENT, 468), [punch(IN, 9, 12), punch(OUT, 18, 0)], cfg(full='8', short_as_half=True))
        self.assertEqual(changes, {'status': HALF, 'short_minutes': 12})

    def test_a_short_day_stays_half_day_not_absent(self):
        # Leaving at 12:00 is an early exit, so the stored record already carries that flag.
        self.assertIsNone(plan_record_change(record(HALF, 120, is_early_exit=True, short_minutes=340), [punch(IN, 9, 0), punch(OUT, 12, 0)], cfg()))

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


class ImportedDayTests(SimpleTestCase):
    """Days the HR import wrote before it followed the Punch Rules: stored IN/OUT times, no punch rows."""

    def test_an_old_import_loses_the_break_it_never_deducted(self):
        # The old import stored the raw span (09:12-18:00 = 528 min) and skipped the 1 h lunch.
        old = record(PRESENT, 528, first_in=time(9, 12), last_out=time(18, 0))
        self.assertEqual(plan_imported_change(old, cfg()), {'total_working_minutes': 468})

    def test_an_old_four_hour_import_is_no_longer_a_full_day(self):
        old = record(PRESENT, 240, first_in=time(9, 0), last_out=time(13, 0))     # the old rule: 240 min or more is Present
        self.assertEqual(
            plan_imported_change(old, cfg()),
            {'status': HALF, 'total_working_minutes': 180, 'short_minutes': 280, 'is_early_exit': True},
        )

    def test_an_import_that_is_already_right_is_left_alone(self):
        current = record(PRESENT, 468, first_in=time(9, 12), last_out=time(18, 0))
        self.assertIsNone(plan_imported_change(current, cfg()))

    def test_an_import_without_a_usable_in_out_pair_is_left_alone(self):
        self.assertIsNone(plan_imported_change(record(PRESENT, 0), cfg()))
        self.assertIsNone(plan_imported_change(record(PRESENT, 0, first_in=time(9, 0), last_out=None), cfg()))
        self.assertIsNone(plan_imported_change(record(PRESENT, 0, first_in=time(18, 0), last_out=time(9, 0)), cfg()))

    def test_a_person_s_note_on_an_imported_day_is_kept(self):
        old = record(PRESENT, 240, note='Checked with HR', first_in=time(9, 0), last_out=time(13, 0))
        self.assertNotIn('note', plan_imported_change(old, cfg()))

    def test_planning_uses_stored_times_only_for_days_from_the_import(self):
        old = record(PRESENT, 240, first_in=time(9, 0), last_out=time(13, 0))
        plan = RecalcPlan()
        _plan_one(plan, old, [], True, cfg())
        self.assertEqual([change.source for change in plan.changes], [SOURCE_IMPORT])
        self.assertEqual(plan.changes[0].new_status, HALF)

    def test_a_day_with_no_punches_that_was_not_imported_is_skipped(self):
        # leave, manual entry and the like: nothing to recompute from
        plan = RecalcPlan()
        _plan_one(plan, record(PRESENT, 240, first_in=time(9, 0), last_out=time(13, 0)), [], False, cfg())
        self.assertEqual((plan.changes, list(plan.skipped)), ([], ['no punches and not from the import (leave, manual entry)']))

    def test_real_punches_win_over_stored_import_times(self):
        stored = record(HALF, 468, first_in=time(9, 0), last_out=time(13, 0))
        plan = RecalcPlan()
        _plan_one(plan, stored, [punch(IN, 9, 12), punch(OUT, 18, 0)], True, cfg())
        self.assertEqual([change.source for change in plan.changes], [SOURCE_PUNCHES])
        self.assertEqual(plan.changes[0].new_status, PRESENT)

    def test_a_day_still_clocked_in_is_skipped_even_if_imported(self):
        plan = RecalcPlan()
        _plan_one(plan, record(PRESENT, 0, first_in=time(9, 0), last_out=time(13, 0)), [punch(IN, 9, 0)], True, cfg())
        self.assertEqual((plan.changes, plan.skipped), ([], {'still clocked in': 1}))
