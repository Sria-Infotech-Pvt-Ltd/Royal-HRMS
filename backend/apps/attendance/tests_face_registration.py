"""
Tests for the Face Registration submission/approval workflow.

Split out of tests.py (its own domain, keeps both files under the 300-line
convention) — see face_registration.py for the endpoints under test.
"""
from __future__ import annotations

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    FACE_CONSENT_TEXT_VERSION,
    FACE_RECOGNITION_MODEL_VERSION,
    AttendanceFaceVerificationRules,
    AttendanceSettings,
    FaceRegistrationRequest,
)
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _set_face_verification_mandatory(is_mandatory: bool) -> None:
    """Flips the org-wide toggle (Attendance Settings -> Face ID Verification)
    that FaceRegistrationSubmitView now gates submissions on."""
    settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
    AttendanceFaceVerificationRules.objects.update_or_create(
        settings=settings, defaults={'is_mandatory': is_mandatory},
    )


def _make_pending_request(employee) -> FaceRegistrationRequest:
    return FaceRegistrationRequest.objects.create(
        employee=employee,
        face_embedding=[0.1, 0.2, 0.3],
        liveness_passed=True,
        liveness_score=0.92,
    )


class FaceRegistrationSubmissionTests(TestCase):
    """Any authenticated employee can submit their own request — no permission
    required — as long as the org-wide toggle is on (see FaceRegistrationSubmissionDisabledTests
    for the off case)."""

    def setUp(self):
        cache.clear()
        _set_face_verification_mandatory(True)
        self.client   = APIClient()
        self.employee = make_user('facereg-employee@test.com')
        _login(self.client, 'facereg-employee@test.com')

    def test_submit_creates_correctly_shaped_pending_request(self):
        resp = self.client.post(
            reverse('face-registration-submit'),
            {
                'face_embedding': [0.1, 0.2, 0.3, 0.4],
                'liveness_passed': True,
                'liveness_score': 0.95,
                'consent_acknowledged': True,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_PENDING)
        self.assertEqual(face_request.face_embedding, [0.1, 0.2, 0.3, 0.4])
        self.assertTrue(face_request.liveness_passed)
        self.assertEqual(face_request.liveness_score, 0.95)
        self.assertEqual(face_request.embedding_model_version, FACE_RECOGNITION_MODEL_VERSION)
        self.assertIsNone(face_request.approved_by)
        self.assertIsNone(face_request.approved_at)
        # Consent is stamped server-side from consent_acknowledged, never
        # taken as a client-supplied timestamp.
        self.assertIsNotNone(face_request.consent_given_at)
        self.assertEqual(face_request.consent_text_version, FACE_CONSENT_TEXT_VERSION)

    def test_submit_rejects_missing_face_embedding(self):
        resp = self.client.post(
            reverse('face-registration-submit'),
            {'liveness_passed': True, 'consent_acknowledged': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_submit_never_accepts_a_raw_image_field(self):
        # face_embedding is a float list, not a file — a raw image payload
        # simply fails FloatField coercion instead of being stored anywhere.
        resp = self.client.post(
            reverse('face-registration-submit'),
            {'face_embedding': ['not-a-float'], 'liveness_passed': True, 'consent_acknowledged': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_submit_rejects_missing_consent(self):
        resp = self.client.post(
            reverse('face-registration-submit'),
            {'face_embedding': [0.1, 0.2, 0.3, 0.4], 'liveness_passed': True, 'liveness_score': 0.95},
            format='json',
        )
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_submit_rejects_consent_explicitly_false(self):
        resp = self.client.post(
            reverse('face-registration-submit'),
            {
                'face_embedding': [0.1, 0.2, 0.3, 0.4],
                'liveness_passed': True,
                'liveness_score': 0.95,
                'consent_acknowledged': False,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())


class FaceRegistrationSubmissionDisabledTests(TestCase):
    """When the org-wide toggle is off, self-submission is refused outright —
    see is_face_verification_mandatory() in services_face_matching.py."""

    def setUp(self):
        cache.clear()
        _set_face_verification_mandatory(False)
        self.client   = APIClient()
        self.employee = make_user('facereg-disabled@test.com')
        _login(self.client, 'facereg-disabled@test.com')

    def test_submit_is_refused_when_toggle_is_off(self):
        resp = self.client.post(
            reverse('face-registration-submit'),
            {'face_embedding': [0.1, 0.2, 0.3, 0.4], 'liveness_passed': True, 'liveness_score': 0.95},
            format='json',
        )
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('contact your administrator', resp.data['message'].lower())
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())


class FaceRegistrationApprovalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client    = APIClient()
        self.hr_role   = make_role('hr', permission_codenames=['facial_recognition.approve'])
        self.hr_user   = make_user('facereg-hr@test.com', role=self.hr_role)
        self.employee  = make_user('facereg-target@test.com')

    def _review(self, pk, payload):
        return self.client.patch(
            reverse('face-registration-review', kwargs={'pk': pk}),
            payload,
            format='json',
        )

    def test_approve_sets_approved_by_and_approved_at(self):
        _login(self.client, 'facereg-hr@test.com')
        face_request = _make_pending_request(self.employee)

        resp = self._review(face_request.pk, {'status': 'approved'})

        self.assertEqual(resp.status_code, 200, resp.data)
        face_request.refresh_from_db()
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_APPROVED)
        self.assertEqual(face_request.approved_by_id, self.hr_user.id)
        self.assertIsNotNone(face_request.approved_at)

    def test_reject_sets_status_rejected(self):
        _login(self.client, 'facereg-hr@test.com')
        face_request = _make_pending_request(self.employee)

        resp = self._review(face_request.pk, {'status': 'rejected'})

        self.assertEqual(resp.status_code, 200, resp.data)
        face_request.refresh_from_db()
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_REJECTED)

    def test_cannot_approve_own_request(self):
        _login(self.client, 'facereg-hr@test.com')
        own_request = _make_pending_request(self.hr_user)

        resp = self._review(own_request.pk, {'status': 'approved'})

        self.assertEqual(resp.status_code, 403)
        self.assertIn('cannot approve', resp.data['message'].lower())
        own_request.refresh_from_db()
        self.assertEqual(own_request.status, FaceRegistrationRequest.STATUS_PENDING)
        self.assertIsNone(own_request.approved_by)

    def test_non_pending_request_cannot_be_actioned(self):
        _login(self.client, 'facereg-hr@test.com')
        face_request = _make_pending_request(self.employee)
        face_request.status = FaceRegistrationRequest.STATUS_APPROVED
        face_request.save(update_fields=['status'])

        resp = self._review(face_request.pk, {'status': 'rejected'})

        self.assertEqual(resp.status_code, 409)
        face_request.refresh_from_db()
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_APPROVED)

    def test_permission_denied_never_mutates_the_request(self):
        no_perm_role = make_role('employee_no_facial_perm')
        no_perm_user = make_user('facereg-noperm@test.com', role=no_perm_role)
        _login(self.client, 'facereg-noperm@test.com')
        face_request = _make_pending_request(self.employee)

        resp = self._review(face_request.pk, {'status': 'approved'})

        self.assertEqual(resp.status_code, 403)
        face_request.refresh_from_db()
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_PENDING)
        self.assertIsNone(face_request.approved_by)
        self.assertIsNone(face_request.approved_at)
        self.assertNotEqual(no_perm_user.id, face_request.employee_id)

    def test_two_active_registrations_for_the_same_employee_violate_the_db_constraint(self):
        # Bypasses activate_registration entirely (direct .create() calls) —
        # this asserts the DB itself refuses two simultaneously-active rows
        # for one employee, not just that application code happens to avoid
        # it. See uniq_active_face_registration_per_employee in
        # FaceRegistrationRequest.Meta.constraints.
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=[0.1, 0.2, 0.3],
            status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FaceRegistrationRequest.objects.create(
                    employee=self.employee, face_embedding=[0.4, 0.5, 0.6],
                    status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True,
                )

    def test_approving_via_review_deactivates_the_prior_active_registration(self):
        _login(self.client, 'facereg-hr@test.com')
        prior = FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=[0.1, 0.2, 0.3],
            status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True,
        )
        new_request = _make_pending_request(self.employee)

        resp = self._review(new_request.pk, {'status': 'approved'})

        self.assertEqual(resp.status_code, 200, resp.data)
        new_request.refresh_from_db()
        prior.refresh_from_db()
        self.assertTrue(new_request.is_active)
        self.assertFalse(prior.is_active)
        # Only is_active moved — the prior row's own approval decision is an
        # immutable audit record and must stay exactly as it was.
        self.assertEqual(prior.status, FaceRegistrationRequest.STATUS_APPROVED)

    def test_hr_register_deactivates_the_prior_active_registration(self):
        _set_face_verification_mandatory(True)
        _login(self.client, 'facereg-hr@test.com')
        prior = FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=[0.1, 0.2, 0.3],
            status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True,
        )

        resp = self.client.post(
            reverse('face-registration-hr-register'),
            {
                'employee_uuid':   str(self.employee.pk),
                'face_embedding':  [0.4, 0.5, 0.6, 0.7],
                'liveness_passed': True,
                'liveness_score':  0.95,
                'consent_acknowledged': True,
            },
            format='json',
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        prior.refresh_from_db()
        self.assertFalse(prior.is_active)
        new_request = FaceRegistrationRequest.objects.get(pk=resp.data['data']['id'])
        self.assertTrue(new_request.is_active)
        self.assertNotEqual(new_request.pk, prior.pk)


class FaceRegistrationPendingListTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        self.hr_role  = make_role('hr', permission_codenames=['facial_recognition.approve'])
        self.hr_user  = make_user('facereg-list-hr@test.com', role=self.hr_role)
        self.employee = make_user('facereg-list-employee@test.com')

    def test_permission_denied_for_holder_without_approve_permission(self):
        no_perm_role = make_role('employee_no_facial_perm_2')
        make_user('facereg-list-noperm@test.com', role=no_perm_role)
        _login(self.client, 'facereg-list-noperm@test.com')

        resp = self.client.get(reverse('face-registration-pending'))

        self.assertEqual(resp.status_code, 403)

    def test_lists_only_pending_requests_for_permission_holder(self):
        pending = _make_pending_request(self.employee)
        approved = _make_pending_request(self.employee)
        approved.status = FaceRegistrationRequest.STATUS_APPROVED
        approved.save(update_fields=['status'])

        _login(self.client, 'facereg-list-hr@test.com')
        resp = self.client.get(reverse('face-registration-pending'))

        self.assertEqual(resp.status_code, 200, resp.data)
        result_ids = {row['id'] for row in resp.data['data']['results']}
        self.assertIn(str(pending.pk), result_ids)
        self.assertNotIn(str(approved.pk), result_ids)


class FaceRegistrationHRRegisterConsentTests(TestCase):
    """consent_acknowledged is required on the HR-witnessed capture path too
    — HR confirms the employee consented in person before this request."""

    def setUp(self):
        cache.clear()
        _set_face_verification_mandatory(True)
        self.client   = APIClient()
        self.hr_role  = make_role('hr', permission_codenames=['facial_recognition.approve'])
        self.hr_user  = make_user('facereg-hr-register@test.com', role=self.hr_role)
        self.employee = make_user('facereg-hr-target@test.com')
        _login(self.client, 'facereg-hr-register@test.com')

    def _register(self, **overrides):
        payload = {
            'employee_uuid':   str(self.employee.pk),
            'face_embedding':  [0.1, 0.2, 0.3, 0.4],
            'liveness_passed': True,
            'liveness_score':  0.95,
            'consent_acknowledged': True,
        }
        payload.update(overrides)
        return self.client.post(reverse('face-registration-hr-register'), payload, format='json')

    def test_register_with_consent_succeeds_and_stamps_consent(self):
        resp = self._register()

        self.assertEqual(resp.status_code, 201, resp.data)
        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_APPROVED)
        self.assertIsNotNone(face_request.consent_given_at)
        self.assertEqual(face_request.consent_text_version, FACE_CONSENT_TEXT_VERSION)

    def test_register_rejects_missing_consent(self):
        resp = self.client.post(
            reverse('face-registration-hr-register'),
            {
                'employee_uuid':   str(self.employee.pk),
                'face_embedding':  [0.1, 0.2, 0.3, 0.4],
                'liveness_passed': True,
                'liveness_score':  0.95,
                # consent_acknowledged omitted entirely
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_register_rejects_consent_explicitly_false(self):
        resp = self._register(consent_acknowledged=False)
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())
