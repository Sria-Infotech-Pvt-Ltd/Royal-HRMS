"""
WebSocket auth middleware — mirrors apps.accounts.authentication.CookieJWTAuthentication
for the Channels ASGI stack.

The REST API authenticates via the httpOnly 'royal_access_token' cookie (see
CookieJWTAuthentication) rather than Django sessions, so Channels' built-in
AuthMiddlewareStack (session-based) doesn't apply here — this reads the same
cookie and validates it with the same SimpleJWT logic instead.
"""
import logging
from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

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
def _get_user_from_token(raw_token: str):
    from django.db import close_old_connections
    from rest_framework_simplejwt.authentication import JWTAuthentication

    if not raw_token:
        return AnonymousUser()

    try:
        auth = JWTAuthentication()
        validated = auth.get_validated_token(raw_token.encode())
        return auth.get_user(validated)
    except Exception:
        return AnonymousUser()
    finally:
        # database_sync_to_async runs this on a thread-pool thread and does NOT
        # close the DB connection it opens afterward (unlike a normal Django
        # request) - that thread's connection then sits idle until the same
        # thread happens to get reused, which can be hours for a big pool with
        # sporadic traffic. Confirmed directly: aira_db was holding 53 idle
        # connections (some 9+ hours old) out of Postgres's 100-connection
        # limit, causing "Database is temporarily unavailable" across every
        # app on the server, not just Aira. Same fix already applied in
        # config/celery.py for the same reason.
        close_old_connections()


class CookieJWTAuthMiddleware(BaseMiddleware):
    """Populates scope['user'] from the royal_access_token cookie on the WS handshake."""

    async def __call__(self, scope, receive, send):
        raw_token = _cookie_from_scope(scope, 'royal_access_token')
        scope['user'] = await _get_user_from_token(raw_token)
        return await super().__call__(scope, receive, send)


def CookieJWTAuthMiddlewareStack(inner):
    return CookieJWTAuthMiddleware(inner)
