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
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import ExecutionResult

_NO_MATCH_MESSAGE = "Sorry, I didn't understand that command."


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
        second, mock = self._run('clock_in', BORDERLINE['clock_in'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'clock_in')
        self.assertNotEqual(second['message'], _NO_MATCH_MESSAGE)

    def test_clock_out(self):
        second, mock = self._run('clock_out', BORDERLINE['clock_out'], 'apps.voice_commands.conversation.execute_intent')
        mock.assert_called_once()
        self.assertEqual(mock.call_args.args[0], 'clock_out')
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

        execute_patcher = patch('apps.voice_commands.conversation.execute_intent')
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
        self.assertEqual(self.mock_execute.call_args.args[0], 'clock_in')
        self.assertEqual(result['message'], 'You have been clocked in successfully.')
        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
