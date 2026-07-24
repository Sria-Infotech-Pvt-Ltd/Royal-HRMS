import json
from datetime import date
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_APPLY_LEAVE, execute_intent


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


def _fake_slots():
    return {
        'leave_type': 'sick',
        'start_date': date(2026, 7, 22),
        'end_date': date(2026, 7, 24),
        'reason': 'feeling unwell today',
    }


# _execute_apply_leave submits through LeaveRequestListCreateView directly
# (APIRequestFactory + force_authenticate) rather than duplicating that
# view's balance/overlap/approval-chain business rules — these tests mock
# the view call itself, isolating the executor's own request-building and
# message-construction logic.

class ApplyLeaveExecutorTests(SimpleTestCase):
    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor.force_authenticate')
    def test_successful_submission_returns_success_with_dates_and_type_in_message(
        self, mock_force_authenticate, mock_view_cls,
    ):
        mock_response = MagicMock(
            status_code=201,
            data={'success': True, 'message': 'Leave request submitted.', 'data': {'id': 'req-1'}},
        )
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()

        result = execute_intent(INTENT_APPLY_LEAVE, request, slots=_fake_slots())

        self.assertTrue(result.success)
        self.assertIn('sick', result.message)
        self.assertIn('2026-07-22', result.message)
        self.assertIn('2026-07-24', result.message)
        self.assertEqual(result.data, {'id': 'req-1'})

    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor.force_authenticate')
    def test_authenticates_the_synthetic_request_as_the_calling_user(self, mock_force_authenticate, mock_view_cls):
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=201, data={'data': {}})
        request = _fake_request()

        execute_intent(INTENT_APPLY_LEAVE, request, slots=_fake_slots())

        mock_force_authenticate.assert_called_once()
        self.assertEqual(mock_force_authenticate.call_args.kwargs['user'], request.user)

    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor.force_authenticate')
    def test_business_rule_failure_surfaces_the_views_error_message(self, mock_force_authenticate, mock_view_cls):
        mock_response = MagicMock(
            status_code=422,
            data={'success': False, 'message': 'Insufficient balance. You have 2.0 day(s) available.'},
        )
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()

        result = execute_intent(INTENT_APPLY_LEAVE, request, slots=_fake_slots())

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Insufficient balance. You have 2.0 day(s) available.')

    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor.force_authenticate')
    def test_failure_without_a_message_falls_back_to_generic_message(self, mock_force_authenticate, mock_view_cls):
        mock_response = MagicMock(status_code=500, data={})
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()

        result = execute_intent(INTENT_APPLY_LEAVE, request, slots=_fake_slots())

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Could not submit the leave request.')

    @patch('apps.voice_commands.executor.LeaveRequestListCreateView')
    @patch('apps.voice_commands.executor.force_authenticate')
    def test_payload_sent_to_the_view_contains_only_the_four_collected_slots(
        self, mock_force_authenticate, mock_view_cls,
    ):
        captured = {}

        def _capture_view(django_request):
            captured['body'] = json.loads(django_request.body)
            return MagicMock(status_code=201, data={'data': {}})

        mock_view_cls.as_view.return_value = _capture_view
        request = _fake_request()

        execute_intent(INTENT_APPLY_LEAVE, request, slots=_fake_slots())

        self.assertEqual(captured['body'], {
            'leave_type': 'sick',
            'start_date': '2026-07-22',
            'end_date': '2026-07-24',
            'reason': 'feeling unwell today',
        })
