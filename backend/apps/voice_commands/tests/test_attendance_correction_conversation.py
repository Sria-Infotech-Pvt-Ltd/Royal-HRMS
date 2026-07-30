from datetime import date, time
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import INTENT_REQUEST_ATTENDANCE_CORRECTION
from apps.voice_commands.executor_result import ExecutionResult


def _fake_request(user_id=42):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


class _FakePendingStore:
    """Same in-memory stand-in for the Redis-backed clarification cache used
    in test_apply_leave_conversation.py — see that file for why."""

    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _patch_pending_store(store: _FakePendingStore):
    # conversation_attendance_correction.py binds its own set_pending/
    # clear_pending directly from apps.voice_commands.clarification (to
    # avoid a circular import back into conversation.py, same reasoning
    # conversation_payroll.py and conversation_clarification.py give) — both
    # bindings need patching, or a write from that module silently lands in
    # the real cache while conversation.py's own reads come from the fake store.
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_attendance_correction.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_attendance_correction.clear_pending', side_effect=store.clear),
    )


class SingleUtteranceAllSlotsTests(SimpleTestCase):
    @patch('apps.voice_commands.conversation_attendance_correction.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_all_slots_present_submits_immediately_without_clarification(self, mock_get_pending, mock_execute):
        # _submit() (conversation_attendance_correction.py) calls execute_intent
        # bound in ITS OWN module namespace, not conversation.py's — same
        # reasoning conversation_payroll.py's own execute_intent import needs
        # patching separately in its own tests.
        mock_execute.return_value = ExecutionResult(
            success=True, message='Attendance correction request submitted successfully.',
        )
        request = _fake_request()

        result = handle_transcript(
            request, 'correct my clock in on july 20 2026 to 9:15 am i forgot to punch',
        )

        self.assertEqual(result['intent'], INTENT_REQUEST_ATTENDANCE_CORRECTION)
        self.assertTrue(result['success'])
        mock_execute.assert_called_once()
        slots = mock_execute.call_args.kwargs['slots']
        self.assertEqual(slots['date'], date(2026, 7, 20))
        self.assertEqual(slots['punch_type'], 'IN')
        self.assertEqual(slots['correct_in_time'], time(9, 15))
        self.assertEqual(slots['reason'], 'forgot_to_punch')

    @patch('apps.voice_commands.conversation_attendance_correction.set_pending')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_partial_utterance_does_not_submit_and_stores_pending(self, mock_get_pending, mock_set_pending):
        request = _fake_request()

        result = handle_transcript(request, 'my attendance is wrong')

        mock_set_pending.assert_called_once()
        self.assertEqual(result['intent'], INTENT_REQUEST_ATTENDANCE_CORRECTION)
        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['conversational'])
        self.assertIn('date', result['message'].lower())


