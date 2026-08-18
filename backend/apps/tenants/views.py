import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from apps.tenants.authentication import PlatformAdminAuthentication
from apps.tenants.models import ALL_MODULES, Client, PlatformAdmin, PlatformSMTPSettings
from apps.tenants.permissions import IsPlatformAdmin
from apps.tenants.serializers import (
    ClientCreateSerializer, ClientSerializer, PlatformAdminLoginSerializer, PlatformSMTPSettingsSerializer,
)
from apps.tenants.services import CompanyCodeTaken, InvalidModules, create_pending_client
from apps.tenants.tasks import finish_provisioning_task
from apps.tenants.throttles import PlatformAdminLoginRateThrottle
from apps.tenants.tokens import PlatformAdminRefreshToken

logger = logging.getLogger(__name__)

_ACCESS_COOKIE  = 'platform_access_token'
_REFRESH_COOKIE = 'platform_refresh_token'


def _set_platform_cookies(resp, access: str, refresh: str | None = None) -> None:
    resp.set_cookie(
        _ACCESS_COOKIE, access,
        max_age=900, httponly=True, secure=not settings.DEBUG, samesite='Lax', domain=None,
    )
    if refresh is not None:
        resp.set_cookie(
            _REFRESH_COOKIE, refresh,
            max_age=604800, httponly=True, secure=not settings.DEBUG, samesite='Lax', domain=None,
        )


class ResolveCompanyDomainView(APIView):
    """
    Unauthenticated — lets the frontend ask "which company does the domain
    the browser is actually on belong to?" so a company with a real custom
    domain configured (Client.custom_domain, set by a platform admin) can
    skip typing a Company ID and land straight on their own branded login.

    Takes ?domain= explicitly rather than reading the request's own Host
    header — this request already crossed the Next.js proxy by the time it
    reaches Django, and what browser Host header survives that hop isn't
    something to rely on. window.location.hostname on the frontend is
    always accurate, so it's passed through as a plain query param instead.

    Setting Client.custom_domain alone does not make a domain reachable —
    see the field's own docstring in apps/tenants/models.py for the DNS/
    hosting steps that still have to happen outside this codebase.
    """
    permission_classes     = [AllowAny]
    authentication_classes = []

    def get(self, request):
        domain = (request.query_params.get('domain') or '').strip().lower()
        if not domain:
            return error('domain query parameter is required.')
        try:
            client = Client.objects.get(custom_domain__iexact=domain, is_active=True)
        except Client.DoesNotExist:
            return error('No company registered for this domain.', http_status=status.HTTP_404_NOT_FOUND)
        return success('OK', data={'company_code': client.company_code})


