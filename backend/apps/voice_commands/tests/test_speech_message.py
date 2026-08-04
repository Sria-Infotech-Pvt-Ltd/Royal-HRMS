"""
TTS confidentiality: ExecutionResult.speech_message is the content-redacted
stand-in for `message` that TTS actually speaks — `message` itself (shown in
the panel/toast) always keeps full detail. These tests confirm each sensitive
intent sets speech_message to a generic, figure-free/name-free line while
leaving `message` untouched, and that the payload dict built by
conversation.py/conversation_leave_approval.py/conversation_payroll.py
actually carries it through to the API response.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import (
    INTENT_CANCEL_LEAVE,
    INTENT_CHECK_LEAVE_BALANCE,
    INTENT_CHECK_LEAVE_STATUS,
    INTENT_CHECK_MY_PAYSLIP,
    execute_intent,
)
from apps.voice_commands.executor_approval import execute_identify_leave_approval_target
from apps.voice_commands.executor_payroll import execute_identify_employee_payslip


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


class LeaveSpeechMessageTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_leave.LeaveBalanceSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveBalance.objects')
    def test_check_leave_balance_speech_message_omits_figures(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value = [MagicMock()]
        mock_serializer_cls.return_value.data = [
            {'leave_type_display': 'Sick', 'available_days': 7},
        ]
        request = _fake_request()

        result = execute_intent(INTENT_CHECK_LEAVE_BALANCE, request)

        self.assertIn('7', result.message)  # full detail still in `message`
        self.assertEqual(result.speech_message, 'Your leave balance is ready to view.')
        self.assertNotIn('7', result.speech_message)
        self.assertNotIn('Sick', result.speech_message)

    @patch('apps.voice_commands.executor_leave.LeaveRequestSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_check_leave_status_speech_message_omits_dates(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value.__getitem__.return_value = [MagicMock()]
        mock_serializer_cls.return_value.data = [{
            'leave_type_display': 'Sick', 'start_date': '2026-07-20',
            'end_date': '2026-07-24', 'status': 'approved',
        }]
        request = _fake_request()

        result = execute_intent(INTENT_CHECK_LEAVE_STATUS, request)

        self.assertIn('2026-07-20', result.message)
        self.assertEqual(result.speech_message, 'Your leave status is ready to view.')
        self.assertNotIn('2026-07-20', result.speech_message)

    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_cancel_leave_speech_message_omits_type_and_dates(self, mock_objects):
        leave_request = MagicMock()
        leave_request.get_leave_type_display.return_value = 'Sick'
        leave_request.start_date = '2026-07-20'
        leave_request.end_date = '2026-07-24'
        mock_objects.filter.return_value.order_by.return_value = [leave_request]
        request = _fake_request()

        result = execute_intent(INTENT_CANCEL_LEAVE, request)

        self.assertIn('2026-07-20', result.message)
        self.assertIn('Sick', result.message)
        self.assertEqual(result.speech_message, 'Your leave request has been cancelled.')
        self.assertNotIn('2026-07-20', result.speech_message)
        self.assertNotIn('Sick', result.speech_message)


class PayslipSpeechMessageTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll.EmployeePayslipSerializer')
    @patch('apps.voice_commands.executor_payroll._most_recent_payslip')
    def test_check_my_payslip_speech_message_omits_figures(self, mock_lookup, mock_serializer_cls):
        mock_lookup.return_value = MagicMock()
        mock_serializer_cls.return_value.data = {
            'cycle_end': '2026-07-31', 'gross_earnings': '50000.00',
            'total_deductions': '5000.00', 'net_pay': '45000.00', 'status': 'SENT',
        }
        request = _fake_request()

        result = execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        self.assertIn('45000.00', result.message)
        self.assertEqual(result.speech_message, 'Your payslip is ready — check your screen for the details.')
        self.assertNotIn('45000.00', result.speech_message)

    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll._most_recent_payslip')
    @patch('apps.voice_commands.executor_payroll._find_employees_by_name')
    def test_check_employee_payslip_speech_message_omits_figures_and_name(
        self, mock_find, mock_lookup, mock_force_authenticate, mock_view_cls,
    ):
        mock_find.return_value = [{'user_id': 'u1', 'employee_name': 'Priya Sharma'}]
        mock_lookup.return_value = MagicMock()
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'data': {
                'cycle_end': '2026-07-31', 'gross_earnings': '80000.00',
                'total_deductions': '8000.00', 'net_pay': '72000.00', 'status': 'SENT',
            }},
        )
        request = _fake_request()

        result = execute_identify_employee_payslip(request, 'priya')

        self.assertIn('72000.00', result.message)
        self.assertIn('Priya Sharma', result.message)
        self.assertEqual(result.speech_message, 'The payslip is ready — check your screen for the details.')
        self.assertNotIn('72000.00', result.speech_message)
        self.assertNotIn('Priya', result.speech_message)


class LeaveApprovalSpeechMessageTests(SimpleTestCase):
    """approve_leave/reject_leave's identify-then-confirm step: speech keeps
    the employee name + dates (needed for the caller to confirm by voice
    which request this is) but drops the leave TYPE — the one piece that can
    reveal a health/personal category about a THIRD PARTY."""

    @patch('apps.voice_commands.executor_approval.match_employee_name')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    def test_single_match_speech_message_keeps_name_and_dates_drops_type(
        self, mock_force_authenticate, mock_view_cls, mock_match,
    ):
        row = {
            'id': 'req1', 'employee_name': 'Arjun Rao', 'leave_type_display': 'Maternity',
            'start_date': '2026-08-01', 'end_date': '2026-08-10', 'status': 'pending',
        }
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200, data={'data': {'results': [row]}},
        )
        mock_match.return_value = [{
            'request_id': 'req1', 'employee_name': 'Arjun Rao',
            'leave_type_display': 'Maternity', 'start_date': '2026-08-01', 'end_date': '2026-08-10',
        }]
        request = _fake_request()

        result = execute_identify_leave_approval_target(request, 'approve', 'arjun')

        self.assertIn('Maternity', result.message)
        self.assertIn('Arjun Rao', result.speech_message)
        self.assertIn('2026-08-01', result.speech_message)
        self.assertNotIn('Maternity', result.speech_message)


class SpeechMessagePayloadThreadingTests(SimpleTestCase):
    """Confirms handle_transcript's final payload dict actually surfaces
    speech_message (not just ExecutionResult internally) — the field the
    frontend reads. Sensitive intents get a redacted value; everything else
    gets None (falls back to `message` on the frontend)."""

    @patch('apps.voice_commands.executor_leave.LeaveBalanceSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveBalance.objects')
    def test_check_leave_balance_payload_carries_speech_message(self, mock_objects, mock_serializer_cls):
        from apps.voice_commands.conversation import handle_transcript
        from apps.voice_commands.normalizer import normalize_transcript  # noqa: F401 (documents intent)

        mock_objects.filter.return_value.order_by.return_value = [MagicMock()]
        mock_serializer_cls.return_value.data = [{'leave_type_display': 'Sick', 'available_days': 3}]
        request = _fake_request()
        request.user.id = 42

        with patch('apps.voice_commands.clarification.get_pending', return_value=None):
            payload = handle_transcript(request, 'check my leave balance')

        self.assertEqual(payload['speech_message'], 'Your leave balance is ready to view.')
        self.assertIn('3', payload['message'])

    @patch('apps.voice_commands.executor_attendance.StatsSerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_non_sensitive_intent_payload_has_no_speech_message(self, mock_service, mock_serializer_cls):
        from apps.voice_commands.conversation import handle_transcript

        mock_serializer_cls.return_value.data = {
            'days_present': 10, 'late_arrivals': 0, 'lop_pending': 0,
            'avg_hours_per_day': 8.0, 'attendance_percentage': 90, 'working_days': 11,
        }
        request = _fake_request()
        request.user.id = 42

        with patch('apps.voice_commands.clarification.get_pending', return_value=None):
            payload = handle_transcript(request, 'check my attendance')

        self.assertIsNone(payload['speech_message'])
