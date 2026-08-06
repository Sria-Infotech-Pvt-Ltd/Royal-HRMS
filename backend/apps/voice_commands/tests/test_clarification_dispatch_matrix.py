"""
Regression coverage for a reported bug: "I need to clock myself in" (a
borderline-confidence transcript) triggers the did-you-mean clarification
("did you mean: clock me in?"), and answering "yes" was reported to return
"Sorry, I didn't understand that command." instead of actually executing
clock_in.

Investigation (see PR discussion / commit message for the full trace):
tracing every function in the call chain — matcher.match_intent,
conversation_clarification.start_clarification/continue_clarification,
conversation._dispatch_matched_intent, and clarification.get_pending/
set_pending/clear_pending — plus three independent reproductions (a bare
script against the real cache backend, a Django SimpleTestCase using a
realistic dual-module-patched pending store, and this full 17-intent
matrix) all show the "did you mean" -> "yes" -> dispatch handoff working
correctly for clock_in and for every other registered intent, including the
explicit conversational=True override start_clarification applies for
candidates that are themselves registered conversational: false (see that
function's own docstring, which already names clock_in and
check_leave_balance as the motivating examples).

The one place this DID appear to fail was a test-authoring mistake, not an
application bug: patching apps.voice_commands.conversation.get_pending to
unconditionally return None (the pattern several *single-turn* tests in
this suite correctly use) breaks a *two-turn* sequence, since it makes the
second call blind to the pending state the first call's real set_pending
wrote — the transcript "yes" then really is unrecognized as anything but a
fresh (low-confidence, no-candidate) utterance, and genuinely gets the
generic no-match message. That is correct behavior for that scenario, not
this bug.

This file exists so that if the underlying dispatch ever does regress for
any intent, the failure shows up here immediately and by name, without
requiring every future intent addition to remember to hand-write its own
did-you-mean/yes coverage — the BORDERLINE dict below is the only thing
a new intent needs to add.
"""
from __future__ import annotations

import datetime
import time
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import clarification
from apps.voice_commands.conversation import _EXPIRED_CLARIFICATION_MESSAGE, handle_transcript
from apps.voice_commands.executor import ExecutionResult

_NO_MATCH_MESSAGE = "Sorry, I didn't understand that command."
_DECLINED_MESSAGE = "Okay, is there anything else I can help you with?"


def _fake_request(user_id=42):
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


def _patch_pending_store(store):
    """
    Every conversation_*.py module that can write pending state during THIS
    flow binds its own set_pending/clear_pending import (to avoid a circular
    import back into conversation.py — see each module's own docstring), so
    all of them need patching here, not just conversation.py's — the exact
    gap a too-narrow patch list papered over in this bug's own investigation
    (see this file's module docstring).
    """
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_clarification.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_clarification.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_leave_approval.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_leave_approval.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_payroll.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_payroll.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_attendance_correction.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_attendance_correction.clear_pending', side_effect=store.clear),
    )


# One borderline-confidence (candidate-band: matcher.CLARIFICATION_CONFIDENCE_THRESHOLD
# <= score < matcher.DEFAULT_CONFIDENCE_THRESHOLD, i.e. [60, 80)) transcript per
# registered intent — a truncated/garbled variant of one of that intent's own
# registered phrases, verified (in DidYouMeanYesMatrixTests below) to land in
# that band against the real registry and resolve to that intent as the
# candidate. Adding a new intent to the registry means adding one entry here.
BORDERLINE = {
    'clock_in': 'clock',
    'clock_out': 'me out',
    'check_leave_balance': 'balance',
    'check_leave_status': 'show my leave',
    'cancel_leave': 'cancel my',
    'check_attendance_stats': "how's my this month",
    'check_attendance_summary': 'show my summary',
    'apply_leave': 'apply for',
    'check_team_leave_queue': "show my team's",
    'check_team_attendance': 'show dashboard',
    'approve_leave': 'approve for',
    'reject_leave': 'reject',
    'check_my_payslip': 'my salary',
    'acknowledge_payslip': 'acknowledge my',
    'raise_payslip_query': 'raise a query about',
    'check_employee_payslip': 'payslip',
    'request_attendance_correction': 'request attendance',
}


