from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.attendance.models import AttendancePunch
from apps.voice_commands.executor import INTENT_CLOCK_IN, INTENT_CLOCK_OUT, execute_intent


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


class GeolocationForwardingTests(SimpleTestCase):
    """
    Confirms execute_intent() forwards latitude/longitude straight into the
    same 'latitude'/'longitude' keys PunchService.record_punch() reads
    (services_attendance.py:130-131 -> GeofencingService.validate) — the
    plumbing VoiceCommandButton's silent geolocation retry depends on to
    actually get a clock_in/clock_out past a geofencing rejection. No new
    validation happens anywhere in this path; PunchWriteSerializer and
    GeofencingService are the same real checks the manual ClockWidget punch
    already goes through (see executor_attendance._execute_punch).
    """

    @patch('apps.voice_commands.executor_attendance.PunchService.record_punch')
    def test_clock_in_forwards_latitude_and_longitude_when_present(self, mock_record_punch):
        execute_intent(
            INTENT_CLOCK_IN, _fake_request(), attendance_mode=AttendancePunch.MODE_OFFICE,
            latitude=17.385044, longitude=78.486671,
        )

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['latitude'], 17.385044)
        self.assertEqual(punch_data['longitude'], 78.486671)

    @patch('apps.voice_commands.executor_attendance.PunchService.record_punch')
    def test_clock_out_forwards_latitude_and_longitude_when_present(self, mock_record_punch):
        execute_intent(
            INTENT_CLOCK_OUT, _fake_request(), attendance_mode=AttendancePunch.MODE_OFFICE,
            latitude=12.9716, longitude=77.5946,
        )

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['latitude'], 12.9716)
        self.assertEqual(punch_data['longitude'], 77.5946)

    @patch('apps.voice_commands.executor_attendance.PunchService.record_punch')
    def test_clock_in_with_no_coordinates_forwards_none(self, mock_record_punch):
        # The original (pre-retry) attempt — no coordinates yet, exactly like
        # every voice clock_in before this feature existed.
        execute_intent(INTENT_CLOCK_IN, _fake_request(), attendance_mode=AttendancePunch.MODE_OFFICE)

        _, punch_data = mock_record_punch.call_args.args
        self.assertIsNone(punch_data['latitude'])
        self.assertIsNone(punch_data['longitude'])

    @patch('apps.voice_commands.executor_attendance.PunchService.record_punch')
    def test_non_office_mode_forwards_coordinates_harmlessly(self, mock_record_punch):
        # GeofencingService's non-office validators never look at
        # employee_lat/employee_lon (services_geofencing._validate_no_geofence)
        # — but if the frontend happens to have coordinates on hand while in
        # wfh/field/etc. mode, there's no reason to strip them; they're just
        # carried into the audit trail, same as the manual ClockWidget already
        # does regardless of mode.
        execute_intent(
            INTENT_CLOCK_IN, _fake_request(), attendance_mode=AttendancePunch.MODE_WFH,
            latitude=17.385044, longitude=78.486671,
        )

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['latitude'], 17.385044)
        self.assertEqual(punch_data['longitude'], 78.486671)
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_WFH)
