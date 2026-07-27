from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.hrms.models import REQ_L2_PENDING, REQ_PENDING
from apps.voice_commands.executor import (
    INTENT_CANCEL_LEAVE,
    INTENT_CHECK_LEAVE_STATUS,
    execute_intent,
)


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


def _fake_serialized_request(**overrides):
    base = {
        'id': 'req-1',
        'leave_type': 'earned',
        'leave_type_display': 'Earned Leave',
        'start_date': '2026-08-10',
        'end_date': '2026-08-12',
        'status': REQ_PENDING,
    }
    base.update(overrides)
    return base


# ── check_leave_status ────────────────────────────────────────────────────────
# LeaveRequest.objects and LeaveRequestSerializer are both mocked — this
# isolates the executor's own logic (query shape, message construction) from
# real serialization and the live Neon Postgres DATABASE_URL in backend/.env.

class CheckLeaveStatusTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_leave.LeaveRequestSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_no_requests_returns_friendly_message(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value.__getitem__.return_value = []
        mock_serializer_cls.return_value.data = []

        result = execute_intent(INTENT_CHECK_LEAVE_STATUS, _fake_request())

        self.assertTrue(result.success)
        self.assertEqual(result.message, 'You have no leave requests on record.')

    @patch('apps.voice_commands.executor_leave.LeaveRequestSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_summarizes_single_most_recent_request(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value.__getitem__.return_value = [MagicMock()]
        mock_serializer_cls.return_value.data = [_fake_serialized_request()]

        result = execute_intent(INTENT_CHECK_LEAVE_STATUS, _fake_request())

        self.assertTrue(result.success)
        self.assertIn('Earned Leave', result.message)
        self.assertIn('2026-08-10', result.message)
        self.assertIn('2026-08-12', result.message)
        self.assertIn('pending manager approval', result.message)
        self.assertNotIn('more recent request', result.message)

    @patch('apps.voice_commands.executor_leave.LeaveRequestSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_mentions_additional_requests_when_more_than_one(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value.__getitem__.return_value = [MagicMock(), MagicMock()]
        mock_serializer_cls.return_value.data = [
            _fake_serialized_request(status=REQ_L2_PENDING),
            _fake_serialized_request(id='req-0'),
        ]

        result = execute_intent(INTENT_CHECK_LEAVE_STATUS, _fake_request())

        self.assertTrue(result.success)
        self.assertIn('pending HR approval', result.message)
        self.assertIn('1 more recent request', result.message)

    @patch('apps.voice_commands.executor_leave.LeaveRequestSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_queries_only_own_requests_most_recent_first(self, mock_objects, mock_serializer_cls):
        mock_objects.filter.return_value.order_by.return_value.__getitem__.return_value = []
        mock_serializer_cls.return_value.data = []
        request = _fake_request()

        execute_intent(INTENT_CHECK_LEAVE_STATUS, request)

        mock_objects.filter.assert_called_once_with(employee=request.user)
        mock_objects.filter.return_value.order_by.assert_called_once_with('-created_at')


# ── cancel_leave ───────────────────────────────────────────────────────────────

def _fake_pending_request(leave_type_display='Earned Leave', start_date='2026-08-10', end_date='2026-08-12'):
    obj = MagicMock()
    obj.get_leave_type_display.return_value = leave_type_display
    obj.start_date = start_date
    obj.end_date = end_date
    return obj


class CancelLeaveTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_no_cancellable_requests_returns_rejection(self, mock_objects):
        mock_objects.filter.return_value.order_by.return_value = []

        result = execute_intent(INTENT_CANCEL_LEAVE, _fake_request())

        self.assertFalse(result.success)
        self.assertIn("don't have any pending", result.message)

    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_more_than_one_cancellable_request_asks_to_be_specific(self, mock_objects):
        mock_objects.filter.return_value.order_by.return_value = [
            _fake_pending_request(), _fake_pending_request(),
        ]

        result = execute_intent(INTENT_CANCEL_LEAVE, _fake_request())

        self.assertFalse(result.success)
        self.assertIn('more than one pending', result.message)
        self.assertIn('dashboard', result.message)

    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_exactly_one_cancellable_request_gets_cancelled(self, mock_objects):
        pending = _fake_pending_request()
        mock_objects.filter.return_value.order_by.return_value = [pending]

        result = execute_intent(INTENT_CANCEL_LEAVE, _fake_request())

        self.assertTrue(result.success)
        self.assertIn('Earned Leave', result.message)
        self.assertIn('2026-08-10', result.message)
        self.assertIn('2026-08-12', result.message)
        self.assertIn('cancelled', result.message)
        pending.save.assert_called_once_with(update_fields=['status', 'updated_at'])

    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_cancellation_sets_status_to_cancelled(self, mock_objects):
        from apps.hrms.models import REQ_CANCELLED

        pending = _fake_pending_request()
        mock_objects.filter.return_value.order_by.return_value = [pending]

        execute_intent(INTENT_CANCEL_LEAVE, _fake_request())

        self.assertEqual(pending.status, REQ_CANCELLED)

    @patch('apps.voice_commands.executor_leave.LeaveRequest.objects')
    def test_only_queries_pending_and_l2_pending_statuses_for_own_requests(self, mock_objects):
        mock_objects.filter.return_value.order_by.return_value = []
        request = _fake_request()

        execute_intent(INTENT_CANCEL_LEAVE, request)

        mock_objects.filter.assert_called_once_with(
            employee=request.user,
            status__in=(REQ_PENDING, REQ_L2_PENDING),
        )
