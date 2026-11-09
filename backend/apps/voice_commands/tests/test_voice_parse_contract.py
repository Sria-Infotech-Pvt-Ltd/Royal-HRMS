"""
Phase 6 contract test: the JSON the REAL /api/voice/parse/ endpoint sends to the frontend.

Existing tests prove the conversation payload (handle_transcript) and the frontend tests prove the mapping from a mocked
response; this closes the gap between them by checking the serialized HTTP response itself, with a real user, a real
face registration and the real attempt cap (private test DB only). The frontend reads exactly these keys:
  data.result.blocked / data.result.retry_after_seconds   -> shared face lockout (postVoiceParse keeps `result`)
  data.is_clarification                                    -> Hindi recovery decision
The backend stays authoritative: the lockout is enforced here with no frontend state involved at all.
"""
from __future__ import annotations

from django.urls import reverse

from apps.attendance.models import AttendancePunch
from apps.attendance.tests_face_id_policy import APPROVAL, OFFICE_LAT, OFFICE_LON, FaceIdTestBase
from apps.attendance.tests_face_mode_matrix import set_face_rules


class VoiceParseEndpointContractTests(FaceIdTestBase):
    def _voice(self, transcript, **extra):
        response = self.client.post(reverse('voice-parse'), {
            'transcript': transcript, 'lang': 'en', 'latitude': OFFICE_LAT, 'longitude': OFFICE_LON, **extra,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def test_every_response_carries_is_clarification_and_a_clarification_sets_it(self):
        ordinary = self._voice('hello')
        self.assertIs(ordinary['is_clarification'], False)
        self.assertTrue(ordinary['success'])

        clarification = self._voice('balance')  # a borderline utterance: "did you mean ...?"
        self.assertIs(clarification['is_clarification'], True)
        self.assertTrue(clarification['awaiting_input'])
        self.assertEqual(clarification['intent'], 'check_leave_balance')

    def test_a_slot_filling_question_is_not_a_clarification(self):
        question = self._voice('apply for sick leave')
        self.assertTrue(question['awaiting_input'])
        self.assertIs(question['is_clarification'], False)

    def test_real_lockout_reaches_the_client_as_result_blocked_with_retry_after_seconds(self):
        set_face_rules(mode=APPROVAL, fallback='none')
        self._register_approved()
        blocked_payload = None
        for index in range(12):
            start = self._voice('punch in')
            if (start['result'] or {}).get('blocked'):
                blocked_payload = start
                break
            self.assertEqual(start['result'], {'awaiting_face_proof': True})
            self.assertIs(start['is_clarification'], False)
            reply = self._voice(
                'punch in', face_embedding=[1.0 + index * 0.01] * 128, liveness_passed=True,
                liveness_score=0.9, capture_session_id=f'contract-{index}',
            )
            if (reply['result'] or {}).get('blocked'):
                blocked_payload = reply
                break
        self.assertIsNotNone(blocked_payload, 'the attempt cap never produced a blocked response')
        self.assertFalse(blocked_payload['success'])
        self.assertFalse(blocked_payload['awaiting_input'])
        self.assertIs(blocked_payload['result']['blocked'], True)
        self.assertIsInstance(blocked_payload['result']['retry_after_seconds'], int)
        self.assertGreater(blocked_payload['result']['retry_after_seconds'], 0)
        self.assertIs(blocked_payload['is_clarification'], False)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_backend_stays_authoritative_without_any_frontend_lockout_state(self):
        """Even a client that forgot/lost its lockout (cleared storage, new tab) is refused again by the server."""
        set_face_rules(mode=APPROVAL, fallback='none')
        self._register_approved()
        for index in range(12):
            self._voice('punch in')
            reply = self._voice(
                'punch in', face_embedding=[1.0 + index * 0.01] * 128, liveness_passed=True,
                liveness_score=0.9, capture_session_id=f'auth-{index}',
            )
            if (reply['result'] or {}).get('blocked'):
                break
        # A brand-new conversation presenting the CORRECT face is still blocked while the cap holds.
        self._voice('punch in')
        again = self._voice(
            'punch in', face_embedding=[0.1] * 128, liveness_passed=True, liveness_score=0.9,
            capture_session_id='after-block',
        )
        self.assertFalse(again['success'])
        self.assertIs(again['result']['blocked'], True)
        self.assertGreater(again['result']['retry_after_seconds'], 0)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())
