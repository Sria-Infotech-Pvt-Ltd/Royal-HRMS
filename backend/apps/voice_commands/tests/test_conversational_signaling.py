from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import INTENT_APPLY_LEAVE, INTENT_CLOCK_IN, ExecutionResult
from apps.voice_commands.matcher import NO_MATCH_INTENT, get_conversational


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
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
    )


class ConversationalRegistryTests(SimpleTestCase):
    """get_conversational() reads registry/intents_en.yaml's `conversational` field."""

    def test_apply_leave_is_conversational(self):
        self.assertTrue(get_conversational(INTENT_APPLY_LEAVE))

    def test_request_attendance_correction_is_conversational(self):
        """Slot-filling infrastructure now exists for this intent (date,
        punch_type, correct_in_time/correct_out_time, reason — see
        correction_slot_extractor.py/conversation_attendance_correction.py),
        same multi-turn shape as apply_leave."""
        self.assertTrue(get_conversational('request_attendance_correction'))

    def test_every_other_real_intent_is_not_conversational(self):
        non_conversational_intents = [
            'clock_in', 'clock_out', 'check_leave_balance', 'check_leave_status',
            'cancel_leave', 'check_attendance_stats', 'check_attendance_summary',
            'check_team_leave_queue', 'check_team_attendance',
        ]
        for intent in non_conversational_intents:
            with self.subTest(intent=intent):
                self.assertFalse(get_conversational(intent))

    def test_unregistered_intent_defaults_to_not_conversational(self):
        self.assertFalse(get_conversational(NO_MATCH_INTENT))
        self.assertFalse(get_conversational('__totally_unregistered_intent__'))


class ApplyLeaveConversationalSignalingTests(SimpleTestCase):
    """
    Full apply_leave conversation (mirrors test_apply_leave_conversation.py's
    MultiTurnSlotFillingTests), asserting conversational/awaiting_input at
    every stage — this is the exact signal the frontend needs to stop
    hardcoding per-intent "does this need a follow-up" logic.
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

    def test_full_conversation_signals_correctly_at_every_stage(self):
        # Turn 1 — bare "apply for leave": flow has begun, awaiting leave_type.
        result = handle_transcript(self.request, 'apply for leave')
        self.assertTrue(result['conversational'])
        self.assertTrue(result['awaiting_input'])

        # Turn 2 — answer leave_type, awaiting start_date.
        result = handle_transcript(self.request, 'sick')
        self.assertTrue(result['conversational'])
        self.assertTrue(result['awaiting_input'])

        # Turn 3 — answer start_date, awaiting end_date.
        result = handle_transcript(self.request, 'july 22 2026')
        self.assertTrue(result['conversational'])
        self.assertTrue(result['awaiting_input'])

        # Turn 4 — answer end_date, awaiting reason.
        result = handle_transcript(self.request, 'july 24 2026')
        self.assertTrue(result['conversational'])
        self.assertTrue(result['awaiting_input'])

        # Turn 5 — answer reason, all slots complete -> submits. conversational
        # stays true (still an apply_leave response); awaiting_input flips to
        # false — "done, this can close now".
        result = handle_transcript(self.request, 'i am feeling unwell')
        self.assertTrue(result['conversational'])
        self.assertFalse(result['awaiting_input'])

    def test_invalid_clarification_answer_re_ask_still_signals_awaiting_input(self):
        self.store.set(42, INTENT_APPLY_LEAVE, {})

        result = handle_transcript(self.request, 'banana')  # invalid leave_type answer

        self.mock_execute.assert_not_called()
        self.assertTrue(result['conversational'])
        self.assertTrue(result['awaiting_input'])

    def test_single_utterance_with_all_slots_submits_immediately_but_stays_conversational(self):
        # No clarification turn needed at all, yet this is still an
        # apply_leave response — conversational must stay true even though
        # this particular exchange only took one turn.
        result = handle_transcript(
            self.request, 'apply for sick leave from july 22 to july 24 because i am unwell',
        )

        self.mock_execute.assert_called_once()
        self.assertTrue(result['conversational'])
        self.assertFalse(result['awaiting_input'])


class ImmediateActionIntentSignalingTests(SimpleTestCase):
    """A non-apply_leave intent must always report conversational: false, awaiting_input: false."""

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_clock_in_is_never_conversational(self, mock_get_pending, mock_execute):
        mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')
        request = _fake_request()

        result = handle_transcript(request, 'clock in')

        self.assertEqual(result['intent'], INTENT_CLOCK_IN)
        self.assertFalse(result['conversational'])
        self.assertFalse(result['awaiting_input'])

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_successful_clock_in_reports_success_true(self, mock_get_pending, mock_execute):
        mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')
        request = _fake_request()

        result = handle_transcript(request, 'clock in')

        self.assertTrue(result['success'])

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_geofencing_rejected_clock_in_reports_success_false(self, mock_get_pending, mock_execute):
        # This is the exact signal VoiceCommandButton's retry flow keys off:
        # a real ExecutionResult failure (e.g. GeofencingService's "GPS is
        # mandatory" PermissionError, caught in executor_attendance._execute_punch) must
        # surface as success: false in the payload, not just a message string.
        mock_execute.return_value = ExecutionResult(
            success=False,
            message=(
                'Your location is required to clock in at this branch. '
                'Please allow location access in your browser and try again.'
            ),
        )
        request = _fake_request()

        result = handle_transcript(request, 'clock in')

        self.assertFalse(result['success'])
        self.assertEqual(result['intent'], INTENT_CLOCK_IN)

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_clock_in_forwards_latitude_and_longitude_to_execute_intent(self, mock_get_pending, mock_execute):
        mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')
        request = _fake_request()

        handle_transcript(request, 'clock in', latitude=17.385044, longitude=78.486671)

        call_kwargs = mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs['latitude'], 17.385044)
        self.assertEqual(call_kwargs['longitude'], 78.486671)

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_clock_in_with_no_coordinates_forwards_none(self, mock_get_pending, mock_execute):
        mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')
        request = _fake_request()

        handle_transcript(request, 'clock in')

        call_kwargs = mock_execute.call_args.kwargs
        self.assertIsNone(call_kwargs['latitude'])
        self.assertIsNone(call_kwargs['longitude'])


class NoMatchSignalingTests(SimpleTestCase):
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_no_match_is_never_conversational(self, mock_get_pending):
        request = _fake_request()

        result = handle_transcript(request, 'what is the weather today in paris')

        self.assertEqual(result['intent'], NO_MATCH_INTENT)
        self.assertFalse(result['conversational'])
        self.assertFalse(result['awaiting_input'])

    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_no_match_reports_success_false(self, mock_get_pending):
        request = _fake_request()

        result = handle_transcript(request, 'what is the weather today in paris')

        self.assertFalse(result['success'])
