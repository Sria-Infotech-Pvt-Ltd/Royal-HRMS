"""
WebSocket auth middleware — mirrors apps.accounts.authentication.CookieJWTAuthentication
for the Channels ASGI stack.

The REST API authenticates via the httpOnly 'royal_access_token' cookie (see
CookieJWTAuthentication) rather than Django sessions, so Channels' built-in
AuthMiddlewareStack (session-based) doesn't apply here — this reads the same
cookie and validates it with the same SimpleJWT logic instead.

Tenant scoping: this used to skip schema activation entirely and just call
auth.get_user(validated), which runs a User query against whatever schema
the connection happened to be on. Since database_sync_to_async's underlying
thread pool can reuse the same OS thread (and Django's DB connection is
thread-local) across unrelated WebSocket connections, that could either
silently fail to find the user against the wrong schema, or worse, resolve
to a same-ID user from whichever tenant a previous connection on that
thread last activated. _get_user_and_schema_from_token now mirrors
apps.tenants.middleware.TenantSchemaMiddleware's fail-closed pattern:
always reset to public first, then only activate the tenant named in the
token's own 'company_schema' claim, verified against the Client registry,
before ever touching the User table.
"""
import logging
from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.db import connection

logger = logging.getLogger(__name__)


def _cookie_from_scope(scope: dict, name: str) -> str:
    """scope['headers'] is a list of (bytes, bytes) tuples per the ASGI spec."""
    for key, value in scope.get('headers') or []:
        if key == b'cookie':
            jar = SimpleCookie()
            jar.load(value.decode())
            morsel = jar.get(name)
            return morsel.value if morsel else ''
    return ''


@database_sync_to_async
def _get_user_and_schema_from_token(raw_token: str):
    """
    Returns (user, schema_name). schema_name is handed back explicitly (not
    left for the caller to read off `connection` later) because this runs
    inside database_sync_to_async's worker thread — by the time control
    returns to the consumer's plain async code, there's no reliable
    guarantee that reading `connection.schema_name` there reflects what was
    just activated here. Explicit return value sidesteps that entirely.
    """
    from rest_framework_simplejwt.authentication import JWTAuthentication

    from apps.tenants.models import Client

    # Fail-closed default — never leave whatever tenant schema a previous
    # connection on this reused thread happened to activate.
    connection.set_schema_to_public()

    if not raw_token:
        return AnonymousUser(), None

    try:
        auth = JWTAuthentication()
        validated = auth.get_validated_token(raw_token.encode())
    except Exception:
        return AnonymousUser(), None

    schema_name = validated.get('company_schema')
    if not schema_name:
        return AnonymousUser(), None

    try:
        tenant = Client.objects.get(schema_name=schema_name, is_active=True)
    except Client.DoesNotExist:
        logger.warning('WebSocket auth token referenced unknown/inactive schema %s', schema_name)
        return AnonymousUser(), None

    connection.set_tenant(tenant)

    try:
        return auth.get_user(validated), schema_name
    except Exception:
        return AnonymousUser(), None


class CookieJWTAuthMiddleware(BaseMiddleware):
    """Populates scope['user'] and scope['tenant_schema'] from the royal_access_token cookie on the WS handshake."""

    async def __call__(self, scope, receive, send):
        raw_token = _cookie_from_scope(scope, 'royal_access_token')
        scope['user'], scope['tenant_schema'] = await _get_user_and_schema_from_token(raw_token)
        return await super().__call__(scope, receive, send)


def CookieJWTAuthMiddlewareStack(inner):
    return CookieJWTAuthMiddleware(inner)
