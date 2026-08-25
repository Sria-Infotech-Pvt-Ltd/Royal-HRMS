from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.attendance.models import AttendancePunch
from apps.attendance.services_geofencing import GeofencingService


def _geofenced_branch():
    return SimpleNamespace(
        has_coordinates=True,
        geofencing_enabled=True,
        latitude=17.385044,
        longitude=78.486671,
        allowed_radius_meters=150,
    )


def _fake_employee():
    return SimpleNamespace(pk='voice-tester', branch='HQ')


def _approved_wfh_request():
    return SimpleNamespace(
        latitude=17.385044,
        longitude=78.486671,
        location_label='Test WFH Location',
    )


class AttendanceModeGeofenceTests(SimpleTestCase):
    """
    Confirms _MODE_VALIDATORS routes the mode string voice_commands detects to
    the right validator: office requires GPS and rejects without it; wfh
    requires an approved WorkFromHomeRequest for today AND matching GPS
    (see services_geofencing.py's _validate_wfh); field/client_location/
    remote_office all succeed without GPS — the same behavior the existing
    web punch flow relies on.

    Branch/WorkFromHomeRequest resolution is mocked (SimpleNamespace, no DB)
    rather than using real Branch/User/WorkFromHomeRequest rows, since
    backend/.env points DATABASE_URL at a live shared Neon Postgres instance
    and this suite must not trigger a test database creation against it —
    _fake_employee()'s non-UUID pk would otherwise fail UUID validation the
    moment any of these validators queried the database directly.
    """

    @patch('apps.attendance.services_geofencing._resolve_all_allowed_branches')
    def test_office_mode_rejected_without_gps(self, mock_resolve):
        mock_resolve.return_value = [_geofenced_branch()]

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_OFFICE,
        )

        self.assertFalse(result.is_allowed)

    @patch('apps.hrms.models.WorkFromHomeRequest.approved_for')
    def test_wfh_mode_without_approved_request_is_rejected(self, mock_approved_for):
        mock_approved_for.return_value = None

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_WFH,
        )

        self.assertFalse(result.is_allowed)

    @patch('apps.hrms.models.WorkFromHomeRequest.approved_for')
    def test_wfh_mode_with_approved_request_requires_gps(self, mock_approved_for):
        mock_approved_for.return_value = _approved_wfh_request()

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_WFH,
        )

        self.assertFalse(result.is_allowed)

    @patch('apps.hrms.models.WorkFromHomeRequest.approved_for')
    def test_wfh_mode_with_approved_request_and_matching_gps_is_allowed(self, mock_approved_for):
        mock_approved_for.return_value = _approved_wfh_request()

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_WFH,
            employee_lat=17.385044, employee_lon=78.486671,
        )

        self.assertTrue(result.is_allowed)

    @patch('apps.attendance.services_geofencing._resolve_employee_branch')
    def test_field_mode_allowed_without_gps(self, mock_resolve):
        mock_resolve.return_value = _geofenced_branch()

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_FIELD,
        )

        self.assertTrue(result.is_allowed)

    @patch('apps.attendance.services_geofencing._resolve_employee_branch')
    def test_client_location_mode_allowed_without_gps(self, mock_resolve):
        mock_resolve.return_value = _geofenced_branch()

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_CLIENT_LOCATION,
        )

        self.assertTrue(result.is_allowed)

    @patch('apps.attendance.services_geofencing._resolve_employee_branch')
    def test_remote_office_mode_allowed_without_gps(self, mock_resolve):
        mock_resolve.return_value = _geofenced_branch()

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_REMOTE_OFFICE,
        )

        self.assertTrue(result.is_allowed)