class DidYouMeanYesMatrixTests(SimpleTestCase):
    """
    For every intent in the registry: a borderline transcript asks
    "did you mean", then "yes" must actually dispatch to that intent's real
    action — mocking only the final DB-writing execute_intent call (per
    module, since which module owns that call varies — see
    _patch_pending_store's docstring), same pattern the rest of this test
    package already uses. Immediate-action intents (clock_in, clock_out,
    check_leave_balance, ...) dispatch straight to execute_intent from the
    borderline text alone. Conversational intents that need more slots than
    a short borderline phrase can carry (apply_leave, request_attendance_
    correction) additionally mock their own slot-extraction step to force
    one-shot completion — same technique the pre-existing raise_payslip_query
    clarification test uses for extract_payslip_query_description. This
    proves the full round trip actually executes, not just that routing
    reached the right module.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        self.request = _fake_request()

    def _run(self, intent, transcript, patch_target, extra_patches=None):
        with patch(patch_target) as mock_execute:
            mock_execute.return_value = ExecutionResult(
                success=True, message=f'{intent}-DONE',
                data={'outcome': 'single_match', 'matched': {'request_id': 'r1'}},
            )
            if extra_patches:
                for target, retval in extra_patches:
                    ctx = patch(target, return_value=retval)
                    ctx.start()
                    self.addCleanup(ctx.stop)

            first = handle_transcript(self.request, transcript)
            self.assertTrue(
                60 <= first['confidence'] < 80,
                f'{intent}: transcript {transcript!r} not in the clarification band, '
                f'confidence={first["confidence"]} — BORDERLINE needs a new value.',
            )
            self.assertEqual(first['intent'], intent, f'{intent}: wrong candidate {first["intent"]}')
            self.assertTrue(first['awaiting_input'], f'{intent}: turn 1 did not await input')
            self.assertIn('did you mean', first['message'].lower())

            second = handle_transcript(self.request, 'yes')
            return second, mock_execute

    def test_clock_in(self):
        # clock_in/clock_out dispatch through conversation_clock_in_face.py,
        # not conversation.py's own execute_intent — see that module. Its
        # is_face_verification_mandatory=False fast path is what keeps this a
        # one-shot dispatch (the mandatory-on path awaits a facial-proof turn
        # instead, covered separately in apps.attendance.tests_face_verification.py).
        second, mock = self._run(
            'clock_in', BORDERLINE['clock_in'], 'apps.voice_commands.conversation_clock_in_face.execute_clock_in',
            extra_patches=[('apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', False)],
        )
        mock.assert_called_once()
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_clock_out(self):
        second, mock = self._run(
            'clock_out', BORDERLINE['clock_out'], 'apps.voice_commands.conversation_clock_in_face.execute_clock_out',
            extra_patches=[('apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', False)],
        )
        mock.assert_called_once()
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_leave_balance(self):
        second, mock = self._run('check_leave_balance', BORDERLINE['check_leave_balance'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_leave_balance')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_leave_status(self):
        second, mock = self._run('check_leave_status', BORDERLINE['check_leave_status'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_leave_status')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_cancel_leave(self):
        second, mock = self._run('cancel_leave', BORDERLINE['cancel_leave'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'cancel_leave')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_attendance_stats(self):
        second, mock = self._run('check_attendance_stats', BORDERLINE['check_attendance_stats'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_attendance_stats')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_attendance_summary(self):
        second, mock = self._run('check_attendance_summary', BORDERLINE['check_attendance_summary'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_attendance_summary')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_team_leave_queue(self):
        second, mock = self._run('check_team_leave_queue', BORDERLINE['check_team_leave_queue'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_team_leave_queue')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_team_attendance(self):
        second, mock = self._run('check_team_attendance', BORDERLINE['check_team_attendance'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_team_attendance')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_my_payslip(self):
        second, mock = self._run('check_my_payslip', BORDERLINE['check_my_payslip'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_my_payslip')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_acknowledge_payslip(self):
        second, mock = self._run('acknowledge_payslip', BORDERLINE['acknowledge_payslip'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'acknowledge_payslip')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_approve_leave(self):
        second, mock = self._run('approve_leave', BORDERLINE['approve_leave'], 'apps.voice_commands.conversation_leave_approval.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'approve_leave')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_reject_leave(self):
        second, mock = self._run('reject_leave', BORDERLINE['reject_leave'], 'apps.voice_commands.conversation_leave_approval.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'reject_leave')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_check_employee_payslip(self):
        second, mock = self._run('check_employee_payslip', BORDERLINE['check_employee_payslip'], 'apps.voice_commands.conversation_payroll.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'check_employee_payslip')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_raise_payslip_query(self):
        second, mock = self._run(
            'raise_payslip_query', BORDERLINE['raise_payslip_query'], 'apps.voice_commands.conversation_payroll.execute_intent',
            extra_patches=[('apps.voice_commands.conversation_payroll.extract_payslip_query_description', 'my payslip amount looks wrong')],
        )
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'raise_payslip_query')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_apply_leave(self):
        full_slots = {
            'leave_type': 'sick',
            'start_date': datetime.date(2026, 7, 22),
            'end_date': datetime.date(2026, 7, 24),
            'reason': 'feeling unwell',
        }
        second, mock = self._run(
            'apply_leave', BORDERLINE['apply_leave'], 'apps.voice_commands.conversation.execute_intent',
            extra_patches=[('apps.voice_commands.conversation.extract_apply_leave_slots', full_slots)],
        )
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'apply_leave')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_request_attendance_correction(self):
        full_slots = {
            'date': datetime.date(2026, 7, 20),
            'punch_type': 'IN',
            'correct_in_time': datetime.time(9, 0),
            'reason': 'FORGOT',
        }
        second, mock = self._run(
            'request_attendance_correction', BORDERLINE['request_attendance_correction'],
            'apps.voice_commands.conversation_attendance_correction.execute_intent',
            extra_patches=[('apps.voice_commands.conversation_attendance_correction.extract_correction_slots', full_slots)],
        )
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'request_attendance_correction')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_no_declines_with_friendly_reset_for_every_intent(self):
        """
        For every intent in BORDERLINE: a "did you mean" clarification
        declined with "no" must get the distinct, friendly reset message —
        never the generic "didn't understand" message, which is reserved for
        transcripts that never matched anything at all. Declining never
        reaches execute_intent for any intent (the decision is made before
        dispatch), so unlike the "yes" tests above this doesn't need a
        per-module execute_intent patch — one loop covers all 17 by name via
        subTest.
        """
        for intent, transcript in BORDERLINE.items():
            with self.subTest(intent=intent):
                self.store._store.clear()

                first = handle_transcript(self.request, transcript)
                self.assertTrue(first['awaiting_input'], f'{intent}: turn 1 did not await input')

                second = handle_transcript(self.request, 'no')

                self.assertEqual(second['message'], _DECLINED_MESSAGE, f'{intent}: wrong decline message')
                self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE, f'{intent}: fell back to generic no-match')
                self.assertTrue(second['success'], f'{intent}: decline must not be reported as a failure')
                self.assertFalse(second['awaiting_input'])
                self.assertNotIn(42, self.store._store, f'{intent}: pending not cleared')


class RealCacheRoundTripTests(SimpleTestCase):
    """
    Everything above patches conversation.py's and its sibling modules'
    set_pending/get_pending/clear_pending with an in-memory dict
    (_FakePendingStore) — deliberately unlike apps.voice_commands.clarification,
    that dict has no TTL and nothing ever evicts it, so it can NEVER
    reproduce "the pending clarification is gone by the time the answer
    arrives" (real TTL expiry, real cache eviction, or any other real
    session-state gap) no matter how it's exercised. This class instead goes
    through the real clarification.py cache functions untouched (the same
    cache backend config/settings.py wires up for every environment,
    including this test run — see get_pending/set_pending/clear_pending's
    own docstrings), for three intents spanning the three different dispatch
    shapes in the registry (an immediate-action intent, a
    conversational-band-only-when-borderline intent, and a fully
    conversational multi-turn intent), to close exactly the "unit tests pass
    but it doesn't actually work live" gap this suite's own bug once fell
    into (see this file's module docstring).
    """

    def setUp(self):
        self._user_id = 90210
        clarification.clear_pending(self._user_id)
        self.addCleanup(clarification.clear_pending, self._user_id)
        self.request = _fake_request(self._user_id)

    def _yes_then_no(self, intent, transcript, execute_patch_target, extra_patches=None):
        # yes leg
        with patch(execute_patch_target) as mock_execute:
            mock_execute.return_value = ExecutionResult(success=True, message=f'{intent}-DONE')
            patches = [patch(target, return_value=retval) for target, retval in (extra_patches or [])]
            for p in patches:
                p.start()
            try:
                first = handle_transcript(self.request, transcript)
                self.assertTrue(first['awaiting_input'], f'{intent}: turn 1 did not await input (real cache)')
                second_yes = handle_transcript(self.request, 'yes')
            finally:
                for p in patches:
                    p.stop()
        mock_execute.assert_called_once()
        self.assertNotEqual(second_yes['message'], _NO_MATCH_MESSAGE)

        # no leg, fresh clarification
        clarification.clear_pending(self._user_id)
        with patch(execute_patch_target) as mock_execute_no:
            handle_transcript(self.request, transcript)
            second_no = handle_transcript(self.request, 'no')
        mock_execute_no.assert_not_called()
        self.assertEqual(second_no['message'], _DECLINED_MESSAGE)
        self.assertIsNone(clarification.get_pending(self._user_id))

    def test_clock_in_yes_and_no_over_the_real_cache(self):
        self._yes_then_no(
            'clock_in', BORDERLINE['clock_in'], 'apps.voice_commands.conversation_clock_in_face.execute_clock_in',
            extra_patches=[('apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', False)],
        )

    def test_check_leave_balance_yes_and_no_over_the_real_cache(self):
        self._yes_then_no('check_leave_balance', BORDERLINE['check_leave_balance'], 'apps.voice_commands.conversation.execute_intent')

    def test_request_attendance_correction_yes_and_no_over_the_real_cache(self):
        full_slots = {
            'date': datetime.date(2026, 7, 20),
            'punch_type': 'IN',
            'correct_in_time': datetime.time(9, 0),
            'reason': 'FORGOT',
        }
        self._yes_then_no(
            'request_attendance_correction', BORDERLINE['request_attendance_correction'],
            'apps.voice_commands.conversation_attendance_correction.execute_intent',
            extra_patches=[('apps.voice_commands.conversation_attendance_correction.extract_correction_slots', full_slots)],
        )


class RealCacheExpiryRegressionTests(SimpleTestCase):
    """
    The actual reported regression, reproduced end to end: a "did you mean"
    clarification whose pending state has genuinely expired (real TTL, real
    cache, real elapsed wall-clock time — not a mocked get_pending) by the
    time the user's "yes" or "no" answer arrives. Before this fix, BOTH
    answers fell all the way through to conversation.py's fully generic
    no-match branch, since nothing there knew a clarification had ever been
    pending — see expired_answer_detector.looks_like_expired_slot_answer's
    now-added parse_yes_no() check. Uses a real, shortened TTL and an actual
    sleep past it, exactly like test_apply_leave_conversation.py's own
    GenuineExpiryAfterRealInactivityTests does for the slot-filling case.
    """

    def setUp(self):
        self._user_id = 90211
        clarification.clear_pending(self._user_id)
        self.addCleanup(clarification.clear_pending, self._user_id)
        self.request = _fake_request(self._user_id)

    @patch('apps.voice_commands.clarification.PENDING_TIMEOUT_SECONDS', 1)
    @patch('apps.voice_commands.conversation.execute_intent')
    def test_yes_after_genuine_expiry_gets_the_timeout_message_not_the_generic_one(self, mock_execute):
        first = handle_transcript(self.request, BORDERLINE['clock_in'])
        self.assertTrue(first['awaiting_input'])

        time.sleep(1.5)
        self.assertIsNone(clarification.get_pending(self._user_id))

        result = handle_transcript(self.request, 'yes')

        mock_execute.assert_not_called()
        self.assertEqual(result['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        self.assertNotEqual(result['message'], _NO_MATCH_MESSAGE)

    @patch('apps.voice_commands.clarification.PENDING_TIMEOUT_SECONDS', 1)
    @patch('apps.voice_commands.conversation.execute_intent')
    def test_no_after_genuine_expiry_gets_the_timeout_message_not_the_generic_one(self, mock_execute):
        first = handle_transcript(self.request, BORDERLINE['check_leave_balance'])
        self.assertTrue(first['awaiting_input'])

        time.sleep(1.5)
        self.assertIsNone(clarification.get_pending(self._user_id))

        result = handle_transcript(self.request, 'no')

        mock_execute.assert_not_called()
        self.assertEqual(result['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        self.assertNotEqual(result['message'], _NO_MATCH_MESSAGE)


class GeofencingRetryDuringClarificationTests(SimpleTestCase):
    """
    Real reported follow-up: clock_in landing in the clarification band
    ("did you mean: clock in?"), confirmed with "yes", dispatches correctly
    but then gets geofence-rejected for missing GPS (office mode, no
    coordinates yet — voice never collects them up front). useVoiceCommand.ts
    catches exactly this rejection, captures the browser's location, and
    silently resubmits the SAME answer transcript ("yes") with coordinates
    attached. Before continue_clarification re-armed pending for this one
    case, that resubmit found no pending state (continue_clarification's own
    clear_pending had already fired on the first "yes") and was misread as a
    stale answer to an expired clarification — clock-in never actually
    completed no matter how quickly the user answered.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        # clock_in dispatches through conversation_clock_in_face.py, not
        # conversation.py's own execute_intent — see that module. Its
        # is_face_verification_mandatory=False fast path is what keeps this
        # geofence-retry mechanic identical to before that module existed.
        mandatory_patcher = patch(
            'apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', return_value=False,
        )
        mandatory_patcher.start()
        self.addCleanup(mandatory_patcher.stop)
        self.request = _fake_request()

    def test_yes_rejected_for_missing_gps_stays_pending_then_succeeds_on_located_retry(self):
        first = handle_transcript(self.request, BORDERLINE['clock_in'])
        self.assertTrue(first['awaiting_input'])

        with patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in') as mock_execute:
            mock_execute.return_value = ExecutionResult(
                success=False,
                message=(
                    'Your location is required to clock in at this branch. '
                    'Please allow location access in your browser and try again.'
                ),
            )
            rejected = handle_transcript(self.request, 'yes')

        self.assertFalse(rejected['success'])
        # Not re-labeled as a stale/expired answer -- the clarification must
        # still be alive for the browser's silent retry to complete.
        self.assertNotEqual(rejected['message'], _EXPIRED_CLARIFICATION_MESSAGE)
        self.assertNotEqual(rejected['message'], _NO_MATCH_MESSAGE)
        self.assertIn(42, self.store._store)
        self.assertEqual(self.store._store[42]['intent'], 'clock_in')

        with patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in') as mock_execute_located:
            mock_execute_located.return_value = ExecutionResult(
                success=True, message='You have been clocked in successfully.',
            )
            located = handle_transcript(self.request, 'yes', latitude=17.38, longitude=78.48)

        mock_execute_located.assert_called_once()
        self.assertEqual(mock_execute_located.call_args.kwargs['latitude'], 17.38)
        self.assertEqual(mock_execute_located.call_args.kwargs['longitude'], 78.48)
        self.assertTrue(located['success'])
        self.assertEqual(located['message'], 'You have been clocked in successfully.')
        self.assertNotIn(42, self.store._store)  # cleared once it actually succeeds

    def test_non_gps_rejection_is_terminal_and_does_not_stay_pending(self):
        """A DIFFERENT failure (e.g. already clocked in) must not be treated
        as retryable -- only the specific missing-GPS message re-arms."""
        handle_transcript(self.request, BORDERLINE['clock_in'])

        with patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in') as mock_execute:
            mock_execute.return_value = ExecutionResult(success=False, message='You have already clocked in today.')
            result = handle_transcript(self.request, 'yes')

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'You have already clocked in today.')
        self.assertNotIn(42, self.store._store)


