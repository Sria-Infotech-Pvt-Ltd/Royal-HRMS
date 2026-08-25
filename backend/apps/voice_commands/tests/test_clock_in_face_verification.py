"""
Coverage for conversation_clock_in_face.py — the voice-initiated clock-in/out
facial proof turn, exercised ONLY when AttendanceFaceVerificationRules.
is_mandatory is on (the mandatory=False fast path is covered instead by
test_conversational_signaling.py/test_clarification_dispatch_matrix.py,
which predate this module and assert the "feature off" behaviour is
unchanged).

All DB-touching collaborators (FaceRegistrationRequest, GeofencingService,
FaceVerificationService, the actual punch executors) are mocked at their
conversation_clock_in_face.py import site, same convention the rest of this
SimpleTestCase-based package uses — see e.g. test_clarification_dispatch_matrix.py.
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
    rejection_message="We couldn't match your face to your registered Face ID. You can try again, or "
                       "contact your HR representative if this keeps happening.",
)
_BLOCKED_OUTCOME = FaceVerificationOutcome(
    required=True, embedding_provided=True, is_match=False, distance=None,
    rejection_message='Too many failed face verification attempts. Please wait a few minutes before trying again, or contact HR if this keeps happening.',
    blocked=True,
)


class NoRegistrationTests(SimpleTestCase):
    """Item 5 — an employee with no approved face ID is told to contact HR/
    their manager, not left stuck in a dead-end dialogue."""

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
        mock_model.objects.filter.return_value.exists.return_value = False
        mock_model.STATUS_APPROVED = 'approved'

    def test_no_registration_points_to_hr_and_does_not_stay_pending(self):
        result = handle_transcript(_fake_request(), 'clock in')

        self.assertFalse(result['success'])
        self.assertIn('hr', result['message'].lower())
        self.assertIn('manager', result['message'].lower())
        self.assertIsNone(self.store.get(42))


class GeofenceReuseTests(SimpleTestCase):
    """The facial-proof flow must reuse GeofencingService.validate as-is —
    a rejection surfaces before the camera step, in the same shape the
    existing GPS-missing retry (useVoiceCommand.ts) already expects."""

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
            result = handle_transcript(_fake_request(), 'clock in')

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], rejected.rejection_message)
        self.assertIsNone(self.store.get(42))

    def test_geofence_allowed_opens_the_facial_proof_turn(self):
        with patch('apps.voice_commands.conversation_clock_in_face.GeofencingService.validate', return_value=_ALLOWED_GEOFENCE):
            result = handle_transcript(_fake_request(), 'clock in')

        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['conversational'])
        self.assertTrue(result['result']['awaiting_face_proof'])
        pending = self.store.get(42)
        self.assertEqual(pending['intent'], 'clock_in')
        self.assertEqual(pending['slots']['stage'], 'awaiting_face_proof')


class FacialProofTurnTests(SimpleTestCase):
    """Second+ turn — a descriptor comes back from FaceVerificationModal."""

    def setUp(self):
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)
        self.store.set(42, 'clock_in', {
            'stage': 'awaiting_face_proof', 'attendance_mode': 'office',
            'latitude': 17.38, 'longitude': 78.48, 'attempt': 0,
        })
        self.request = _fake_request()

    def test_match_completes_the_punch(self):
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MATCH_OUTCOME), \
             patch('apps.voice_commands.conversation_clock_in_face.execute_clock_in') as mock_execute:
            mock_execute.return_value = ExecutionResult(success=True, message='You have been clocked in successfully.')
            result = handle_transcript(self.request, 'clock in', face_embedding=[0.1, 0.2], liveness_passed=True, liveness_score=0.9)

        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs['latitude'], 17.38)
        self.assertEqual(call_kwargs['longitude'], 78.48)
        self.assertEqual(call_kwargs['face_embedding'], [0.1, 0.2])
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'You have been clocked in successfully.')
        self.assertIsNone(self.store.get(42))

    def test_mismatch_reprompts_with_attempt_retained(self):
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MISMATCH_OUTCOME):
            result = handle_transcript(self.request, 'clock in', face_embedding=[0.1, 0.2])

        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['success'])  # mid-dialogue retry, not a terminal failure
        # result must carry awaiting_face_proof=True (not None) — this is what
        # useVoiceCommand.ts's isAwaitingFaceProof() keys on to reopen
        # FaceVerificationModal for the retry; a None result here left the
        # camera never reopening after a mismatch (found 2026-08-13).
        self.assertTrue(result['result']['awaiting_face_proof'])
        pending = self.store.get(42)
        self.assertEqual(pending['slots']['attempt'], 1)

    def test_mismatch_retry_message_is_the_backend_specific_reason_not_a_generic_string(self):
        """FR-2: this used to always show a hardcoded generic retry line
        regardless of why verify_for_punch actually rejected the attempt —
        the same distinct rejection_message that already reaches the user
        correctly on web must now reach them on voice too."""
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MISMATCH_OUTCOME):
            result = handle_transcript(self.request, 'clock in', face_embedding=[0.1, 0.2])

        self.assertEqual(result['message'], _MISMATCH_OUTCOME.rejection_message)
        self.assertNotIn('lighting', result['message'].lower())

    def test_third_mismatch_gives_up_and_suggests_manual_clock_in(self):
        self.store.set(42, 'clock_in', {
            'stage': 'awaiting_face_proof', 'attendance_mode': 'office',
            'latitude': 17.38, 'longitude': 78.48, 'attempt': 2,
        })
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_MISMATCH_OUTCOME):
            result = handle_transcript(self.request, 'clock in', face_embedding=[0.1, 0.2])

        self.assertFalse(result['success'])
        self.assertFalse(result['awaiting_input'])
        self.assertIn('manual clock in', result['message'].lower())
        self.assertIsNone(self.store.get(42))

    def test_blocked_outcome_is_terminal_on_the_first_attempt_not_retried(self):
        """Attempt-cap/replay rejections (outcome.blocked) must never consume
        the 3-try budget with a retry prompt — they're already terminal."""
        with patch('apps.voice_commands.conversation_clock_in_face.FaceVerificationService.verify_for_punch', return_value=_BLOCKED_OUTCOME):
            result = handle_transcript(self.request, 'clock in', face_embedding=[0.1, 0.2])

        self.assertFalse(result['success'])
        self.assertFalse(result['awaiting_input'])
        self.assertEqual(result['message'], _BLOCKED_OUTCOME.rejection_message)
        self.assertIsNone(self.store.get(42))

    def test_missing_embedding_on_continuation_reasks_without_consuming_an_attempt(self):
        result = handle_transcript(self.request, 'clock in')

        self.assertTrue(result['awaiting_input'])
        self.assertTrue(result['result']['awaiting_face_proof'])
        pending = self.store.get(42)
        self.assertEqual(pending['slots']['attempt'], 0)
