"""
Tests for the face-verification lockout countdown, the insecure-transport audit row, the
"register first, then punch" rule, and the notification sent when HR reviews a registration.
"""
from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    AttendanceFaceVerificationRules,
    AttendancePunch,
    AttendanceSettings,
    FaceRegistrationRequest,
    FaceVerificationAttempt,
)
from apps.attendance.services_face_antispoofing import MAX_FAILED_ATTEMPTS
from apps.attendance.services_face_matching import FaceVerificationService
from apps.notifications.models import Notification

REGISTERED_EMBEDDING = [0.01 * i for i in range(128)]
MISMATCHED_EMBEDDING = [v + 1.0 for v in REGISTERED_EMBEDDING]


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data


def _set_mandatory(is_mandatory: bool) -> None:
    settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
    AttendanceFaceVerificationRules.objects.update_or_create(
        settings=settings, defaults={'is_mandatory': is_mandatory},
    )


def _approved(employee) -> FaceRegistrationRequest:
    return FaceRegistrationRequest.objects.create(
        employee=employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True, liveness_score=0.9,
        status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True,
    )


class FaceLockoutTests(TestCase):
    def setUp(self):
        cache.clear()
        _set_mandatory(True)
        self.client   = APIClient()
        self.employee = make_user('lockout@test.com', role=make_role('employee'))
        _approved(self.employee)
        _login(self.client, 'lockout@test.com')

    def tearDown(self):
        cache.clear()

    def _punch(self, embedding, session):
        return self.client.post(reverse('attendance-punch'), {
            'punch_type': 'IN', 'attendance_mode': 'office', 'face_embedding': embedding,
            'liveness_passed': True, 'capture_session_id': session,
        }, format='json')

    def test_ordinary_mismatch_is_403_without_a_lockout_payload(self):
        resp = self._punch(MISMATCHED_EMBEDDING, 's1')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(resp.data['data'].get('blocked', False))

    def test_attempt_cap_returns_blocked_with_retry_after_seconds(self):
        for i in range(MAX_FAILED_ATTEMPTS):
            self._punch([v + 1.0 + i * 0.01 for v in REGISTERED_EMBEDDING], f'cap-{i}')
        resp = self._punch([v + 3.0 for v in REGISTERED_EMBEDDING], 'cap-next')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertTrue(resp.data['data']['blocked'])
        self.assertGreater(resp.data['data']['retry_after_seconds'], 0)
        self.assertLessEqual(resp.data['data']['retry_after_seconds'], 901)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_seconds_until_unblocked_is_none_below_the_cap(self):
        from apps.attendance.services_face_antispoofing import FaceAntiSpoofingGuard
        self._punch(MISMATCHED_EMBEDDING, 'one')
        self.assertIsNone(FaceAntiSpoofingGuard.seconds_until_unblocked(self.employee))


class InsecureTransportAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        _set_mandatory(True)
        self.employee = make_user('insecure@test.com', role=make_role('employee'))
        _approved(self.employee)

    def tearDown(self):
        cache.clear()

    @override_settings(IS_LOCAL_OR_TEST_ENV=False)
    def test_insecure_punch_is_blocked_and_audited(self):
        outcome = FaceVerificationService.verify_for_punch(
            self.employee, 'web', REGISTERED_EMBEDDING, capture_session_id='insecure-1',
            liveness_passed=True, is_secure=False,
        )
        self.assertTrue(outcome.required)
        self.assertTrue(outcome.blocked)
        self.assertFalse(outcome.is_match)
        attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        self.assertEqual(attempt.rejection_reason, FaceVerificationAttempt.REJECTION_INSECURE)
        self.assertFalse(attempt.is_match)
        self.assertEqual(len(attempt.embedding_fingerprint), 64)


class RegisterFirstThenPunchTests(TestCase):
    """The employee must have an HR-approved Face ID before the capture step is even reached."""

    def setUp(self):
        cache.clear()
        _set_mandatory(True)
        self.client   = APIClient()
        self.employee = make_user('registerfirst@test.com', role=make_role('employee'))
        _login(self.client, 'registerfirst@test.com')

    def tearDown(self):
        cache.clear()

    def _punch(self, **extra):
        return self.client.post(reverse('attendance-punch'), {
            'punch_type': 'IN', 'attendance_mode': 'office', **extra,
        }, format='json')

    def test_not_registered_is_told_to_register_first_and_come_back(self):
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        message = resp.data['message'].lower()
        self.assertIn('register your face id first', message)
        self.assertIn('come back', message)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_pending_is_told_to_wait_for_hr_approval(self):
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )
        resp = self._punch(face_embedding=REGISTERED_EMBEDDING, liveness_passed=True)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('waiting for hr approval', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_no_face_attempt_row_is_written_before_registration(self):
        self._punch(face_embedding=REGISTERED_EMBEDDING, liveness_passed=True)
        self.assertEqual(FaceVerificationAttempt.objects.count(), 0)

    def test_rejected_is_told_to_register_again(self):
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
            status=FaceRegistrationRequest.STATUS_REJECTED,
        )
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('register it again', resp.data['message'].lower())


class FaceReviewNotificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        hr_role       = make_role('hr', permission_codenames=['facial_recognition.approve'])
        self.hr_user  = make_user('review-hr@test.com', role=hr_role)
        self.employee = make_user('review-employee@test.com', role=make_role('employee'), hr=self.hr_user)
        _login(self.client, 'review-hr@test.com')

    def tearDown(self):
        cache.clear()

    def _pending(self):
        return FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )

    def _review(self, pk, payload):
        return self.client.patch(reverse('face-registration-review', kwargs={'pk': pk}), payload, format='json')

    def test_approval_notifies_the_employee_in_app_and_by_email(self):
        face_request = self._pending()
        with mock.patch('apps.notifications.tasks.send_lifecycle_email_task.apply_async') as queued:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self._review(face_request.pk, {'status': 'approved'})
        self.assertEqual(resp.status_code, 200, resp.data)
        note = Notification.objects.get(user=self.employee, notification_type='face_registration_status')
        self.assertEqual(note.title, 'Face ID Registration Approved')
        self.assertEqual(note.module, 'facial_recognition')
        queued.assert_called_once()
        self.assertEqual(queued.call_args.kwargs['args'][1], 'face_registration_approved')

    def test_rejection_notifies_with_the_reviewer_notes(self):
        face_request = self._pending()
        with mock.patch('apps.notifications.tasks.send_lifecycle_email_task.apply_async') as queued:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self._review(face_request.pk, {'status': 'rejected', 'notes': 'Photo was blurry'})
        self.assertEqual(resp.status_code, 200, resp.data)
        note = Notification.objects.get(user=self.employee, notification_type='face_registration_status')
        self.assertEqual(note.title, 'Face ID Registration Rejected')
        args = queued.call_args.kwargs['args']
        self.assertEqual(args[1], 'face_registration_rejected')
        self.assertEqual(args[2]['notes'], 'Photo was blurry')
