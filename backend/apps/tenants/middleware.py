"""
Resolves which company's PostgreSQL schema a request runs against, from the
validated `royal_access_token` cookie's `company_schema` claim — NOT from
the request's hostname. This project's login form takes a Company ID field
(see apps/accounts/views.py LoginView), not a subdomain, so django-tenants'
own TenantMainMiddleware (host-based) isn't used; this replaces it.

Runs first in MIDDLEWARE (see config/settings.py) so every view's ORM
queries are already scoped to the right company before any permission
check or view code runs — none of the existing business logic needed to
change for multi-tenancy because of this.
"""
import logging

from django.db import connection
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.feature_gate import resolve_module_for_path
from apps.tenants.models import MODULE_LABELS, Client

logger = logging.getLogger(__name__)


class TenantSchemaMiddleware(MiddlewareMixin):
    """
    Defaults every request to the public schema (registry only, no company
    data) — this is deliberately the fail-closed default: an invalid,
    missing, or expired token means no tenant data is reachable at all,
    rather than accidentally leaking whichever tenant a previous request on
    a reused connection/thread happened to activate.

    The login and token-refresh endpoints resolve their own tenant
    explicitly (LoginView looks up the Client from the submitted company
    code) — they don't rely on this middleware, since at that point there
    is no token yet.
    """

    def process_request(self, request):
        connection.set_schema_to_public()

        # Platform-admin requests must always run on public (Client and
        # PlatformAdmin both live there) regardless of any stray tenant
        # cookie the same browser might also be carrying (e.g. someone
        # testing both a company login and the platform-admin area in one
        # browser session) — this API's own auth reads a completely
        # separate cookie anyway, but this keeps schema activation
        # deterministic rather than relying on that.
        if request.path.startswith('/api/platform-admin/'):
            return

        token_str = request.COOKIES.get('royal_access_token')
        if not token_str:
            return

        try:
            token = AccessToken(token_str)
        except TokenError:
            # Invalid/expired — leave on public; DRF's own auth will reject
            # the request normally for endpoints that require a valid token.
            return

        schema_name = token.get('company_schema')
        if not schema_name:
            return

        try:
            tenant = Client.objects.get(schema_name=schema_name, is_active=True)
        except Client.DoesNotExist:
            logger.warning('Access token referenced unknown/inactive schema %s', schema_name)
            return

        connection.set_tenant(tenant)

        module = resolve_module_for_path(request.path)
        if module and not tenant.has_module(module):
            # Not core.responses.error() here: that returns a DRF Response,
            # which needs APIView.finalize_response() to actually render as
            # JSON — plain Django middleware never goes through that
            # pipeline. JsonResponse matches the same envelope shape instead.
            label = MODULE_LABELS.get(module, module)
            return JsonResponse(
                {
                    'status': 'error',
                    'message': f'{label} is not enabled for your company. Contact your administrator to enable it.',
                    'data': {},
                },
                status=403,
            )
