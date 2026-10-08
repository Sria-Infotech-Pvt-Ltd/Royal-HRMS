"""
Human-readable location for attendance punches.

AttendancePunch.location_label is resolved by a best-effort, fire-and-forget
background task (apps.attendance.tasks.reverse_geocode_punch_task) dispatched
via transaction.on_commit() after the punch is already saved — never on the
employee's clock-in/out request path. A geocoding failure/timeout must never
fail the punch; it just leaves location_label empty, and the HR detail API/
UI already handle that gracefully.

Also covers: the new clock_in/out_location_label fields on the HR attendance
detail endpoint (same permission gate as the pre-existing coordinate fields),
and confirms this change doesn't interact with UK Shift's geofence bypass,
SGT/ICT or default-shift geofence behaviour, or the daily 1-IN/1-OUT limit.
"""
from __future__ import annotations

from datetime import time
from unittest.mock import patch

import requests
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendancePunch, EmployeeShiftAssignment, WorkingHoursPolicy
from apps.attendance.services_geocoding import reverse_geocode
from apps.attendance.tasks import reverse_geocode_punch_task
from apps.branch.models import Branch, City, State
from config.test_runner import TEST_COMPANY_CODE

OFFICE_LAT = 17.385044
OFFICE_LON = 78.486671
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


# ══════════════════════════════════════════════════════════════════════════════
#  services_geocoding.reverse_geocode — pure function, no DB
# ══════════════════════════════════════════════════════════════════════════════

class ReverseGeocodeServiceTests(SimpleTestCase):
    def _mock_response(self, address: dict):
        mock_resp = type('R', (), {})()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {'address': address}
        return mock_resp

    @patch('apps.attendance.services_geocoding.requests.get')
    def test_successful_response_returns_city_state_country_label(self, mock_get):
        mock_get.return_value = self._mock_response({
            'city': 'Hyderabad', 'state': 'Telangana', 'country': 'India',
        })
        label = reverse_geocode(OFFICE_LAT, OFFICE_LON)
        self.assertEqual(label, 'Hyderabad, Telangana, India')

    @patch('apps.attendance.services_geocoding.requests.get')
    def test_response_with_road_includes_area_before_city(self, mock_get):
        mock_get.return_value = self._mock_response({
            'road': 'Banjara Hills', 'city': 'Hyderabad', 'state': 'Telangana', 'country': 'India',
        })
        label = reverse_geocode(OFFICE_LAT, OFFICE_LON)
        self.assertEqual(label, 'Banjara Hills, Hyderabad, Telangana, India')

    @patch('apps.attendance.services_geocoding.requests.get')
    def test_missing_individual_fields_are_omitted_not_fabricated(self, mock_get):
        mock_get.return_value = self._mock_response({'city': 'Hyderabad', 'country': 'India'})
        label = reverse_geocode(OFFICE_LAT, OFFICE_LON)
        self.assertEqual(label, 'Hyderabad, India')  # no fabricated "None" for the missing state

    @patch('apps.attendance.services_geocoding.requests.get')
    def test_timeout_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout('simulated timeout')
        self.assertIsNone(reverse_geocode(OFFICE_LAT, OFFICE_LON))

    @patch('apps.attendance.services_geocoding.requests.get')
    def test_http_error_returns_none(self, mock_get):
        mock_get.side_effect = requests.exceptions.HTTPError('simulated 429')
        self.assertIsNone(reverse_geocode(OFFICE_LAT, OFFICE_LON))

    @patch('apps.attendance.services_geocoding.requests.get')
    def test_empty_address_returns_none(self, mock_get):
        mock_get.return_value = self._mock_response({})
        self.assertIsNone(reverse_geocode(OFFICE_LAT, OFFICE_LON))


# ══════════════════════════════════════════════════════════════════════════════
#  reverse_geocode_punch_task — called directly, not via .delay()/apply_async()
# ══════════════════════════════════════════════════════════════════════════════

class ReverseGeocodePunchTaskTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('employee_geocode_task_test')
        self.employee = make_user(
            'geocodetask@test.com', role=role, password='TestPass123!', employee_id='EMPGT001',
        )
        self.punch = AttendancePunch.objects.create(
            employee=self.employee, punch_type=AttendancePunch.PUNCH_IN,
            punched_at=timezone.now(), latitude=OFFICE_LAT, longitude=OFFICE_LON,
        )

    # 1. Successful geocoding stores location_label.
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_successful_geocode_stores_location_label(self, mock_geocode):
        mock_geocode.return_value = 'Hyderabad, Telangana, India'
        reverse_geocode_punch_task(connection.schema_name, str(self.punch.id))
        self.punch.refresh_from_db()
        self.assertEqual(self.punch.location_label, 'Hyderabad, Telangana, India')

    # 2. Geocoding failure does not fail the punch.
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_geocode_failure_does_not_fail_punch(self, mock_geocode):
        mock_geocode.return_value = None  # reverse_geocode()'s own contract for any failure
        reverse_geocode_punch_task(connection.schema_name, str(self.punch.id))
        self.punch.refresh_from_db()
        self.assertEqual(self.punch.location_label, '')
        # The punch itself is completely untouched otherwise.
        self.assertEqual(self.punch.punch_type, AttendancePunch.PUNCH_IN)

    # 3. Geocoding timeout does not fail the punch (task-level: an unexpected
    # exception escaping reverse_geocode entirely must still not propagate).
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_geocode_timeout_does_not_raise_from_task(self, mock_geocode):
        mock_geocode.side_effect = requests.exceptions.Timeout('simulated timeout')
        try:
            reverse_geocode_punch_task(connection.schema_name, str(self.punch.id))
        except Exception as exc:  # noqa: BLE001 — explicitly asserting this never happens
            self.fail(f'reverse_geocode_punch_task raised: {exc}')
        self.punch.refresh_from_db()
        self.assertEqual(self.punch.location_label, '')

    def test_task_is_a_no_op_for_a_punch_with_no_coordinates(self):
        bare_punch = AttendancePunch.objects.create(
            employee=self.employee, punch_type=AttendancePunch.PUNCH_OUT, punched_at=timezone.now(),
        )
        reverse_geocode_punch_task(connection.schema_name, str(bare_punch.id))
        bare_punch.refresh_from_db()
        self.assertEqual(bare_punch.location_label, '')

    def test_task_is_a_no_op_for_a_missing_punch_id(self):
        import uuid
        try:
            reverse_geocode_punch_task(connection.schema_name, str(uuid.uuid4()))
        except Exception as exc:  # noqa: BLE001
            self.fail(f'reverse_geocode_punch_task raised for a missing punch: {exc}')


# ══════════════════════════════════════════════════════════════════════════════
#  End-to-end: real punch -> transaction.on_commit -> task -> location_label
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PunchGeocodingIntegrationTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        role = make_role('employee_geocode_integration_test')
        self.employee = make_user(
            'geocodeintegration@test.com', role=role, password='TestPass123!', employee_id='EMPGI001',
        )

    # 4 & 5. Clock In and Clock Out locations are stored/resolved separately.
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_clock_in_and_out_locations_resolved_independently(self, mock_geocode):
        mock_geocode.side_effect = ['Hyderabad, Telangana, India', 'Suryapet, Telangana, India']
        client = APIClient()
        _login(client, 'geocodeintegration@test.com')

        _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        _punch(client, 'OUT', FAR_LAT, FAR_LON)

        in_punch = AttendancePunch.objects.get(employee=self.employee, punch_type='IN')
        out_punch = AttendancePunch.objects.get(employee=self.employee, punch_type='OUT')
        self.assertEqual(in_punch.location_label, 'Hyderabad, Telangana, India')
        self.assertEqual(out_punch.location_label, 'Suryapet, Telangana, India')

    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_geocoding_failure_does_not_affect_punch_success_end_to_end(self, mock_geocode):
        mock_geocode.return_value = None
        client = APIClient()
        _login(client, 'geocodeintegration@test.com')
        resp = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee, punch_type='IN')
        self.assertEqual(punch.location_label, '')


