"""Test-only isolation for the voice-command tests: no automated test may reach a real, paid provider.

Voice's only external provider is Sarvam (``apps.voice_commands.sarvam_client``, called through ``requests``).
Importing this package (which unittest discovery does before running any voice test) does two things:

1. Blanks ``settings.SARVAM_API_KEY`` for the whole test process. A developer ``.env`` with a real key would otherwise
   let every "no match" transcript reach the LLM fallback and bill a real call. With no key the fallback takes its
   documented "not configured" path and returns the same generic no-match answer. Tests that need a key already set
   one with ``override_settings`` (see ``test_sarvam_client.py``), and that still works because ``override_settings``
   restores to the blank value afterwards.
2. Makes any HTTP request to a ``sarvam.ai`` host fail immediately with a ``ConnectionError`` (a safety net in case a
   test sets a key but forgets to mock the call). Tests that patch ``sarvam_client.requests.post`` are not affected,
   because the patched function never reaches ``Session.request``. Only ``sarvam.ai`` hosts are blocked, so nothing
   else in the process is touched.
"""
from __future__ import annotations

from urllib.parse import urlparse

import requests
from django.conf import settings

BLOCKED_PROVIDER_SUFFIXES = ('sarvam.ai',)


class ExternalProviderBlockedError(requests.ConnectionError):
    """Raised instead of making a real HTTP call to a paid provider during tests."""


_real_session_request = requests.sessions.Session.request


def _guarded_session_request(self, method, url, *args, **kwargs):
    host = (urlparse(str(url)).hostname or '').lower()
    if any(host == s or host.endswith('.' + s) for s in BLOCKED_PROVIDER_SUFFIXES):
        raise ExternalProviderBlockedError(f'Real call to {host} blocked in tests; mock it instead.')
    return _real_session_request(self, method, url, *args, **kwargs)


if requests.sessions.Session.request is _real_session_request:
    requests.sessions.Session.request = _guarded_session_request

settings.SARVAM_API_KEY = ''
