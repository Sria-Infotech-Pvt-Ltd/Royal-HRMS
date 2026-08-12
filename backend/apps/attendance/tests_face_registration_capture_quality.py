"""
Tests for the optional multi-frame capture-quality metadata added to
FaceRegistrationRequest (capture_frame_count/capture_variance) — see
frontend lib/faceApi/{clahe,qualityGate,frameCapture}.ts and
hooks/useFaceLivenessCapture.ts's framesToCapture/normalizeLighting options
for the client side of this.

Deliberately a NEW file rather than folded into tests_face_verification.py —
that file covers punch-time verification (a different concern from
registration capture quality) and is currently blocked by an unrelated
pre-existing --keepdb test-database drift issue (a stale test_neondb missing
a default for a since-removed consent_text_version migration). These tests
avoid that entirely by not relying on --keepdb.
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import FaceRegistrationRequest


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


REGISTERED_EMBEDDING = [0.01 * i for i in range(128)]


class SelfSubmitCaptureQualityTests(TestCase):
    """POST /api/attendance/face-registration/ (FaceRegistrationSubmitView)."""

    def setUp(self):
        self.client = APIClient()
        self.employee = make_user('capturequality@test.com', role=make_role('employee'), password='TestPass123!')
        _login(self.client, 'capturequality@test.com')

    def _submit(self, **overrides):
        payload = {
            'face_embedding': REGISTERED_EMBEDDING, 'liveness_passed': True, 'liveness_score': 0.95,
            'consent_acknowledged': True,
        }
        payload.update(overrides)
        return self.client.post(reverse('face-registration-submit'), payload, format='json')

    def test_capture_quality_fields_are_stored_when_provided(self):
        resp = self._submit(capture_frame_count=4, capture_variance=0.0821)
        self.assertEqual(resp.status_code, 201, resp.data)

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertEqual(face_request.capture_frame_count, 4)
        self.assertAlmostEqual(face_request.capture_variance, 0.0821)
        # Exposed on the read serializer too — see FaceRegistrationReadSerializer.
        self.assertEqual(resp.data['data']['capture_frame_count'], 4)
        self.assertAlmostEqual(resp.data['data']['capture_variance'], 0.0821)

    def test_capture_quality_fields_default_to_null_when_omitted(self):
        """Backward compatibility: a caller that hasn't adopted the
        multi-frame pipeline (or predates it) still submits successfully,
        same as before these fields existed."""
        resp = self._submit()
        self.assertEqual(resp.status_code, 201, resp.data)

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertIsNone(face_request.capture_frame_count)
        self.assertIsNone(face_request.capture_variance)
        self.assertIsNone(resp.data['data']['capture_frame_count'])

    def test_capture_frame_count_must_be_positive(self):
        resp = self._submit(capture_frame_count=0)
        self.assertEqual(resp.status_code, 422, resp.data)

    def test_capture_variance_must_be_non_negative(self):
        resp = self._submit(capture_variance=-0.5)
        self.assertEqual(resp.status_code, 422, resp.data)

    def test_null_capture_quality_fields_are_accepted_explicitly(self):
        """The frontend's single-frame path (framesToCapture=1, the
        punch-time default) never sends these keys at all, but a caller that
        explicitly sends null for both must also work the same as omitting
        them — DRF's allow_null=True covers this, this just proves it."""
        resp = self._submit(capture_frame_count=None, capture_variance=None)
        self.assertEqual(resp.status_code, 201, resp.data)


class HRRegisterCaptureQualityTests(TestCase):
    """POST /api/attendance/face-registration/register/ (FaceRegistrationHRRegisterView)."""

    def setUp(self):
        self.client = APIClient()
        hr_role = make_role('hr_capture_quality', permission_codenames=['facial_recognition.approve'])
        self.hr_user = make_user('hr-capturequality@test.com', role=hr_role)
        self.employee = make_user('employee-capturequality@test.com', role=make_role('employee_capture_quality'))
        _login(self.client, 'hr-capturequality@test.com')

        from apps.attendance.models import AttendanceFaceVerificationRules, AttendanceSettings
        settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
        AttendanceFaceVerificationRules.objects.update_or_create(settings=settings, defaults={'is_mandatory': True})

    def _register(self, **overrides):
        payload = {
            'employee_uuid': str(self.employee.pk),
            'face_embedding': REGISTERED_EMBEDDING,
            'liveness_passed': True,
            'liveness_score': 0.95,
            'consent_acknowledged': True,
        }
        payload.update(overrides)
        return self.client.post(reverse('face-registration-hr-register'), payload, format='json')

    def test_capture_quality_fields_are_stored_when_provided(self):
        resp = self._register(capture_frame_count=3, capture_variance=0.041)
        self.assertEqual(resp.status_code, 201, resp.data)

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertEqual(face_request.capture_frame_count, 3)
        self.assertAlmostEqual(face_request.capture_variance, 0.041)

    def test_capture_quality_fields_default_to_null_when_omitted(self):
        resp = self._register()
        self.assertEqual(resp.status_code, 201, resp.data)

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertIsNone(face_request.capture_frame_count)
        self.assertIsNone(face_request.capture_variance)


class ModelDefaultsTests(TestCase):
    """Direct model-level check, independent of either view."""

    def test_fields_are_nullable_and_default_to_none(self):
        employee = make_user('modeldefaults@test.com', role=make_role('employee_model_defaults'))
        face_request = FaceRegistrationRequest.objects.create(
            employee=employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )
        self.assertIsNone(face_request.capture_frame_count)
        self.assertIsNone(face_request.capture_variance)
