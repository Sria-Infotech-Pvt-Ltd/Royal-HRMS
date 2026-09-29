"""
Regression tests for EmployeeDetailView.get()'s self-view bypass —
was unconditionally gated on employees.view (an HR/admin-only
permission), so a plain employee viewing their OWN record via the ESS
"My Profile" -> "Open full employee profile" drawer (mode="self",
which deliberately reuses this exact endpoint) got a 403 before ever
reaching the self-view-aware bank-masking logic below it.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile


class EmployeeDetailSelfViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_plain_employee_can_view_their_own_record(self):
        role = make_role('employee_selfview_test')
        user = make_user('selfview@test.com', role=role, employee_id='EMP90001')
        self.client.force_authenticate(user=user)

        resp = self.client.get(reverse('employee-detail', args=['EMP90001']))
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_plain_employee_cannot_view_someone_elses_record(self):
        role = make_role('employee_selfview_test2')
        user = make_user('selfview2@test.com', role=role, employee_id='EMP90002')
        make_user('other-employee@test.com', role=make_role('other_role_selfview_test'), employee_id='EMP90003')
        self.client.force_authenticate(user=user)

        resp = self.client.get(reverse('employee-detail', args=['EMP90003']))
        self.assertEqual(resp.status_code, 403)

    def test_self_view_shows_real_unmasked_bank_details(self):
        role = make_role('employee_selfview_test3')
        user = make_user('selfview3@test.com', role=role, employee_id='EMP90004')
        EmployeeProfile.objects.create(user=user, account_number='1234567890', ifsc_code='HDFC0001234')
        self.client.force_authenticate(user=user)

        resp = self.client.get(reverse('employee-detail', args=['EMP90004']))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['profile']['account_number'], '1234567890')

    def test_hr_with_employees_view_can_still_view_others(self):
        hr_role = make_role('hr_selfview_test', permission_codenames=['employees.view'])
        hr_user = make_user('hr-selfview@test.com', role=hr_role, password='TestPass123!')
        make_user('target-selfview@test.com', role=make_role('employee_selfview_test4'), employee_id='EMP90005')
        self.client.force_authenticate(user=hr_user)

        resp = self.client.get(reverse('employee-detail', args=['EMP90005']))
        self.assertEqual(resp.status_code, 200, resp.data)
