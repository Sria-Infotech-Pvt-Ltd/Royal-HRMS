"""Critical-path tests for punch recording and geofence validation.

This app had zero test coverage before the 2026-07-22 engineering audit.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendancePunch
from apps.branch.models import Branch, City, State


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class PolicyCrudRegressionTests(TestCase):
    """Regression tests for late_mark_lop.py and absence_alert.py.

    Both views were completely broken: they checked Django's native
    user.has_perm() against a permission backend this app never populates
    (instead of the custom Role/RolePermission system used everywhere else),
    called paginate()/paginated_data() with reversed arguments, and passed
    error()/success() a `status=` kwarg that doesn't exist on those functions
    (the real parameter is `http_status`). Every endpoint in both files would
    have 403'd every real user, and crashed with a TypeError even for a
    superuser. These tests exercise the full CRUD cycle end-to-end.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('hr', permission_codenames=[
            'attendance.view', 'attendance.create', 'attendance.edit', 'attendance.delete',
        ])
        self.user = make_user('hrpolicy@test.com', role=role, password='TestPass123!')
        _login(self.client, 'hrpolicy@test.com')

    def test_late_mark_lop_policy_full_crud_cycle(self):
        create_resp = self.client.post(
            reverse('late-mark-lop-list'),
            {'name': 'Standard LOP Policy', 'late_marks_per_lop': 3, 'lop_deduction_unit': 'full_day'},
            format='json',
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        policy_id = create_resp.data['data']['id']
        self.assertTrue(create_resp.data['data']['policy_code'].startswith('LM-'))

        list_resp = self.client.get(reverse('late-mark-lop-list'))
        self.assertEqual(list_resp.status_code, 200, list_resp.data)

        detail_resp = self.client.get(reverse('late-mark-lop-detail', kwargs={'pk': policy_id}))
        self.assertEqual(detail_resp.status_code, 200, detail_resp.data)

        update_resp = self.client.patch(
            reverse('late-mark-lop-detail', kwargs={'pk': policy_id}),
            {'late_marks_per_lop': 5},
            format='json',
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.data)
        self.assertEqual(update_resp.data['data']['late_marks_per_lop'], 5)

        delete_resp = self.client.delete(reverse('late-mark-lop-detail', kwargs={'pk': policy_id}))
        self.assertEqual(delete_resp.status_code, 200, delete_resp.data)

    def test_late_mark_lop_policy_requires_real_permission(self):
        no_perm_role = make_role('employee_no_perms')
        make_user('nopolicy@test.com', role=no_perm_role, password='TestPass123!')
        client = APIClient()
        _login(client, 'nopolicy@test.com')
        resp = client.get(reverse('late-mark-lop-list'))
        self.assertEqual(resp.status_code, 403)

    def test_absence_alert_policy_full_crud_cycle(self):
        create_resp = self.client.post(
            reverse('absence-alert-list'),
            {
                'name': 'Standard Absence Alert', 'absent_days_threshold': 3,
                'notification_recipients': 'manager_and_hr',
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        policy_id = create_resp.data['data']['id']
        self.assertTrue(create_resp.data['data']['policy_code'].startswith('AA-'))

        list_resp = self.client.get(reverse('absence-alert-list'))
        self.assertEqual(list_resp.status_code, 200, list_resp.data)

        delete_resp = self.client.delete(reverse('absence-alert-detail', kwargs={'pk': policy_id}))
        self.assertEqual(delete_resp.status_code, 200, delete_resp.data)


# Hyderabad coordinates, used as the "office" location for geofence tests.
OFFICE_LAT = 17.385044
OFFICE_LON = 78.486671
# ~15 km away — well outside any reasonable office geofence.
FAR_LAT = 17.529730
FAR_LON = 78.618416


class PunchServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('employee')
        self.employee = make_user('puncher@test.com', role=role, password='TestPass123!')
        _login(self.client, 'puncher@test.com')

    def _punch(self, **overrides):
        # 'office', not 'wfh' — most of this class tests double-clock-in/out
        # logic that's mode-agnostic, and this employee has no real Branch
        # row resolvable from their branch string, so 'office' mode no-ops
        # (unassigned → allowed) rather than requiring an approved
        # WorkFromHomeRequest.
        payload = {'punch_type': 'IN', 'attendance_mode': 'office'}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def test_wfh_clock_in_without_approved_request_is_rejected(self):
        # Replaces an older test asserting the opposite (WFH succeeded
        # unconditionally, even with no GPS) — see services_geofencing.
        # _validate_wfh's own docstring: that unconditional-success behavior
        # was the exact gap a later WFH-approval feature deliberately closed.
        resp = self._punch(punch_type='IN', attendance_mode='wfh')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('approved work-from-home request', resp.data['message'].lower())
        self.assertFalse(
            AttendancePunch.objects.filter(
                employee=self.employee, punch_type=AttendancePunch.PUNCH_IN,
            ).exists()
        )

    def test_double_clock_in_is_rejected(self):
        self._punch(punch_type='IN')
        resp = self._punch(punch_type='IN')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already clocked in', resp.data['message'].lower())

    def test_clock_out_without_clock_in_is_rejected(self):
        resp = self._punch(punch_type='OUT')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not currently clocked in', resp.data['message'].lower())

    def test_clock_in_then_out_succeeds(self):
        in_resp = self._punch(punch_type='IN')
        self.assertEqual(in_resp.status_code, 200, in_resp.data)
        out_resp = self._punch(punch_type='OUT')
        self.assertEqual(out_resp.status_code, 200, out_resp.data)


class GeofencingPunchTests(TestCase):
    """Office-mode punches must be validated against the employee's branch
    geofence when one is configured.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # 'TG' is already seeded by a branch migration — reuse it rather than
        # colliding with the unique `code` constraint.
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='HYD01', branch_name='Head Office', address='Test Address',
            state=state, city=city,
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        role = make_role('employee')
        self.employee = make_user(
            'office@test.com', role=role, password='TestPass123!',
            branch='Head Office',
        )
        _login(self.client, 'office@test.com')

    def _punch(self, lat, lon):
        return self.client.post(
            reverse('attendance-punch'),
            {
                'punch_type': 'IN',
                'attendance_mode': 'office',
                'latitude': lat,
                'longitude': lon,
            },
            format='json',
        )

    def test_punch_inside_geofence_is_allowed(self):
        resp = self._punch(OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_punch_outside_geofence_is_rejected(self):
        resp = self._punch(FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('outside your assigned office location', resp.data['message'])

    def test_office_punch_without_gps_is_rejected(self):
        resp = self.client.post(
            reverse('attendance-punch'),
            {'punch_type': 'IN', 'attendance_mode': 'office'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn('location is required', resp.data['message'].lower())


class AttendanceGeofenceCheckViewTests(TestCase):
    """
    /attendance/geofence-check/ — the web ClockWidget/ClockInButton call this
    BEFORE opening the face verification modal (see useClockWidget.
    prepareLocation), so the geofence rejection has to arrive independent of
    ever submitting a punch. Reuses the exact same GeofencingService.validate
    GeofencingPunchTests already exercises through the punch endpoint — this
    just confirms the read-only pre-check wraps it correctly and writes
    nothing.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='HYD02', branch_name='Geofence Check Office', address='Test Address',
            state=state, city=city,
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        role = make_role('employee')
        self.employee = make_user(
            'geocheck@test.com', role=role, password='TestPass123!',
            branch='Geofence Check Office',
        )
        _login(self.client, 'geocheck@test.com')

    def _check(self, lat=None, lon=None):
        payload = {'attendance_mode': 'office'}
        if lat is not None:
            payload['latitude'] = lat
        if lon is not None:
            payload['longitude'] = lon
        return self.client.post(reverse('attendance-geofence-check'), payload, format='json')

    def test_inside_geofence_is_allowed_and_writes_no_punch(self):
        resp = self._check(OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['is_allowed'])
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_outside_geofence_is_rejected_before_any_punch_exists(self):
        resp = self._check(FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('outside your assigned office location', resp.data['message'])
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_missing_gps_is_rejected_the_same_as_the_punch_endpoint(self):
        resp = self._check()
        self.assertEqual(resp.status_code, 403)
        self.assertIn('location is required', resp.data['message'].lower())

    def test_wfh_mode_without_approved_request_is_rejected(self):
        # Replaces an older test asserting WFH mode never needed GPS at
        # all — see PunchServiceTests.test_wfh_clock_in_without_approved_
        # request_is_rejected for the same fix and the reasoning behind it.
        resp = self.client.post(
            reverse('attendance-geofence-check'),
            {'attendance_mode': 'wfh'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('approved work-from-home request', resp.data['message'].lower())
