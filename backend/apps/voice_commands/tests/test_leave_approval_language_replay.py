"""
Same leaked-contextvar bug class as test_clarification_language_replay.py/
test_stt_confirmation_language_replay.py, found while fixing parse_yes_no's
missing Hindi word recognition (haan/nahi) — conversation_leave_approval.py's
multi-turn approve_leave/reject_leave flow never stashed or replayed
response_language at all, on ANY of its turns (identify, disambiguate,
confirm). A Hindi-resolved "approve leave for sarah" confirmed with a plain
"yes"/"haan" (which carries no STT language signal of its own) would
dispatch — and every message built from it, including a "be more specific"
disambiguation turn in between — in English regardless of what language the
original command was actually in.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import language
from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.language import LANG_EN, LANG_HI


def _fake_request(user_id: int = 42):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = True
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    request.user.role.role_permissions = role_permissions
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
    """Same in-memory stand-in for the Redis-backed clarification cache used
    throughout this test package — see test_apply_leave_conversation.py."""

    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _patch_pending_store(store: _FakePendingStore):
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_leave_approval.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_leave_approval.clear_pending', side_effect=store.clear),
    )


class LeaveApprovalLanguageReplayTests(SimpleTestCase):
    def setUp(self):
        language.set_current_language(LANG_EN)
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        language.set_current_language(LANG_EN)

    @patch('apps.dashboard.views.overview.push_leave_update')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveApprovalView')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_hindi_single_match_confirmed_with_haan_stays_hindi(
        self, mock_list_view, mock_approval_view, mock_force_authenticate, mock_push_leave_update,
    ):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        mock_approval_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={
                'success': True, 'message': 'Request approved.',
                'data': {'id': 'req-1', 'status': 'approved', 'employee_name': 'Sarah Khan'},
            },
        )
        request = _fake_request()

        first = handle_transcript(request, 'approve leave for sarah khan', response_language=LANG_HI)
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_HI)
        self.assertEqual(self.store.get(42)['slots']['response_language'], LANG_HI)

        # Confirming with the Hindi word itself (parse_yes_no's own fix),
        # on a turn that carries no language signal of its own.
        second = handle_transcript(request, 'haan')

        self.assertFalse(second['awaiting_input'])
        self.assertEqual(second['language'], LANG_HI)
        mock_approval_view.as_view.return_value.assert_called_once()

    def test_english_single_match_confirmed_with_yes_stays_english(self):
        with patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView') as mock_list_view:
            mock_list_view.as_view.return_value.return_value = _team_queue_response(
                [_pending_row('req-1', 'Sarah Khan')],
            )
            request = _fake_request()

            first = handle_transcript(request, 'approve leave for sarah khan')
            self.assertTrue(first['awaiting_input'])
            self.assertEqual(first['language'], LANG_EN)
            self.assertEqual(self.store.get(42)['slots']['response_language'], LANG_EN)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_hindi_origin_survives_a_be_more_specific_disambiguation_turn(
        self, mock_view_cls, mock_force_authenticate,
    ):
        """The name-disambiguation retry turn ("sam cooper") itself carries no
        language signal — response_language must survive THAT turn too, not
        just the final yes/no confirmation (this is why the fix threads
        response_language through _resolve_leave_approval_target explicitly
        rather than re-reading get_current_language() on every call)."""
        mock_view_cls.as_view.return_value.return_value = _team_queue_response([
            _pending_row('req-1', 'Sam Cooper'),
            _pending_row('req-2', 'Sam Anderson'),
        ])
        request = _fake_request()

        first = handle_transcript(request, 'approve leave for sam', response_language=LANG_HI)
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_HI)

        second = handle_transcript(request, 'sam cooper')
        self.assertTrue(second['awaiting_input'])
        self.assertEqual(second['language'], LANG_HI)
        self.assertEqual(self.store.get(42)['slots']['response_language'], LANG_HI)
        self.assertEqual(self.store.get(42)['slots']['request_id'], 'req-1')

    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_hindi_decline_stays_hindi_and_does_not_dispatch(self, mock_list_view):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        request = _fake_request()

        handle_transcript(request, 'reject leave for sarah khan', response_language=LANG_HI)
        with patch('apps.voice_commands.executor_approval.LeaveApprovalView') as mock_approval_view:
            result = handle_transcript(request, 'नहीं')

        self.assertEqual(result['language'], LANG_HI)
        mock_approval_view.as_view.assert_not_called()
        self.assertIsNone(self.store.get(42))

    @patch('apps.voice_commands.executor_approval.LeaveRequestListCreateView')
    def test_unclear_answer_reasks_in_hindi_and_keeps_the_stashed_language(self, mock_list_view):
        mock_list_view.as_view.return_value.return_value = _team_queue_response(
            [_pending_row('req-1', 'Sarah Khan')],
        )
        request = _fake_request()

        handle_transcript(request, 'approve leave for sarah khan', response_language=LANG_HI)
        reask = handle_transcript(request, 'maybe')

        self.assertTrue(reask['awaiting_input'])
        self.assertEqual(reask['language'], LANG_HI)
        self.assertEqual(self.store.get(42)['slots']['response_language'], LANG_HI)
