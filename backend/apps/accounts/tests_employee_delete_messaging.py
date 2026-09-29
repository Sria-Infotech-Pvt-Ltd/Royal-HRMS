"""
Regression tests for EmployeeDetailView.delete()'s messaging and
idempotency — QA report issue #3 (High): the endpoint only ever
soft-deletes (is_active=False, full record incl. PII retained for
statutory compliance) but used to unconditionally say "deleted
successfully" (misleading), and calling it twice on the same employee
both times reported success with no indication the second call did
nothing new.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


class EmployeeDeleteMessagingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_delete_msg_test', permission_codenames=['employees.delete'])
        self.hr_user = make_user('hr-deletemsg@test.com', role=hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)
        self.target = make_user('target-deletemsg@test.com', role=make_role('employee_delete_msg_test'), employee_id='EMP91001')

    def test_delete_message_does_not_claim_full_deletion(self):
        resp = self.client.delete(reverse('employee-detail', args=['EMP91001']))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('deleted successfully', resp.data['message'].lower())
        self.assertIn('deactivat', resp.data['message'].lower())

        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        # The record itself is retained, not removed.
        self.assertTrue(self.target.email)

    def test_deleting_an_already_inactive_employee_is_rejected(self):
        first = self.client.delete(reverse('employee-detail', args=['EMP91001']))
        self.assertEqual(first.status_code, 200, first.data)

        second = self.client.delete(reverse('employee-detail', args=['EMP91001']))
        self.assertEqual(second.status_code, 400)
        self.assertIn('already deactivated', second.data['message'].lower())
