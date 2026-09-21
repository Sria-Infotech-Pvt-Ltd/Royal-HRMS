"""
Tests for face biometric data lifecycle on employee separation.

Split out of tests_face_registration.py (its own domain, keeps both files
under the 300-line convention) — see services_face_lifecycle.py for the
purge logic under test, and apps.accounts.views.EmployeeDetailView for the
two call sites (deactivate, delete) that trigger it.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import FaceRegistrationRequest, FaceVerificationAttempt
from apps.attendance.services_face_lifecycle import purge_face_data_for_employee
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _make_registration(employee, status=FaceRegistrationRequest.STATUS_APPROVED) -> FaceRegistrationRequest:
    return FaceRegistrationRequest.objects.create(
        employee=employee,
        face_embedding=[0.1, 0.2, 0.3],
        liveness_passed=True,
        liveness_score=0.92,
        status=status,
    )


def _make_attempt(employee, **overrides) -> FaceVerificationAttempt:
    defaults = dict(
        employee=employee,
        source='web',
        capture_session_id='session-abc-123',
        embedding_fingerprint='a' * 64,
        liveness_passed=True,
        liveness_score=0.9,
        is_match=True,
        distance=0.2,
    )
    defaults.update(overrides)
    return FaceVerificationAttempt.objects.create(**defaults)


class PurgeFaceDataServiceTests(TestCase):
    """Unit tests for the service function itself, independent of the HTTP layer."""

    def setUp(self):
        self.employee = make_user('lifecycle-employee@test.com')

    def test_deletes_all_registration_rows(self):
        _make_registration(self.employee, status=FaceRegistrationRequest.STATUS_APPROVED)
        _make_registration(self.employee, status=FaceRegistrationRequest.STATUS_REJECTED)

        result = purge_face_data_for_employee(self.employee)

        self.assertEqual(result['registrations_deleted'], 2)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_anonymizes_but_does_not_delete_verification_attempts(self):
        attempt = _make_attempt(self.employee)

        result = purge_face_data_for_employee(self.employee)

        self.assertEqual(result['attempts_anonymized'], 1)
        attempt.refresh_from_db()
        # Still exists — never deleted, per FaceVerificationAttempt's own
        # "kept for HR/security audit" docstring.
        self.assertTrue(FaceVerificationAttempt.objects.filter(pk=attempt.pk).exists())
        # Biometric-identifying fields scrubbed...
        self.assertEqual(attempt.embedding_fingerprint, '')
        self.assertEqual(attempt.capture_session_id, '')
        # ...but the audit-relevant fields survive untouched.
        self.assertTrue(attempt.is_match)
        self.assertEqual(attempt.distance, 0.2)
        self.assertEqual(attempt.source, 'web')

    def test_no_data_is_not_an_error(self):
        # An employee who never registered a face ID is the common case,
        # not an error condition.
        result = purge_face_data_for_employee(self.employee)
        self.assertEqual(result, {'registrations_deleted': 0, 'attempts_anonymized': 0})

    def test_does_not_touch_other_employees_data(self):
        other_employee = make_user('lifecycle-other@test.com')
        _make_registration(other_employee)
        _make_attempt(other_employee)

        purge_face_data_for_employee(self.employee)

        self.assertTrue(FaceRegistrationRequest.objects.filter(employee=other_employee).exists())
        other_attempt = FaceVerificationAttempt.objects.get(employee=other_employee)
        self.assertNotEqual(other_attempt.embedding_fingerprint, '')


class EmployeeDeactivationTriggersPurgeTests(TestCase):
    """End-to-end: hitting the actual deactivate/delete endpoints purges
    the target employee's face data, not the acting admin's."""

    def setUp(self):
        cache.clear()
        self.client  = APIClient()
        self.admin_role = make_role('system_admin_lifecycle', permission_codenames=['employees.edit', 'employees.delete'])
        self.admin   = make_user('lifecycle-admin@test.com', role=self.admin_role)
        self.target  = make_user('lifecycle-target@test.com', employee_id='LC-001')
        _make_registration(self.target)
        _make_attempt(self.target)
        _login(self.client, 'lifecycle-admin@test.com')

    def test_patch_deactivate_purges_target_employees_face_data(self):
        resp = self.client.patch(
            reverse('employee-detail', kwargs={'employee_id': self.target.employee_id}),
            {'is_active': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.target).exists())
        attempt = FaceVerificationAttempt.objects.get(employee=self.target)
        self.assertEqual(attempt.embedding_fingerprint, '')

    def test_patch_reactivate_does_not_purge(self):
        # Deactivate first (purges), then reactivate — reactivating must not
        # itself trigger another purge call (nothing left to purge anyway,
        # but this also documents that only the False transition purges).
        self.target.is_active = False
        self.target.save(update_fields=['is_active'])
        _make_registration(self.target)  # simulate HR re-registering after reactivation

        resp = self.client.patch(
            reverse('employee-detail', kwargs={'employee_id': self.target.employee_id}),
            {'is_active': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(FaceRegistrationRequest.objects.filter(employee=self.target).exists())

    def test_delete_purges_target_employees_face_data(self):
        resp = self.client.delete(
            reverse('employee-detail', kwargs={'employee_id': self.target.employee_id}),
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.target).exists())
