from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_CHECK_TEAM_LEAVE_QUEUE, execute_intent
from apps.voice_commands.matcher import get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_leave_approve: bool):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_leave_approve
    user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions))

    request = MagicMock()
    request.META = {}
    request.user = user
    return request


class CheckTeamLeaveQueueRegistryTests(SimpleTestCase):
    def test_requires_leave_approve_permission(self):
        self.assertEqual(get_required_permission(INTENT_CHECK_TEAM_LEAVE_QUEUE), 'leave.approve')


class CheckTeamLeaveQueuePermissionDeniedTests(SimpleTestCase):
    """
    Locks in the deliberate behavior difference from the REST endpoint:
    LeaveRequestListCreateView.get()'s scope=team branch (hrms/views/leave.py
    :556-561) silently falls back to the caller's own requests when
    leave.approve is absent, instead of rejecting. Voice must NOT reproduce
    that fallback — a caller without leave.approve must get an explicit
    permission-denied message, and the underlying view must never even be
    called (proving no fallback-to-own-requests path was reached).
    """

    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_user_without_leave_approve_is_rejected_not_given_own_requests(self, mock_view_cls):
        request = _fake_request(has_leave_approve=False)

        result = execute_intent(INTENT_CHECK_TEAM_LEAVE_QUEUE, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()


class CheckTeamLeaveQueueExecutorTests(SimpleTestCase):
    """
    Once past the permission gate (leave.approve present), the executor
    submits scope=team through LeaveRequestListCreateView.get() directly —
    these tests mock that view call and check only the executor's own
    request-building and message-construction logic.
    """

    def _run(self, mock_view_cls, count):
        mock_response = MagicMock(
            status_code=200,
            data={'success': True, 'message': 'Leave requests retrieved.', 'data': {'count': count, 'results': []}},
        )
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request(has_leave_approve=True)

        return execute_intent(INTENT_CHECK_TEAM_LEAVE_QUEUE, request)

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_zero_pending_requests(self, mock_view_cls, mock_force_authenticate):
        result = self._run(mock_view_cls, count=0)

        self.assertTrue(result.success)
        self.assertEqual(result.message, 'You have no leave requests pending your approval.')

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_singular_message_for_exactly_one(self, mock_view_cls, mock_force_authenticate):
        result = self._run(mock_view_cls, count=1)

        self.assertTrue(result.success)
        self.assertEqual(result.message, 'You have 1 leave request pending your approval.')

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_plural_message_and_count_for_several(self, mock_view_cls, mock_force_authenticate):
        result = self._run(mock_view_cls, count=5)

        self.assertTrue(result.success)
        self.assertEqual(result.message, 'You have 5 leave requests pending your approval.')

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_authenticates_the_synthetic_request_as_the_calling_user(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200, data={'data': {'count': 0, 'results': []}},
        )
        request = _fake_request(has_leave_approve=True)

        execute_intent(INTENT_CHECK_TEAM_LEAVE_QUEUE, request)

        mock_force_authenticate.assert_called_once()
        self.assertEqual(mock_force_authenticate.call_args.kwargs['user'], request.user)

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_requests_scope_team(self, mock_view_cls, mock_force_authenticate):
        captured = {}

        def _capture_view(django_request):
            captured['scope'] = django_request.GET.get('scope')
            return MagicMock(status_code=200, data={'data': {'count': 0, 'results': []}})

        mock_view_cls.as_view.return_value = _capture_view
        request = _fake_request(has_leave_approve=True)

        execute_intent(INTENT_CHECK_TEAM_LEAVE_QUEUE, request)

        self.assertEqual(captured['scope'], 'team')

    @patch('apps.voice_commands.executor.force_authenticate')
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    def test_view_error_surfaces_its_message(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=403, data={'success': False, 'message': 'Permission denied.'},
        )
        request = _fake_request(has_leave_approve=True)

        result = execute_intent(INTENT_CHECK_TEAM_LEAVE_QUEUE, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Permission denied.')
