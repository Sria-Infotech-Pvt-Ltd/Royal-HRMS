"""
Coverage for conversation_clock_in_face.py's clock_out path.

conversation_clock_in_face.py handles clock_in AND clock_out through the
same functions (start_voice_clock_punch/continue_voice_clock_punch,
dispatched via _executor_for) — see conversation.py's single
`if intent in (INTENT_CLOCK_IN, INTENT_CLOCK_OUT)` dispatch line and the
registry's symmetric clock_in/clock_out phrase lists
(registry/intents_en.yaml). There was previously no test exercising "clock
out" end-to-end through that shared code, only "clock in"
(test_clock_in_face_verification.py) — this file closes that gap and locks
in that the location-check-then-facial-proof order applies identically to
clock-out.

Mirrors test_clock_in_face_verification.py's structure and mocking
conventions exactly, substituting the clock_out intent/executor/phrase.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.attendance.services_face_matching import FaceVerificationOutcome
from apps.attendance.services_geofencing import GeofenceResult
from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import ExecutionResult


def _fake_request(user_id=42):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    request.is_secure.return_value = True
    return request


class _FakePendingStore:
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
        patch('apps.voice_commands.conversation_clock_in_face.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_clock_in_face.clear_pending', side_effect=store.clear),
    )


_ALLOWED_GEOFENCE = GeofenceResult(
    is_allowed=True, is_inside_geofence=True, calculated_distance=12.0, branch=None, rejection_message=None,
)
_MATCH_OUTCOME = FaceVerificationOutcome(
    required=True, embedding_provided=True, is_match=True, distance=0.2, rejection_message=None,
)
_MISMATCH_OUTCOME = FaceVerificationOutcome(
    required=True, embedding_provided=True, is_match=False, distance=0.9,
    rejection_message='Face verification failed. Please try again in good lighting, facing the camera directly.',
)
_BLOCKED_OUTCOME = FaceVerificationOutcome(
    required=True, embedding_provided=True, is_match=False, distance=None,
    rejection_message='Too many failed face verification attempts. Please wait a few minutes before trying again, or contact HR if this keeps happening.',
    blocked=True,
)


class ClockOutGeofenceReuseTests(SimpleTestCase):
    """Same contract as clock_in's GeofenceReuseTests: geofence is checked —
    and can reject — BEFORE the facial proof turn ever opens."""

    def setUp(self):
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)
        mandatory = patch('apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', return_value=True)
        mandatory.start()
        self.addCleanup(mandatory.stop)
        registration = patch('apps.voice_commands.conversation_clock_in_face.FaceRegistrationRequest')
        mock_model = registration.start()
        self.addCleanup(registration.stop)
        mock_model.objects.filter.return_value.exists.return_value = True

    def test_geofence_rejection_is_terminal_and_not_pending(self):
        rejected = GeofenceResult(
            is_allowed=False, is_inside_geofence=False, calculated_distance=500.0,
            branch=None, rejection_message='Your location is required to clock in at this branch. Please allow location access in your browser and try again.',
        )
        with patch('apps.voice_commands.conversation_clock_in_face.GeofencingService.validate', return_value=rejected):
            result = handle_transcript(_fake_request(), 'clock out')

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], rejected.rejection_message)
        self.assertIsNone(self.store.get(42))

    def test_geofence_allowed_opens_the_facial_proof_turn(self):
        with patch('apps.voice_commands.conversation_clock_in_face.GeofencingService.validate', return_value=_ALLOWED_GEOFENCE):
            result = handle_transcript(_fake_request(), 'clock out')

        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['conversational'])
        self.assertTrue(result['result']['awaiting_face_proof'])
        pending = self.store.get(42)
        self.assertEqual(pending['intent'], 'clock_out')
        self.assertEqual(pending['slots']['stage'], 'awaiting_face_proof')


class ClockOutFacialProofTurnTests(SimpleTestCase):
    """Second+ turn for clock_out — a descriptor comes back from
    FaceVerificationModal, routed through execute_clock_out (not
    execute_clock_in) once matched."""

    def setUp(self):
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)
        self.store.set(42, 'clock_out', {
            'stage': 'awaiting_face_proof', 'attendance_mode': 'office',
            'latitude': 17.38, 'longitude': 78.48, 'attempt': 0,
        })
        self.request = _fake_request()

    def test_match_completes_the_punch_via_execute_clock_out(self):
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MATCH_OUTCOME), \
             patch('apps.voice_commands.conversation_clock_in_face.execute_clock_out') as mock_execute_out, \
             patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in') as mock_execute_in:
            mock_execute_out.return_value = ExecutionResult(success=True, message='You have been clocked out successfully.')
            result = handle_transcript(self.request, 'clock out', face_embedding=[0.1, 0.2], liveness_passed=True, liveness_score=0.9)

        mock_execute_out.assert_called_once()
        mock_execute_in.assert_not_called()
        call_kwargs = mock_execute_out.call_args.kwargs
        self.assertEqual(call_kwargs['latitude'], 17.38)
        self.assertEqual(call_kwargs['longitude'], 78.48)
        self.assertEqual(call_kwargs['face_embedding'], [0.1, 0.2])
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'You have been clocked out successfully.')
        self.assertIsNone(self.store.get(42))

    def test_mismatch_reprompts_with_attempt_retained(self):
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MISMATCH_OUTCOME):
            result = handle_transcript(self.request, 'clock out', face_embedding=[0.1, 0.2])

        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['success'])  # mid-dialogue retry, not a terminal failure
        # result must carry awaiting_face_proof=True (not None) — this is what
        # useVoiceCommand.ts's isAwaitingFaceProof() keys on to reopen
        # FaceVerificationModal for the retry; a None result here left the
        # camera never reopening after a mismatch (found 2026-08-13).
        self.assertTrue(result['result']['awaiting_face_proof'])
        pending = self.store.get(42)
        self.assertEqual(pending['slots']['attempt'], 1)

    def test_third_mismatch_gives_up_and_suggests_manual_clock_in(self):
        self.store.set(42, 'clock_out', {
            'stage': 'awaiting_face_proof', 'attendance_mode': 'office',
            'latitude': 17.38, 'longitude': 78.48, 'attempt': 2,
        })
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MISMATCH_OUTCOME):
            result = handle_transcript(self.request, 'clock out', face_embedding=[0.1, 0.2])

        self.assertFalse(result['success'])
        self.assertFalse(result['awaiting_input'])
        # Same manual-button fallback message clock_in gives — the dashboard's
        # Clock In/Out button is a single toggle, so the copy stays generic.
        self.assertIn('manual clock in', result['message'].lower())
        self.assertIsNone(self.store.get(42))

    def test_blocked_outcome_is_terminal_on_the_first_attempt_not_retried(self):
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_BLOCKED_OUTCOME):
            result = handle_transcript(self.request, 'clock out', face_embedding=[0.1, 0.2])

        self.assertFalse(result['success'])
        self.assertFalse(result['awaiting_input'])
        self.assertEqual(result['message'], _BLOCKED_OUTCOME.rejection_message)
        self.assertIsNone(self.store.get(42))