class PlatformAdminLoginView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []
    throttle_classes       = [PlatformAdminLoginRateThrottle]

    def post(self, request):
        serializer = PlatformAdminLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        email    = serializer.validated_data['email'].strip().lower()
        password = serializer.validated_data['password']

        try:
            admin = PlatformAdmin.objects.get(email__iexact=email, is_active=True)
        except PlatformAdmin.DoesNotExist:
            return error('Invalid email or password.', http_status=status.HTTP_401_UNAUTHORIZED)

        if admin.is_locked():
            remaining = admin.locked_until - timezone.now()
            minutes   = int(remaining.total_seconds() // 60) + 1
            return error(
                f'Account locked due to multiple failed login attempts. '
                f'Try again in {minutes} minute(s).',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if not admin.check_password(password):
            admin.increment_failed_login()
            logger.warning('Failed platform admin login attempt for %s (attempt %d)', email, admin.failed_login_attempts)
            return error('Invalid email or password.', http_status=status.HTTP_401_UNAUTHORIZED)

        admin.reset_failed_login()
        admin.last_login = timezone.now()
        admin.save(update_fields=['last_login', 'updated_at'])

        refresh = PlatformAdminRefreshToken.for_admin(admin)
        logger.info('Platform admin %s logged in', email)

        resp = success('Login successful.', data={
            'admin': {'id': str(admin.id), 'email': admin.email, 'full_name': admin.full_name},
        })
        _set_platform_cookies(resp, str(refresh.access_token), str(refresh))
        return resp


class PlatformAdminLogoutView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def post(self, request):
        # No .blacklist() call here — rest_framework_simplejwt.token_blacklist
        # is a TENANT_APP (its models FK to the tenant User model, see
        # config/settings.py SHARED_APPS/TENANT_APPS split), and a
        # platform-admin request never activates a tenant schema, so those
        # tables don't exist in `public`. Cookie deletion alone is enough
        # for this low-traffic internal surface.
        logger.info('Platform admin %s logged out', request.user.email)
        resp = success('Logged out successfully.')
        resp.delete_cookie(_ACCESS_COOKIE, path='/')
        resp.delete_cookie(_REFRESH_COOKIE, path='/')
        return resp


class PlatformAdminTokenRefreshView(APIView):
    """Silent token refresh. Reads the httpOnly refresh cookie → sets a new httpOnly access cookie."""
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_refresh = request.COOKIES.get(_REFRESH_COOKIE)
        if not raw_refresh:
            return error('Session expired. Please log in again.', http_status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = PlatformAdminRefreshToken(raw_refresh)
        except TokenError:
            return error('Token is invalid or expired.', http_status=status.HTTP_401_UNAUTHORIZED)

        if not refresh.get('is_platform_admin'):
            return error('Invalid session.', http_status=status.HTTP_401_UNAUTHORIZED)

        if not PlatformAdmin.objects.filter(pk=refresh['platform_admin_id'], is_active=True).exists():
            return error('Account not found or inactive.', http_status=status.HTTP_401_UNAUTHORIZED)

        # Deliberately does not rotate/blacklist the refresh token (see
        # PlatformAdminLogoutView for why) — just mints a fresh access
        # token from the still-valid refresh token.
        resp = success('Token refreshed successfully.')
        _set_platform_cookies(resp, str(refresh.access_token))
        return resp


class PlatformAdminMeView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def get(self, request):
        admin = request.user
        return success('OK', data={
            'id': str(admin.id), 'email': admin.email, 'full_name': admin.full_name,
        })


class CompanyListCreateView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def get(self, request):
        clients = Client.objects.all().order_by('-created_at')
        page_obj, paginator = paginate(clients, request, default_page_size=20)
        return success('Companies retrieved.', paginated_data(
            paginator, page_obj, ClientSerializer(page_obj.object_list, many=True).data,
        ))

    def post(self, request):
        serializer = ClientCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data = serializer.validated_data
        # Only the fast part (uniqueness/module validation + one registry
        # row insert) happens in this request — schema creation and
        # everything after it runs in a Celery task, independent of this
        # web server process (see apps/tenants/services.py's module
        # docstring for why: the server itself used to kill synchronous
        # provisioning mid-migration on every restart/reload).
        try:
            client = create_pending_client(
                company_code=data['company_code'],
                company_name=data['company_name'],
                modules=data['modules'],
            )
        except InvalidModules as exc:
            return error(f'{exc} Valid: {", ".join(ALL_MODULES)}')
        except CompanyCodeTaken as exc:
            return error(f'Company code "{exc}" is already in use.')

        finish_provisioning_task.delay(str(client.id), data['admin_email'], client.enabled_modules)

        logger.info(
            'Company %s provisioning started in the background by platform admin %s',
            client.company_code, request.user.email,
        )
        return success(
            'Company creation started — this runs in the background and takes a few minutes. '
            'It will show as "Active" in the list once ready, with a button to view its login password.',
            data={'client': ClientSerializer(client).data},
            http_status=status.HTTP_202_ACCEPTED,
        )


class CompanyDetailView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def _get_client(self, pk):
        try:
            return Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return None

    def get(self, request, pk):
        client = self._get_client(pk)
        if not client:
            return error('Company not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Company retrieved.', ClientSerializer(client).data)

    def patch(self, request, pk):
        client = self._get_client(pk)
        if not client:
            return error('Company not found.', http_status=status.HTTP_404_NOT_FOUND)

        update_fields = ['updated_at']
        if 'is_active' in request.data:
            client.is_active = bool(request.data['is_active'])
            update_fields.append('is_active')
        if 'enabled_modules' in request.data:
            modules = request.data['enabled_modules']
            if not isinstance(modules, list) or (set(modules) - set(ALL_MODULES)):
                return error(f'enabled_modules must be a list drawn from: {", ".join(ALL_MODULES)}')
            client.enabled_modules = modules
            update_fields.append('enabled_modules')
        if 'custom_domain' in request.data:
            domain = (request.data['custom_domain'] or '').strip().lower()
            if domain and Client.objects.exclude(pk=client.pk).filter(custom_domain__iexact=domain).exists():
                return error(f'Domain "{domain}" is already assigned to another company.')
            client.custom_domain = domain
            update_fields.append('custom_domain')

        client.save(update_fields=update_fields)
        logger.info('Company %s updated by platform admin %s', client.company_code, request.user.email)
        return success('Company updated.', ClientSerializer(client).data)


class CompanyRevealPasswordView(APIView):
    """
    Shows a company's generated admin password exactly once, then clears
    it — the async-provisioning equivalent of the password the old
    synchronous POST /companies/ response used to return directly, back
    when the whole thing finished within one HTTP request/response cycle.
    """
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def post(self, request, pk):
        try:
            client = Client.objects.get(pk=pk)
        except Client.DoesNotExist:
            return error('Company not found.', http_status=status.HTTP_404_NOT_FOUND)

        if not client.pending_admin_password:
            return error(
                'No password available — either already viewed, or provisioning isn\'t finished yet.',
                http_status=status.HTTP_404_NOT_FOUND,
            )

        password = client.pending_admin_password
        client.pending_admin_password = ''
        client.save(update_fields=['pending_admin_password', 'updated_at'])
        logger.info('Password for company %s revealed by platform admin %s', client.company_code, request.user.email)
        return success('Password retrieved — this is the only time it will be shown.', data={'password': password})


class PlatformSMTPSettingsView(APIView):
    """
    The platform's own outbound-mail account (apps.tenants.models.
    PlatformSMTPSettings) — used only for cross-tenant emails like
    "your company has been provisioned" (see
    apps.tenants.utils.send_company_provisioned_email), never for any one
    company's own mail (that's apps.accounts.models.SMTPSettings, a
    separate per-tenant setting).
    """
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def get(self, request):
        smtp = PlatformSMTPSettings.get_solo()
        return success('Platform SMTP settings retrieved.', PlatformSMTPSettingsSerializer(smtp).data)

    def put(self, request):
        smtp = PlatformSMTPSettings.get_solo()
        # password is write_only + not required — omitting it in a PUT keeps
        # the existing one rather than blanking it out, so the platform
        # admin doesn't have to re-enter it just to change e.g. from_email.
        data = {k: v for k, v in request.data.items() if not (k == 'password' and not v)}
        serializer = PlatformSMTPSettingsSerializer(smtp, data=data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('Platform SMTP settings updated by %s', request.user.email)
        return success('Platform SMTP settings saved.', PlatformSMTPSettingsSerializer(smtp).data)