class MultiTurnSlotFillingForInPunchTests(SimpleTestCase):
    """
    Full round trip for a clock-in correction — date, then punch_type
    ("in"), then correct_in_time only (correct_out_time is never asked,
    since punch_type is IN), then reason.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        # _submit() (conversation_attendance_correction.py) calls execute_intent
        # bound in ITS OWN module namespace, not conversation.py's.
        execute_patcher = patch('apps.voice_commands.conversation_attendance_correction.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(
            success=True, message='Attendance correction request submitted successfully.',
        )

        self.request = _fake_request()

    def test_full_flow_asks_only_correct_in_time_not_out_time(self):
        # Turn 1 — bare correction phrase, asks for date.
        result = handle_transcript(self.request, 'correct my attendance')
        self.assertIn('date', result['message'].lower())
        self.mock_execute.assert_not_called()

        # Turn 2 — answer date, asks for punch_type.
        result = handle_transcript(self.request, 'july 20 2026')
        self.assertIn('clock-in', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['date'], date(2026, 7, 20))

        # Turn 3 — answer punch_type=in, asks for correct_in_time (NOT out_time).
        result = handle_transcript(self.request, 'in')
        self.assertIn('clock-in time', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['punch_type'], 'IN')

        # Turn 4 — answer the time, asks for reason next (out_time skipped).
        result = handle_transcript(self.request, '9:15 am')
        self.assertIn('reason', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['correct_in_time'], time(9, 15))
        self.assertNotIn('correct_out_time', self.store.get(42)['slots'])

        # Turn 5 — answer reason, all slots complete -> submits and clears pending.
        result = handle_transcript(self.request, 'i forgot to punch')
        self.assertIsNone(self.store.get(42))
        self.mock_execute.assert_called_once()
        self.assertEqual(self.mock_execute.call_args.kwargs['slots'], {
            'date': date(2026, 7, 20),
            'punch_type': 'IN',
            'correct_in_time': time(9, 15),
            'reason': 'forgot_to_punch',
        })
        self.assertEqual(result['message'], 'Attendance correction request submitted successfully.')


class MultiTurnSlotFillingForBothPunchTests(SimpleTestCase):
    """A BOTH punch_type needs both times, in the same order
    next_missing_slot() asks for them: correct_in_time before correct_out_time."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        # _submit() (conversation_attendance_correction.py) calls execute_intent
        # bound in ITS OWN module namespace, not conversation.py's.
        execute_patcher = patch('apps.voice_commands.conversation_attendance_correction.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(success=True, message='Submitted.')

        self.request = _fake_request()
        self.store.set(42, INTENT_REQUEST_ATTENDANCE_CORRECTION, {'date': date(2026, 7, 20), 'punch_type': 'BOTH'})

    def test_asks_correct_in_time_then_correct_out_time_then_reason(self):
        result = handle_transcript(self.request, '9 am')
        self.assertIn('clock-out time', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['correct_in_time'], time(9, 0))

        result = handle_transcript(self.request, '6:30 pm')
        self.assertIn('reason', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['correct_out_time'], time(18, 30))

        handle_transcript(self.request, 'the system was down')
        self.mock_execute.assert_called_once()
        self.assertEqual(self.mock_execute.call_args.kwargs['slots']['reason'], 'system_downtime')


class InvalidClarificationAnswerTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        # _submit() (conversation_attendance_correction.py) calls execute_intent
        # bound in ITS OWN module namespace, not conversation.py's.
        execute_patcher = patch('apps.voice_commands.conversation_attendance_correction.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)

        self.request = _fake_request()

    def test_invalid_punch_type_answer_reasks_and_does_not_advance(self):
        self.store.set(42, INTENT_REQUEST_ATTENDANCE_CORRECTION, {'date': date(2026, 7, 20)})

        result = handle_transcript(self.request, 'banana')

        self.mock_execute.assert_not_called()
        self.assertIn('clock-in, clock-out, or both', result['message'].lower())
        self.assertNotIn('punch_type', self.store.get(42)['slots'])

    def test_invalid_time_answer_reasks_and_does_not_advance(self):
        self.store.set(42, INTENT_REQUEST_ATTENDANCE_CORRECTION, {'date': date(2026, 7, 20), 'punch_type': 'IN'})

        result = handle_transcript(self.request, 'sometime in the morning')

        self.mock_execute.assert_not_called()
        self.assertIn("didn't catch a time", result['message'].lower())
        self.assertNotIn('correct_in_time', self.store.get(42)['slots'])

    def test_future_date_answer_reasks_and_does_not_advance(self):
        self.store.set(42, INTENT_REQUEST_ATTENDANCE_CORRECTION, {})

        result = handle_transcript(self.request, 'december 31 2099')

        self.mock_execute.assert_not_called()
        self.assertIn('future', result['message'].lower())
        self.assertNotIn('date', self.store.get(42)['slots'])

    def test_invalid_reason_answer_reasks_and_does_not_advance(self):
        self.store.set(42, INTENT_REQUEST_ATTENDANCE_CORRECTION, {
            'date': date(2026, 7, 20), 'punch_type': 'IN', 'correct_in_time': time(9, 0),
        })

        result = handle_transcript(self.request, 'no particular reason')

        self.mock_execute.assert_not_called()
        self.assertIn("not a reason", result['message'].lower())


class AbandonAndStartFreshTests(SimpleTestCase):
    """A pending correction clarification exists, but the next transcript
    matches a *different* real intent confidently — same abandonment rule
    apply_leave already has."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        # The abandoned-and-replaced command (clock_in) is a one-shot intent
        # dispatched straight from conversation.py's own _dispatch_matched_intent,
        # not through conversation_attendance_correction.py — this is the one
        # test in this file that patches conversation.py's own execute_intent.
        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')

        self.request = _fake_request()
        self.store.set(42, INTENT_REQUEST_ATTENDANCE_CORRECTION, {'date': date(2026, 7, 20)})

    def test_high_confidence_different_intent_drops_pending_and_dispatches_fresh(self):
        result = handle_transcript(self.request, 'clock in')

        self.assertEqual(result['intent'], 'clock_in')
        self.assertIsNone(self.store.get(42))
