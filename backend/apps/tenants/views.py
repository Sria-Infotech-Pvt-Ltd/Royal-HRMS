import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, get_client_ip, success

from apps.tenants.authentication import PlatformAdminAuthentication
from apps.tenants.models import (
    ALL_MODULES, Client, PlatformAdmin, PlatformAdminAuditLog, PlatformAdminOTP,
    PlatformAdminPasswordResetToken, PlatformSMTPSettings,
)
from apps.tenants.permissions import IsPlatformAdmin
from apps.tenants.serializers import (
    ClientCreateSerializer, ClientSerializer, PlatformAdminAccountSerializer, PlatformAdminAuditLogSerializer,
    PlatformAdminChangePasswordSerializer, PlatformAdminForgotPasswordSerializer, PlatformAdminInviteSerializer,
    PlatformAdminLoginSerializer, PlatformAdminResetPasswordSerializer, PlatformAdminVerifyOtpSerializer,
    PlatformSMTPSettingsSerializer,
)
from apps.tenants.services import CompanyCodeTaken, InvalidModules, create_pending_client, generate_password
from apps.tenants.tasks import finish_provisioning_task
from apps.tenants.throttles import (
    PlatformAdminForgotPasswordRateThrottle, PlatformAdminLoginRateThrottle, PlatformAdminOTPVerifyRateThrottle,
)
from apps.tenants.tokens import PlatformAdminRefreshToken
from apps.tenants.utils import send_platform_admin_invite_email, send_platform_admin_otp_email

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


def _log_platform_action(request, action: str, target_company: Client | None = None, changes: dict | None = None) -> None:
    """
    Every platform-admin action that changes something gets a row here —
    previously nonexistent, unlike every tenant-side action which already
    gets an apps.accounts.models.AuditLog row. Best-effort: a logging
    failure must never block the actual action it's recording.
    """
    try:
        PlatformAdminAuditLog.objects.create(
            admin=request.user, action=action, target_company=target_company,
            changes=changes or {}, ip_address=get_client_ip(request),
        )
    except Exception:
        logger.exception('Failed to write platform-admin audit log for action %s', action)


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
                contact_name=data['contact_name'],
                contact_phone=data['contact_phone'],
                address=data['address'],
                gstin=data['gstin'],
                expected_employee_count=data['expected_employee_count'],
                contract_start_date=data['contract_start_date'],
            )
        except InvalidModules as exc:
            return error(f'{exc} Valid: {", ".join(ALL_MODULES)}')
        except CompanyCodeTaken as exc:
            return error(f'Company code "{exc}" is already in use.')

        finish_provisioning_task.delay(str(client.id), data['admin_email'], client.enabled_modules)

        _log_platform_action(request, 'company_created', target_company=client, changes={
            'company_name': client.company_name, 'modules': client.enabled_modules,
        })
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

        # Account-management context — optional, none of it affects
        # provisioning or login, so a blank value just clears the field.
        if 'contact_name' in request.data:
            client.contact_name = (request.data['contact_name'] or '').strip()
            update_fields.append('contact_name')
        if 'contact_phone' in request.data:
            client.contact_phone = (request.data['contact_phone'] or '').strip()
            update_fields.append('contact_phone')
        if 'address' in request.data:
            client.address = (request.data['address'] or '').strip()
            update_fields.append('address')
        if 'gstin' in request.data:
            from apps.tenants.serializers import _GSTIN_RE
            gstin = (request.data['gstin'] or '').strip().upper()
            if gstin and not _GSTIN_RE.match(gstin):
                return error('Enter a valid 15-character GSTIN (e.g. 22AAAAA0000A1Z5).')
            client.gstin = gstin
            update_fields.append('gstin')
        if 'expected_employee_count' in request.data:
            raw = request.data['expected_employee_count']
            if raw in (None, ''):
                client.expected_employee_count = None
            else:
                try:
                    count = int(raw)
                    if count < 1:
                        raise ValueError
                except (TypeError, ValueError):
                    return error('expected_employee_count must be a positive whole number.')
                client.expected_employee_count = count
            update_fields.append('expected_employee_count')
        if 'contract_start_date' in request.data:
            raw = request.data['contract_start_date']
            if raw in (None, ''):
                client.contract_start_date = None
            else:
                try:
                    client.contract_start_date = date.fromisoformat(raw)
                except (TypeError, ValueError):
                    return error('contract_start_date must be in YYYY-MM-DD format.')
            update_fields.append('contract_start_date')

        client.save(update_fields=update_fields)
        _log_platform_action(request, 'company_updated', target_company=client, changes={
            f: request.data[f] for f in (
                'is_active', 'enabled_modules', 'contact_name', 'contact_phone',
                'address', 'gstin', 'expected_employee_count', 'contract_start_date',
            ) if f in request.data
        })
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
        _log_platform_action(request, 'company_password_revealed', target_company=client)
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


