"""
Phase 1 Task A — per-request context for audit/history, using contextvars
(safe across ASGI/Channels, unlike thread-locals). Set by
RequestContextMiddleware for real HTTP requests; set_context() is the
same hook for Celery tasks, management commands and the voice module, so
their ChangeHistory entries are labelled with the right channel too.
"""
from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass, field


@dataclass
class RequestContext:
    actor_id: int | None = None
    ip_address: str | None = None
    user_agent: str = ''
    request_id: str = ''
    channel: str = 'system'  # ui, api_key, system, import, voice, celery


_current: contextvars.ContextVar[RequestContext] = contextvars.ContextVar(
    'platform_request_context', default=RequestContext(),
)


def get_context() -> RequestContext:
    return _current.get()


def set_context(**kwargs) -> contextvars.Token:
    """For Celery tasks / management commands / voice module — e.g.
    set_context(channel='celery', actor_id=None). Returns a token; callers
    that want to reset afterward can pass it to reset_context()."""
    ctx = RequestContext(**{**get_context().__dict__, **kwargs})
    return _current.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    _current.reset(token)


def _client_ip(request) -> str | None:
    # Mirrors core.responses.get_client_ip's own proxy-header handling —
    # intentionally duplicated here rather than imported, to keep
    # platform_core free of a dependency on `core` for something this small.
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get('HTTP_X_REQUEST_ID') or uuid.uuid4().hex

        # KNOWN LIMITATION (see PHASE1_REPORT.md): this app authenticates
        # via a DRF authentication class (JWT cookie / ExternalAPIKeyAuth),
        # which resolves request.user lazily on DRF's OWN Request wrapper
        # during view dispatch — not on the plain HttpRequest this Django
        # middleware receives, and not during Django's own
        # AuthenticationMiddleware (this app doesn't use session auth).
        # So `request.user` here is reliably unset/anonymous at this point
        # in the chain; actor_id will read as None for every request until
        # a DRF-level hook (e.g. a shared authentication class or
        # permission that calls set_context(actor_id=...) once DRF has
        # actually resolved the user) is added — deliberately NOT guessed
        # at here. IP/user-agent/request_id are unaffected by this and are
        # reliable now.
        token = set_context(
            ip_address=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            request_id=request_id,
        )
        try:
            response = self.get_response(request)
        finally:
            reset_context(token)

        response['X-Request-ID'] = request_id
        return response
