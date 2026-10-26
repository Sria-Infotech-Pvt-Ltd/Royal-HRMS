from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.attendance.services_absence import finalize_missing_attendance
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.hrms.models import LeaveRequest, REQ_APPROVED


class DailyAttendanceCloseoutTests(TestCase):
    def setUp(self):
        role = make_role('daily_closeout_employee')
        self.target_date = timezone.localdate() - timedelta(days=2)
        self.employee = make_user(
            'daily-closeout@example.com',
            role=role,
            employee_id='CLOSEOUT01',
            date_of_joining=self.target_date - timedelta(days=30),
            onboarding_status=User.ONBOARDING_COMPLETE,
        )

    def _finalize(self):
        with (
            patch.object(AttendanceProcessorService, '_is_holiday', return_value=False),
            patch.object(AttendanceProcessorService, '_is_weekly_off', return_value=False),
        ):
            return finalize_missing_attendance(self.target_date)

    def test_missing_workday_is_recorded_absent_and_closeout_is_idempotent(self):
        result = self._finalize()
        record = AttendanceRecord.objects.get(employee=self.employee, date=self.target_date)

        self.assertEqual(result['created'], 1)
        self.assertEqual(record.status, AttendanceRecord.STATUS_ABSENT)
        self.assertEqual(self._finalize()['created'], 0)

    def test_approved_leave_gets_on_leave_record_not_absence(self):
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type='casual',
            duration='full_day',
            start_date=self.target_date,
            end_date=self.target_date,
            total_days=1,
            reason='Approved leave',
            status=REQ_APPROVED,
        )

        result = self._finalize()

        self.assertEqual(result['created'], 1)
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.employee, date=self.target_date).status,
            AttendanceRecord.STATUS_ON_LEAVE,
        )

    def test_existing_attendance_is_not_overwritten(self):
        AttendanceRecord.objects.create(
            employee=self.employee,
            date=self.target_date,
            status=AttendanceRecord.STATUS_PRESENT,
        )

        result = self._finalize()

        self.assertEqual(result['created'], 0)
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.employee, date=self.target_date).status,
            AttendanceRecord.STATUS_PRESENT,
        )