# ─── Platform-admin password recovery ─────────────────────────────────────────
# Mirrors apps.accounts.views's ForgotPasswordView/VerifyOTPView/
# ResetPasswordView exactly, but keyed to PlatformAdmin — previously the
# only way to recover a platform admin's forgotten password was direct
# database access, unlike every tenant user who already has this flow.

class PlatformAdminForgotPasswordView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []
    throttle_classes       = [PlatformAdminForgotPasswordRateThrottle]

    def post(self, request):
        serializer = PlatformAdminForgotPasswordSerializer(data=request.data, context={})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        admin = serializer.context.get('admin')
        if not admin:
            # Same response either way — never reveal whether the email is
            # a registered platform admin (see accounts.ForgotPasswordView).
            return success('OTP sent to your email address. It is valid for 10 minutes.')

        try:
            _, plain_otp = PlatformAdminOTP.create_for_admin(admin)
        except Exception:
            logger.exception('Failed to create platform-admin OTP for %s', admin.email)
            return error('Could not generate OTP. Please try again later.', http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            send_platform_admin_otp_email(admin.email, plain_otp, admin.full_name)
        except Exception:
            logger.exception('Failed to send platform-admin OTP email to %s', admin.email)
            return error(
                'Failed to send OTP email. Please check platform SMTP settings or try again later.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('Platform-admin OTP sent to %s', admin.email)
        return success('OTP sent to your email address. It is valid for 10 minutes.')


class PlatformAdminVerifyOtpView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []
    throttle_classes       = [PlatformAdminOTPVerifyRateThrottle]

    def post(self, request):
        serializer = PlatformAdminVerifyOtpSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        email     = serializer.validated_data['email']
        otp_input = serializer.validated_data['otp']

        try:
            admin = PlatformAdmin.objects.get(email__iexact=email, is_active=True)
        except PlatformAdmin.DoesNotExist:
            return error('No active platform admin found with this email address.')

        otp_obj = PlatformAdminOTP.objects.filter(admin=admin, is_used=False).order_by('-created_at').first()
        if not otp_obj:
            return error('No OTP found. Please request a new OTP.')

        PlatformAdminOTP.objects.filter(pk=otp_obj.pk).update(attempts=F('attempts') + 1)
        otp_obj.refresh_from_db(fields=['attempts'])

        if not otp_obj.is_valid():
            return error('OTP has expired or maximum attempts exceeded. Please request a new OTP.')
        if not otp_obj.check_otp(otp_input):
            return error('Invalid OTP. Please try again.')

        with transaction.atomic():
            otp_obj.is_used = True
            otp_obj.save(update_fields=['is_used'])
            reset_token = PlatformAdminPasswordResetToken.create_for_admin(admin)

        logger.info('Platform-admin OTP verified for %s', email)
        return success('OTP verified successfully.', data={'reset_token': str(reset_token.id)})


class PlatformAdminResetPasswordView(APIView):
    permission_classes     = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PlatformAdminResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        reset_token_id = serializer.validated_data['reset_token']
        new_password   = serializer.validated_data['new_password']

        try:
            token_obj = PlatformAdminPasswordResetToken.objects.select_related('admin').get(id=reset_token_id)
        except PlatformAdminPasswordResetToken.DoesNotExist:
            return error('Invalid or expired reset token.')

        if not token_obj.is_valid():
            return error('This reset token has already been used or has expired.')

        admin = token_obj.admin
        with transaction.atomic():
            admin.set_password(new_password)
            admin.failed_login_attempts = 0
            admin.locked_until          = None
            admin.save(update_fields=['password', 'failed_login_attempts', 'locked_until', 'updated_at'])
            token_obj.is_used = True
            token_obj.save(update_fields=['is_used'])

        logger.info('Password reset for platform admin %s', admin.email)
        return success('Password has been reset successfully. Please log in with your new password.')


class PlatformAdminChangePasswordView(APIView):
    """Voluntary change from My Account, for an already-authenticated platform admin."""
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def post(self, request):
        serializer = PlatformAdminChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        admin        = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        if not admin.check_password(old_password):
            return error('Current password is incorrect.')

        admin.set_password(new_password)
        admin.save(update_fields=['password', 'updated_at'])
        logger.info('Password changed for platform admin %s', admin.email)

        resp = success('Password changed successfully. Please log in again with your new password.')
        resp.delete_cookie(_ACCESS_COOKIE, path='/')
        resp.delete_cookie(_REFRESH_COOKIE, path='/')
        return resp


# ─── Platform admin accounts (invite / list / deactivate) ─────────────────────

class PlatformAdminAccountListCreateView(APIView):
    """
    Adding a second platform admin used to require the createsuperuser
    management command — there was no UI path at all. This lets an existing
    admin invite another one directly.
    """
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def get(self, request):
        admins = PlatformAdmin.objects.all().order_by('-created_at')
        page_obj, paginator = paginate(admins, request, default_page_size=20)
        return success('Platform admins retrieved.', paginated_data(
            paginator, page_obj, PlatformAdminAccountSerializer(page_obj.object_list, many=True).data,
        ))

    def post(self, request):
        serializer = PlatformAdminInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        email     = serializer.validated_data['email'].strip().lower()
        full_name = serializer.validated_data['full_name'].strip()
        password  = generate_password()

        new_admin = PlatformAdmin(email=email, full_name=full_name, is_active=True)
        new_admin.set_password(password)
        new_admin.save()

        send_platform_admin_invite_email(email, full_name, password)
        _log_platform_action(request, 'platform_admin_invited', changes={'email': email, 'full_name': full_name})
        logger.info('Platform admin %s invited by %s', email, request.user.email)

        return success(
            'Platform admin created — their login and temporary password were emailed to them.',
            data=PlatformAdminAccountSerializer(new_admin).data,
            http_status=status.HTTP_201_CREATED,
        )


class PlatformAdminAccountDetailView(APIView):
    """PATCH is_active only — deactivating another platform admin. An admin cannot deactivate themselves."""
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def patch(self, request, pk):
        try:
            target = PlatformAdmin.objects.get(pk=pk)
        except PlatformAdmin.DoesNotExist:
            return error('Platform admin not found.', http_status=status.HTTP_404_NOT_FOUND)

        if 'is_active' not in request.data:
            return error('is_active is required.')

        if str(target.pk) == str(request.user.pk) and not request.data['is_active']:
            return error('You cannot deactivate your own account.')

        target.is_active = bool(request.data['is_active'])
        target.save(update_fields=['is_active', 'updated_at'])
        _log_platform_action(
            request, 'platform_admin_deactivated' if not target.is_active else 'platform_admin_reactivated',
            changes={'email': target.email},
        )
        logger.info('Platform admin %s set is_active=%s by %s', target.email, target.is_active, request.user.email)
        return success('Platform admin updated.', PlatformAdminAccountSerializer(target).data)


# ─── Audit log + dashboard ─────────────────────────────────────────────────────

class PlatformAdminAuditLogListView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def get(self, request):
        logs = PlatformAdminAuditLog.objects.select_related('admin', 'target_company').all()
        page_obj, paginator = paginate(logs, request, default_page_size=20)
        return success('Audit log retrieved.', paginated_data(
            paginator, page_obj, PlatformAdminAuditLogSerializer(page_obj.object_list, many=True).data,
        ))


class PlatformAdminDashboardStatsView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes     = [IsPlatformAdmin]

    def _company_usage(self, clients: list[Client]) -> list[dict]:
        """
        Real activity per company — not just the registry row. Switches
        into each fully-provisioned company's own schema (same pattern as
        apps.tenants.utils.run_for_all_tenants) to count active employees
        and find the most recent AuditLog entry, so a platform admin can
        see which companies are actually being used versus paid-for but
        dormant. Skipped for anything not provisioning_status='active' —
        a pending/failed company's schema may not exist yet or may be
        missing tables (same reasoning as run_for_all_tenants).
        """
        from apps.accounts.models import AuditLog, User

        usage = []
        for client in clients:
            if client.provisioning_status != Client.PROVISIONING_ACTIVE:
                continue
            try:
                with client:
                    employee_count = User.objects.filter(is_active=True).count()
                    last_activity = AuditLog.objects.order_by('-created_at').first()
            except Exception:
                logger.exception('Failed to read usage stats for company %s', client.company_code)
                continue
            usage.append({
                'company_code':    client.company_code,
                'company_name':    client.company_name,
                'employee_count':  employee_count,
                'last_activity_at': last_activity.created_at.isoformat() if last_activity else None,
            })
        return usage

    def get(self, request):
        clients = list(Client.objects.all())
        module_counts = {m: 0 for m in ALL_MODULES}
        for client in clients:
            for module in client.enabled_modules or []:
                if module in module_counts:
                    module_counts[module] += 1

        recent = Client.objects.order_by('-created_at')[:5]
        company_usage = self._company_usage(clients)
        # Companies that have never logged a single action, or haven't in
        # 30+ days, surface first — the platform admin cares more about
        # spotting a dormant paying customer than re-confirming an active one.
        stale_cutoff = timezone.now() - timedelta(days=30)
        company_usage.sort(key=lambda u: u['last_activity_at'] or '')

        return success('Dashboard stats retrieved.', {
            'total_companies':    len(clients),
            'active_companies':   sum(1 for c in clients if c.is_active),
            'disabled_companies': sum(1 for c in clients if not c.is_active),
            'provisioning': {
                'pending': sum(1 for c in clients if c.provisioning_status == Client.PROVISIONING_PENDING),
                'active':  sum(1 for c in clients if c.provisioning_status == Client.PROVISIONING_ACTIVE),
                'failed':  sum(1 for c in clients if c.provisioning_status == Client.PROVISIONING_FAILED),
            },
            'module_adoption': module_counts,
            'recent_companies': ClientSerializer(recent, many=True).data,
            'company_usage': company_usage,
            'dormant_company_count': sum(
                1 for u in company_usage
                if not u['last_activity_at'] or u['last_activity_at'] < stale_cutoff.isoformat()
            ),
        })
