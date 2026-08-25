from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import clarification
from apps.voice_commands.conversation import _NO_MATCH_MESSAGE, handle_transcript
from apps.voice_commands.executor import (
    INTENT_APPLY_LEAVE,
    INTENT_CHECK_ATTENDANCE_STATS,
    INTENT_CHECK_LEAVE_BALANCE,
    INTENT_CHECK_MY_PAYSLIP,
    ExecutionResult,
)
from apps.voice_commands.language import text
from apps.voice_commands.matcher import NO_MATCH_INTENT, MatchResult


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
    # conversation.py reads/writes pending state directly (the top-level
    # check + the "abandon on a confident new match" branch), but
    # conversation_clarification.py's start_clarification/continue_clarification
    # also write directly to their own bound set_pending/clear_pending names
    # (see that module's docstring on why it can't import back through
    # conversation.py) — both bindings need patching or a write from one
    # module silently lands in the real cache while reads come from the fake
    # store.
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_clarification.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_clarification.clear_pending', side_effect=store.clear),
    )


class MiddleConfidenceTriggersClarificationTests(SimpleTestCase):
    """
    These transcripts are real garbled speech-to-text near-misses pulled from
    logs/voice_commands.log — actual attempts at "raise a query about my
    payslip" mangled by the browser's speech recognizer. Both score in
    [60, 80) against the real registry (matcher.CLARIFICATION_CONFIDENCE_THRESHOLD
    to matcher.DEFAULT_CONFIDENCE_THRESHOLD) — below the confident-match bar
    but clearly not gibberish either.

    A third logged near-miss, "raise a query about my attendance", used to
    land here too (candidate raise_payslip_query, ~69.84) before
    request_attendance_correction gained its own "raise a query/concern about
    my attendance" phrases — it now resolves as a confident direct match to
    request_attendance_correction instead, which is the fix, not a
    regression. See test_matcher.py's collision tests for that pair.
    """

    def tearDown(self):
        # get_pending is mocked away above, but start_clarification's own
        # set_pending call is NOT — it writes to the real cache (LocMemCache
        # in tests). Clean it up so it can't leak into a later test that
        # reads the real cache for this same user id.
        clarification.clear_pending(42)

    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_garbled_payslip_query_asks_did_you_mean(self, mock_get_pending):
        request = _fake_request()

        result = handle_transcript(request, 'raise a queryAbout my Paisley')

        self.assertEqual(result['intent'], 'raise_payslip_query')
        self.assertTrue(60 <= result['confidence'] < 80)
        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['conversational'])
        self.assertIn('did you mean', result['message'].lower())
        self.assertTrue(result['success'])

    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_heavily_garbled_query_asks_did_you_mean(self, mock_get_pending):
        request = _fake_request()

        result = handle_transcript(request, 'Praise a queryAbout my Paisley')

        self.assertEqual(result['intent'], 'raise_payslip_query')
        self.assertTrue(60 <= result['confidence'] < 80)
        self.assertTrue(result['awaiting_input'])

    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_clarification_question_names_the_actual_closest_phrase(self, mock_get_pending):
        """The question quotes the specific registered phrase that scored
        closest — not just the intent name — so it reads as a natural,
        answerable question."""
        request = _fake_request()

        result = handle_transcript(request, 'raise a queryAbout my Paisley')

        self.assertEqual(result['message'], 'Did you mean: "raise a query on my payslip"?')


class LowConfidenceStillNoMatchTests(SimpleTestCase):
    """Truly unrelated transcripts — real gibberish from the same logs — must
    keep getting the plain no-match message, not a random guess."""

    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_nonsense_transcript_is_still_a_flat_no_match(self, mock_get_pending):
        request = _fake_request()

        result = handle_transcript(request, 'what is the weather today in paris')

        self.assertEqual(result['intent'], NO_MATCH_INTENT)
        self.assertLess(result['confidence'], 60)
        self.assertFalse(result['awaiting_input'])
        self.assertFalse(result['conversational'])
        self.assertEqual(result['message'], text(_NO_MATCH_MESSAGE))
        self.assertFalse(result['success'])

    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_keyboard_mash_is_still_a_flat_no_match(self, mock_get_pending):
        request = _fake_request()

        result = handle_transcript(request, 'asdkjhasd')

        self.assertEqual(result['intent'], NO_MATCH_INTENT)
        self.assertLess(result['confidence'], 60)
        self.assertEqual(result['message'], text(_NO_MATCH_MESSAGE))


