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


class AttendanceModeGeofenceTests(SimpleTestCase):
    """
    Confirms _MODE_VALIDATORS routes the mode string voice_commands detects to
    the right validator: office still requires GPS and rejects without it,
    while wfh/field/client_location/remote_office all succeed without GPS —
    the same behavior the existing web punch flow relies on.

    Branch resolution is mocked (SimpleNamespace, no DB) rather than using
    real Branch/User rows, since backend/.env points DATABASE_URL at a live
    shared Neon Postgres instance and this suite must not trigger a test
    database creation against it.
    """

    @patch('apps.attendance.services_geofencing._resolve_all_allowed_branches')
    def test_office_mode_rejected_without_gps(self, mock_resolve):
        mock_resolve.return_value = [_geofenced_branch()]

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_OFFICE,
        )

        self.assertFalse(result.is_allowed)

    @patch('apps.attendance.services_geofencing._resolve_employee_branch')
    def test_wfh_mode_allowed_without_gps(self, mock_resolve):
        mock_resolve.return_value = _geofenced_branch()

        result = GeofencingService.validate(
            employee=_fake_employee(), attendance_mode=AttendancePunch.MODE_WFH,
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
