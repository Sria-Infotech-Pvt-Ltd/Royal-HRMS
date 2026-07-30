import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import INTENT_APPROVE_LEAVE, INTENT_REJECT_LEAVE, execute_intent
from apps.voice_commands.matcher import get_conversational, get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_leave_approve: bool = True, user_id: int = 42):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_leave_approve
    request = MagicMock()
    request.META = {}
    request.user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions), id=user_id, pk=user_id)
    return request


def _team_queue_response(rows):
    return MagicMock(
        status_code=200,
        data={'success': True, 'message': 'Leave requests retrieved.', 'data': {'count': len(rows), 'results': rows}},
    )


def _pending_row(request_id, employee_name, leave_type_display='Sick Leave', status='pending'):
    return {
        'id': request_id,
        'employee_name': employee_name,
        'leave_type_display': leave_type_display,
        'start_date': '2026-07-25',
        'end_date': '2026-07-26',
        'status': status,
    }


class _FakePendingStore:
    """Same in-memory stand-in used by test_apply_leave_conversation.py for the Redis-backed clarification cache."""

    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _patch_pending_store(store):
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        # approve_leave/reject_leave's own turn-taking now lives in
        # conversation_leave_approval.py (split out of conversation.py to
        # stay under this project's 300-line file convention), which binds
        # its own set_pending/clear_pending imports — both module bindings
        # need patching so every call in the flow hits the same fake store.
        patch('apps.voice_commands.conversation_leave_approval.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_leave_approval.clear_pending', side_effect=store.clear),
    )


class ApproveRejectLeaveRegistryTests(SimpleTestCase):
    def test_both_intents_require_leave_approve(self):
        self.assertEqual(get_required_permission(INTENT_APPROVE_LEAVE), 'leave.approve')
        self.assertEqual(get_required_permission(INTENT_REJECT_LEAVE), 'leave.approve')

    def test_both_intents_are_conversational(self):
        self.assertTrue(get_conversational(INTENT_APPROVE_LEAVE))
        self.assertTrue(get_conversational(INTENT_REJECT_LEAVE))


class PermissionDeniedTests(SimpleTestCase):
    """
    Mirrors test_check_team_leave_queue.py's permission-denied pattern: a
    caller without leave.approve must never reach the team leave queue at
    all, on either intent — proven by asserting the underlying view was
    never called, not just that the message came back wrong.
    """

    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_approve_leave_denied_without_leave_approve(self, mock_view_cls):
        request = _fake_request(has_leave_approve=False)

        result = execute_intent(INTENT_APPROVE_LEAVE, request, slots={'stage': 'identify', 'name_query': 'sarah'})

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_reject_leave_denied_without_leave_approve(self, mock_view_cls):
        request = _fake_request(has_leave_approve=False)

        result = execute_intent(INTENT_REJECT_LEAVE, request, slots={'stage': 'identify', 'name_query': 'sarah'})

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_conversation_flow_never_reaches_either_view_without_permission(self, mock_list_view, mock_approval_view):
        request = _fake_request(has_leave_approve=False)

        result = handle_transcript(request, 'approve leave for sarah')

        self.assertEqual(result['message'], _PERMISSION_DENIED_MESSAGE)
        self.assertFalse(result['awaiting_input'])
        mock_list_view.as_view.assert_not_called()
        mock_approval_view.as_view.assert_not_called()


class ZeroMatchTests(SimpleTestCase):
    """A name is given, but nothing on the team's pending queue matches it — ends the flow, nothing pending."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_zero_match_ends_the_flow_with_a_clear_message(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        request = _fake_request()

        result = handle_transcript(request, 'approve leave for nobody special')

        self.assertIn('no pending leave request found', result['message'].lower())
        self.assertFalse(result['awaiting_input'])
        self.assertIsNone(self.store.get(42))


class NoNameGivenThenDisambiguationTests(SimpleTestCase):
    """No name in the first utterance -> ask; the answer is then used directly as the name query."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_no_name_asks_who_then_resolves_on_the_next_turn(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        request = _fake_request()

        result = handle_transcript(request, 'approve leave')
        self.assertTrue(result['awaiting_input'])
        self.assertIn('who', result['message'].lower())

        result = handle_transcript(request, 'sarah khan')
        self.assertTrue(result['awaiting_input'])
        self.assertIn('sarah khan', result['message'].lower())
        self.assertIn('yes or no', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['request_id'], 'req-1')


class MultipleMatchDisambiguationTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_ambiguous_name_asks_to_be_more_specific_without_storing_a_request_id(
        self, mock_view_cls, mock_force_authenticate,
    ):
        mock_view_cls.as_view.return_value.return_value = _team_queue_response([
            _pending_row('req-1', 'Sam Cooper'),
            _pending_row('req-2', 'Sam Anderson'),
        ])
        request = _fake_request()

        result = handle_transcript(request, 'approve leave for sam')

        self.assertTrue(result['awaiting_input'])
        self.assertIn('more specific', result['message'].lower())
        pending = self.store.get(42)
        self.assertIsNotNone(pending)
        self.assertNotIn('request_id', pending['slots'])

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_being_more_specific_on_the_next_turn_resolves_to_a_single_match(
        self, mock_view_cls, mock_force_authenticate,
    ):
        mock_view_cls.as_view.return_value.return_value = _team_queue_response([
            _pending_row('req-1', 'Sam Cooper'),
            _pending_row('req-2', 'Sam Anderson'),
        ])
        request = _fake_request()

        handle_transcript(request, 'approve leave for sam')
        result = handle_transcript(request, 'sam cooper')

        self.assertTrue(result['awaiting_input'])
        self.assertEqual(self.store.get(42)['slots']['request_id'], 'req-1')


class SingleMatchThenYesFullFlowTests(SimpleTestCase):
    """The complete happy path: identify a unique match, confirm with 'yes', and the real approval view is called."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_yes_triggers_the_real_approval_call(self, mock_list_view, mock_approval_view, mock_force_authenticate):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan', leave_type_display='Sick Leave')],
        )
        mock_approval_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={
                'success': True, 'message': 'Request approved.',
                'data': {'id': 'req-1', 'status': 'approved', 'employee_name': 'Sarah Khan'},
            },
        )
        request = _fake_request()

        first = handle_transcript(request, 'approve leave for sarah khan')
        self.assertTrue(first['awaiting_input'])

        second = handle_transcript(request, 'yes')

        self.assertFalse(second['awaiting_input'])
        self.assertIn('approved', second['message'].lower())
        self.assertIsNone(self.store.get(42))

        mock_approval_view.as_view.return_value.assert_called_once()
        call_args = mock_approval_view.as_view.return_value.call_args
        self.assertEqual(call_args.kwargs.get('request_id'), 'req-1')
        sent_body = json.loads(call_args.args[0].body)
        self.assertEqual(sent_body['action'], 'approve')

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_reject_leave_sends_action_reject(self, mock_list_view, mock_approval_view, mock_force_authenticate):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-9', 'Sarah Khan')],
        )
        mock_approval_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'success': True, 'message': 'Request rejected.', 'data': {'employee_name': 'Sarah Khan'}},
        )
        request = _fake_request()

        handle_transcript(request, 'reject leave for sarah khan')
        result = handle_transcript(request, 'yes')

        self.assertFalse(result['awaiting_input'])
        self.assertIn('rejected', result['message'].lower())
        call_args = mock_approval_view.as_view.return_value.call_args
        sent_body = json.loads(call_args.args[0].body)
        self.assertEqual(sent_body['action'], 'reject')


class SingleMatchThenNoTests(SimpleTestCase):
    """Declining the confirmation cancels gracefully — the real approval view must never be called."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_no_cancels_without_calling_the_approval_view(self, mock_list_view, mock_force_authenticate, mock_approval_view):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        request = _fake_request()

        handle_transcript(request, 'approve leave for sarah khan')
        result = handle_transcript(request, 'no')

        self.assertFalse(result['awaiting_input'])
        self.assertIn('not', result['message'].lower())
        self.assertIsNone(self.store.get(42))
        mock_approval_view.as_view.assert_not_called()


class AmbiguousConfirmationAnswerTests(SimpleTestCase):
    """An unclear answer to the yes/no question re-asks rather than guessing."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_unclear_answer_reasks_and_keeps_the_pending_request_id(
        self, mock_list_view, mock_force_authenticate, mock_approval_view,
    ):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        request = _fake_request()

        handle_transcript(request, 'approve leave for sarah khan')
        result = handle_transcript(request, 'maybe later')

        self.assertTrue(result['awaiting_input'])
        self.assertIn('yes or a no', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['request_id'], 'req-1')
        mock_approval_view.as_view.assert_not_called()

        # A clear answer on the following turn still completes the flow.
        mock_approval_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'success': True, 'message': 'Request approved.', 'data': {'employee_name': 'Sarah Khan'}},
        )
        result = handle_transcript(request, 'yes')
        self.assertFalse(result['awaiting_input'])
        mock_approval_view.as_view.return_value.assert_called_once()


class SelfApprovalStillBlockedTests(SimpleTestCase):
    """
    Not reachable through the normal identify step (the team queue query
    already excludes the caller's own requests via _approval_scope_filter),
    but if a request_id for the caller's own leave request ever reached the
    confirm stage, LeaveApprovalView.post()'s existing self-approval block
    must still apply unchanged — voice only relays that response, it never
    re-implements or bypasses the check.
    """

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    def test_confirm_stage_surfaces_the_views_self_approval_block(self, mock_approval_view, mock_force_authenticate):
        mock_approval_view.as_view.return_value.return_value = MagicMock(
            status_code=403,
            data={'success': False, 'message': 'You cannot approve or reject your own leave request.'},
        )
        request = _fake_request()

        result = execute_intent(
            INTENT_APPROVE_LEAVE, request, slots={'stage': 'confirm', 'request_id': 'req-self'},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'You cannot approve or reject your own leave request.')
