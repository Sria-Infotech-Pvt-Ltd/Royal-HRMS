import time
from datetime import date
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import clarification
from apps.voice_commands.conversation import (
    _EXPIRED_CLARIFICATION_MESSAGE,
    _NO_MATCH_MESSAGE,
    _looks_like_expired_slot_answer,
    handle_transcript,
)
from apps.voice_commands.executor import INTENT_APPLY_LEAVE, ExecutionResult
from apps.voice_commands.matcher import NO_MATCH_INTENT


def _fake_request(user_id=42):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


class _FakePendingStore:
    """
    In-memory stand-in for the Redis-backed clarification cache — lets tests
    exercise a realistic multi-turn sequence (set on turn N, read on turn
    N+1) without touching django.core.cache or a real/local Redis instance.
    """

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
    )


class SingleUtteranceAllSlotsTests(SimpleTestCase):
    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_all_slots_present_submits_immediately_without_clarification(self, mock_get_pending, mock_execute):
        mock_execute.return_value = ExecutionResult(success=True, message='Your sick leave request has been submitted.')
        request = _fake_request()

        result = handle_transcript(
            request, 'apply for sick leave from july 22 to july 24 because i am unwell',
        )

        self.assertEqual(result['intent'], INTENT_APPLY_LEAVE)
        self.assertEqual(result['message'], 'Your sick leave request has been submitted.')
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs['slots']['leave_type'], 'sick')
        self.assertEqual(call_kwargs['slots']['reason'], 'i am unwell')
        self.assertIn('start_date', call_kwargs['slots'])
        self.assertIn('end_date', call_kwargs['slots'])

    @patch('apps.voice_commands.conversation.set_pending')
    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_partial_utterance_does_not_submit_and_stores_pending(self, mock_get_pending, mock_execute, mock_set_pending):
        request = _fake_request()

        result = handle_transcript(request, 'apply for sick leave')

        mock_execute.assert_not_called()
        mock_set_pending.assert_called_once()
        self.assertEqual(result['intent'], INTENT_APPLY_LEAVE)
        self.assertIn('start', result['message'].lower())


class MultiTurnSlotFillingTests(SimpleTestCase):
    """
    Each slot is missing one at a time — proves the full round trip through
    handle_transcript across four separate calls, in the exact order
    next_missing_slot() asks for them: leave_type, start_date, end_date, reason.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(success=True, message='Your leave request has been submitted.')

        self.request = _fake_request()

    def test_full_four_turn_flow(self):
        # Turn 1 — bare "apply for leave", nothing captured, asks for leave_type.
        result = handle_transcript(self.request, 'apply for leave')
        self.assertEqual(result['message'], (
            'What type of leave would you like to apply for — Casual Leave, Earned Leave, '
            'Sick Leave, Leave Without Pay, Maternity Leave, or Paternity Leave?'
        ))
        self.mock_execute.assert_not_called()

        # Turn 2 — answer leave_type, asks for start_date next.
        result = handle_transcript(self.request, 'sick')
        self.assertIn('start', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['leave_type'], 'sick')

        # Turn 3 — answer start_date, asks for end_date next.
        result = handle_transcript(self.request, 'july 22 2026')
        self.assertIn('end', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['start_date'], date(2026, 7, 22))

        # Turn 4 — answer end_date, asks for reason next.
        result = handle_transcript(self.request, 'july 24 2026')
        self.assertIn('reason', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['end_date'], date(2026, 7, 24))

        # Turn 5 — answer reason, all slots complete -> submits and clears pending.
        result = handle_transcript(self.request, 'i am feeling unwell')
        self.assertIsNone(self.store.get(42))
        self.mock_execute.assert_called_once()
        call_kwargs = self.mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs['slots'], {
            'leave_type': 'sick',
            'start_date': date(2026, 7, 22),
            'end_date': date(2026, 7, 24),
            'reason': 'i am feeling unwell',
        })
        self.assertEqual(result['message'], 'Your leave request has been submitted.')


class InvalidClarificationAnswerTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)

        self.request = _fake_request()
        self.store.set(42, INTENT_APPLY_LEAVE, {})

    def test_invalid_leave_type_answer_reasks_and_does_not_advance(self):
        result = handle_transcript(self.request, 'banana')

        self.mock_execute.assert_not_called()
        self.assertIn('Sick', result['message'])
        # Still awaiting leave_type — nothing was recorded for a bad answer.
        self.assertEqual(self.store.get(42)['slots'], {})

    def test_valid_answer_after_invalid_one_advances_normally(self):
        handle_transcript(self.request, 'banana')  # rejected
        result = handle_transcript(self.request, 'sick')  # now valid

        self.assertEqual(self.store.get(42)['slots']['leave_type'], 'sick')
        self.assertIn('start', result['message'].lower())


class AbandonAndStartFreshTests(SimpleTestCase):
    """
    A pending apply_leave clarification exists, but the next transcript
    matches a *different* real intent with high confidence — the user has
    clearly moved on, so the stale pending state is dropped instead of being
    force-interpreted as (e.g.) a leave_type answer.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')

        self.request = _fake_request()
        self.store.set(42, INTENT_APPLY_LEAVE, {'leave_type': 'sick'})

    def test_high_confidence_different_intent_drops_pending_and_dispatches_fresh(self):
        result = handle_transcript(self.request, 'clock in')

        self.assertIsNone(self.store.get(42))
        self.assertEqual(result['intent'], 'clock_in')
        self.mock_execute.assert_called_once()
        self.assertEqual(self.mock_execute.call_args.args[0], 'clock_in')

    def test_nonsense_transcript_while_pending_is_treated_as_a_clarification_answer_not_abandoned(self):
        # "asdkjhasd" doesn't match any real intent, so it's NOT a "clearly
        # moved on" signal — it's treated as a (bad) answer to start_date.
        self.store.clear(42)
        self.store.set(42, INTENT_APPLY_LEAVE, {'leave_type': 'sick'})

        result = handle_transcript(self.request, 'asdkjhasd')

        self.assertIsNotNone(self.store.get(42))
        self.mock_execute.assert_not_called()
        self.assertIn('date', result['message'].lower())


