from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.attendance.models import AttendancePunch
from apps.voice_commands.executor import INTENT_CLOCK_IN, INTENT_CLOCK_OUT, execute_intent


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


class ExecutorModeForwardingTests(SimpleTestCase):
    """
    Confirms execute_intent() forwards the detected attendance_mode into the
    exact 'attendance_mode' key PunchService.record_punch() reads at
    services_attendance.py:114 — for both clock_in and clock_out.
    """

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    def test_clock_in_forwards_detected_mode(self, mock_record_punch):
        execute_intent(INTENT_CLOCK_IN, _fake_request(), attendance_mode=AttendancePunch.MODE_WFH)

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_WFH)

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    def test_clock_out_forwards_detected_mode(self, mock_record_punch):
        execute_intent(INTENT_CLOCK_OUT, _fake_request(), attendance_mode=AttendancePunch.MODE_FIELD)

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_FIELD)

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    def test_clock_in_defaults_to_office_when_no_mode_passed(self, mock_record_punch):
        execute_intent(INTENT_CLOCK_IN, _fake_request())

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_OFFICE)

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    def test_clock_out_forwards_client_location_mode(self, mock_record_punch):
        execute_intent(INTENT_CLOCK_OUT, _fake_request(), attendance_mode=AttendancePunch.MODE_CLIENT_LOCATION)

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_CLIENT_LOCATION)


class ClockOutModeInheritanceTests(SimpleTestCase):
    """
    Regression tests: a plain 'clock out' (no mode phrase) must NOT silently
    default to office — that forces a geofence check against the office on a
    day that was opened as WFH/field/client_location/remote_office, producing
    a rejection meant for a completely different scenario. It must inherit
    the mode from today's still-open IN punch instead, the same way the web
    ClockWidget reuses one mode-dropdown value across both the IN and OUT
    clicks (frontend/.../ClockWidget.tsx:89).

    AttendancePunch.objects is mocked rather than hitting a real queryset —
    backend/.env points DATABASE_URL at a live shared Neon Postgres instance,
    so this suite must not trigger test database creation against it.
    """

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    @patch('apps.voice_commands.executor.AttendancePunch.objects')
    def test_clock_out_with_no_mode_inherits_open_in_punch_mode(self, mock_objects, mock_record_punch):
        open_in_punch = MagicMock(punch_type=AttendancePunch.PUNCH_IN, attendance_mode=AttendancePunch.MODE_WFH)
        mock_objects.filter.return_value.order_by.return_value.first.return_value = open_in_punch

        execute_intent(INTENT_CLOCK_OUT, _fake_request(), attendance_mode=None)

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_WFH)

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    @patch('apps.voice_commands.executor.AttendancePunch.objects')
    def test_clock_out_with_explicit_mode_skips_open_in_punch_lookup(self, mock_objects, mock_record_punch):
        execute_intent(INTENT_CLOCK_OUT, _fake_request(), attendance_mode=AttendancePunch.MODE_FIELD)

        mock_objects.filter.assert_not_called()
        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_FIELD)

    @patch('apps.voice_commands.executor.PunchService.record_punch')
    @patch('apps.voice_commands.executor.AttendancePunch.objects')
    def test_clock_out_with_no_open_in_punch_falls_back_to_office(self, mock_objects, mock_record_punch):
        mock_objects.filter.return_value.order_by.return_value.first.return_value = None

        execute_intent(INTENT_CLOCK_OUT, _fake_request(), attendance_mode=None)

        _, punch_data = mock_record_punch.call_args.args
        self.assertEqual(punch_data['attendance_mode'], AttendancePunch.MODE_OFFICE)
