"""
Audit entries for the candidate-side onboarding transitions, with the right actor:

  * onboarding_draft_started   — the first step save (pending -> draft), by the employee or by HR on their behalf
  * onboarding_submitted       — the employee submits their own onboarding
  * onboarding_submitted_by_hr — HR submits on the employee's behalf (already existed; pinned here)

`on_behalf` in the entry says whether the actor is someone other than the employee. The API responses are unchanged.
"""
from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile, User

BRANCH = 'Audit Branch'
SHARED = 'apps.accounts.views.shared'


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _entries(employee, action):
    return AuditLog.objects.filter(action=action, object_id=str(employee.pk))


class OnboardingAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        hr_role = make_role('audit_onb_hr', permission_codenames=['onboarding.edit', 'employees.edit', 'employees.view'])
        self.hr = make_user('audit_hr@test.com', role=hr_role, employee_id='AH001', branch=BRANCH)
        self.employee = make_user(
            'audit_emp@test.com', employee_id='AE001', branch=BRANCH,
            requires_self_service_onboarding=True, onboarding_status=User.ONBOARDING_PENDING,
        )
        EmployeeProfile.objects.create(user=self.employee)

    def _submission_validation_passes(self):
        """Isolate the audit wiring from the (separately tested) required-field/document/face validation."""
        for name in ('_missing_required', '_missing_education_experience', '_missing_required_docs'):
            patcher = patch(f'{SHARED}.{name}', return_value=[])
            patcher.start()
            self.addCleanup(patcher.stop)
        face = patch('apps.attendance.services_face_policy.can_employee_self_register', return_value=False)
        face.start()
        self.addCleanup(face.stop)

    def _save_step(self, client, url):
        # A step save normally needs every required field of the step; the audit wiring is what is under test here.
        with patch(f'{SHARED}._step_required_configs', return_value=[]):
            return client.patch(url, {'gender': 'male'}, format='json')

    # ── submission ────────────────────────────────────────────────────────────

    def test_self_submission_is_audited_with_the_employee_as_actor(self):
        self._submission_validation_passes()
        response = _api(self.employee).post('/api/onboarding/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'Onboarding submitted. Awaiting HR approval.')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.onboarding_status, User.ONBOARDING_SUBMITTED)
        entry = _entries(self.employee, 'onboarding_submitted').get()
        self.assertEqual(entry.user_id, self.employee.pk)
        self.assertEqual(entry.changes, {'employee': self.employee.email, 'on_behalf': False})
        self.assertEqual(entry.branch, BRANCH)

    def test_hr_submission_on_behalf_is_audited_with_the_hr_actor_and_not_as_a_self_submission(self):
        self._submission_validation_passes()
        response = _api(self.hr).post(f'/api/onboarding/employees/{self.employee.pk}/submit/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        entry = _entries(self.employee, 'onboarding_submitted_by_hr').get()
        self.assertEqual(entry.user_id, self.hr.pk)
        self.assertFalse(_entries(self.employee, 'onboarding_submitted').exists())

    def test_a_rejected_submission_writes_no_entry(self):
        # No validation patching: the profile is empty, so the submit is refused.
        response = _api(self.employee).post('/api/onboarding/', {}, format='json')
        self.assertNotEqual(response.json().get('status'), 'success')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.onboarding_status, User.ONBOARDING_PENDING)
        self.assertFalse(_entries(self.employee, 'onboarding_submitted').exists())

    def test_a_failing_audit_write_never_blocks_the_submission(self):
        self._submission_validation_passes()
        with patch(f'{SHARED}.AuditLog') as audit_log:
            audit_log.objects.create.side_effect = RuntimeError('audit table unavailable')
            response = _api(self.employee).post('/api/onboarding/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.onboarding_status, User.ONBOARDING_SUBMITTED)

    # ── draft start ───────────────────────────────────────────────────────────

    def test_first_self_service_step_save_records_draft_start_once(self):
        client = _api(self.employee)
        self.assertEqual(self._save_step(client, '/api/onboarding/step/0/').status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.onboarding_status, User.ONBOARDING_DRAFT)
        entry = _entries(self.employee, 'onboarding_draft_started').get()
        self.assertEqual(entry.user_id, self.employee.pk)
        self.assertEqual(entry.changes['on_behalf'], False)
        self._save_step(client, '/api/onboarding/step/0/')  # already draft: no second entry
        self.assertEqual(_entries(self.employee, 'onboarding_draft_started').count(), 1)

    def test_draft_start_by_hr_on_behalf_records_the_hr_actor(self):
        response = self._save_step(_api(self.hr), f'/api/onboarding/employees/{self.employee.pk}/step/0/')
        self.assertEqual(response.status_code, 200)
        entry = _entries(self.employee, 'onboarding_draft_started').get()
        self.assertEqual(entry.user_id, self.hr.pk)
        self.assertEqual(entry.changes['on_behalf'], True)
        self.assertTrue(_entries(self.employee, 'onboarding_step_saved_by_hr').exists())  # existing entry unchanged

    def test_no_draft_entry_when_the_employee_is_not_pending(self):
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_DRAFT)
        self._save_step(_api(self.employee), '/api/onboarding/step/0/')
        self.assertFalse(_entries(self.employee, 'onboarding_draft_started').exists())
