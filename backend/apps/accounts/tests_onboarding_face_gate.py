"""
Tests for the onboarding submit gate on Face ID registration
(OnboardingView._submit — apps/accounts/views.py) — only enforced when the
org-wide Face ID Verification toggle (AttendanceFaceVerificationRules, see
apps.attendance) is mandatory. Split out of tests.py to keep it under the
300-line convention.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EDUCATION_LEVEL_BACHELORS, EducationRecord, EmployeeDocument, EmployeeProfile
from apps.attendance.models import (
    AttendanceFaceVerificationRules,
    AttendanceSettings,
    FaceRegistrationRequest,
)


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


def _set_face_verification_mandatory(is_mandatory: bool) -> None:
    settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
    AttendanceFaceVerificationRules.objects.update_or_create(
        settings=settings, defaults={'is_mandatory': is_mandatory},
    )


def _complete_profile(user) -> EmployeeProfile:
    """Fills every field _submit() requires, except documents/face ID.
    Education is now its own bespoke list (EducationRecord), not a step-1
    generic field — _missing_education_experience() requires at least one
    row with institution filled."""
    EducationRecord.objects.create(
        employee=user, level=EDUCATION_LEVEL_BACHELORS,
        institution='Test University', end_date='2017-06-01',
    )
    return EmployeeProfile.objects.create(
        user=user,
        date_of_birth='1995-01-01', gender=EmployeeProfile.GENDER_MALE,
        marital_status=EmployeeProfile.MARITAL_SINGLE, father_name='Test Father',
        current_address='123 Test Street',
        current_district='Test District', current_state='Test State', current_pin_code='500001',
        highest_qualification='B.Tech', institution='Test University', year_of_passing=2017,
        account_holder_name='Test User', account_type=EmployeeProfile.ACCOUNT_SAVINGS,
        account_number='1234567890', ifsc_code='SBIN0001234',
        bank_name='State Bank', bank_branch_name='Main Branch',
        emergency_name='Emergency Contact', emergency_relationship='Parent',
        emergency_phone='9999999999',
    )


def _upload_required_documents(user) -> None:
    # Reads the live, admin-configurable required list (DocumentTypeConfig)
    # instead of a hardcoded PAN/Aadhaar/Degree trio — that hardcoded list
    # was already stale (missing Cancelled Cheque/Signed Offer Letter,
    # required since an earlier migration) and broke again the moment any
    # further required type was added (10th/12th Certificate). This test
    # only cares about the Face ID gate, not the document-required gate, so
    # it should never need updating again when the required list changes.
    from apps.accounts.models import DocumentTypeConfig
    for doc_type in DocumentTypeConfig.objects.filter(visible=True, required=True).values_list('type_key', flat=True):
        EmployeeDocument.objects.create(
            user=user, document_type=doc_type,
            file='documents/2026/01/dummy.pdf', file_name='dummy.pdf', file_size=1024,
        )


class OnboardingFaceGateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user   = make_user('onboard-face@test.com', role=make_role('employee_onboard_face'))
        _login(self.client, 'onboard-face@test.com')
        _complete_profile(self.user)
        _upload_required_documents(self.user)

    def _submit(self):
        return self.client.post(reverse('onboarding'), {}, format='json')

    def test_submit_succeeds_without_face_registration_when_toggle_is_off(self):
        _set_face_verification_mandatory(False)
        resp = self._submit()
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_submit_is_blocked_without_face_registration_when_mandatory(self):
        _set_face_verification_mandatory(True)
        resp = self._submit()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face id registration', resp.data['message'].lower())

        self.user.refresh_from_db()
        self.assertNotEqual(self.user.onboarding_status, self.user.ONBOARDING_SUBMITTED)

    def test_submit_succeeds_with_pending_face_registration_when_mandatory(self):
        _set_face_verification_mandatory(True)
        FaceRegistrationRequest.objects.create(
            employee=self.user, face_embedding=[0.1, 0.2, 0.3], liveness_passed=True,
        )
        resp = self._submit()
        self.assertEqual(resp.status_code, 200, resp.data)

        self.user.refresh_from_db()
        self.assertEqual(self.user.onboarding_status, self.user.ONBOARDING_SUBMITTED)
