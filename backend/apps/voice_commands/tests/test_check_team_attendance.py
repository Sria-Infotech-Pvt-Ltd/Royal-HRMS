from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_CHECK_TEAM_ATTENDANCE, execute_intent
from apps.voice_commands.matcher import get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_attendance_view: bool):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_attendance_view
    user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions))

    request = MagicMock()
    request.META = {}
    request.user = user
    return request


def _stat_cards(**overrides):
    stats = {
        'present_today': 0, 'absent': 0, 'late_arrivals': 0,
        'on_leave': 0, 'total_employees': 0,
    }
    stats.update(overrides)
    return stats


class CheckTeamAttendanceRegistryTests(SimpleTestCase):
    def test_requires_attendance_view_permission(self):
        self.assertEqual(get_required_permission(INTENT_CHECK_TEAM_ATTENDANCE), 'attendance.view')


class CheckTeamAttendancePermissionDeniedTests(SimpleTestCase):
    """
    Unlike check_team_leave_queue's underlying view, HRAttendanceDashboardView
    already rejects outright (403) without attendance.view — but voice's own
    gate must still reject BEFORE reaching the view at all, for the same
    reason as the leave queue: a caller without permission should get a
    clear rejection, not depend on the downstream view's own check.
    """

    @patch('apps.voice_commands.executor.HRAttendanceDashboardView')
    def test_user_without_attendance_view_is_rejected_before_reaching_the_view(self, mock_view_cls):
        request = _fake_request(has_attendance_view=False)

        result = execute_intent(INTENT_CHECK_TEAM_ATTENDANCE, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()


class CheckTeamAttendanceExecutorTests(SimpleTestCase):
    """
    Once past the permission gate (attendance.view present), the executor
    calls HRAttendanceDashboardView.get() directly — these tests mock that
    view call and check only the executor's own message-construction logic.
    """

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.HRAttendanceDashboardView')
    def test_summarizes_stat_cards_in_one_sentence(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'success': True, 'message': 'Dashboard stats loaded.', 'data': {
                'stat_cards': _stat_cards(present_today=42, absent=3, late_arrivals=2, on_leave=5, total_employees=50),
                'summary_chips': {}, 'tab_badges': {},
            }},
        )
        request = _fake_request(has_attendance_view=True)

        result = execute_intent(INTENT_CHECK_TEAM_ATTENDANCE, request)

        self.assertTrue(result.success)
        self.assertIn('42', result.message)
        self.assertIn('50', result.message)
        self.assertIn('3', result.message)
        self.assertIn('5', result.message)
        self.assertIn('2', result.message)

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.HRAttendanceDashboardView')
    def test_authenticates_the_synthetic_request_as_the_calling_user(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200, data={'data': {'stat_cards': _stat_cards()}},
        )
        request = _fake_request(has_attendance_view=True)

        execute_intent(INTENT_CHECK_TEAM_ATTENDANCE, request)

        mock_force_authenticate.assert_called_once()
        self.assertEqual(mock_force_authenticate.call_args.kwargs['user'], request.user)

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.HRAttendanceDashboardView')
    def test_view_error_surfaces_its_message(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=403, data={'success': False, 'message': 'Permission denied.'},
        )
        request = _fake_request(has_attendance_view=True)

        result = execute_intent(INTENT_CHECK_TEAM_ATTENDANCE, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Permission denied.')

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.HRAttendanceDashboardView')
    def test_failure_without_a_message_falls_back_to_generic_message(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=500, data={})
        request = _fake_request(has_attendance_view=True)

        result = execute_intent(INTENT_CHECK_TEAM_ATTENDANCE, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Could not retrieve the team attendance dashboard.')
