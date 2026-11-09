"""Proves the voice tests cannot reach a real paid provider (see tests/__init__.py)."""
from __future__ import annotations

import requests
from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.voice_commands import sarvam_client
from apps.voice_commands.tests import ExternalProviderBlockedError


class ExternalCallIsolationTests(SimpleTestCase):
    def test_no_sarvam_key_is_configured_by_default_in_tests(self):
        self.assertEqual(settings.SARVAM_API_KEY, '')
        self.assertFalse(sarvam_client.is_configured())

    def test_a_real_sarvam_request_is_blocked_even_when_a_key_is_set(self):
        with override_settings(SARVAM_API_KEY='sk_test_key'):
            self.assertTrue(sarvam_client.is_configured())
            with self.assertRaises(ExternalProviderBlockedError):
                requests.post('https://api.sarvam.ai/v1/chat/completions', json={}, timeout=1)

    def test_blocked_call_is_a_requests_error_so_production_error_handling_still_runs(self):
        with override_settings(SARVAM_API_KEY='sk_test_key'):
            self.assertIsNone(sarvam_client.chat_completion([{'role': 'user', 'content': 'hi'}]))

    def test_other_hosts_are_not_touched_by_the_guard(self):
        # Only the provider hosts are blocked; a non-provider host reaches the real Session.request (here: a bad URL
        # scheme, which fails locally before any network access).
        with self.assertRaises(requests.exceptions.InvalidSchema):
            requests.get('nonexistent-scheme://example.invalid/')
