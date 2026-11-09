"""
Voice Punch In/Out follows the SAME server Face ID policy as the web punch (services_face_policy.guidance), and a
face-verification block keeps its countdown (`blocked` + `retry_after_seconds`) all the way back to the client.

Two layers:
  - SimpleTestCase tests stub the policy/outcome to pin the voice wiring (messages, fallback, payload shape).
  - DB tests use the real policy, real registrations and the real verification service (private test DB only) and
    compare voice against the web status endpoint, so the two channels cannot drift.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.attendance.models import AttendancePunch, FaceRegistrationRequest
from apps.attendance.services_face_antispoofing import MAX_FAILED_ATTEMPTS
from apps.attendance.services_face_matching import FaceVerificationBlockedError, FaceVerificationOutcome
from apps.attendance.tests_face_id_policy import (
    APPROVAL, HR_ONLY, OFFICE_LAT, OFFICE_LON, SELF, FaceIdTestBase, _embedding,
)
from apps.attendance.tests_face_mode_matrix import NOT_REGISTERED, PENDING, REJECTED, set_face_rules
from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.conversation_clock_in_face import continue_voice_clock_punch
from apps.voice_commands.executor_attendance import _execute_punch
from apps.voice_commands.executor_result import ExecutionResult

_FACE = 'apps.voice_commands.conversation_clock_in_face'


class _FakePendingStore:
    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _policy(state, *, fallback=False, message='Policy message for this state.'):
    return {
        'is_mandatory': True, 'state': state, 'requires_face_to_punch': state == 'approved',
        'fallback_active': fallback, 'message': message,
    }


def _fake_request(user_id=42):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    request.is_secure.return_value = True
    return request


class VoicePunchFollowsServerPolicyTests(SimpleTestCase):
    """Policy stubbed: voice must show the server's own message, never open the camera for an employee without an
    approved Face ID, and take the same-turn fallback path only when the policy says the fallback is active."""

    def setUp(self):
        self.store = _FakePendingStore()
        for target, fn in (
            ('apps.voice_commands.conversation.get_pending', self.store.get),
            ('apps.voice_commands.conversation.set_pending', self.store.set),
            ('apps.voice_commands.conversation.clear_pending', self.store.clear),
            (f'{_FACE}.set_pending', self.store.set),
            (f'{_FACE}.clear_pending', self.store.clear),
        ):
            patcher = patch(target, side_effect=fn)
            patcher.start()
            self.addCleanup(patcher.stop)
        mandatory = patch(f'{_FACE}.is_face_verification_mandatory', return_value=True)
        mandatory.start()
        self.addCleanup(mandatory.stop)

    def _run(self, policy, transcript='punch in'):
        with patch(f'{_FACE}.face_policy_guidance', return_value=policy), \
             patch(f'{_FACE}.execute_clock_in') as mock_in, patch(f'{_FACE}.execute_clock_out') as mock_out, \
             patch(f'{_FACE}.GeofencingService.validate') as mock_geo:
            mock_in.return_value = ExecutionResult(success=True, message='Punched in successfully.')
            mock_out.return_value = ExecutionResult(success=True, message='Punched out successfully.')
            mock_geo.return_value = MagicMock(is_allowed=True)
            result = handle_transcript(_fake_request(), transcript)
        return result, mock_in, mock_out, mock_geo

    def test_not_registered_pending_rejected_show_the_server_message_and_never_open_the_camera(self):
        for state in ('not_registered', 'pending', 'rejected'):
            with self.subTest(state):
                message = f'Server instruction for {state}.'
                result, mock_in, _, mock_geo = self._run(_policy(state, message=message))
                self.assertFalse(result['success'])
                self.assertEqual(result['message'], message)
                self.assertFalse(result['awaiting_input'])
                self.assertFalse((result['result'] or {}).get('awaiting_face_proof'))
                self.assertIsNone(self.store.get(42))
                mock_in.assert_not_called()
                mock_geo.assert_not_called()

    def test_no_voice_specific_contact_hr_text_remains(self):
        result, *_ = self._run(_policy('not_registered', message='Register first, then come back.'))
        self.assertEqual(result['message'], 'Register first, then come back.')

    def test_active_fallback_punches_in_the_same_turn_without_the_camera(self):
        for state in ('not_registered', 'pending', 'rejected'):
            with self.subTest(state):
                result, mock_in, _, mock_geo = self._run(_policy(state, fallback=True))
                self.assertTrue(result['success'])
                self.assertEqual(result['message'], 'Punched in successfully.')
                self.assertFalse(result['awaiting_input'])
                self.assertIsNone(self.store.get(42))
                mock_in.assert_called_once()

    def test_active_fallback_applies_to_punch_out_too(self):
        _, _, mock_out, _ = self._run(_policy('not_registered', fallback=True), transcript='punch out')
        mock_out.assert_called_once()

    def test_approved_opens_the_face_proof_step_after_the_geofence_check(self):
        result, mock_in, _, mock_geo = self._run(_policy('approved'))
        self.assertTrue(result['awaiting_input'])
        self.assertEqual(result['result'], {'awaiting_face_proof': True})
        mock_geo.assert_called_once()
        mock_in.assert_not_called()
        self.assertIsNotNone(self.store.get(42))


class VoiceLockoutPayloadTests(SimpleTestCase):
    """A terminal face-verification block keeps blocked/retry_after_seconds on every voice path."""

    def setUp(self):
        self.store = _FakePendingStore()
        for target, fn in (
            (f'{_FACE}.set_pending', self.store.set), (f'{_FACE}.clear_pending', self.store.clear),
        ):
            patcher = patch(target, side_effect=fn)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _pending(self):
        return {'intent': 'clock_in', 'slots': {
            'stage': 'awaiting_face_proof', 'attendance_mode': None, 'latitude': None, 'longitude': None, 'attempt': 0,
        }}

    def test_blocked_outcome_returns_blocked_and_retry_after_seconds(self):
        blocked = FaceVerificationOutcome(
            required=True, embedding_provided=True, is_match=False, distance=None,
            rejection_message='Too many failed face verification attempts.', blocked=True, retry_after_seconds=120,
        )
        with patch(f'{_FACE}.FaceVerificationService.verify_for_punch', return_value=blocked):
            result = continue_voice_clock_punch(_fake_request(), self._pending(), [0.1] * 128, True, 0.9, 'sess')
        self.assertFalse(result['success'])
        self.assertFalse(result['awaiting_input'])
        self.assertEqual(result['result'], {'blocked': True, 'retry_after_seconds': 120})
        self.assertEqual(result['message'], 'Too many failed face verification attempts.')
        self.assertIn('is_clarification', result)
        self.assertIsNone(self.store.get(42))

    def test_ordinary_mismatch_has_no_lockout_payload_and_stays_retryable(self):
        mismatch = FaceVerificationOutcome(
            required=True, embedding_provided=True, is_match=False, distance=0.9, rejection_message='No match.',
        )
        with patch(f'{_FACE}.FaceVerificationService.verify_for_punch', return_value=mismatch):
            result = continue_voice_clock_punch(_fake_request(), self._pending(), [0.1] * 128, True, 0.9, 'sess')
        self.assertTrue(result['awaiting_input'])
        self.assertEqual(result['result'], {'awaiting_face_proof': True})

    def test_execute_punch_keeps_the_countdown_from_a_blocked_error(self):
        serializer = MagicMock()
        serializer.is_valid.return_value = True
        serializer.validated_data.copy.return_value = {}
        request = MagicMock()
        request.META = {}
        request.is_secure.return_value = True
        with patch('apps.voice_commands.executor_attendance.PunchWriteSerializer', return_value=serializer), \
             patch('apps.voice_commands.executor_attendance.PunchService.record_punch',
                   side_effect=FaceVerificationBlockedError('Blocked for now.', 90)):
            outcome = _execute_punch(request, 'IN', 'office', 'ok')
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.message, 'Blocked for now.')
        self.assertEqual(outcome.data, {'blocked': True, 'retry_after_seconds': 90})

    def test_execute_punch_plain_permission_error_has_no_lockout_payload(self):
        serializer = MagicMock()
        serializer.is_valid.return_value = True
        serializer.validated_data.copy.return_value = {}
        request = MagicMock()
        request.META = {}
        request.is_secure.return_value = True
        with patch('apps.voice_commands.executor_attendance.PunchWriteSerializer', return_value=serializer), \
             patch('apps.voice_commands.executor_attendance.PunchService.record_punch',
                   side_effect=PermissionError('Plain refusal.')):
            outcome = _execute_punch(request, 'IN', 'office', 'ok')
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.data)


class VoiceMatchesWebPolicyTests(FaceIdTestBase):
    """Real policy and real registrations: voice and the web status endpoint must say the same thing."""

    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)

    def _voice(self, transcript='punch in', **kwargs):
        request = APIRequestFactory().post('/api/voice/parse/', {}, format='json')
        request.user = self.employee
        return handle_transcript(request, transcript, latitude=OFFICE_LAT, longitude=OFFICE_LON, **kwargs)

    def _put_in_state(self, state):
        if state == 'approved':
            self._register_approved()
        elif state in (PENDING, REJECTED):
            FaceRegistrationRequest.objects.create(
                employee=self.employee, face_embedding=_embedding(), liveness_passed=True,
                status=(FaceRegistrationRequest.STATUS_PENDING if state == PENDING
                        else FaceRegistrationRequest.STATUS_REJECTED),
            )

    def test_voice_message_equals_the_web_status_message_for_every_unapproved_state_and_mode(self):
        for mode in (SELF, HR_ONLY, APPROVAL):
            for state in (NOT_REGISTERED, PENDING, REJECTED):
                with self.subTest(f'{mode}/{state}'):
                    FaceRegistrationRequest.objects.filter(employee=self.employee).delete()
                    set_face_rules(mode=mode, fallback='none')
                    self._put_in_state(state)
                    web_message = self._status()['message']
                    result = self._voice()
                    self.assertFalse(result['success'])
                    self.assertEqual(result['message'], web_message)
                    self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_fallback_enabled_voice_punch_is_recorded_and_flagged_like_web(self):
        for state in (NOT_REGISTERED, PENDING):
            with self.subTest(state):
                FaceRegistrationRequest.objects.filter(employee=self.employee).delete()
                AttendancePunch.objects.filter(employee=self.employee).delete()
                set_face_rules(mode=APPROVAL, fallback='until_approved')
                self._put_in_state(state)
                self.assertTrue(self._status()['fallback_active'])
                result = self._voice()
                self.assertTrue(result['success'], result)
                punch = AttendancePunch.objects.get(employee=self.employee)
                self.assertTrue(punch.face_fallback)
                self.assertEqual(punch.source, 'voice')

    def test_approved_employee_gets_the_camera_step_and_no_punch_yet(self):
        set_face_rules(mode=APPROVAL, fallback='until_approved')
        self._put_in_state('approved')
        result = self._voice()
        self.assertTrue(result['awaiting_input'])
        self.assertEqual(result['result'], {'awaiting_face_proof': True})
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_real_attempt_cap_returns_the_countdown_through_voice(self):
        set_face_rules(mode=APPROVAL, fallback='none')
        self._register_approved()
        pending = {'intent': 'clock_in', 'slots': {
            'stage': 'awaiting_face_proof', 'attendance_mode': 'office',
            'latitude': OFFICE_LAT, 'longitude': OFFICE_LON, 'attempt': 0,
        }}
        request = APIRequestFactory().post('/api/voice/parse/', {}, format='json')
        request.user = self.employee
        base = _embedding(0.1)
        result = None
        for index in range(MAX_FAILED_ATTEMPTS + 1):
            wrong = [value + 1.0 + index * 0.01 for value in base]
            result = continue_voice_clock_punch(request, pending, wrong, True, 0.9, f'cap-{index}')
            if (result['result'] or {}).get('blocked'):
                break
        self.assertTrue((result['result'] or {}).get('blocked'), result)
        self.assertGreater(result['result']['retry_after_seconds'], 0)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())


class VoiceRequiresApprovedAndActiveRegistrationTests(FaceIdTestBase):
    """Phase 7.1: a registration only counts when it is BOTH approved AND active (services_face_policy.
    active_registration). Voice, the web status endpoint, the fallback rule and the punch-time match must agree."""

    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)

    def _row(self, *, status, is_active):
        return FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=_embedding(), liveness_passed=True, status=status,
            is_active=is_active,
        )

    def _voice(self, transcript='punch in', **kwargs):
        request = APIRequestFactory().post('/api/voice/parse/', {}, format='json')
        request.user = self.employee
        return handle_transcript(request, transcript, latitude=OFFICE_LAT, longitude=OFFICE_LON, **kwargs)

    def test_approved_but_inactive_is_not_a_valid_registration_and_never_opens_the_camera(self):
        set_face_rules(mode=APPROVAL, fallback='none')
        self._row(status=FaceRegistrationRequest.STATUS_APPROVED, is_active=False)
        status = self._status()
        self.assertEqual(status['state'], 'not_registered')
        self.assertFalse(status['requires_face_to_punch'])
        result = self._voice()
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], status['message'])
        self.assertFalse((result['result'] or {}).get('awaiting_face_proof'))
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_a_matching_face_cannot_use_an_inactive_registration_to_punch(self):
        set_face_rules(mode=APPROVAL, fallback='none')
        self._row(status=FaceRegistrationRequest.STATUS_APPROVED, is_active=False)
        # Even a conversation already sitting at the face-proof stage (e.g. the registration was deactivated mid-dialogue)
        # cannot be completed: the accept path re-resolves the registration and finds none.
        pending = {'intent': 'clock_in', 'slots': {
            'stage': 'awaiting_face_proof', 'attendance_mode': 'office',
            'latitude': OFFICE_LAT, 'longitude': OFFICE_LON, 'attempt': 0,
        }}
        request = APIRequestFactory().post('/api/voice/parse/', {}, format='json')
        request.user = self.employee
        result = continue_voice_clock_punch(request, pending, _embedding(), True, 0.9, 'inactive-1')
        self.assertFalse(result['success'])
        self.assertFalse(result['awaiting_input'])
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_approved_but_inactive_gets_the_fallback_only_if_the_policy_allows_it(self):
        set_face_rules(mode=APPROVAL, fallback='until_approved')
        self._row(status=FaceRegistrationRequest.STATUS_APPROVED, is_active=False)
        self.assertTrue(self._status()['fallback_active'])
        result = self._voice()
        self.assertTrue(result['success'], result)
        self.assertTrue(AttendancePunch.objects.get(employee=self.employee).face_fallback)

    def test_active_but_not_approved_is_not_treated_as_approved(self):
        set_face_rules(mode=APPROVAL, fallback='none')
        self._row(status=FaceRegistrationRequest.STATUS_PENDING, is_active=True)
        status = self._status()
        self.assertEqual(status['state'], 'pending')
        self.assertFalse(status['requires_face_to_punch'])
        result = self._voice()
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], status['message'])
        self.assertFalse((result['result'] or {}).get('awaiting_face_proof'))

    def test_active_but_not_approved_does_not_block_the_fallback(self):
        # Before 7.1 such a row made the policy say "approved", which switched the fallback off for the employee.
        set_face_rules(mode=APPROVAL, fallback='until_approved')
        self._row(status=FaceRegistrationRequest.STATUS_REJECTED, is_active=True)
        self.assertEqual(self._status()['state'], 'rejected')
        self.assertTrue(self._status()['fallback_active'])

    def test_an_old_approval_does_not_hide_a_newer_pending_request(self):
        set_face_rules(mode=APPROVAL, fallback='none')
        self._row(status=FaceRegistrationRequest.STATUS_APPROVED, is_active=False)
        self._row(status=FaceRegistrationRequest.STATUS_PENDING, is_active=False)
        self.assertEqual(self._status()['state'], 'pending')
        self.assertFalse(self._voice()['success'])

    def test_approved_and_active_still_opens_the_camera(self):
        set_face_rules(mode=APPROVAL, fallback='until_approved')
        self._row(status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True)
        self.assertEqual(self._status()['state'], 'approved')
        result = self._voice()
        self.assertTrue(result['awaiting_input'])
        self.assertEqual(result['result'], {'awaiting_face_proof': True})

    def test_the_policy_and_the_punch_time_match_share_one_definition(self):
        from apps.attendance.services_face_matching import FaceVerificationService
        from apps.attendance.services_face_policy import active_registration

        cases = (
            (FaceRegistrationRequest.STATUS_APPROVED, True, True),
            (FaceRegistrationRequest.STATUS_APPROVED, False, False),
            (FaceRegistrationRequest.STATUS_PENDING, True, False),
        )
        for status, is_active, valid in cases:
            with self.subTest(f'{status}/active={is_active}'):
                FaceRegistrationRequest.objects.filter(employee=self.employee).delete()
                self._row(status=status, is_active=is_active)
                self.assertEqual(active_registration(self.employee) is not None, valid)
                self.assertEqual(FaceVerificationService._resolve_active_registration(self.employee) is not None, valid)
