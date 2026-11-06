"""Phase 2C proof: Face ID registration mode x employee state x fallback matrix, and the consent-version contract.

Every case drives the real endpoints (status, punch, self-registration submit) so the result is the SERVER policy
(services_face_policy.guidance) - the frontend's punchGate only reflects these flags.

  can open camera  == status.requires_face_to_punch      (only an approved Face ID verifies a face at punch time)
  can punch        == punch endpoint does not refuse     (approved: only WITH a face capture; others: only via fallback)
  self-registration== status.can_self_register, enforced by the submit endpoint (403 in hr_in_person)
"""
from __future__ import annotations

import itertools

from django.core.cache import cache
from django.urls import reverse

from apps.accounts.factories import make_user
from apps.attendance.services import AttendanceSettingsService

from apps.attendance.models import (
    FACE_CONSENT_TEXT_VERSION, AttendancePunch, FaceRegistrationRequest,
)
from apps.attendance.tests_face_id_policy import (
    APPROVAL, HR_ONLY, SELF, FaceIdTestBase, _embedding,
)

_admin_seq = itertools.count()


def set_face_rules(mandatory=True, mode=APPROVAL, fallback='none', days=7):
    # Same as tests_face_id_policy.set_face_rules, but with a unique admin per call (that helper derives the admin's
    # email from the punch count, which collides when called repeatedly in one test).
    admin = make_user(f'matrix-admin-{next(_admin_seq)}@test.com')
    AttendanceSettingsService.partial_update({'face_verification': {
        'is_mandatory': mandatory, 'registration_mode': mode, 'fallback_policy': fallback, 'fallback_days': days,
    }}, admin)
    cache.clear()

APPROVED, NOT_REGISTERED, PENDING, REJECTED = 'approved', 'not_registered', 'pending', 'rejected'


class ModeStateFallbackMatrixTests(FaceIdTestBase):
    def _put_in_state(self, state):
        if state == APPROVED:
            self._register_approved()
        elif state in (PENDING, REJECTED):
            FaceRegistrationRequest.objects.create(
                employee=self.employee, face_embedding=_embedding(), liveness_passed=True,
                status=(FaceRegistrationRequest.STATUS_PENDING if state == PENDING
                        else FaceRegistrationRequest.STATUS_REJECTED),
            )

    def _submit(self):
        return self.client.post(reverse('face-registration-submit'), {
            'face_embedding': _embedding(), 'liveness_passed': True, 'consent_acknowledged': True,
        }, format='json')

    def test_mode_x_state_x_fallback_matrix(self):
        for mode in (SELF, HR_ONLY, APPROVAL):
            for fallback in ('none', 'until_approved'):
                for state in (APPROVED, NOT_REGISTERED, PENDING, REJECTED):
                    label = f'{mode}/{fallback}/{state}'
                    with self.subTest(label):
                        FaceRegistrationRequest.objects.all().delete()
                        AttendancePunch.objects.all().delete()
                        set_face_rules(mode=mode, fallback=fallback)
                        self._put_in_state(state)

                        status = self._status()
                        fallback_on = fallback != 'none' and state != APPROVED
                        self.assertEqual(status['state'], state, label)
                        # camera opens only for an approved Face ID
                        self.assertEqual(status['requires_face_to_punch'], state == APPROVED, label)
                        self.assertEqual(status['fallback_active'], fallback_on, label)
                        # self-registration: never in HR-only mode, never while a request is pending
                        self.assertEqual(
                            status['can_self_register'], mode != HR_ONLY and state != PENDING, label)

                        punch = self._punch()
                        if state == APPROVED:
                            # needs a face capture; a bare punch (no face payload) is refused, camera is required
                            self.assertEqual(punch.status_code, 400, (label, punch.data))
                            self.assertFalse(AttendancePunch.objects.exists(), label)
                        elif fallback_on:
                            self.assertEqual(punch.status_code, 200, (label, punch.data))
                            self.assertTrue(AttendancePunch.objects.get().face_fallback, label)
                        else:
                            self.assertEqual(punch.status_code, 400, (label, punch.data))
                            self.assertEqual(punch.data['message'], status['message'], label)
                            self.assertFalse(AttendancePunch.objects.exists(), label)

    def test_self_registration_endpoint_enforces_the_mode(self):
        expected = {
            (SELF, NOT_REGISTERED): 201, (SELF, REJECTED): 201,
            (APPROVAL, NOT_REGISTERED): 201, (APPROVAL, REJECTED): 201,
            (HR_ONLY, NOT_REGISTERED): 403, (HR_ONLY, REJECTED): 403,
        }
        for (mode, state), code in expected.items():
            with self.subTest(f'{mode}/{state}'):
                FaceRegistrationRequest.objects.all().delete()
                set_face_rules(mode=mode)
                self._put_in_state(state)
                resp = self._submit()
                self.assertEqual(resp.status_code, code, resp.data)

    def test_pending_cannot_submit_again_in_any_mode(self):
        for mode in (SELF, HR_ONLY, APPROVAL):
            with self.subTest(mode):
                FaceRegistrationRequest.objects.all().delete()
                set_face_rules(mode=mode)
                self._put_in_state(PENDING)
                self.assertGreaterEqual(self._submit().status_code, 400)


class ConsentVersionContractTests(FaceIdTestBase):
    """FACE_CONSENT_TEXT_VERSION is write-only metadata: stamped on creation, never read/validated afterwards."""

    def _submit(self):
        return self.client.post(reverse('face-registration-submit'), {
            'face_embedding': _embedding(), 'liveness_passed': True, 'consent_acknowledged': True,
        }, format='json')

    def test_constant_is_v2_literal(self):
        # Pinned literal (other tests compare against the constant itself, which would pass for any value).
        self.assertEqual(FACE_CONSENT_TEXT_VERSION, 'v2')

    def test_new_self_registration_records_v2(self):
        set_face_rules(mode=SELF)
        self.assertEqual(self._submit().status_code, 201)
        self.assertEqual(FaceRegistrationRequest.objects.get(employee=self.employee).consent_text_version, 'v2')

    def test_existing_v1_record_stays_valid_and_untouched(self):
        set_face_rules(mode=SELF)
        legacy = FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=_embedding(), liveness_passed=True,
            consent_text_version='v1', status=FaceRegistrationRequest.STATUS_APPROVED,
        )
        from apps.attendance.services_face_matching import activate_registration
        activate_registration(legacy)
        status = self._status()
        self.assertEqual(status['state'], APPROVED)            # a v1 consent still counts as approved
        self.assertTrue(status['requires_face_to_punch'])
        legacy.refresh_from_db()
        self.assertEqual(legacy.consent_text_version, 'v1')    # not rewritten by any later activity
