"""
Tests for the Edit Record panel's "Save as Draft" feature — EmployeeEditDraft
model + EmployeeEditDraftView/EmployeeEditDraftResumeView
(backend/apps/accounts/views/employee_edit_drafts.py). A draft is private to
the admin who saved it: these tests exist specifically to pin that down,
since the whole point of per-(employee, created_by) storage is that one
admin's in-progress edit never leaks to another.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeEditDraft


class EmployeeEditDraftTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('edit_draft_hr', permission_codenames=['employees.edit'])
        self.hr_user = make_user('hr-editdraft@test.com', role=self.hr_role, password='TestPass123!')
        self.target = make_user('target-editdraft@test.com', employee_id='EMP91001')
        self.client.force_authenticate(user=self.hr_user)
        self.url = reverse('employee-edit-draft', args=['EMP91001'])
        self.resume_url = reverse('employee-edit-draft-resume', args=['EMP91001'])

    def test_get_with_no_draft_returns_none(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['data']['draft'])
        self.assertFalse(AuditLog.objects.filter(action__startswith='employee_edit_draft').exists())

    def test_post_creates_draft_and_logs_created(self):
        resp = self.client.post(self.url, {'data': {'foo': 'bar'}, 'last_step': 2}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        draft = EmployeeEditDraft.objects.get(employee=self.target, created_by=self.hr_user)
        self.assertEqual(draft.data, {'foo': 'bar'})
        self.assertEqual(draft.last_step, 2)
        self.assertTrue(AuditLog.objects.filter(action='employee_edit_draft_created', object_id=str(self.target.id)).exists())

    def test_post_again_updates_same_row_and_logs_updated(self):
        self.client.post(self.url, {'data': {'foo': 'bar'}, 'last_step': 1}, format='json')
        resp = self.client.post(self.url, {'data': {'foo': 'baz'}, 'last_step': 3}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(EmployeeEditDraft.objects.filter(employee=self.target, created_by=self.hr_user).count(), 1)
        draft = EmployeeEditDraft.objects.get(employee=self.target, created_by=self.hr_user)
        self.assertEqual(draft.data, {'foo': 'baz'})
        self.assertEqual(draft.last_step, 3)
        self.assertTrue(AuditLog.objects.filter(action='employee_edit_draft_updated').exists())

    def test_get_after_post_returns_draft(self):
        self.client.post(self.url, {'data': {'foo': 'bar'}, 'last_step': 2}, format='json')
        resp = self.client.get(self.url)
        self.assertEqual(resp.data['data']['draft']['data'], {'foo': 'bar'})
        self.assertEqual(resp.data['data']['draft']['last_step'], 2)

    def test_resume_logs_and_returns_draft(self):
        self.client.post(self.url, {'data': {'foo': 'bar'}, 'last_step': 2}, format='json')
        resp = self.client.post(self.resume_url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['draft']['data'], {'foo': 'bar'})
        self.assertTrue(AuditLog.objects.filter(action='employee_edit_draft_resumed').exists())

    def test_resume_with_no_draft_404s(self):
        resp = self.client.post(self.resume_url)
        self.assertEqual(resp.status_code, 404)

    def test_delete_removes_draft_and_logs_discarded(self):
        self.client.post(self.url, {'data': {'foo': 'bar'}, 'last_step': 2}, format='json')
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(EmployeeEditDraft.objects.filter(employee=self.target, created_by=self.hr_user).exists())
        self.assertTrue(AuditLog.objects.filter(action='employee_edit_draft_discarded').exists())

    def test_delete_with_no_draft_is_a_no_op_200(self):
        resp = self.client.delete(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(AuditLog.objects.filter(action='employee_edit_draft_discarded').exists())

    def test_without_employees_edit_permission_403s(self):
        plain_role = make_role('edit_draft_plain')
        plain_user = make_user('plain-editdraft@test.com', role=plain_role, password='TestPass123!')
        self.client.force_authenticate(user=plain_user)
        resp = self.client.post(self.url, {'data': {}, 'last_step': 0}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_draft_is_private_to_the_admin_who_created_it(self):
        self.client.post(self.url, {'data': {'secret': 'hr-one'}, 'last_step': 1}, format='json')

        other_hr_role = make_role('edit_draft_hr2', permission_codenames=['employees.edit'])
        other_hr = make_user('hr2-editdraft@test.com', role=other_hr_role, password='TestPass123!')
        self.client.force_authenticate(user=other_hr)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['data']['draft'])

        resume_resp = self.client.post(self.resume_url)
        self.assertEqual(resume_resp.status_code, 404)

        # The second admin saving their own draft must not clobber the first's.
        self.client.post(self.url, {'data': {'secret': 'hr-two'}, 'last_step': 0}, format='json')
        self.assertEqual(EmployeeEditDraft.objects.filter(employee=self.target).count(), 2)
        self.assertEqual(
            EmployeeEditDraft.objects.get(employee=self.target, created_by=self.hr_user).data,
            {'secret': 'hr-one'},
        )

    def test_invalid_data_type_rejected(self):
        resp = self.client.post(self.url, {'data': 'not-an-object', 'last_step': 0}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_saving_live_record_does_not_auto_delete_unrelated_drafts_table_sanity(self):
        # Sanity check only — the actual "save live record clears the draft"
        # behavior lives in the frontend (EditRecordModal.onSaveChanges), not
        # this endpoint; this just confirms the draft row is otherwise inert
        # and doesn't affect EmployeeDetailView's own PUT.
        self.client.post(self.url, {'data': {'foo': 'bar'}, 'last_step': 2}, format='json')
        resp = self.client.put(reverse('employee-detail', args=['EMP91001']), {'full_name': 'Updated Name'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(EmployeeEditDraft.objects.filter(employee=self.target, created_by=self.hr_user).exists())


class DraftIndicatorTests(TestCase):
    """The "Draft" badge: shown to the admin who saved a draft, never to anyone else."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('draft_flag_hr', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-draftflag@test.com', role=role, password='TestPass123!')
        self.other_hr = make_user('hr2-draftflag@test.com', role=make_role('draft_flag_hr2', permission_codenames=['employees.edit', 'employees.view']), password='TestPass123!')
        self.target = make_user('target-draftflag@test.com', employee_id='EMP91002')
        EmployeeEditDraft.objects.create(employee=self.target, created_by=self.hr_user, data={'a': 1}, last_step=4)

    def _list_row(self, user):
        self.client.force_authenticate(user=user)
        resp = self.client.get(reverse('employee-list-create') + '?search=EMP91002')
        self.assertEqual(resp.status_code, 200, resp.data)
        return next(row for row in resp.data['data']['results'] if row['id'] == 'EMP91002')

    def test_list_flags_the_creators_draft(self):
        self.assertTrue(self._list_row(self.hr_user)['has_edit_draft'])

    def test_list_does_not_flag_it_for_another_admin(self):
        self.assertFalse(self._list_row(self.other_hr)['has_edit_draft'])

    def test_profile_flag_follows_the_draft_and_clears_on_discard(self):
        self.client.force_authenticate(user=self.hr_user)
        url = reverse('employee-detail', args=['EMP91002'])
        self.assertTrue(self.client.get(url).data['data']['has_edit_draft'])
        self.client.delete(reverse('employee-edit-draft', args=['EMP91002']))
        self.assertFalse(self.client.get(url).data['data']['has_edit_draft'])
