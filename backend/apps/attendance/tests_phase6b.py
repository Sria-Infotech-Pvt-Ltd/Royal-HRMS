"""
Phase 6B — tests for the Shift model, geofence v2 parity with the legacy
Haversine check, the device push endpoint (idempotency, clock skew,
unknown employee), and the comp-off earning hook on approved
holiday/weekly-off overtime.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone as dt_timezone
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.attendance.models import AttendanceOvertime
from apps.attendance.models_device import AttendanceDevice, DevicePunchLog
from apps.attendance.models_geofence import Geofence
from apps.attendance.models_shift import Shift
from apps.attendance.services_device_push import push_punches
from apps.attendance.services_geofence_v2 import validate_point
from apps.attendance.services_geofencing import GpsCoordinate, haversine_distance
from apps.attendance.services_hr_ops import create_overtime
from apps.hrms.models_leave_ledger import LeaveTransaction


class ShiftModelTests(TestCase):
    def test_crosses_midnight_derived_on_save(self):
        day_shift = Shift.objects.create(code='DAY', name='Day Shift', start_time=time(9, 0), end_time=time(18, 0))
        night_shift = Shift.objects.create(code='NIGHT', name='Night Shift', start_time=time(22, 0), end_time=time(6, 0))

        self.assertFalse(day_shift.crosses_midnight)
        self.assertTrue(night_shift.crosses_midnight)


class GeofenceV2ParityTests(TestCase):
    def test_circle_validation_matches_legacy_haversine_distance(self):
        geofence = Geofence(
            code='TEST', name='Test', type=Geofence.TYPE_CIRCLE,
            center_latitude=Decimal('12.9716'), center_longitude=Decimal('77.5946'), radius_meters=200,
        )
        point = GpsCoordinate(latitude=12.9720, longitude=77.5950)

        is_inside, distance = validate_point(point, geofence)
        expected_distance = haversine_distance(point, GpsCoordinate(latitude=12.9716, longitude=77.5946))

        self.assertAlmostEqual(distance, expected_distance, places=6)
        self.assertEqual(is_inside, distance <= 200)

    def test_point_outside_radius_rejected(self):
        geofence = Geofence(
            code='TEST2', name='Test2', type=Geofence.TYPE_CIRCLE,
            center_latitude=Decimal('12.9716'), center_longitude=Decimal('77.5946'), radius_meters=50,
        )
        far_point = GpsCoordinate(latitude=13.05, longitude=77.65)
        is_inside, distance = validate_point(far_point, geofence)
        self.assertFalse(is_inside)
        self.assertGreater(distance, 50)

    def test_polygon_point_inside(self):
        geofence = Geofence(
            code='POLY', name='Poly', type=Geofence.TYPE_POLYGON,
            polygon_points=[[0, 0], [0, 10], [10, 10], [10, 0]],
        )
        inside_point = GpsCoordinate(latitude=5, longitude=5)
        outside_point = GpsCoordinate(latitude=50, longitude=50)
        self.assertTrue(validate_point(inside_point, geofence)[0])
        self.assertFalse(validate_point(outside_point, geofence)[0])


class DevicePushTests(TestCase):
    def setUp(self):
        self.device = AttendanceDevice.objects.create(code='DEV1', name='Lobby Biometric')
        self.employee = make_user('devicepushemp@test.com', password='TestPass123!')
        self.employee.employee_id = 'EMP77001'
        self.employee.save(update_fields=['employee_id'])

    def test_accepted_punch_creates_attendance_punch(self):
        results = push_punches(self.device, [{
            'device_punch_id': 'DP-1', 'employee_code': 'EMP77001', 'punch_type': 'IN',
            'device_time': datetime(2026, 1, 5, 9, 0, tzinfo=dt_timezone.utc),
        }])
        self.assertEqual(results[0].status, 'accepted')
        log = DevicePunchLog.objects.get(device=self.device, device_punch_id='DP-1')
        self.assertIsNotNone(log.punch)
        self.assertEqual(log.punch.source, 'biometric')

    def test_duplicate_push_rejected_idempotently(self):
        row = {
            'device_punch_id': 'DP-2', 'employee_code': 'EMP77001', 'punch_type': 'IN',
            'device_time': datetime(2026, 1, 5, 9, 0, tzinfo=dt_timezone.utc),
        }
        push_punches(self.device, [row])
        results = push_punches(self.device, [row])
        self.assertEqual(results[0].status, 'duplicate')
        self.assertEqual(DevicePunchLog.objects.filter(device=self.device, device_punch_id='DP-2').count(), 1)

    def test_unknown_employee_rejected(self):
        results = push_punches(self.device, [{
            'device_punch_id': 'DP-3', 'employee_code': 'NOTREAL', 'punch_type': 'IN',
            'device_time': datetime(2026, 1, 5, 9, 0, tzinfo=dt_timezone.utc),
        }])
        self.assertEqual(results[0].status, 'rejected')
        log = DevicePunchLog.objects.get(device=self.device, device_punch_id='DP-3')
        self.assertIsNone(log.punch)

    def test_clock_skew_recorded(self):
        results = push_punches(self.device, [{
            'device_punch_id': 'DP-4', 'employee_code': 'EMP77001', 'punch_type': 'IN',
            'device_time': datetime(2020, 1, 1, tzinfo=dt_timezone.utc),
        }])
        log = DevicePunchLog.objects.get(device=self.device, device_punch_id='DP-4')
        self.assertGreater(log.clock_skew_seconds, 0)


class DevicePushEndpointTests(TestCase):
    def setUp(self):
        self.device = AttendanceDevice.objects.create(code='DEV2', name='Gate Kiosk')
        self.employee = make_user('devicepushapi@test.com', password='TestPass123!')
        self.employee.employee_id = 'EMP77002'
        self.employee.save(update_fields=['employee_id'])
        self.client = APIClient()

    def test_push_requires_valid_api_key(self):
        resp = self.client.post(
            reverse('attendance-device-push'),
            {'punches': [{'device_punch_id': 'X', 'employee_code': 'EMP77002', 'punch_type': 'IN', 'device_time': '2026-01-05T09:00:00+00:00'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_push_with_valid_key_succeeds(self):
        resp = self.client.post(
            reverse('attendance-device-push'),
            {'punches': [{'device_punch_id': 'Y', 'employee_code': 'EMP77002', 'punch_type': 'IN', 'device_time': '2026-01-05T09:00:00+00:00'}]},
            format='json', HTTP_X_DEVICE_API_KEY=self.device.api_key,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['results'][0]['status'], 'accepted')


class CompOffEarningFromOvertimeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_leave_types')

    def setUp(self):
        self.employee = make_user('otcompoffemp@test.com', password='TestPass123!')
        self.employee.employee_id = 'EMP77003'
        self.employee.save(update_fields=['employee_id'])
        self.hr_user = make_user('othruser@test.com', password='TestPass123!')
        self.hr_user.employee_id = 'EMP77004'
        self.hr_user.save(update_fields=['employee_id'])

    def test_approved_holiday_overtime_grants_comp_off(self):
        create_overtime({
            'employee_id': self.employee.employee_id, 'date': date(2026, 1, 5),
            'ot_start': time(9, 0), 'ot_end': time(17, 0), 'ot_type': AttendanceOvertime.OT_TYPE_HOLIDAY,
            'reason': 'Worked on holiday', 'approved_by': self.hr_user.employee_id,
        }, created_by=self.hr_user)

        self.assertTrue(
            LeaveTransaction.objects.filter(
                employee=self.employee, txn_type=LeaveTransaction.TXN_COMP_OFF_EARNED,
            ).exists()
        )

    def test_regular_overtime_does_not_grant_comp_off(self):
        create_overtime({
            'employee_id': self.employee.employee_id, 'date': date(2026, 1, 6),
            'ot_start': time(18, 0), 'ot_end': time(20, 0), 'ot_type': AttendanceOvertime.OT_TYPE_REGULAR,
            'reason': 'Regular OT', 'approved_by': self.hr_user.employee_id,
        }, created_by=self.hr_user)

        self.assertFalse(
            LeaveTransaction.objects.filter(
                employee=self.employee, txn_type=LeaveTransaction.TXN_COMP_OFF_EARNED,
            ).exists()
        )

    def test_insufficient_hours_on_weekly_off_ot_does_not_crash(self):
        # 1 hour is below the 4-hour comp-off minimum -> CompOffError is
        # caught and logged, OT entry creation must still succeed.
        ot_entry = create_overtime({
            'employee_id': self.employee.employee_id, 'date': date(2026, 1, 7),
            'ot_start': time(9, 0), 'ot_end': time(10, 0), 'ot_type': AttendanceOvertime.OT_TYPE_WEEKLY_OFF,
            'reason': 'Short weekly-off OT', 'approved_by': self.hr_user.employee_id,
        }, created_by=self.hr_user)
        self.assertIsNotNone(ot_entry.id)
