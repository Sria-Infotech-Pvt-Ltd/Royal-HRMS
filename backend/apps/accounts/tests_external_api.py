"""
Regression tests for the External API (Project Budget & Tracking and any
future internal system that needs basic, read-only employee info without
a real HRMS login). Covers: API-key auth accept/reject, no bank/PAN/
Aadhaar data ever appears in the response, a revoked key stops working
immediately, and every fetch is audit-logged.
"""
from __future__ import annotations

import hashlib

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, ExternalAPIKey


def _make_key(name: str, raw_key: str = 'eak_testkey123', is_active: bool = True) -> ExternalAPIKey:
    return ExternalAPIKey.objects.create(
        name=name,
        key_hash=hashlib.sha256(raw_key.encode('utf-8')).hexdigest(),
        is_active=is_active,
    )


class ExternalEmployeeListAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('external_api_test_role')
        make_user('someone@test.com', role=role, employee_id='EMP00001')
        self.url = reverse('external-employee-list')

    def test_missing_api_key_is_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_invalid_api_key_is_rejected(self):
        resp = self.client.get(self.url, HTTP_X_API_KEY='not-a-real-key')
        self.assertEqual(resp.status_code, 401)

    def test_valid_api_key_is_accepted(self):
        _make_key('project_budget_tool')
        resp = self.client.get(self.url, HTTP_X_API_KEY='eak_testkey123')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_revoked_key_stops_working(self):
        _make_key('project_budget_tool', is_active=False)
        resp = self.client.get(self.url, HTTP_X_API_KEY='eak_testkey123')
        self.assertEqual(resp.status_code, 401)


class ExternalEmployeeListDataTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        _make_key('project_budget_tool')
        role = make_role('external_api_test_role2')
        self.employee = make_user(
            'jane@test.com', role=role, employee_id='EMP00002', full_name='Jane Doe',
        )

    def _get(self):
        return self.client.get(reverse('external-employee-list'), HTTP_X_API_KEY='eak_testkey123')

    def test_response_contains_only_basic_fields(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200, resp.data)
        row = next(r for r in resp.data['data']['results'] if r['employee_id'] == 'EMP00002')
        self.assertEqual(set(row.keys()), {
            'employee_id', 'full_name', 'email', 'department', 'designation', 'role', 'branch', 'is_active',
        })
        self.assertEqual(row['full_name'], 'Jane Doe')
        # No bank/PAN/Aadhaar-shaped keys ever, under any name.
        for forbidden in ('account_number', 'ifsc_code', 'bank_name', 'pan_number', 'pan_masked', 'aadhaar_number', 'aadhaar_masked'):
            self.assertNotIn(forbidden, row)

    def test_inactive_employees_excluded(self):
        self.employee.is_active = False
        self.employee.save(update_fields=['is_active'])
        resp = self._get()
        ids = [r['employee_id'] for r in resp.data['data']['results']]
        self.assertNotIn('EMP00002', ids)

    def test_fetch_is_audit_logged(self):
        self._get()
        log = AuditLog.objects.filter(action='external_employee_list_fetch').first()
        self.assertIsNotNone(log)
        self.assertIsNone(log.user)
        self.assertEqual(log.changes.get('client'), 'project_budget_tool')
