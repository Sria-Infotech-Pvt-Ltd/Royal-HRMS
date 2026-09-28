"""
Regression tests for the IFSC -> Bank/Branch lookup (see views_ifsc.py) —
mocks the outbound Razorpay call so these run fast/deterministically and
don't depend on a third-party service being reachable.
"""
from __future__ import annotations

from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


class IfscLookupTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('ifsc_lookup_test')
        user = make_user('ifsc-lookup@test.com', role=role, password='TestPass123!')
        self.client.force_authenticate(user=user)

    @patch('apps.accounts.views_ifsc.requests.get')
    def test_valid_code_returns_bank_and_branch(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: {
            'BANK': 'HDFC Bank', 'BRANCH': 'TEST BRANCH',
            'ADDRESS': '123 Test St', 'CITY': 'Pune', 'STATE': 'MAHARASHTRA',
        })
        resp = self.client.get(reverse('onboarding-ifsc-lookup', args=['HDFC0001234']))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['bank'], 'HDFC Bank')
        self.assertEqual(resp.data['data']['branch'], 'TEST BRANCH')

    def test_malformed_code_rejected_before_any_network_call(self):
        resp = self.client.get(reverse('onboarding-ifsc-lookup', args=['NOTVALID']))
        self.assertEqual(resp.status_code, 400)

    @patch('apps.accounts.views_ifsc.requests.get')
    def test_unknown_code_returns_404(self, mock_get):
        mock_get.return_value = Mock(status_code=404)
        resp = self.client.get(reverse('onboarding-ifsc-lookup', args=['ABCD0999999']))
        self.assertEqual(resp.status_code, 404)

    @patch('apps.accounts.views_ifsc.requests.get')
    def test_network_failure_returns_502_not_500(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError('boom')
        resp = self.client.get(reverse('onboarding-ifsc-lookup', args=['HDFC0001234']))
        self.assertEqual(resp.status_code, 502)

    def test_requires_authentication(self):
        anon_client = APIClient()
        resp = anon_client.get(reverse('onboarding-ifsc-lookup', args=['HDFC0001234']))
        self.assertEqual(resp.status_code, 401)
