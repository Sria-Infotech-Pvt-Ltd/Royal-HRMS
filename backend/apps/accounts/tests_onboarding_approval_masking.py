"""
Regression tests for OnboardingApprovalSerializer.get_profile() masking
PAN/Aadhaar/bank fields for viewers without employees.view_sensitive —
this serializer used to nest a plain EmployeeProfileSerializer, which
returns full unmasked values (correct for the self-service /onboarding/
and /employees/me/ endpoints it's designed for, but a leak when reused
here to show HR someone ELSE's onboarding submission).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile, User


class OnboardingApprovalMaskingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.target = make_user('submitted@test.com', role=make_role('employee_masking_test'))
        self.target.onboarding_status = User.ONBOARDING_SUBMITTED
        self.target.save(update_fields=['onboarding_status'])
        EmployeeProfile.objects.create(
            user=self.target,
            pan_number='ABCDE1234F', aadhaar_number='123456789012',
            account_number='9876543210', ifsc_code='HDFC0001234',
            pf_number='PF123456789',
        )

    def _get_detail(self):
        return self.client.get(reverse('onboarding-approve', args=[self.target.id]))

    def test_viewer_without_view_sensitive_sees_masked_values(self):
        role = make_role('hr_no_sensitive_test', permission_codenames=['onboarding.approve'])
        hr = make_user('hr-nosensitive@test.com', role=role, password='TestPass123!')
        self.client.force_authenticate(user=hr)

        resp = self._get_detail()
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = resp.data['data']['profile']
        self.assertNotIn('ABCDE1234F', profile['pan_number'])
        self.assertNotIn('123456789012', profile['aadhaar_number'])
        self.assertNotIn('9876543210', profile['account_number'])
        self.assertNotIn('HDFC0001234', profile['ifsc_code'])
        self.assertNotIn('PF123456789', profile['pf_number'])
        self.assertTrue(profile['pan_number'].endswith('F'))
        self.assertIn('••••', profile['account_number'])

    def test_viewer_with_view_sensitive_sees_real_values(self):
        role = make_role('hr_sensitive_test', permission_codenames=['onboarding.approve', 'employees.view_sensitive'])
        hr = make_user('hr-sensitive@test.com', role=role, password='TestPass123!')
        self.client.force_authenticate(user=hr)

        resp = self._get_detail()
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = resp.data['data']['profile']
        self.assertEqual(profile['pan_number'], 'ABCDE1234F')
        self.assertEqual(profile['aadhaar_number'], '123456789012')
        self.assertEqual(profile['account_number'], '9876543210')

    def test_superuser_sees_real_values(self):
        role = make_role('no_perms_masking_test')
        admin = make_user('admin-masking@test.com', role=role, is_superuser=True)
        self.client.force_authenticate(user=admin)

        resp = self._get_detail()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['profile']['pan_number'], 'ABCDE1234F')
