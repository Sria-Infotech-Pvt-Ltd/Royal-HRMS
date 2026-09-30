"""
API-key authentication for OTHER INTERNAL SYSTEMS calling into this app —
not for real HRMS users. Every existing endpoint in this codebase
authenticates via the normal JWT-cookie login flow (a real logged-in
User), which doesn't apply to an unmanned system like the Project Budget
& Tracking tool: it has no employee login of its own, so it presents a
pre-shared API key in a header instead.

Deliberately its own, separate authentication class — not layered onto
JWTAuthentication — so a leaked/misused API key can only ever reach the
handful of endpoints that explicitly opt into this class, never anything
gated by the normal employees.* permission system.
"""
from __future__ import annotations

import hashlib

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import ExternalAPIKey

API_KEY_HEADER = 'HTTP_X_API_KEY'


class _ExternalServiceIdentity:
    """
    Stand-in for `request.user` on an external-API-key-authenticated
    request — there is no real User row for an external system, but DRF's
    IsAuthenticated permission (and anything else that reads
    request.user.is_authenticated) still needs something truthy here.
    """
    is_authenticated = True
    is_active = True
    pk = None

    def __init__(self, api_key: ExternalAPIKey):
        self.api_key = api_key
        self.name = api_key.name

    def __str__(self):
        return f'external-api:{self.name}'


class ExternalAPIKeyAuthentication(BaseAuthentication):
    """Validates the `X-API-Key` header against ExternalAPIKey.key_hash.

    Returns (service_identity, api_key) on success — `request.auth` is the
    real ExternalAPIKey row, which callers use for audit logging and
    per-key rate limiting (see ExternalAPIKeyThrottle)."""

    def authenticate(self, request):
        raw_key = request.META.get(API_KEY_HEADER)
        if not raw_key:
            return None

        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        api_key = ExternalAPIKey.objects.filter(key_hash=key_hash, is_active=True).first()
        if not api_key:
            raise AuthenticationFailed('Invalid or inactive API key.')

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=['last_used_at'])
        return (_ExternalServiceIdentity(api_key), api_key)

    def authenticate_header(self, request):
        # Returning a value here makes DRF respond 401 (not 403) when the
        # header is missing entirely, matching standard API-key convention.
        return 'X-API-Key'
