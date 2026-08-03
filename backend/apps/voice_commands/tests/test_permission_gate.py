from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.attendance.models import AttendancePunch
from apps.voice_commands.executor import (
    INTENT_APPLY_LEAVE,
    INTENT_CANCEL_LEAVE,
    INTENT_CHECK_ATTENDANCE_STATS,
    INTENT_CHECK_ATTENDANCE_SUMMARY,
    INTENT_CHECK_LEAVE_BALANCE,
    INTENT_CHECK_LEAVE_STATUS,
    INTENT_CLOCK_IN,
    INTENT_CLOCK_OUT,
    INTENT_REQUEST_ATTENDANCE_CORRECTION,
    execute_intent,
)
from apps.voice_commands.matcher import get_required_permission

# Not a real intent — nothing in the registry or executor's dispatch table
# maps to this. It exists purely so these tests can prove the permission gate
# itself works, without wiring anything real to a required_permission (none
# of the three real intents need one today — see registry/intents_en.yaml).
_FAKE_INTENT = '__test_only_gated_intent__'
_FAKE_PERMISSION = 'voice_test.fake_permission'
_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."
_NO_MATCH_FALLBACK_MESSAGE = "I didn't understand that command."


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


class ExistingIntentsUnaffectedTests(SimpleTestCase):
    """
    (a) The three real intents must keep working for any authenticated user,
    regardless of role or assigned permissions — confirms required_permission
    is genuinely null for all three in the real registry, and that an
    authenticated user with NO role/permissions at all still reaches real
    dispatch (not blocked by the gate).
    """

    def test_registry_declares_no_required_permission_for_any_real_intent(self):
        self.assertIsNone(get_required_permission(INTENT_CLOCK_IN))
        self.assertIsNone(get_required_permission(INTENT_CLOCK_OUT))
        self.assertIsNone(get_required_permission(INTENT_CHECK_LEAVE_BALANCE))
        self.assertIsNone(get_required_permission(INTENT_CHECK_LEAVE_STATUS))
        self.assertIsNone(get_required_permission(INTENT_CANCEL_LEAVE))
        self.assertIsNone(get_required_permission(INTENT_CHECK_ATTENDANCE_STATS))
        self.assertIsNone(get_required_permission(INTENT_CHECK_ATTENDANCE_SUMMARY))
        self.assertIsNone(get_required_permission(INTENT_REQUEST_ATTENDANCE_CORRECTION))
        self.assertIsNone(get_required_permission(INTENT_APPLY_LEAVE))

    @patch('apps.voice_commands.executor_attendance.PunchService.record_punch')
    def test_clock_in_reaches_dispatch_for_user_with_no_role(self, mock_record_punch):
        request = _fake_request()
        request.user.role = None  # no role, no permissions whatsoever

        result = execute_intent(INTENT_CLOCK_IN, request, attendance_mode=AttendancePunch.MODE_OFFICE)

        mock_record_punch.assert_called_once()
        self.assertTrue(result.success)

    @patch('apps.voice_commands.executor_attendance.PunchService.record_punch')
    def test_clock_out_reaches_dispatch_for_user_with_no_role(self, mock_record_punch):
        request = _fake_request()
        request.user.role = None

        result = execute_intent(INTENT_CLOCK_OUT, request, attendance_mode=AttendancePunch.MODE_OFFICE)

        mock_record_punch.assert_called_once()
        self.assertTrue(result.success)

    @patch('apps.voice_commands.executor_leave.LeaveBalance.objects')
    def test_check_leave_balance_reaches_dispatch_for_user_with_no_role(self, mock_objects):
        mock_objects.filter.return_value.order_by.return_value = []
        request = _fake_request()
        request.user.role = None

        result = execute_intent(INTENT_CHECK_LEAVE_BALANCE, request)

        mock_objects.filter.assert_called_once()
        self.assertTrue(result.success)

    @patch('apps.voice_commands.executor_leave.LeaveRequestSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_check_leave_status_reaches_dispatch_for_user_with_no_role(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value.__getitem__.return_value = []
        mock_serializer_cls.return_value.data = []
        request = _fake_request()
        request.user.role = None

        result = execute_intent(INTENT_CHECK_LEAVE_STATUS, request)

        mock_objects.filter.assert_called_once()
        self.assertTrue(result.success)

    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_cancel_leave_reaches_dispatch_for_user_with_no_role(self, mock_objects):
        mock_objects.filter.return_value.order_by.return_value = []
        request = _fake_request()
        request.user.role = None

        result = execute_intent(INTENT_CANCEL_LEAVE, request)

        # Not blocked by the permission gate — rejected for a business reason
        # (no cancellable requests) instead of "You don't have permission...".
        mock_objects.filter.assert_called_once()
        self.assertNotEqual(result.message, _PERMISSION_DENIED_MESSAGE)

    @patch('apps.voice_commands.executor_attendance.StatsSerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_check_attendance_stats_reaches_dispatch_for_user_with_no_role(self, mock_service, mock_serializer_cls):
        mock_serializer_cls.return_value.data = {
            'days_present': 0, 'late_arrivals': 0, 'lop_pending': 0,
            'avg_hours_per_day': 0.0, 'attendance_percentage': 0, 'working_days': 0,
        }
        request = _fake_request()
        request.user.role = None

        result = execute_intent(INTENT_CHECK_ATTENDANCE_STATS, request)

        mock_service.get_stats.assert_called_once()
        self.assertTrue(result.success)

    @patch('apps.voice_commands.executor_attendance.MonthlySummarySerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_check_attendance_summary_reaches_dispatch_for_user_with_no_role(self, mock_service, mock_serializer_cls):
        mock_serializer_cls.return_value.data = {
            'working_days': 0, 'days_present': 0, 'days_absent': 0,
            'leave_days': 0, 'half_days': 0, 'ot_hours': '0',
        }
        request = _fake_request()
        request.user.role = None

        result = execute_intent(INTENT_CHECK_ATTENDANCE_SUMMARY, request)

        mock_service.get_monthly_summary.assert_called_once()
        self.assertTrue(result.success)

    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_request_attendance_correction_reaches_dispatch_for_user_with_no_role(
        self, mock_force_authenticate, mock_view_cls,
    ):
        from datetime import date, time

        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=201, data={'data': {}})
        request = _fake_request()
        request.user.role = None
        slots = {'date': date(2026, 7, 22), 'punch_type': 'IN', 'correct_in_time': time(9, 0), 'reason': 'forgot_to_punch'}

        result = execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=slots)

        self.assertNotEqual(result.message, _PERMISSION_DENIED_MESSAGE)

    @patch('apps.voice_commands.executor_leave.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor_leave.force_authenticate')
    def test_apply_leave_reaches_dispatch_for_user_with_no_role(self, mock_force_authenticate, mock_view_cls):
        mock_response = MagicMock(status_code=201, data={'success': True, 'message': 'ok', 'data': {}})
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()
        request.user.role = None
        slots = {
            'leave_type': 'sick', 'start_date': '2026-07-22',
            'end_date': '2026-07-24', 'reason': 'feeling unwell today',
        }

        result = execute_intent(INTENT_APPLY_LEAVE, request, slots=slots)

        mock_view_cls.as_view.return_value.assert_called_once()
        self.assertTrue(result.success)


class PermissionGateMechanismTests(SimpleTestCase):
    """
    (b) Proves the gate mechanism itself, using a synthetic intent + codename
    that nothing real is wired to. get_required_permission() and
    has_required_permission() are both mocked, so this exercises only
    execute_intent()'s gating logic — not real registry content or a real
    RolePermission row (that's covered by test_permissions.py separately).
    """

    @patch('apps.voice_commands.executor.has_required_permission')
    @patch('apps.voice_commands.executor.get_required_permission')
    def test_user_without_the_required_permission_is_rejected(self, mock_get_required, mock_has_permission):
        mock_get_required.return_value = _FAKE_PERMISSION
        mock_has_permission.return_value = False

        result = execute_intent(_FAKE_INTENT, _fake_request())

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_has_permission.assert_called_once()

    @patch('apps.voice_commands.executor.has_required_permission')
    @patch('apps.voice_commands.executor.get_required_permission')
    def test_user_with_the_required_permission_passes_the_gate(self, mock_get_required, mock_has_permission):
        mock_get_required.return_value = _FAKE_PERMISSION
        mock_has_permission.return_value = True

        result = execute_intent(_FAKE_INTENT, _fake_request())

        # _FAKE_INTENT isn't a real dispatchable intent, so once past the gate
        # it falls through to the "unknown intent" branch — a DIFFERENT
        # message than the rejection above proves the gate let it through
        # rather than blocking it.
        self.assertNotEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        self.assertEqual(result.message, _NO_MATCH_FALLBACK_MESSAGE)

    @patch('apps.voice_commands.executor.has_required_permission')
    @patch('apps.voice_commands.executor.get_required_permission')
    def test_null_required_permission_skips_the_check_entirely(self, mock_get_required, mock_has_permission):
        mock_get_required.return_value = None

        execute_intent(_FAKE_INTENT, _fake_request())

        mock_has_permission.assert_not_called()
