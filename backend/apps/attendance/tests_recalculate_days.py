"""recalculate_attendance_days repairs days saved with the old rule (approved early punch-in not counted), and nothing else."""
from __future__ import annotations

import datetime
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.attendance.models import AttendanceAuditLog, AttendancePunch, AttendanceRecord
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.attendance.services_recalculate_days import recalculate_correction_days

TODAY = timezone.localdate()
YESTERDAY = TODAY - datetime.timedelta(days=1)
ZONE = timezone.get_current_timezone()


def _at(day: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, minute)), ZONE)


class RecalculateDaysTests(TestCase):
    def setUp(self):
        cache.clear()
        self.employee = make_user('recalc-emp@test.com', employee_id='EMPRC001', date_of_joining=TODAY - datetime.timedelta(days=120))

    def _punch(self, day, hour, minute, kind, source='web'):
        return AttendancePunch.objects.create(employee=self.employee, punched_at=_at(day, hour, minute), punch_type=kind, source=source, attendance_mode='office')

    def _stale_record(self, day=YESTERDAY, status='half_day', start=datetime.time(13, 55), end=datetime.time(18, 0), minutes=245):
        return AttendanceRecord.objects.create(employee=self.employee, date=day, status=status, first_punch_in=start, last_punch_out=end, total_working_minutes=minutes)

    def _surya_day(self, day=YESTERDAY):
        """Came at 9:00 and forgot; an approved correction added IN 9:00; he punched in at 13:55 anyway and out at 18:00."""
        self._punch(day, 9, 0, 'IN', source='manual')
        self._punch(day, 13, 55, 'IN')
        self._punch(day, 18, 0, 'OUT')

    def test_a_day_saved_with_the_late_start_is_recalculated_from_the_approved_earlier_punch_in(self):
        self._surya_day()
        self._stale_record()
        changes = recalculate_correction_days(14)
        self.assertEqual(len(changes), 1)
        record = AttendanceRecord.objects.get(employee=self.employee, date=YESTERDAY)
        self.assertEqual(record.first_punch_in, datetime.time(9, 0))
        self.assertGreater(record.total_working_minutes, 400)

    def test_dry_run_shows_the_change_but_saves_nothing(self):
        self._surya_day()
        self._stale_record()
        out = StringIO()
        call_command('recalculate_attendance_days', '--dry-run', stdout=out)
        self.assertIn('would change', out.getvalue())
        self.assertEqual(AttendanceRecord.objects.get(employee=self.employee, date=YESTERDAY).first_punch_in, datetime.time(13, 55))

    def test_running_it_again_changes_nothing(self):
        self._surya_day()
        self._stale_record()
        recalculate_correction_days(14)
        self.assertEqual(recalculate_correction_days(14), [])

    def test_a_day_hr_edited_by_hand_is_left_alone(self):
        self._surya_day()
        record = self._stale_record()
        AttendanceAuditLog.objects.create(employee=self.employee, date=YESTERDAY, event=AttendanceAuditLog.EVENT_MANUALLY_EDITED, record=record, action='HR manually edited attendance record.')
        self.assertEqual(recalculate_correction_days(14), [])
        self.assertEqual(AttendanceRecord.objects.get(pk=record.pk).first_punch_in, datetime.time(13, 55))

    def test_a_day_without_any_manual_punch_is_left_alone_even_if_it_looks_odd(self):
        self._punch(YESTERDAY, 13, 55, 'IN')
        self._punch(YESTERDAY, 18, 0, 'OUT')
        self._stale_record(start=datetime.time(10, 0))
        self.assertEqual(recalculate_correction_days(14), [])

    def test_leave_holiday_week_off_and_absent_days_are_decisions_and_stay(self):
        for offset, status in enumerate(('on_leave', 'holiday', 'weekly_off', 'absent'), start=1):
            day = TODAY - datetime.timedelta(days=offset)
            self._punch(day, 9, 0, 'IN', source='manual')
            self._punch(day, 18, 0, 'OUT')
            AttendanceRecord.objects.create(employee=self.employee, date=day, status=status, total_working_minutes=0)
        self.assertEqual(recalculate_correction_days(14), [])

    def test_days_older_than_the_window_are_left_alone(self):
        old = TODAY - datetime.timedelta(days=30)
        self._surya_day(old)
        self._stale_record(day=old)
        self.assertEqual(recalculate_correction_days(14), [])
        self.assertEqual(len(recalculate_correction_days(45)), 1)

    def test_a_day_inside_a_closed_payroll_cycle_is_left_alone(self):
        from apps.payroll.models import PayrollCycle
        self._surya_day()
        self._stale_record()
        cycle = PayrollCycle(cycle_start=YESTERDAY - datetime.timedelta(days=10), cycle_end=TODAY, pay_date=TODAY, status='closed', created_by=self.employee)
        PayrollCycle.objects.bulk_create([cycle])
        self.assertEqual(recalculate_correction_days(14), [])

    def test_the_command_can_be_limited_to_one_employee(self):
        self._surya_day()
        self._stale_record()
        other = make_user('recalc-other@test.com', employee_id='EMPRC002', date_of_joining=TODAY - datetime.timedelta(days=120))
        self.assertEqual(recalculate_correction_days(14, employee_key='EMPRC002'), [])
        self.assertEqual(len(recalculate_correction_days(14, employee_key='EMPRC001')), 1)
        self.assertEqual(AttendanceProcessorService.process_day(other, YESTERDAY).employee_id, other.id)