# ══════════════════════════════════════════════════════════════════════════════
#  HR attendance detail API — location_label fields + permissions
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceDetailLocationLabelAPITests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        Branch.objects.create(
            branch_code='GEOLBL01', branch_name='Geocode Label Test Office', address='Test Address',
            state=state, city=city,
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        hr_role = make_role('hr_geocode_label_test', permission_codenames=['attendance.view'])
        self.hr = make_user(
            'hr.geocodelabel@test.com', role=hr_role, password='TestPass123!', employee_id='EMPHRGL001',
        )
        emp_role = make_role('employee_geocode_label_test')
        self.employee = make_user(
            'geocodelabel@test.com', role=emp_role, password='TestPass123!',
            employee_id='EMPGL001', branch='Geocode Label Test Office',
        )

        from apps.attendance.services_attendance import AttendanceProcessorService

        self.in_punch = AttendancePunch.objects.create(
            employee=self.employee, punch_type=AttendancePunch.PUNCH_IN,
            punched_at=timezone.now(), latitude=OFFICE_LAT, longitude=OFFICE_LON,
            location_label='Hyderabad, Telangana, India',
        )
        self.out_punch = AttendancePunch.objects.create(
            employee=self.employee, punch_type=AttendancePunch.PUNCH_OUT,
            punched_at=timezone.now(), latitude=FAR_LAT, longitude=FAR_LON,
            location_label='',  # not yet resolved
        )
        self.record = AttendanceProcessorService.process_day(self.employee, timezone.localdate())

    def _detail_url(self):
        return f"{reverse('hr-attendance-detail', kwargs={'pk': self.record.id})}?date={self.record.date.isoformat()}"

    # 6. Attendance Detail API returns location_label (resolved and unresolved).
    def test_detail_api_returns_resolved_and_unresolved_location_labels(self):
        client = APIClient()
        _login(client, 'hr.geocodelabel@test.com')
        resp = client.get(self._detail_url())
        self.assertEqual(resp.status_code, 200, resp.data)
        detail = resp.data['data']
        self.assertEqual(detail['clock_in_location_label'], 'Hyderabad, Telangana, India')
        self.assertIsNone(detail['clock_out_location_label'])  # empty string -> None, not fabricated
        # Coordinates are still present alongside the label — never replaced.
        self.assertAlmostEqual(detail['clock_in_latitude'], OFFICE_LAT, places=5)

    # 7. Unauthorized users cannot access location data.
    def test_unauthorized_user_cannot_access_location_label(self):
        no_perm_role = make_role('no_perm_geocode_label_test')
        make_user('noperm.geocodelabel@test.com', role=no_perm_role, password='TestPass123!')
        client = APIClient()
        _login(client, 'noperm.geocodelabel@test.com')
        resp = client.get(self._detail_url())
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('clock_in_location_label', resp.data)


# ══════════════════════════════════════════════════════════════════════════════
#  Regression: UK Shift / SGT-ICT / default geofence + daily limit unchanged
# ══════════════════════════════════════════════════════════════════════════════

class GeocodingDoesNotAffectExistingShiftBehaviorTests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        Branch.objects.create(
            branch_code='GEOLBL02', branch_name='Geocode Regression Office', address='Test Address',
            state=state, city=city,
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        self.uk_policy = WorkingHoursPolicy.objects.get(policy_code='WH-UK')
        self.sgt_policy = WorkingHoursPolicy.objects.get(policy_code='WH-SGT-ICT')

        role = make_role('employee_geocode_regression_test')
        self.uk_emp = make_user(
            'ukgeoreg@test.com', role=role, password='TestPass123!',
            employee_id='EMPGR001', branch='Geocode Regression Office',
        )
        self.sgt_emp = make_user(
            'sgtgeoreg@test.com', role=role, password='TestPass123!',
            employee_id='EMPGR002', branch='Geocode Regression Office',
        )
        self.default_emp = make_user(
            'defaultgeoreg@test.com', role=role, password='TestPass123!',
            employee_id='EMPGR003', branch='Geocode Regression Office',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.sgt_emp, policy=self.sgt_policy, effective_from=timezone.localdate(),
        )

    # 8. UK Shift still bypasses geofence.
    def test_uk_shift_still_bypasses_geofence(self):
        client = APIClient()
        _login(client, 'ukgeoreg@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)

    # 9. GPS is still required for UK Shift.
    def test_uk_shift_still_requires_gps(self):
        client = APIClient()
        _login(client, 'ukgeoreg@test.com')
        resp = _punch(client, 'IN')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('location is required', resp.data['message'].lower())

    # 10. SGT/ICT behavior remains unchanged.
    def test_sgt_ict_geofence_unchanged(self):
        client = APIClient()
        _login(client, 'sgtgeoreg@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 403, resp.data)

    # 11. Global 09:00-18:00 fallback behavior remains unchanged.
    def test_default_shift_geofence_unchanged(self):
        client = APIClient()
        _login(client, 'defaultgeoreg@test.com')
        inside = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(inside.status_code, 200, inside.data)
        outside = _punch(client, 'OUT', FAR_LAT, FAR_LON)
        self.assertEqual(outside.status_code, 403, outside.data)

    # 12. Daily 1-IN + 1-OUT restriction remains unchanged.
    def test_daily_punch_limit_unchanged(self):
        client = APIClient()
        _login(client, 'ukgeoreg@test.com')
        _punch(client, 'IN', FAR_LAT, FAR_LON)
        second_in = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(second_in.status_code, 400, second_in.data)
        self.assertIn('already clocked in', second_in.data['message'].lower())