class CacheExpiryTests(SimpleTestCase):
    """
    Simulates the 120s TTL lapsing between turns: get_pending() returning
    None is exactly what a real cache backend (Redis or LocMem) returns once
    a key has expired — from handle_transcript's point of view there is no
    difference between "never set" and "expired", so this is a faithful
    stand-in for real expiry without a real sleep in the test suite.
    """

    @patch('apps.voice_commands.conversation.set_pending')
    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_expired_pending_state_is_treated_as_a_fresh_command(self, mock_get_pending, mock_execute, mock_set_pending):
        mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')
        request = _fake_request()

        # If the expired apply_leave clarification were still honored, "clock
        # in" would be misread as a slot answer instead of a fresh command.
        result = handle_transcript(request, 'clock in')

        self.assertEqual(result['intent'], 'clock_in')
        mock_execute.assert_called_once()
        self.assertEqual(mock_execute.call_args.args[0], 'clock_in')


class ExpiredClarificationHeuristicTests(SimpleTestCase):
    """
    Covers the case CacheExpiryTests above deliberately doesn't: when the
    expired pending state's answer is itself slot-answer-shaped (a bare
    leave type or date) rather than an unrelated real command like "clock
    in", _looks_like_expired_slot_answer() should recognize it and return a
    distinct timeout message instead of the generic "didn't understand" one
    — so the user knows their leave application timed out rather than
    wondering whether their answer was garbled.
    """

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_bare_leave_type_answer_after_expiry_returns_timeout_message(self, mock_get_pending, mock_execute):
        result = handle_transcript(_fake_request(), 'sick')

        self.assertEqual(result['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        self.assertEqual(result['intent'], NO_MATCH_INTENT)
        mock_execute.assert_not_called()

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_bare_date_answer_after_expiry_returns_timeout_message(self, mock_get_pending, mock_execute):
        result = handle_transcript(_fake_request(), 'july 24 2026')

        self.assertEqual(result['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        mock_execute.assert_not_called()

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_genuinely_unrecognized_command_still_gets_the_generic_message(self, mock_get_pending, mock_execute):
        # No leave-type keyword, no parseable date -- this is what an actual
        # unrecognized command looks like, and must NOT be mislabeled as a
        # timed-out clarification.
        result = handle_transcript(_fake_request(), 'asdkjhasd')

        self.assertEqual(result['message'], _NO_MATCH_MESSAGE)
        mock_execute.assert_not_called()

    def test_unrelated_fresh_command_is_not_flagged_as_a_slot_answer(self):
        # Regression: "how many unapproved leaves i have" contains neither a
        # leave-type keyword nor a parseable date -- it's an unrelated fresh
        # command (now registered as check_leave_status, see intents_en.yaml),
        # not a stray answer to an expired apply_leave clarification. It must
        # never trip the heuristic, clean state or not.
        self.assertFalse(_looks_like_expired_slot_answer('how many unapproved leaves i have'))

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_unrelated_fresh_command_from_a_clean_state_is_dispatched_not_flagged_as_timeout(
        self, mock_get_pending, mock_execute,
    ):
        mock_execute.return_value = ExecutionResult(success=True, message='You have 3 pending leave requests.')

        result = handle_transcript(_fake_request(), 'how many unapproved leaves i have')

        self.assertNotEqual(result['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        self.assertEqual(result['intent'], 'check_leave_status')
        mock_execute.assert_called_once()


class GenuineExpiryAfterRealInactivityTests(SimpleTestCase):
    """
    End-to-end version of the heuristic tests above: uses the real
    clarification cache (no mocked get_pending/set_pending) with a
    shortened TTL and an actual sleep past it, proving the distinct timeout
    message is returned after genuine inactivity, not just when a test
    simulates expiry by mocking get_pending to return None.
    """

    def setUp(self):
        clarification.clear_pending(777)
        self.addCleanup(clarification.clear_pending, 777)

    @patch('apps.voice_commands.clarification.PENDING_TIMEOUT_SECONDS', 1)
    @patch('apps.voice_commands.conversation.execute_intent')
    def test_real_inactivity_past_ttl_returns_distinct_timeout_message(self, mock_execute):
        request = _fake_request(777)

        # Turn 1 (real cache write): starts apply_leave, asks for leave_type.
        first = handle_transcript(request, 'apply for leave')
        self.assertIn('leave', first['message'].lower())

        # Real inactivity longer than the (patched, shortened) TTL.
        time.sleep(1.5)
        self.assertIsNone(clarification.get_pending(777))

        result = handle_transcript(request, 'sick')

        self.assertEqual(result['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        mock_execute.assert_not_called()


class RelativeDayWordInFirstUtteranceRegressionTests(SimpleTestCase):
    """
    Regression coverage for the bug where "apply for sick leave tomorrow"
    silently set BOTH start_date and end_date to tomorrow's date from a
    substring match against the whole first utterance — never asking the
    user for either date, and silently discarding any explicit date given in
    a later turn because next_missing_slot() considered both slots already
    filled. See slot_extractor._parse_single_date's allow_relative param and
    extract_date_range's no-range fallback branch for the fix.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(success=True, message='Your leave request has been submitted.')

        self.request = _fake_request()

    def test_relative_day_word_does_not_silently_fill_both_date_slots(self):
        # Turn 1 — "tomorrow" appears in the sentence, but this is not a
        # targeted date answer, so it must NOT resolve either date slot.
        result = handle_transcript(self.request, 'i want to apply for sick leave tomorrow')

        self.mock_execute.assert_not_called()
        self.assertIn('start', result['message'].lower())
        stored_slots = self.store.get(42)['slots']
        self.assertEqual(stored_slots, {'leave_type': 'sick'})
        self.assertNotIn('start_date', stored_slots)
        self.assertNotIn('end_date', stored_slots)

    def test_explicit_date_in_a_later_turn_correctly_fills_the_slot(self):
        # Turn 1, same as above.
        handle_transcript(self.request, 'i want to apply for sick leave tomorrow')

        # Turn 2 — the system is now specifically asking for start_date, so
        # an explicit date given here must be captured, not discarded.
        result = handle_transcript(self.request, 'july 25 2026')
        self.assertIn('end', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['start_date'], date(2026, 7, 25))

        # Turn 3 — likewise for end_date.
        result = handle_transcript(self.request, 'july 28 2026')
        self.assertIn('reason', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['end_date'], date(2026, 7, 28))

        # Turn 4 — reason completes the flow; submitted dates must be the
        # explicit ones from turns 2 and 3, not "tomorrow" from turn 1.
        handle_transcript(self.request, 'not feeling well')
        self.mock_execute.assert_called_once()
        call_kwargs = self.mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs['slots']['start_date'], date(2026, 7, 25))
        self.assertEqual(call_kwargs['slots']['end_date'], date(2026, 7, 28))