class ClarificationConfirmationTests(SimpleTestCase):
    """Second-turn handling once a clarification question is pending — reuses
    the exact same Redis-backed pending mechanism apply_leave/approve_leave
    already rely on, just a new 'stage' value."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(
            success=True, message='Your query has been submitted to HR.',
        )

        # test_confident_new_command_mid_clarification_abandons_it below
        # abandons into clock_in, which dispatches through
        # conversation_clock_in_face.py rather than execute_intent above —
        # see that module.
        mandatory_patcher = patch(
            'apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', return_value=False,
        )
        mandatory_patcher.start()
        self.addCleanup(mandatory_patcher.stop)
        clock_in_patcher = patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in')
        self.mock_execute_clock_in = clock_in_patcher.start()
        self.addCleanup(clock_in_patcher.stop)
        self.mock_execute_clock_in.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')

        self.request = _fake_request()

    def test_yes_confirms_and_dispatches_the_candidate_intent(self):
        # Turn 1: middle-confidence guess.
        first = handle_transcript(self.request, 'raise a queryAbout my Paisley')
        self.assertTrue(first['awaiting_input'])

        # Turn 2: user confirms. raise_payslip_query is itself a
        # conversational intent (it may ask a follow-up question of its
        # own for the query description) — mock_execute stubs out that
        # inner flow so this test only asserts the clarification handoff.
        with patch('apps.voice_commands.conversation_payroll.execute_intent', self.mock_execute), \
             patch(
                 'apps.voice_commands.conversation_payroll.extract_payslip_query_description',
                 return_value='my payslip amount looks wrong',
             ):
            result = handle_transcript(self.request, 'yes')

        self.mock_execute.assert_called_once()
        self.assertEqual(result['intent'], 'raise_payslip_query')
        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
        self.assertNotIn(42, self.store._store)  # pending cleared

    def test_no_declines_with_a_friendly_reset_not_the_generic_no_match_message(self):
        # A "no" answer is a deliberate, expected decline -- not a failure to
        # understand -- so it must NOT reuse the generic no-match message
        # (that message is reserved for transcripts that never matched
        # anything at all, see LowConfidenceStillNoMatchTests below).
        handle_transcript(self.request, 'raise a queryAbout my Paisley')

        result = handle_transcript(self.request, 'no')

        self.mock_execute.assert_not_called()
        self.assertNotEqual(result['intent'], NO_MATCH_INTENT)
        self.assertNotEqual(result['message'], text(_NO_MATCH_MESSAGE))
        self.assertEqual(result['message'], "Okay, is there anything else I can help you with?")
        self.assertTrue(result['success'])
        self.assertFalse(result['awaiting_input'])
        self.assertNotIn(42, self.store._store)  # pending cleared, not left dangling

    def test_unclear_answer_re_asks_the_same_question_instead_of_guessing(self):
        first = handle_transcript(self.request, 'raise a queryAbout my Paisley')

        result = handle_transcript(self.request, 'maybe')

        self.mock_execute.assert_not_called()
        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['conversational'])
        self.assertIn('yes or a no', result['message'].lower())
        self.assertEqual(first['intent'], result['intent'])  # still awaiting the same candidate

    def test_confident_new_command_mid_clarification_abandons_it(self):
        """A user who ignores the clarification question and says something
        else clear and confident should get THAT command, not be stuck
        answering yes/no for a guess they've moved past — same abandonment
        rule apply_leave/approve_leave already have."""
        handle_transcript(self.request, 'raise a queryAbout my Paisley')

        result = handle_transcript(self.request, 'clock in')

        self.assertEqual(result['intent'], 'clock_in')
        self.assertNotIn(42, self.store._store)


class ClarificationWithNonConversationalCandidateTests(SimpleTestCase):
    """A candidate intent that is itself registered conversational: false
    (e.g. check_leave_balance) must still show the yes/no follow-up UI while
    the clarification question is pending — conversational=True is an
    explicit override for this one turn, not read off that intent's own
    registry entry (see conversation_clarification's _payload docstring)."""

    def tearDown(self):
        clarification.clear_pending(42)

    @patch('apps.voice_commands.conversation.execute_intent')
    @patch('apps.voice_commands.conversation.match_intent')
    @patch('apps.voice_commands.conversation.get_pending', return_value=None)
    def test_middle_confidence_non_conversational_candidate_still_awaits_confirmation(
        self, mock_get_pending, mock_match_intent, mock_execute,
    ):
        mock_match_intent.return_value = MatchResult(
            intent=NO_MATCH_INTENT, confidence=70.0,
            matched_phrase='check my leave balance', candidate_intent=INTENT_CHECK_LEAVE_BALANCE,
        )
        request = _fake_request()

        result = handle_transcript(request, 'some garbled leave balance phrase')

        self.assertEqual(result['intent'], INTENT_CHECK_LEAVE_BALANCE)
        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['conversational'])
        mock_execute.assert_not_called()  # awaiting confirmation, nothing dispatched yet


