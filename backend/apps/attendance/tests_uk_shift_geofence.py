"""
UK Shift geofence exemption: GPS capture + storage stays mandatory, but
branch-distance geofence validation is skipped specifically for employees
assigned to the UK Shift (identified by the immutable WorkingHoursPolicy
policy_code 'WH-UK', never the editable display name). Every other shift
(SGT/ICT, the unassigned global 09:00-18:00 default) keeps the existing
geofence behaviour unchanged.

Also covers: the new Clock In/Clock Out coordinate fields on the HR
attendance detail endpoint, gated behind the same pre-existing permission
check, and confirms this change doesn't interact with face verification,
the daily 1-IN/1-OUT limit, or shift-aware late/early-exit resolution.
"""
from __future__ import annotations

from datetime import time

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    AttendancePunch,
    AttendanceRecord,
    AttendanceSettings,
    AttendanceWorkingHours,
    EmployeeShiftAssignment,
    WorkingHoursPolicy,
)
from apps.branch.models import Branch, City, State
from config.test_runner import TEST_COMPANY_CODE

# Hyderabad, matching apps/attendance/tests.py's GeofencingPunchTests fixture.
OFFICE_LAT = 17.385044
OFFICE_LON = 78.486671
# ~15 km away — well outside any reasonable office geofence.
FAR_LAT = 17.529730
FAR_LON = 78.618416


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _punch(client: APIClient, punch_type: str, lat=None, lon=None):
    payload = {'punch_type': punch_type, 'attendance_mode': 'office'}
    if lat is not None:
        payload['latitude'] = lat
    if lon is not None:
        payload['longitude'] = lon
    return client.post(reverse('attendance-punch'), payload, format='json')


