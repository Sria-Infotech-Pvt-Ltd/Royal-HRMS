"""
Regression tests for the Accounts endpoints that now apply core.access.employee_in_scope:

  1. bank-change approve/reject     4. onboarding approvals ?view=pipeline
  2. reporting-manager PATCH        5. by-id onboarding document / custom-file access
  3. approval-matrix GET/POST/DELETE  6. audit-log list (blank-branch default-deny)

Each: an out-of-scope actor is denied with the endpoint's existing contract and nothing changes; an in-scope actor
still succeeds. Fixtures: tests_employee_scope.build_world().
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import (
    ApprovalWorkflowRule, AuditLog, CustomFieldFileValue, EmployeeApprovalOverride, EmployeeDocument, EmployeeProfile, User,
)
from apps.accounts.tests_employee_scope import build_world
from apps.accounts.views.custom_field_files import CustomFieldFileValueView
from apps.accounts.views.onboarding_documents import EmployeeDocumentView
from apps.recruitment.models import Candidate


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class ScopeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()


class BankChangeScopeTests(ScopeTestCase):
    def _pending(self, employee) -> EmployeeProfile:
        return EmployeeProfile.objects.create(
            user=employee, bank_change_status=EmployeeProfile.BANK_CHANGE_PENDING,
            pending_account_number='123456789012', pending_ifsc_code='HDFC0001234',
        )

    def _post(self, actor, employee, decision='approve'):
        return _api(actor).post(f'/api/employees/{employee.employee_id}/bank-change/{decision}/', {}, format='json')

    def test_out_of_scope_actors_get_404_and_the_change_stays_pending(self):
        profile = self._pending(self.w.emp_hyd)
        for actor in (self.w.hr_blr, self.w.hr_none, self.w.mgr):
            for decision in ('approve', 'reject'):
                self.assertEqual(self._post(actor, self.w.emp_hyd, decision).status_code, 404, (actor.employee_id, decision))
        profile.refresh_from_db()
        self.assertEqual(profile.bank_change_status, EmployeeProfile.BANK_CHANGE_PENDING)

    def test_in_scope_actors_can_still_decide(self):
        for actor, employee in ((self.w.hr_hyd, self.w.emp_hyd), (self.w.root, self.w.emp_blr), (self.w.mgr, self.w.report)):
            profile = self._pending(employee)
            self.assertEqual(self._post(actor, employee).status_code, 200, actor.employee_id)
            profile.refresh_from_db()
            self.assertNotEqual(profile.bank_change_status, EmployeeProfile.BANK_CHANGE_PENDING)


class ReportingManagerScopeTests(ScopeTestCase):
    def _patch(self, actor, employee):
        return _api(actor).patch(
            f'/api/employees/{employee.employee_id}/reporting-manager/',
            {'reporting_manager_id': str(self.w.mgr.pk)}, format='json',
        )

    def test_out_of_scope_actor_is_denied_and_the_manager_is_unchanged(self):
        for actor in (self.w.hr_blr, self.w.hr_none):
            self.assertEqual(self._patch(actor, self.w.emp_hyd).status_code, 404)
        self.w.emp_hyd.refresh_from_db()
        self.assertIsNone(self.w.emp_hyd.reporting_manager_id)

    def test_in_scope_actor_can_still_assign(self):
        self.assertEqual(self._patch(self.w.hr_hyd, self.w.emp_hyd).status_code, 200)
        self.w.emp_hyd.refresh_from_db()
        self.assertEqual(self.w.emp_hyd.reporting_manager_id, self.w.mgr.pk)


class ApprovalMatrixScopeTests(ScopeTestCase):
    def _url(self, employee, query=''):
        return f'/api/employees/{employee.employee_id}/approval-matrix/{query}'

    def _overrides(self, employee):
        return EmployeeApprovalOverride.objects.filter(employee=employee, workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE)

    def test_out_of_scope_actor_cannot_read_write_or_delete(self):
        EmployeeApprovalOverride.objects.create(employee=self.w.emp_hyd, workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE)
        client = _api(self.w.hr_blr)
        self.assertEqual(client.get(self._url(self.w.emp_hyd)).status_code, 404)
        self.assertEqual(client.post(self._url(self.w.emp_hyd), {'workflow_type': 'leave'}, format='json').status_code, 404)
        self.assertEqual(client.delete(self._url(self.w.emp_hyd, '?workflow_type=leave')).status_code, 404)
        self.assertTrue(self._overrides(self.w.emp_hyd).exists())  # the delete did not happen

    def test_out_of_scope_actor_cannot_create_an_override(self):
        response = _api(self.w.hr_none).post(self._url(self.w.emp_hyd), {'workflow_type': 'leave'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self._overrides(self.w.emp_hyd).exists())

    def test_out_of_scope_actor_cannot_put_or_patch_an_override(self):
        client = _api(self.w.hr_blr)
        for method in (client.put, client.patch):
            response = method(self._url(self.w.emp_hyd), {'workflow_type': 'leave'}, format='json')
            self.assertEqual(response.status_code, 404, method.__name__)
        self.assertFalse(self._overrides(self.w.emp_hyd).exists())

    def test_in_scope_actor_can_still_put_and_patch(self):
        client = _api(self.w.hr_hyd)
        for method in (client.put, client.patch):
            self._overrides(self.w.emp_hyd).delete()
            response = method(self._url(self.w.emp_hyd), {'workflow_type': 'leave'}, format='json')
            self.assertEqual(response.status_code, 200, method.__name__)
            self.assertTrue(self._overrides(self.w.emp_hyd).exists(), method.__name__)

    def test_in_scope_actor_can_still_read_write_and_delete(self):
        client = _api(self.w.hr_hyd)
        self.assertEqual(client.get(self._url(self.w.emp_hyd)).status_code, 200)
        self.assertEqual(client.post(self._url(self.w.emp_hyd), {'workflow_type': 'leave'}, format='json').status_code, 200)
        self.assertTrue(self._overrides(self.w.emp_hyd).exists())
        self.assertEqual(client.delete(self._url(self.w.emp_hyd, '?workflow_type=leave')).status_code, 200)
        self.assertFalse(self._overrides(self.w.emp_hyd).exists())


class OnboardingPipelineScopeTests(ScopeTestCase):
    def setUp(self):
        # The shared fixture's own onboarding candidate must not appear in these counts.
        User.objects.filter(pk=self.w.pending.pk).update(onboarding_status=User.ONBOARDING_COMPLETE)
        self.in_hyd = self._portal_user(1, self.w.hyd)
        self.in_blr = self._portal_user(2, self.w.blr)
        self.of_mgr = self._portal_user(3, self.w.hyd, manager=self.w.mgr)

    def _portal_user(self, number, branch, manager=None) -> User:
        user = make_user(
            f'pipe{number}@test.com', employee_id=f'PL{number:03d}', branch='', reporting_manager=manager,
            onboarding_status=User.ONBOARDING_PENDING, account_activated_at=None,
        )
        Candidate.objects.create(name=f'Pipe {number}', email=f'pipecand{number}@test.com', position_applied='Tester', branch=branch, portal_user=user)
        return user

    def _pipeline(self, actor):
        response = _api(actor).get('/api/onboarding/approvals/?view=pipeline')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        return {row['id'] for row in data['results']}, data['stats']['pending']

    def test_each_actor_only_sees_and_counts_their_scope(self):
        ids = lambda *users: {str(user.pk) for user in users}  # noqa: E731
        self.assertEqual(self._pipeline(self.w.hr_hyd), (ids(self.in_hyd, self.of_mgr), 2))
        self.assertEqual(self._pipeline(self.w.hr_blr), (ids(self.in_blr), 1))
        self.assertEqual(self._pipeline(self.w.hr_none), (set(), 0))
        self.assertEqual(self._pipeline(self.w.mgr), (ids(self.of_mgr), 1))
        self.assertEqual(self._pipeline(self.w.root), (ids(self.in_hyd, self.in_blr, self.of_mgr), 3))


class ByIdFileScopeTests(ScopeTestCase):
    """The gate lives in _get_doc/_get_value; storage (ImageKit) is never touched."""

    def setUp(self):
        self.document = EmployeeDocument.objects.create(user=self.w.emp_hyd, document_type='pan', file='scope/a.pdf', file_name='a.pdf', file_size=1)
        self.custom = CustomFieldFileValue.objects.create(user=self.w.emp_hyd, field_key='scope_key', file='scope/b.pdf', file_name='b.pdf', file_size=1)

    def _results(self, actor):
        request = SimpleNamespace(user=actor)
        _, doc_error = EmployeeDocumentView()._get_doc(request, self.document.pk)
        _, value_error = CustomFieldFileValueView()._get_value(request, str(self.custom.pk))
        return (doc_error.status_code if doc_error else 200), (value_error.status_code if value_error else 200)

    def test_owner_and_in_scope_actors_still_get_the_file(self):
        for actor in (self.w.emp_hyd, self.w.hr_hyd, self.w.root):
            self.assertEqual(self._results(actor), (200, 200), actor.employee_id)

    def test_out_of_scope_actors_see_a_missing_file(self):
        for actor in (self.w.hr_blr, self.w.hr_none, self.w.mgr):
            self.assertEqual(self._results(actor), (404, 404), actor.employee_id)

    def test_actor_without_employees_edit_keeps_the_existing_403(self):
        self.assertEqual(self._results(self.w.emp_blr), (403, 403))

    def test_manager_still_reaches_a_direct_reports_file(self):
        EmployeeDocument.objects.filter(pk=self.document.pk).update(user=self.w.report)
        CustomFieldFileValue.objects.filter(pk=self.custom.pk).update(user=self.w.report)
        self.assertEqual(self._results(self.w.mgr), (200, 200))


class ByIdFileHttpDenialTests(ScopeTestCase):
    """Through the real views: a denied request answers before storage is touched. Any ImageKit client use fails."""

    def setUp(self):
        self.document = EmployeeDocument.objects.create(user=self.w.emp_hyd, document_type='pan', file='scope/a.pdf', file_name='a.pdf', file_size=1)
        self.custom = CustomFieldFileValue.objects.create(user=self.w.emp_hyd, field_key='scope_key', file='scope/b.pdf', file_name='b.pdf', file_size=1)
        guard = patch('core.storage._get_client', side_effect=AssertionError('storage must not be touched on a denied request'))
        guard.start()
        self.addCleanup(guard.stop)
        self.urls = {
            'document': (f'/api/onboarding/documents/{self.document.pk}/', 'Document not found.'),
            'custom file': (f'/api/onboarding/custom-file-fields/{self.custom.pk}/', 'File not found.'),
        }

    def _assert_denied(self, actor, expected_status, expected_messages=True):
        client = _api(actor)
        for label, (url, message) in self.urls.items():
            for method in (client.get, client.delete):
                response = method(url)
                self.assertEqual(response.status_code, expected_status, (actor.employee_id, label, method.__name__))
                if expected_messages:
                    self.assertEqual(response.json()['message'], message, (actor.employee_id, label, method.__name__))

    def test_out_of_scope_actors_get_404_on_get_and_delete(self):
        for actor in (self.w.hr_blr, self.w.hr_none, self.w.mgr):
            self._assert_denied(actor, 404)

    def test_denied_deletes_leave_the_files_in_place(self):
        self._assert_denied(self.w.hr_blr, 404)
        self.assertTrue(EmployeeDocument.objects.filter(pk=self.document.pk).exists())
        self.assertTrue(CustomFieldFileValue.objects.filter(pk=self.custom.pk).exists())

    def test_actor_without_employees_edit_keeps_the_existing_403(self):
        self._assert_denied(self.w.emp_blr, 403, expected_messages=False)  # the 403 wording is not part of this change


class AuditLogScopeTests(ScopeTestCase):
    def setUp(self):
        AuditLog.objects.all().delete()
        for branch in (self.w.hyd.branch_name, self.w.blr.branch_name):
            AuditLog.objects.create(user=self.w.root, action='update', module='employees', branch=branch)

    def _count(self, actor):
        response = _api(actor).get('/api/settings/audit/')
        self.assertEqual(response.status_code, 200)
        return response.json()['data']['count']

    def test_branch_user_sees_only_their_branch(self):
        self.assertEqual(self._count(self.w.hr_hyd), 1)

    def test_user_with_no_branch_sees_nothing(self):
        self.assertEqual(self._count(self.w.hr_none), 0)

    def test_settings_edit_exemption_is_preserved(self):
        # KNOWN, TEMPORARY INCONSISTENCY (follow-up security decision): settings.edit does not grant company-wide
        # employee scope (core.access.employee_in_scope) but still grants company-wide audit-log visibility here.
        self.assertEqual(self._count(self.w.settings_blr), 2)
        self.assertEqual(self._count(self.w.root), 2)