class StaleClarificationDoesNotSwallowNewCommandTests(SimpleTestCase):
    """
    Root cause of the reported "did you mean [previous command]" state-leak
    bug (VC-1): CLARIFICATION_STAGE/STT_CONFIRMATION_STAGE only ever expect a
    yes/no answer (see continue_clarification/continue_stt_confirmation's own
    parse_yes_no calls) — a user who ignores an unanswered "did you mean X?"
    question and says something else entirely got that new command silently
    swallowed whenever it ALSO happened to land in the clarification band
    for its own, different candidate: parse_yes_no couldn't recognize it as
    yes/no either, so continue_clarification just re-asked the STALE
    question, reading as "did you mean X?" for a command the user never
    said. Confirmed general (not specific to check_leave_balance/apply_leave)
    by test_generalizes_to_a_different_intent_pair below. Fixed in
    conversation._should_abandon_pending — see its own docstring.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)
        self.request = _fake_request()

    def test_leave_balance_then_apply_leave_starts_apply_leave_fresh(self):
        """The exact reported sequence: check-leave-balance's own unanswered
        clarification must not resurface for a brand new "apply leave"."""
        with patch('apps.voice_commands.conversation.match_intent') as mock_match:
            mock_match.return_value = MatchResult(
                intent=NO_MATCH_INTENT, confidence=75.0,
                matched_phrase='check my leave balance', candidate_intent=INTENT_CHECK_LEAVE_BALANCE,
            )
            first = handle_transcript(self.request, 'garbled leave balance text')
            self.assertTrue(first['awaiting_input'])
            self.assertEqual(first['intent'], INTENT_CHECK_LEAVE_BALANCE)

            mock_match.return_value = MatchResult(
                intent=NO_MATCH_INTENT, confidence=70.0,
                matched_phrase='apply for leave', candidate_intent=INTENT_APPLY_LEAVE,
            )
            second = handle_transcript(self.request, 'apply leave')

        self.assertEqual(second['intent'], INTENT_APPLY_LEAVE)
        self.assertTrue(second['awaiting_input'])
        self.assertIn('apply for leave', second['message'].lower())
        self.assertNotIn('leave balance', second['message'].lower())
        # A fresh pending state for apply_leave now exists — not the stale one.
        self.assertEqual(self.store.get(42)['intent'], INTENT_APPLY_LEAVE)

    def test_generalizes_to_a_different_intent_pair(self):
        """Same bug shape with unrelated intents — proves the fix addresses
        the general mechanism, not just leave_balance/apply_leave."""
        with patch('apps.voice_commands.conversation.match_intent') as mock_match:
            mock_match.return_value = MatchResult(
                intent=NO_MATCH_INTENT, confidence=72.0,
                matched_phrase='how is my attendance', candidate_intent=INTENT_CHECK_ATTENDANCE_STATS,
            )
            first = handle_transcript(self.request, 'garbled attendance text')
            self.assertEqual(first['intent'], INTENT_CHECK_ATTENDANCE_STATS)

            mock_match.return_value = MatchResult(
                intent=NO_MATCH_INTENT, confidence=68.0,
                matched_phrase='check my payslip', candidate_intent=INTENT_CHECK_MY_PAYSLIP,
            )
            second = handle_transcript(self.request, 'garbled payslip text')

        self.assertEqual(second['intent'], INTENT_CHECK_MY_PAYSLIP)
        self.assertNotIn('attendance', second['message'].lower())
        self.assertEqual(self.store.get(42)['intent'], INTENT_CHECK_MY_PAYSLIP)

    def test_genuinely_ambiguous_new_input_still_triggers_did_you_mean(self):
        """Regression guard for the fix itself: with no pre-existing pending
        state at all, a fresh clarification-band utterance must still ask
        its own "did you mean X?" question exactly as before."""
        with patch('apps.voice_commands.conversation.match_intent') as mock_match:
            mock_match.return_value = MatchResult(
                intent=NO_MATCH_INTENT, confidence=70.0,
                matched_phrase='apply for leave', candidate_intent=INTENT_APPLY_LEAVE,
            )
            result = handle_transcript(self.request, 'apply leave')

        self.assertEqual(result['intent'], INTENT_APPLY_LEAVE)
        self.assertTrue(result['awaiting_input'])
        self.assertIn('did you mean', result['message'].lower())

    def test_unclear_answer_with_no_alternate_candidate_still_re_asks_the_pending_question(self):
        """A genuinely unclear yes/no answer — not itself a plausible
        candidate for anything else — must still re-ask the SAME pending
        question rather than being treated as an abandonment. Guards against
        an overly-broad fix that abandons on ANY non-yes/no text."""
        with patch('apps.voice_commands.conversation.match_intent') as mock_match:
            mock_match.return_value = MatchResult(
                intent=NO_MATCH_INTENT, confidence=75.0,
                matched_phrase='check my leave balance', candidate_intent=INTENT_CHECK_LEAVE_BALANCE,
            )
            handle_transcript(self.request, 'garbled leave balance text')

            mock_match.return_value = MatchResult(intent=NO_MATCH_INTENT, confidence=20.0)
            result = handle_transcript(self.request, 'umm maybe')

        self.assertEqual(result['intent'], INTENT_CHECK_LEAVE_BALANCE)
        self.assertTrue(result['awaiting_input'])
        self.assertIn('yes or a no', result['message'].lower())
        # Still the SAME pending clarification, not reset/replaced.
        self.assertEqual(self.store.get(42)['intent'], INTENT_CHECK_LEAVE_BALANCE)
