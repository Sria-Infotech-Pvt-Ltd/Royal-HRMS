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
from apps.tenants.models import ALL_MODULES, Client, PlatformAdmin
from apps.tenants.permissions import IsPlatformAdmin
from apps.tenants.serializers import ClientCreateSerializer, ClientSerializer, PlatformAdminLoginSerializer
from apps.tenants.services import CompanyCodeTaken, InvalidModules, provision_company
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
        try:
            result = provision_company(
                company_code=data['company_code'],
                company_name=data['company_name'],
                admin_email=data['admin_email'],
                modules=data['modules'],
            )
        except InvalidModules as exc:
            return error(f'{exc} Valid: {", ".join(ALL_MODULES)}')
        except CompanyCodeTaken as exc:
            return error(f'Company code "{exc}" is already in use.')
        except Exception:
            logger.exception('Company provisioning failed for %s', data['company_code'])
            return error(
                'Company provisioning failed partway through — check server logs before retrying.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('Company %s provisioned by platform admin %s', result['client'].company_code, request.user.email)
        return success('Company created.', data={
            'client':   ClientSerializer(result['client']).data,
            'password': result['password'],
        }, http_status=status.HTTP_201_CREATED)


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

        client.save(update_fields=update_fields)
        logger.info('Company %s updated by platform admin %s', client.company_code, request.user.email)
        return success('Company updated.', ClientSerializer(client).data)
