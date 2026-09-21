"""
Phase 5c — the "did you mean X?" clarification-flow language leak: a
leaked-contextvar bug of the same class Phase 3.1 already fixed for
conversation_stt_confirmation.py (see
test_stt_confirmation_language_replay.py's own docstring), left unfixed for
this flow. continue_clarification's confirmed dispatch calls conversation.py's
_dispatch_matched_intent directly and NEVER re-enters handle_transcript
(unlike the STT-confirmation flow) — so nothing else was setting the ambient
response language for that call. Before this fix, a Hindi-resolved
clarification confirmed with a plain "yes" (which carries no STT language
signal of its own) would dispatch — and every executor message built from
it would render — in English regardless of what language the original,
now-confirmed command was actually in.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import language
from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import LANG_EN, LANG_HI


def _fake_request(user_id=99):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


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
        patch('apps.voice_commands.conversation_clarification.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_clarification.clear_pending', side_effect=store.clear),
    )


# Real garbled STT near-miss for "raise a query about my payslip" — same
# transcript test_did_you_mean_clarification.py uses; scores in
# matcher's [60, 80) clarification band against raise_payslip_query.
_GARBLED_PAYSLIP_QUERY = 'raise a queryAbout my Paisley'


class ClarificationLanguageReplayTests(SimpleTestCase):
    def setUp(self):
        language.set_current_language(LANG_EN)
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)

        execute_patcher = patch('apps.voice_commands.conversation_payroll.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(
            success=True, message='Your query has been submitted to HR.',
        )

        extract_patcher = patch(
            'apps.voice_commands.conversation_payroll.extract_payslip_query_description',
            return_value='my payslip amount looks wrong',
        )
        extract_patcher.start()
        self.addCleanup(extract_patcher.stop)

    def tearDown(self):
        language.set_current_language(LANG_EN)

    def test_hindi_resolved_clarification_stays_hindi_after_yes(self):
        request = _fake_request()

        # Turn 1: middle-confidence guess, resolved as Hindi — response_language
        # is the same explicit-override parameter a real Hindi-detected turn
        # resolves to server-side; stt_used_language_hint is deliberately NOT
        # used here, since that flag instead routes through the SEPARATE
        # STT-confirmation gate (conversation_stt_confirmation.py), not this
        # "did you mean X?" clarification flow.
        first = handle_transcript(request, _GARBLED_PAYSLIP_QUERY, response_language=LANG_HI)
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_HI)
        self.assertEqual(self.store.get(99)['slots']['response_language'], LANG_HI)

        # Turn 2: user confirms "yes" — a plain answer carrying no STT
        # language signal of its own.
        second = handle_transcript(request, 'yes')

        # The confirmed dispatch must still be Hindi — not silently reset to
        # English by the second call's own (absent) language signal.
        self.assertEqual(second['language'], LANG_HI)
        self.mock_execute.assert_called_once()

    def test_english_resolved_clarification_stays_english_after_yes(self):
        request = _fake_request()

        first = handle_transcript(request, _GARBLED_PAYSLIP_QUERY)
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_EN)
        self.assertEqual(self.store.get(99)['slots']['response_language'], LANG_EN)

        second = handle_transcript(request, 'yes')

        self.assertEqual(second['language'], LANG_EN)

    def test_decline_never_dispatches_regardless_of_stashed_language(self):
        request = _fake_request()
        handle_transcript(request, _GARBLED_PAYSLIP_QUERY, response_language=LANG_HI)

        result = handle_transcript(request, 'no')

        self.assertTrue(result['success'])
        self.mock_execute.assert_not_called()

    def test_reask_on_unclear_answer_does_not_consume_the_stashed_language(self):
        """An unclear yes/no answer re-asks the same question — the stashed
        response_language must still be there, unconsumed, for a later
        genuine 'yes'."""
        request = _fake_request()
        handle_transcript(request, _GARBLED_PAYSLIP_QUERY, response_language=LANG_HI)

        reask = handle_transcript(request, 'maybe')
        self.assertTrue(reask['awaiting_input'])
        self.assertEqual(self.store.get(99)['slots']['response_language'], LANG_HI)

        second = handle_transcript(request, 'yes')
        self.assertEqual(second['language'], LANG_HI)