class UKShiftGeofenceBypassTests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='UKGEO01', branch_name='UK Geofence Test Office', address='Test Address',
            state=state, city=city,
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            allowed_radius_meters=150, geofencing_enabled=True,
        )

        # The real seeded shifts (migrations/0045) — must use the actual
        # policy_code the geofence bypass checks against, not a test stand-in.
        self.uk_policy = WorkingHoursPolicy.objects.get(policy_code='WH-UK')
        self.sgt_policy = WorkingHoursPolicy.objects.get(policy_code='WH-SGT-ICT')

        role = make_role('employee_uk_geofence_test')
        self.uk_emp = make_user(
            'ukgeo@test.com', role=role, password='TestPass123!',
            employee_id='EMPUKG001', branch='UK Geofence Test Office',
        )
        self.sgt_emp = make_user(
            'sgtgeo@test.com', role=role, password='TestPass123!',
            employee_id='EMPUKG002', branch='UK Geofence Test Office',
        )
        self.default_emp = make_user(
            'defaultgeo@test.com', role=role, password='TestPass123!',
            employee_id='EMPUKG003', branch='UK Geofence Test Office',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.sgt_emp, policy=self.sgt_policy, effective_from=timezone.localdate(),
        )

    # 1. UK Shift employee with valid GPS can Clock In outside branch geofence.
    def test_uk_employee_can_clock_in_outside_geofence(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)

    # 2. UK Shift employee with valid GPS can Clock Out outside branch geofence.
    def test_uk_employee_can_clock_out_outside_geofence(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        _punch(client, 'IN', FAR_LAT, FAR_LON)
        resp = _punch(client, 'OUT', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)

    # 3. UK Shift employee still requires GPS coordinates.
    def test_uk_employee_still_requires_gps(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        resp = _punch(client, 'IN')  # no lat/lon at all
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('location is required', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.uk_emp).exists())

    # 4. UK Shift punch stores latitude/longitude.
    def test_uk_employee_punch_stores_coordinates(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        _punch(client, 'IN', FAR_LAT, FAR_LON)
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertAlmostEqual(float(punch.latitude), FAR_LAT, places=5)
        self.assertAlmostEqual(float(punch.longitude), FAR_LON, places=5)

    # 5. UK Shift does not incorrectly mark the punch as inside the branch geofence.
    def test_uk_employee_punch_not_marked_inside_geofence(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        # Even from right at the branch's own coordinates — the bypass must
        # not fabricate a "yes, inside" result either; it should stay neutral.
        _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertIsNone(punch.is_inside_geofence)
        self.assertIsNone(punch.calculated_distance)

    # 6. Normal (unassigned, global 09:00-18:00) employee: geofence unchanged.
    def test_default_shift_employee_geofence_unchanged(self):
        client = APIClient()
        _login(client, 'defaultgeo@test.com')
        inside = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(inside.status_code, 200, inside.data)
        outside = _punch(client, 'OUT', FAR_LAT, FAR_LON)
        self.assertEqual(outside.status_code, 403, outside.data)
        self.assertIn('outside your assigned office location', outside.data['message'])

    # 7. SGT/ICT employee: geofence unchanged — confirms the bypass is
    # strictly UK-specific, not "any assigned shift".
    def test_sgt_ict_employee_geofence_unchanged(self):
        client = APIClient()
        _login(client, 'sgtgeo@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('outside your assigned office location', resp.data['message'])

    # 8. Non-UK behaviour remains unchanged — default employee punching from
    # inside the geofence still gets a normal, fully-validated allow.
    def test_default_shift_employee_inside_geofence_marked_correctly(self):
        client = APIClient()
        _login(client, 'defaultgeo@test.com')
        _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        punch = AttendancePunch.objects.get(employee=self.default_emp, punch_type='IN')
        self.assertTrue(punch.is_inside_geofence)
        self.assertIsNotNone(punch.calculated_distance)

    # 12. Daily 1-IN/1-OUT limit remains unchanged for UK Shift employees.
    def test_uk_employee_daily_punch_limit_unchanged(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        _punch(client, 'IN', FAR_LAT, FAR_LON)
        second_in = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(second_in.status_code, 400, second_in.data)
        self.assertIn('already clocked in', second_in.data['message'].lower())

    # 13. Face verification remains unchanged (off by default — no
    # AttendanceFaceVerificationRules configured) for a UK Shift employee.
    def test_uk_employee_face_verification_path_unaffected(self):
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertFalse(punch.face_verified)

    # 14. Shift resolution (late/early-exit) remains unchanged for UK Shift —
    # the extra early shift lookup in the geofence bypass doesn't interfere
    # with process_day()'s own, separate shift resolution.
    def test_uk_employee_late_arrival_still_detected_correctly(self):
        settings_row = AttendanceSettings.objects.create(is_active=True)
        AttendanceWorkingHours.objects.create(
            settings=settings_row, shift_start=time(9, 0), shift_end=time(18, 0),
            grace_period_minutes=15, missing_punch_grace_minutes=10, break_duration_minutes=30,
        )
        client = APIClient()
        _login(client, 'ukgeo@test.com')
        # UK Shift is 12:00-21:00, grace 15 -> late after 12:15.
        late_time = timezone.make_aware(timezone.datetime.combine(timezone.localdate(), time(12, 30)))
        from unittest.mock import patch
        with patch('django.utils.timezone.now', return_value=late_time):
            resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        record = AttendanceRecord.objects.get(employee=self.uk_emp, date=timezone.localdate())
        self.assertTrue(record.is_late)


class AttendanceDetailLocationAPITests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        Branch.objects.create(
            branch_code='UKGEO02', branch_name='UK Geofence Detail Office', address='Test Address',
            state=state, city=city,
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        self.uk_policy = WorkingHoursPolicy.objects.get(policy_code='WH-UK')

        hr_role = make_role('hr_uk_geofence_detail_test', permission_codenames=['attendance.view'])
        self.hr = make_user(
            'hr.ukgeodetail@test.com', role=hr_role, password='TestPass123!', employee_id='EMPHRUKG001',
        )
        emp_role = make_role('employee_uk_geofence_detail_test')
        self.uk_emp = make_user(
            'ukgeodetail@test.com', role=emp_role, password='TestPass123!',
            employee_id='EMPUKGD001', branch='UK Geofence Detail Office',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )

        emp_client = APIClient()
        _login(emp_client, 'ukgeodetail@test.com')
        _punch(emp_client, 'IN', FAR_LAT, FAR_LON)
        _punch(emp_client, 'OUT', FAR_LAT + 0.01, FAR_LON + 0.01)

        self.record = AttendanceRecord.objects.get(employee=self.uk_emp)

    def _detail_url(self):
        return f"{reverse('hr-attendance-detail', kwargs={'pk': self.record.id})}?date={self.record.date.isoformat()}"

    # 9 & 10. Attendance detail API returns Clock In and Clock Out coordinates.
    def test_detail_api_returns_clock_in_and_out_coordinates(self):
        client = APIClient()
        _login(client, 'hr.ukgeodetail@test.com')
        resp = client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        detail = resp.data['data']
        self.assertAlmostEqual(detail['clock_in_latitude'], FAR_LAT, places=5)
        self.assertAlmostEqual(detail['clock_in_longitude'], FAR_LON, places=5)
        self.assertAlmostEqual(detail['clock_out_latitude'], FAR_LAT + 0.01, places=5)
        self.assertAlmostEqual(detail['clock_out_longitude'], FAR_LON + 0.01, places=5)

    # 11. Unauthorized users cannot access the newly exposed location data.
    def test_unauthorized_user_cannot_access_detail(self):
        no_perm_role = make_role('no_perm_uk_geofence_detail_test')
        make_user('noperm.ukgeodetail@test.com', role=no_perm_role, password='TestPass123!')
        client = APIClient()
        _login(client, 'noperm.ukgeodetail@test.com')
        resp = client.get(self._detail_url())
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('clock_in_latitude', resp.data)