class ReportedBugLiteralTranscriptTests(SimpleTestCase):
    """
    The exact sequence from the bug report, word for word — kept as its own
    test (distinct from the generic matrix above) so a regression here shows
    up under this specific, human-readable name rather than only as
    "test_clock_in" in a table.
    """

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        # clock_in dispatches through conversation_clock_in_face.py, not
        # conversation.py's own execute_intent — see that module.
        mandatory_patcher = patch(
            'apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', return_value=False,
        )
        mandatory_patcher.start()
        self.addCleanup(mandatory_patcher.stop)
        execute_patcher = patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in')
        self.mock_execute = execute_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')

        self.request = _fake_request()

    def test_i_need_to_clock_myself_in_then_yes_actually_clocks_in(self):
        """
        At the time this test was first written, "I need to clock myself in"
        scored 61.11 against clock_in's OLD best phrase ("clock me in") — just
        inside the clarification band [60, 80) — so this test drove it through
        the did-you-mean -> yes -> dispatch handoff.

        A later, unrelated fix (registry/intents_en.yaml: clock_in/clock_out
        gained "i need to clock in"/"i need to clockin" and their clock_out
        equivalents, to stop "i need to clockin myself" colliding with
        request_attendance_correction's "i need to fix my punch" — see that
        file's comments and test_matcher.py's collision tests) gave clock_in
        real "i need to ___" phrase coverage for the first time. This exact
        transcript now scores 83.72 against the new "i need to clock in" —
        past DEFAULT_CONFIDENCE_THRESHOLD (80) — so it dispatches immediately,
        same intent, zero clarification round trip. That's a strict
        improvement (less friction for an unambiguous command), not a
        regression: the clarification handoff itself is still fully exercised
        by DidYouMeanYesMatrixTests.test_clock_in/test_clock_out above via
        BORDERLINE's still-genuinely-borderline 'clock'/'me out'.
        """
        result = handle_transcript(self.request, 'I need to clock myself in')

        self.mock_execute.assert_called_once()
        self.assertEqual(result['message'], 'You have been clocked in successfully.')
        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
