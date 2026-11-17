"""A late arrival is forgiven once the full-day hours are worked, and overtime starts at shift end (shift 9:00-18:00, 30-minute break)."""
from __future__ import annotations

import datetime
import importlib
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from apps.accounts.factories import make_user
from apps.attendance.models import AttendancePunch, AttendanceRecord, AttendanceSettings
from apps.attendance.services import AttendanceSettingsService, DEFAULT_SETTINGS
from apps.attendance.services_attendance import AttendanceProcessorService

IST = ZoneInfo('Asia/Kolkata')
DAY = datetime.date(2030, 3, 4)


def config(forgive: bool = True, ot_threshold: str = '8.50') -> SimpleNamespace:
    return SimpleNamespace(
        working_hours=SimpleNamespace(
            shift_start=datetime.time(9, 0), shift_end=datetime.time(18, 0), grace_period_minutes=15, break_duration_minutes=30,
        ),
        punch_rules=SimpleNamespace(min_hours_full_day=Decimal('8.00'), min_hours_half_day=Decimal('4.00'), early_exit_grace_minutes=30),
        overtime_rules=SimpleNamespace(ot_threshold_hours=Decimal(ot_threshold)),
        late_mark_rules=SimpleNamespace(forgive_late_when_full_hours=forgive),
    )


def punch(kind: str, hour: int, minute: int) -> SimpleNamespace:
    return SimpleNamespace(punch_type=kind, punched_at=datetime.datetime.combine(DAY, datetime.time(hour, minute), tzinfo=IST))


def day(clock_in: tuple[int, int], clock_out: tuple[int, int] | None, **config_options) -> dict:
    punches = [punch(AttendancePunch.PUNCH_IN, *clock_in)] + ([punch(AttendancePunch.PUNCH_OUT, *clock_out)] if clock_out else [])
    return AttendanceProcessorService._calculate(punches, DAY, config(**config_options))


class LateForgivenessTests(SimpleTestCase):
    def test_late_arrival_with_full_hours_is_a_present_day_not_a_late_mark(self):
        result = day((9, 20), (18, 30))          # 9h10 gross, 8h40 after the break
        self.assertEqual(result['status'], AttendanceRecord.STATUS_PRESENT)
        self.assertTrue(result['is_late'])       # the arrival is still recorded
        self.assertIn('not counted as a late mark', result['note'])

    def test_exactly_the_full_hours_is_enough(self):
        self.assertEqual(day((9, 20), (17, 50))['status'], AttendanceRecord.STATUS_PRESENT)      # 8h30 gross = 8h net

    def test_late_arrival_without_full_hours_is_not_forgiven(self):
        self.assertEqual(day((9, 20), (17, 40))['status'], AttendanceRecord.STATUS_HALF_DAY)     # 8h20 gross = 7h50 net

    def test_still_clocked_in_after_a_late_arrival_shows_late_until_clock_out(self):
        self.assertEqual(day((9, 20), None)['status'], AttendanceRecord.STATUS_LATE)

    def test_the_rule_can_be_turned_off(self):
        result = day((9, 20), (18, 30), forgive=False)
        self.assertEqual(result['status'], AttendanceRecord.STATUS_LATE)
        self.assertEqual(result['note'], 'Grace exceeded')

    def test_an_on_time_day_is_present(self):
        result = day((9, 10), (18, 0))
        self.assertEqual((result['status'], result['is_late'], result['note']), (AttendanceRecord.STATUS_PRESENT, False, ''))


class OvertimeStartsAtShiftEndTests(SimpleTestCase):
    def test_nine_to_seven_has_an_hour_of_overtime(self):
        result = day((9, 0), (19, 0))            # 10h gross, 9h30 net, threshold 8h30
        self.assertEqual((result['status'], result['overtime_minutes']), (AttendanceRecord.STATUS_PRESENT, 60))

    def test_leaving_at_shift_end_has_no_overtime(self):
        self.assertEqual(day((9, 0), (18, 0))['overtime_minutes'], 0)

    def test_overtime_counts_from_six_for_someone_on_time(self):
        self.assertEqual(day((9, 0), (18, 45))['overtime_minutes'], 45)

    def test_late_arrival_working_past_seven_is_a_full_day_with_overtime(self):
        result = day((9, 20), (19, 0))           # 9h40 gross, 9h10 net
        self.assertEqual((result['status'], result['overtime_minutes']), (AttendanceRecord.STATUS_PRESENT, 40))

    def test_the_old_nine_hour_threshold_started_overtime_half_an_hour_late(self):
        self.assertEqual(day((9, 0), (18, 30), ot_threshold='9.00')['overtime_minutes'], 0)


class DefaultsAndMigrationTests(TestCase):
    def test_new_installs_default_to_forgiving_late_and_an_overtime_threshold_at_shift_end(self):
        self.assertTrue(DEFAULT_SETTINGS['late_mark_rules']['forgive_late_when_full_hours'])
        self.assertEqual(DEFAULT_SETTINGS['overtime_rules']['ot_threshold_hours'], '8.50')
        settings = AttendanceSettingsService._create(DEFAULT_SETTINGS, make_user('att-defaults@test.com'))
        self.assertTrue(settings.late_mark_rules.forgive_late_when_full_hours)
        self.assertEqual(settings.overtime_rules.ot_threshold_hours, Decimal('8.50'))

    def _settings(self, email: str, threshold: str, break_minutes: int = 30, shift=('09:00:00', '18:00:00')):
        data = {**DEFAULT_SETTINGS, 'overtime_rules': {**DEFAULT_SETTINGS['overtime_rules'], 'ot_threshold_hours': threshold},
                'working_hours': {**DEFAULT_SETTINGS['working_hours'], 'break_duration_minutes': break_minutes, 'shift_start': shift[0], 'shift_end': shift[1]}}
        return AttendanceSettingsService._create(data, make_user(email))

    def _threshold(self, settings) -> Decimal:
        return AttendanceSettings.objects.get(pk=settings.pk).overtime_rules.ot_threshold_hours

    def test_the_migration_fixes_only_a_threshold_that_equals_the_shift_length(self):
        migration = importlib.import_module('apps.attendance.migrations.0051_overtime_starts_at_shift_end')
        clash = self._settings('att-mig-a@test.com', '9.00')
        # one settings row at a time is the norm, but the migration walks all rows, so give the others their own state afterwards
        migration.lower_to_shift_end(apps, None)
        self.assertEqual(self._threshold(clash), Decimal('8.50'))
        migration.restore_shift_length(apps, None)
        self.assertEqual(self._threshold(clash), Decimal('9.00'))

    def test_a_threshold_the_company_chose_is_left_alone(self):
        migration = importlib.import_module('apps.attendance.migrations.0051_overtime_starts_at_shift_end')
        custom = self._settings('att-mig-b@test.com', '10.00')
        migration.lower_to_shift_end(apps, None)
        self.assertEqual(self._threshold(custom), Decimal('10.00'))

    def test_no_break_means_no_change(self):
        migration = importlib.import_module('apps.attendance.migrations.0051_overtime_starts_at_shift_end')
        no_break = self._settings('att-mig-c@test.com', '9.00', break_minutes=0)
        migration.lower_to_shift_end(apps, None)
        self.assertEqual(self._threshold(no_break), Decimal('9.00'))
