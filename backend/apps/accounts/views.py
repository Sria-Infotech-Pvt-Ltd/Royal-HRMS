
from __future__ import annotations

import logging
import os
from collections import defaultdict

import cloudinary.utils
import requests as http_req

from django.conf import settings
from django.core import signing
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import StreamingHttpResponse
from django.db.models.deletion import ProtectedError
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.responses import error, first_error, get_client_ip, success
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import (
    AuditLog,
    Company,
    Department,
    Designation,
    Document,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    OTPVerification,
    PasswordResetToken,
    Permission,
    Role,
    SMTPSettings,
    User,
)
from apps.accounts.serializers import (
    AuditLogSerializer,
    ChangePasswordSerializer,
    CompanySerializer,
    DepartmentSerializer,
    DesignationSerializer,
    DocumentSerializer,
    EmailTemplateAttachmentSerializer,
    EmailTemplateCategorySerializer,
    EmailTemplatePreviewSerializer,
    EmailTemplateSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    PermissionSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    SMTPSettingsSerializer,
    SMTPTestSerializer,
    VerifyOTPSerializer,
)
from apps.accounts.throttles import ForgotPasswordRateThrottle, LoginRateThrottle, OTPVerifyRateThrottle
from apps.accounts.tokens import RoleBasedRefreshToken
from apps.accounts.utils import send_otp_email, send_test_email

logger = logging.getLogger('accounts')



def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _employee_dict(user: User) -> dict:
    parts = user.full_name.strip().split(' ', 1)
    first = parts[0]
    last  = parts[1] if len(parts) > 1 else ''
    if user.is_active and user.must_change_password:
        emp_status = 'onboarding'
    elif not user.is_active:
        emp_status = 'inactive'
    else:
        emp_status = 'active'
    return {
        'id':             str(user.id),
        'employee_id':    user.employee_id,
        'first_name':     first,
        'last_name':      last,
        'full_name':      user.full_name,
        'email':          user.email,
        'phone':          user.phone,
        'department':     user.department,
        'designation':    user.designation,
        'branch':         user.branch,
        'role':           user.role.name         if user.role else '',
        'role_display':   user.role.display_name if user.role else '',
        'date_of_joining': str(user.date_of_joining) if user.date_of_joining else '',
        'date_joined':    user.date_joined.date().isoformat(),
        'is_active':      user.is_active,
        'status':         emp_status,
    }



# ─── Custom permissions ────────────────────────────────────────────────────────

class CanManageRoles(BasePermission):
    """Only hr_admin and system_admin may manage roles, permissions, and settings."""
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, _) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role
            and request.user.role.name in ('hr_admin', 'system_admin')
        )


# ─── Authentication ────────────────────────────────────────────────────────────

class LoginView(APIView):
    permission_classes      = [AllowAny]
    authentication_classes  = []
    throttle_classes        = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        email    = serializer.validated_data['email']
        password = serializer.validated_data['password']

        try:
            user = (
                User.objects
                    .select_related('role')
                    .prefetch_related('role__role_permissions__permission')
                    .get(email__iexact=email)
            )
        except User.DoesNotExist:
            return error('Invalid email or password.', http_status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return error(
                'Your account has been deactivated. Please contact the administrator.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_locked():
            remaining = user.locked_until - timezone.now()
            minutes   = int(remaining.total_seconds() // 60) + 1
            return error(
                f'Account locked due to multiple failed login attempts. '
                f'Try again in {minutes} minute(s).',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if not user.check_password(password):
            user.increment_failed_login()
            logger.warning(
                'Failed login attempt for %s from %s (attempt %d)',
                email, get_client_ip(request), user.failed_login_attempts,
            )
            return error('Invalid email or password.', http_status=status.HTTP_401_UNAUTHORIZED)

        ip = get_client_ip(request)
        user.reset_failed_login(ip_address=ip)

        refresh = RoleBasedRefreshToken.for_user(user)

        AuditLog.objects.create(
            user=user, action='login', module='accounts', ip_address=ip,
        )
        logger.info('User %s logged in from %s', email, ip)

        permissions = (
            [rp.permission.codename for rp in user.role.role_permissions.all()]
            if user.role else []
        )

        resp = success('Login successful.', data={
            'user': {
                'id':                  str(user.id),
                'email':               user.email,
                'full_name':           user.full_name,
                'role':                user.role.name if user.role else None,
                'role_display':        user.role.display_name if user.role else None,
                'employee_id':         user.employee_id,
                'department':          user.department,
                'designation':         user.designation,
                'branch':              user.branch,
                'must_change_password': user.must_change_password,
                'permissions':         permissions,
            },
        })
        resp.set_cookie(
            'royal_access_token', str(refresh.access_token),
            max_age=900, httponly=True, secure=not settings.DEBUG, samesite='Lax', domain=None,
        )
        resp.set_cookie(
            'royal_refresh_token', str(refresh),
            max_age=604800, httponly=True, secure=not settings.DEBUG, samesite='Lax', domain=None,
        )
        if settings.DEBUG:
            for name, morsel in resp.cookies.items():
                attrs = '; '.join(filter(None, [
                    f'Max-Age={morsel["max-age"]}',
                    f'Path={morsel["path"]}',
                    f'Domain={morsel["domain"]}' if morsel['domain'] else 'Domain=(not set)',
                    'Secure' if morsel['secure'] else 'Secure=(not set)',
                    'HttpOnly' if morsel['httponly'] else None,
                    f'SameSite={morsel["samesite"]}' if morsel['samesite'] else None,
                ]))
                logger.debug('[cookie-debug] Set-Cookie: %s=[token]; %s', name, attrs)
        return resp


class TokenRefreshAPIView(APIView):
    """Silent token refresh. Reads the httpOnly refresh cookie → sets new httpOnly cookies."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_str = request.COOKIES.get('royal_refresh_token')
        if not refresh_str:
            return error('Session expired. Please log in again.', http_status=status.HTTP_401_UNAUTHORIZED)
        serializer = TokenRefreshSerializer(data={'refresh': refresh_str})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            return error('Token is invalid or expired.', http_status=status.HTTP_401_UNAUTHORIZED)
        resp = success('Token refreshed successfully.', data={})
        resp.set_cookie(
            'royal_access_token', serializer.validated_data['access'],
            max_age=900, httponly=True, secure=not settings.DEBUG, samesite='Lax', domain=None,
        )
        if 'refresh' in serializer.validated_data:
            resp.set_cookie(
                'royal_refresh_token', serializer.validated_data['refresh'],
                max_age=604800, httponly=True, secure=not settings.DEBUG, samesite='Lax', domain=None,
            )
        return resp


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_str = request.COOKIES.get('royal_refresh_token')
        if refresh_str:
            try:
                RefreshToken(refresh_str).blacklist()
            except TokenError:
                pass  # Already expired — proceed with logout

        AuditLog.objects.create(
            user=request.user, action='logout', module='accounts',
            ip_address=get_client_ip(request),
        )
        logger.info('User %s logged out', request.user.email)
        resp = success('Logged out successfully.')
        resp.delete_cookie('royal_access_token', path='/')
        resp.delete_cookie('royal_refresh_token', path='/')
        return resp


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes   = [ForgotPasswordRateThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data, context={})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        user = serializer.context.get('user')
        if not user:
            return error('No active account found with this email address.')

        try:
            _, plain_otp = OTPVerification.create_for_user(user)
        except Exception as exc:
            logger.exception('Failed to create OTP for %s: %s', user.email, exc)
            return error(
                'Could not generate OTP. Please try again later.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            send_otp_email(user.email, plain_otp, user.full_name)
        except Exception as exc:
            logger.exception('Failed to send OTP email to %s: %s', user.email, exc)
            return error(
                'Failed to send OTP email. Please check your SMTP settings or try again later.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('OTP sent to %s', user.email)
        return success('OTP sent to your email address. It is valid for 10 minutes.')


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes   = [OTPVerifyRateThrottle]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        email     = serializer.validated_data['email']
        otp_input = serializer.validated_data['otp']

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return error('No active account found with this email address.')

        otp_obj = (
            OTPVerification.objects
                           .filter(user=user, is_used=False)
                           .order_by('-created_at')
                           .first()
        )

        if not otp_obj:
            return error('No OTP found. Please request a new OTP.')

        # Increment attempts atomically BEFORE verifying to prevent brute-force.
        OTPVerification.objects.filter(pk=otp_obj.pk).update(
            attempts=F('attempts') + 1
        )
        otp_obj.refresh_from_db(fields=['attempts'])

        if not otp_obj.is_valid():
            return error('OTP has expired or maximum attempts exceeded. Please request a new OTP.')

        if not otp_obj.check_otp(otp_input):
            return error('Invalid OTP. Please try again.')

        with transaction.atomic():
            otp_obj.is_used = True
            otp_obj.save(update_fields=['is_used'])
            reset_token = PasswordResetToken.create_for_user(user)

        logger.info('OTP verified for %s', email)
        return success('OTP verified successfully.', data={'reset_token': str(reset_token.id)})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        reset_token_id = serializer.validated_data['reset_token']
        new_password   = serializer.validated_data['new_password']

        try:
            token_obj = PasswordResetToken.objects.select_related('user').get(id=reset_token_id)
        except PasswordResetToken.DoesNotExist:
            return error('Invalid or expired reset token.')

        if not token_obj.is_valid():
            return error('This reset token has already been used or has expired.')

        user = token_obj.user

        with transaction.atomic():
            user.set_password(new_password)
            user.must_change_password   = False
            user.failed_login_attempts  = 0
            user.locked_until           = None
            user.save(update_fields=[
                'password', 'must_change_password', 'failed_login_attempts', 'locked_until'
            ])
            token_obj.is_used = True
            token_obj.save(update_fields=['is_used'])

        AuditLog.objects.create(
            user=user, action='password_reset', module='accounts',
            ip_address=get_client_ip(request),
        )
        logger.info('Password reset for %s', user.email)
        return success('Password has been reset successfully. Please log in with your new password.')


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        user         = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        if not user.check_password(old_password):
            return error('Current password is incorrect.')

        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])

        AuditLog.objects.create(
            user=user, action='password_changed', module='accounts',
            ip_address=get_client_ip(request),
        )
        logger.info('Password changed for %s', user.email)
        return success('Password changed successfully. Please log in again with your new password.')


# ─── Role management ──────────────────────────────────────────────────────────

class RoleListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        qs = (
            Role.objects
            .prefetch_related('role_permissions__permission')
            .annotate(active_user_count=Count('users', filter=Q(users__is_active=True)))
        )
        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 10

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Roles retrieved successfully.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     RoleSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            role = serializer.save()
        except IntegrityError:
            return error(
                f"Role '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_created', module='accounts',
            object_id=str(role.id),
            changes={'name': role.name, 'display_name': role.display_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" created by %s', role.name, request.user.email)
        return success(
            'Role created successfully.',
            data=RoleSerializer(role).data,
            http_status=status.HTTP_201_CREATED,
        )


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_role(self, pk: int) -> Role | None:
        try:
            return (
                Role.objects
                .prefetch_related('role_permissions__permission')
                .annotate(active_user_count=Count('users', filter=Q(users__is_active=True)))
                .get(pk=pk)
            )
        except Role.DoesNotExist:
            return None

    def get(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Role retrieved successfully.', data=RoleSerializer(role).data)

    def put(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = RoleSerializer(role, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated_role = serializer.save()
        except IntegrityError:
            return error(
                f"Role '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_updated', module='accounts',
            object_id=str(updated_role.id),
            changes={'name': updated_role.name, 'display_name': updated_role.display_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" updated by %s', updated_role.name, request.user.email)
        return success('Role updated successfully.', data=RoleSerializer(updated_role).data)

    def patch(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = RoleSerializer(role, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated_role = serializer.save()
        except IntegrityError:
            return error(
                f"Role '{serializer.validated_data.get('name', role.name)}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_updated', module='accounts',
            object_id=str(updated_role.id),
            changes={k: v for k, v in request.data.items() if not hasattr(v, 'read')},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" partially updated by %s', updated_role.name, request.user.email)
        return success('Role updated successfully.', data=RoleSerializer(updated_role).data)

    def delete(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        active_users = role.users.filter(is_active=True).count()
        if active_users:
            return error(
                f'Cannot delete role "{role.display_name}" — '
                f'{active_users} active user(s) are assigned to it. '
                f'Reassign them first.',
                http_status=status.HTTP_409_CONFLICT,
            )

        role_name = role.name
        try:
            role.delete()
        except ProtectedError:
            return error(
                f'Cannot delete role "{role_name}" — it is referenced by other records.',
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_deleted', module='accounts',
            changes={'name': role_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" deleted by %s', role_name, request.user.email)
        return success(f'Role "{role_name}" deleted successfully.')


# ─── Permission CRUD ──────────────────────────────────────────────────────────

class PermissionListView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        permissions = Permission.objects.all().order_by('module', 'action')
        serialized  = PermissionSerializer(permissions, many=True).data
        grouped: dict[str, list] = defaultdict(list)
        for perm in serialized:
            grouped[perm['module']].append(perm)
        return success('Permissions retrieved successfully.', data=dict(grouped))

    def post(self, request):
        serializer = PermissionSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            permission = serializer.save()
        except IntegrityError:
            return error(
                f"Permission '{serializer.validated_data['codename']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_created', module='accounts',
            object_id=str(permission.id),
            changes={'codename': permission.codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" created by %s', permission.codename, request.user.email)
        return success(
            'Permission created successfully.',
            data=PermissionSerializer(permission).data,
            http_status=status.HTTP_201_CREATED,
        )


class PermissionDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_permission(self, pk: int) -> Permission | None:
        try:
            return Permission.objects.get(pk=pk)
        except Permission.DoesNotExist:
            return None

    def get(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Permission retrieved successfully.', data=PermissionSerializer(perm).data)

    def put(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = PermissionSerializer(perm, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Permission '{serializer.validated_data['codename']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_updated', module='accounts',
            object_id=str(updated.id),
            changes={'codename': updated.codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" updated by %s', updated.codename, request.user.email)
        return success('Permission updated successfully.', data=PermissionSerializer(updated).data)

    def delete(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)

        codename = perm.codename
        try:
            perm.delete()
        except ProtectedError:
            return error(
                f'Cannot delete permission "{codename}" — it is assigned to one or more roles. '
                'Remove it from all roles first.',
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_deleted', module='accounts',
            changes={'codename': codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" deleted by %s', codename, request.user.email)
        return success(f'Permission "{codename}" deleted successfully.')


# ─── Organisation Structure ────────────────────────────────────────────────────

class DepartmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        qs = Department.objects.prefetch_related('designations').all()
        if is_active := request.query_params.get('is_active'):
            qs = qs.filter(is_active=is_active.lower() == 'true')

        # Single query for all user/role data across departments — avoids N+1
        dept_users = (
            User.objects
            .filter(is_active=True)
            .exclude(department='')
            .values('department', 'role__name', 'role__display_name')
        )
        emp_counts: dict = defaultdict(int)
        dept_roles: dict = defaultdict(set)
        for u in dept_users:
            emp_counts[u['department']] += 1
            if u['role__name']:
                dept_roles[u['department']].add((u['role__name'], u['role__display_name']))

        ctx = {
            'emp_counts': dict(emp_counts),
            'dept_roles': {k: sorted(v, key=lambda x: x[1]) for k, v in dept_roles.items()},
        }
        return success(
            'Departments retrieved successfully.',
            data=DepartmentSerializer(qs, many=True, context=ctx).data,
        )

    def post(self, request):
        serializer = DepartmentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            dept = serializer.save()
        except IntegrityError:
            return error(
                f"Department '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='dept_created', module='accounts',
            object_id=str(dept.pk), changes={'name': dept.name},
            ip_address=get_client_ip(request),
        )
        return success(
            'Department created successfully.',
            data=DepartmentSerializer(dept).data,
            http_status=status.HTTP_201_CREATED,
        )


class DepartmentDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get(self, pk: int) -> Department | None:
        try:
            return Department.objects.prefetch_related('designations').get(pk=pk)
        except Department.DoesNotExist:
            return None

    def get(self, request, pk: int):
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Department retrieved.', data=DepartmentSerializer(dept).data)

    def put(self, request, pk: int):
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = DepartmentSerializer(dept, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Department '{serializer.validated_data.get('name', '')}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='dept_updated', module='accounts',
            object_id=str(updated.pk), changes={'name': updated.name},
            ip_address=get_client_ip(request),
        )
        return success('Department updated successfully.', data=DepartmentSerializer(updated).data)

    def patch(self, request, pk: int):
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = DepartmentSerializer(dept, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Department '{serializer.validated_data.get('name', '')}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='dept_updated', module='accounts',
            object_id=str(updated.pk), changes={'name': updated.name},
            ip_address=get_client_ip(request),
        )
        return success('Department updated successfully.', data=DepartmentSerializer(updated).data)

    def delete(self, request, pk: int):
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        if dept.designations.exists():
            return error(
                'Cannot delete a department that has designations. '
                'Remove all designations first.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        name = dept.name
        try:
            dept.delete()
        except ProtectedError:
            return error(
                f'Cannot delete department "{name}" — it is referenced by other records.',
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='dept_deleted', module='accounts',
            object_id=str(dept.pk), changes={'name': name},
            ip_address=get_client_ip(request),
        )
        return success(f'Department "{name}" deleted successfully.')


class DesignationListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        qs = Designation.objects.select_related('department').all()
        if dept_id := request.query_params.get('department'):
            try:
                dept_id = int(dept_id)
            except (TypeError, ValueError):
                return error('department filter must be a valid integer ID.')
            if not Department.objects.filter(pk=dept_id).exists():
                return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
            qs = qs.filter(department_id=dept_id)
        return success(
            'Designations retrieved successfully.',
            data=DesignationSerializer(qs, many=True).data,
        )

    def post(self, request):
        serializer = DesignationSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            desig = serializer.save()
        except IntegrityError:
            return error(
                f"Designation '{serializer.validated_data['name']}' already exists in this department.",
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='designation_created', module='accounts',
            object_id=str(desig.pk),
            changes={'name': desig.name, 'department': desig.department.name},
            ip_address=get_client_ip(request),
        )
        return success(
            'Designation created successfully.',
            data=DesignationSerializer(desig).data,
            http_status=status.HTTP_201_CREATED,
        )


class DesignationDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get(self, pk: int) -> Designation | None:
        try:
            return Designation.objects.select_related('department').get(pk=pk)
        except Designation.DoesNotExist:
            return None

    def get(self, request, pk: int):
        desig = self._get(pk)
        if not desig:
            return error('Designation not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Designation retrieved successfully.', data=DesignationSerializer(desig).data)

    def put(self, request, pk: int):
        desig = self._get(pk)
        if not desig:
            return error('Designation not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = DesignationSerializer(desig, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Designation '{serializer.validated_data.get('name', '')}' already exists in this department.",
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='designation_updated', module='accounts',
            object_id=str(updated.pk),
            changes={'name': updated.name, 'department': updated.department.name},
            ip_address=get_client_ip(request),
        )
        return success('Designation updated successfully.', data=DesignationSerializer(updated).data)

    def patch(self, request, pk: int):
        desig = self._get(pk)
        if not desig:
            return error('Designation not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = DesignationSerializer(desig, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Designation '{serializer.validated_data.get('name', '')}' already exists in this department.",
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='designation_updated', module='accounts',
            object_id=str(updated.pk),
            changes={'name': updated.name, 'department': updated.department.name},
            ip_address=get_client_ip(request),
        )
        return success('Designation updated successfully.', data=DesignationSerializer(updated).data)

    def delete(self, request, pk: int):
        desig = self._get(pk)
        if not desig:
            return error('Designation not found.', http_status=status.HTTP_404_NOT_FOUND)
        active_users = User.objects.filter(designation=desig.name, is_active=True).count()
        if active_users:
            return error(
                f'Cannot delete designation "{desig.name}" — '
                f'{active_users} active employee(s) hold this designation. '
                'Reassign them first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        name = desig.name
        try:
            desig.delete()
        except ProtectedError:
            return error(
                f'Cannot delete designation "{name}" — it is referenced by other records.',
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='designation_deleted', module='accounts',
            object_id=str(desig.pk),
            changes={'name': name, 'department': desig.department.name},
            ip_address=get_client_ip(request),
        )
        return success(f'Designation "{name}" deleted successfully.')


# ─── SMTP Settings ─────────────────────────────────────────────────────────────

class SMTPSettingsListCreateView(APIView):
    """GET  /api/settings/smtp/         — list all SMTP configs
       POST /api/settings/smtp/         — create a new SMTP config"""

    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        configs = SMTPSettings.objects.select_related('updated_by').order_by('name')
        return success(
            f'{configs.count()} SMTP configuration(s) found.',
            data=SMTPSettingsSerializer(configs, many=True).data,
        )

    def post(self, request):
        serializer = SMTPSettingsSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            instance = serializer.save(updated_by=request.user)
        except IntegrityError:
            return error(
                'An SMTP config with this name already exists.',
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='smtp_created', module='settings',
            object_id=str(instance.id),
            changes={'name': instance.name, 'host': instance.host},
            ip_address=get_client_ip(request),
        )
        logger.info('SMTP config "%s" created by %s', instance.name, request.user.email)
        return success(
            f'SMTP configuration "{instance.name}" created successfully.',
            data=SMTPSettingsSerializer(instance).data,
            http_status=status.HTTP_201_CREATED,
        )


class SMTPSettingsDetailView(APIView):
    """GET   /api/settings/smtp/<pk>/   — retrieve one config
       PUT   /api/settings/smtp/<pk>/   — full update
       PATCH /api/settings/smtp/<pk>/   — partial update
       DELETE /api/settings/smtp/<pk>/  — delete"""

    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_or_404(self, pk: int) -> SMTPSettings | None:
        try:
            return SMTPSettings.objects.select_related('updated_by').get(pk=pk)
        except SMTPSettings.DoesNotExist:
            return None

    def get(self, request, pk: int):
        cfg = self._get_or_404(pk)
        if not cfg:
            return error('SMTP configuration not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('SMTP configuration retrieved.', data=SMTPSettingsSerializer(cfg).data)

    def put(self, request, pk: int):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk: int):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk: int, *, partial: bool) -> Response:
        cfg = self._get_or_404(pk)
        if not cfg:
            return error('SMTP configuration not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = SMTPSettingsSerializer(cfg, data=request.data, partial=partial)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        # Preserve stored password when not re-submitted
        if not serializer.validated_data.get('password'):
            serializer.validated_data['password'] = cfg.password

        try:
            instance = serializer.save(updated_by=request.user)
        except IntegrityError:
            return error(
                'An SMTP config with this name already exists.',
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='smtp_updated', module='settings',
            object_id=str(instance.id),
            changes={'name': instance.name, 'host': instance.host},
            ip_address=get_client_ip(request),
        )
        logger.info('SMTP config "%s" updated by %s', instance.name, request.user.email)
        return success(
            f'SMTP configuration "{instance.name}" updated successfully.',
            data=SMTPSettingsSerializer(instance).data,
        )

    def delete(self, request, pk: int):
        cfg = self._get_or_404(pk)
        if not cfg:
            return error('SMTP configuration not found.', http_status=status.HTTP_404_NOT_FOUND)

        was_active = cfg.is_active
        name       = cfg.name
        cfg.delete()

        AuditLog.objects.create(
            user=request.user, action='smtp_deleted', module='settings',
            changes={'name': name, 'was_active': was_active},
            ip_address=get_client_ip(request),
        )
        logger.info('SMTP config "%s" deleted by %s', name, request.user.email)

        msg = f'SMTP configuration "{name}" deleted.'
        if was_active:
            msg += ' No SMTP config is currently active — outgoing emails will fall back to .env settings.'
        return success(msg)


class SMTPActivateView(APIView):
    """POST /api/settings/smtp/<pk>/activate/  — make one config the active sender"""

    permission_classes = [IsAuthenticated, CanManageRoles]

    def post(self, request, pk: int):
        try:
            cfg = SMTPSettings.objects.get(pk=pk)
        except SMTPSettings.DoesNotExist:
            return error('SMTP configuration not found.', http_status=status.HTTP_404_NOT_FOUND)

        cfg.activate()

        AuditLog.objects.create(
            user=request.user, action='smtp_activated', module='settings',
            object_id=str(cfg.id),
            changes={'name': cfg.name},
            ip_address=get_client_ip(request),
        )
        logger.info('SMTP config "%s" activated by %s', cfg.name, request.user.email)
        return success(
            f'SMTP configuration "{cfg.name}" is now active. '
            f'All outgoing emails will use this configuration.',
            data=SMTPSettingsSerializer(cfg).data,
        )


class SMTPTestEmailView(APIView):
    
    permission_classes = [IsAuthenticated, CanManageRoles]

    def post(self, request):
        serializer = SMTPTestSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            send_test_email(
                recipient_email = serializer.validated_data['test_recipient'],
                smtp_config     = serializer.validated_data,
            )
        except Exception as exc:
            logger.error('SMTP test failed for %s: %s', request.user.email, exc, exc_info=True)
            return error(f'Failed to send test email: {exc}')

        logger.info('SMTP test email sent by %s', request.user.email)
        return success(
            f"Test email sent successfully to {serializer.validated_data['test_recipient']}."
        )


# ─── Email Templates ──────────────────────────────────────────────────────────

class EmailTemplateCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        cats = EmailTemplateCategory.objects.all()
        counts = dict(
            EmailTemplate.objects
            .values('template_type')
            .annotate(n=Count('id'))
            .values_list('template_type', 'n')
        )
        return success(
            'Categories retrieved successfully.',
            data=EmailTemplateCategorySerializer(
                cats, many=True, context={'template_counts': counts}
            ).data,
        )

    def post(self, request):
        serializer = EmailTemplateCategorySerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            cat = serializer.save(is_builtin=False)
        except IntegrityError:
            return error(
                f"Category '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )
        logger.info('Email template category "%s" created by %s', cat.name, request.user.email)
        return success('Category created successfully.', data=EmailTemplateCategorySerializer(cat).data, http_status=status.HTTP_201_CREATED)


class EmailTemplateCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_category(self, pk: int) -> EmailTemplateCategory | None:
        try:
            return EmailTemplateCategory.objects.get(pk=pk)
        except EmailTemplateCategory.DoesNotExist:
            return None

    def get(self, request, pk):
        cat = self._get_category(pk)
        if not cat:
            return error('Category not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Category retrieved successfully.', data=EmailTemplateCategorySerializer(cat).data)

    def patch(self, request, pk):
        cat = self._get_category(pk)
        if not cat:
            return error('Category not found.', http_status=status.HTTP_404_NOT_FOUND)
        if cat.is_builtin:
            return error('Built-in categories cannot be modified.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = EmailTemplateCategorySerializer(cat, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        updated = serializer.save()
        return success('Category updated successfully.', data=EmailTemplateCategorySerializer(updated).data)

    def delete(self, request, pk):
        cat = self._get_category(pk)
        if not cat:
            return error('Category not found.', http_status=status.HTTP_404_NOT_FOUND)
        if cat.is_builtin:
            return error('Built-in categories cannot be deleted.', http_status=status.HTTP_403_FORBIDDEN)
        if EmailTemplate.objects.filter(template_type=cat.name).exists():
            return error(
                f'Cannot delete "{cat.display_name}" — templates are assigned to it. Reassign them first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        cat.delete()
        logger.info('Email template category "%s" deleted by %s', cat.name, request.user.email)
        return success(f'Category "{cat.display_name}" deleted successfully.')


class EmailTemplateListCreateView(APIView):
   
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        templates = (
            EmailTemplate.objects
            .select_related('updated_by')
            .prefetch_related('attachments')
            .all()
        )
        category_map = dict(
            EmailTemplateCategory.objects.values_list('name', 'display_name')
        )
        ser_context = {'request': request, 'category_map': category_map}
        grouped: dict[str, list] = defaultdict(list)
        for tpl in templates:
            grouped[tpl.template_type].append(
                EmailTemplateSerializer(tpl, context=ser_context).data
            )
        return success('Email templates retrieved successfully.', data=dict(grouped))
    
    
    def post(self, request):
        serializer = EmailTemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            template = serializer.save(is_builtin=False, updated_by=request.user)
        except IntegrityError:
            return error(
                f"Template '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='email_template_created', module='settings',
            object_id=str(template.id),
            changes={'name': template.name},
            ip_address=get_client_ip(request),
        )
        logger.info('Email template "%s" created by %s', template.name, request.user.email)
        return success(
            'Email template created successfully.',
            data=EmailTemplateSerializer(template).data,
            http_status=status.HTTP_201_CREATED,
        )


class EmailTemplateDetailView(APIView):

    permission_classes = [IsAuthenticated, CanManageRoles]

    _MAX_BYTES = 10 * 1024 * 1024  # 10 MB

    def _get_template(self, pk: int) -> EmailTemplate | None:
        try:
            return EmailTemplate.objects.select_related('updated_by').get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return None

    def get(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Email template retrieved successfully.', data=EmailTemplateSerializer(tpl).data)

    def post(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        file = (
            request.FILES.get('attachments')
            or request.FILES.get('file')
            or (list(request.FILES.values())[0] if request.FILES else None)
        )
        if not file:
            return error('No file provided.')
        if file.content_type not in EmailTemplateAttachment.ALLOWED_MIME_TYPES:
            return error(
                f'File type "{file.content_type}" is not allowed. '
                'Allowed: images (jpg/png/gif/webp), PDF, Word, Excel.',
            )
        if file.size > self._MAX_BYTES:
            return error('File size must not exceed 10 MB.')

        att = EmailTemplateAttachment.objects.create(
            template=tpl,
            file=file,
            filename=file.name,
            mime_type=file.content_type,
            size=file.size,
            uploaded_by=request.user,
        )
        return success(
            'Attachment uploaded successfully.',
            data=EmailTemplateAttachmentSerializer(att, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = EmailTemplateSerializer(tpl, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated = serializer.save(updated_by=request.user)
        except IntegrityError:
            return error(
                f"Template '{serializer.validated_data.get('name', tpl.name)}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='email_template_updated', module='settings',
            object_id=str(updated.id), changes={'name': updated.name},
            ip_address=get_client_ip(request),
        )
        logger.info('Email template "%s" updated by %s', updated.name, request.user.email)
        return success('Email template updated successfully.', data=EmailTemplateSerializer(updated).data)

    def patch(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = EmailTemplateSerializer(tpl, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated = serializer.save(updated_by=request.user)
        except IntegrityError:
            return error(
                f"Template '{serializer.validated_data.get('name', tpl.name)}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        # Process any files uploaded alongside the template fields
        files = request.FILES.getlist('attachments') or request.FILES.getlist('file')
        if not files:
            files = list(request.FILES.values())

        for f in files:
            logger.info(
                'Template "%s" attachment received: name=%s mime=%s size=%d',
                updated.name, f.name, f.content_type, f.size,
            )
            if f.content_type not in self._ALLOWED_MIME:
                logger.warning('Attachment "%s" rejected — MIME type "%s" not allowed.', f.name, f.content_type)
                continue
            if f.size > self._MAX_BYTES:
                logger.warning('Attachment "%s" rejected — size %d exceeds 10 MB limit.', f.name, f.size)
                continue
            EmailTemplateAttachment.objects.create(
                template=updated,
                file=f,
                filename=f.name,
                mime_type=f.content_type,
                size=f.size,
                uploaded_by=request.user,
            )
            logger.info('Attachment "%s" saved for template "%s".', f.name, updated.name)

        AuditLog.objects.create(
            user=request.user, action='email_template_updated', module='settings',
            object_id=str(updated.id),
            changes={k: v for k, v in request.data.items() if not hasattr(v, 'read')},
            ip_address=get_client_ip(request),
        )
        logger.info('Email template "%s" partially updated by %s', updated.name, request.user.email)

        # Re-fetch from DB so the response includes freshly saved attachments
        fresh = (
            EmailTemplate.objects
            .prefetch_related('attachments')
            .get(pk=updated.pk)
        )
        return success('Email template updated successfully.', data=EmailTemplateSerializer(fresh).data)

    def delete(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        attachment_id = request.query_params.get('attachment_id')
        if attachment_id:
            try:
                att = tpl.attachments.get(pk=attachment_id)
            except EmailTemplateAttachment.DoesNotExist:
                return error('Attachment not found.', http_status=status.HTTP_404_NOT_FOUND)
            with transaction.atomic():
                att.delete()
                att.file.delete(save=False)
            return success('Attachment deleted successfully.')

        if tpl.is_builtin:
            return error(
                f'"{tpl.display_name}" is a built-in template and cannot be deleted. '
                'You may disable it instead by setting is_active to false.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        name = tpl.name
        tpl.delete()

        AuditLog.objects.create(
            user=request.user, action='email_template_deleted', module='settings',
            changes={'name': name},
            ip_address=get_client_ip(request),
        )
        logger.info('Email template "%s" deleted by %s', name, request.user.email)
        return success(f'Email template "{name}" deleted successfully.')


class EmailTemplatePreviewView(APIView):

    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_template(self, pk):
        try:
            return (
                EmailTemplate.objects
                .prefetch_related('attachments')
                .get(pk=pk)
            )
        except EmailTemplate.DoesNotExist:
            return None

    def post(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = EmailTemplatePreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        context                         = serializer.validated_data.get('context', {})
        rendered_subject, rendered_body = tpl.render(context)

        attachments = EmailTemplateAttachmentSerializer(
            tpl.attachments.all(), many=True, context={'request': request}
        ).data

        return success('Preview generated.', data={
            'template_name':       tpl.name,
            'subject':             rendered_subject,
            'body':                rendered_body,
            'available_variables': tpl.available_variables,
            'attachments':         attachments,
        })

    def get(self, request, pk):
        tpl = self._get_template(pk)
        if not tpl:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        attachments = EmailTemplateAttachmentSerializer(
            tpl.attachments.all(), many=True, context={'request': request}
        ).data

        return success('Template details retrieved.', data={
            'template_name':       tpl.name,
            'subject':             tpl.subject,
            'body':                tpl.body,
            'available_variables': tpl.available_variables,
            'attachments':         attachments,
        })
    
    def put(self, request, pk):
        try:
            tpl = EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = EmailTemplatePreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        context                         = serializer.validated_data.get('context', {})
        rendered_subject, rendered_body = tpl.render(context)

        # Update the template with the rendered content
        tpl.subject = rendered_subject
        tpl.body    = rendered_body
        tpl.save(update_fields=['subject', 'body'])

        AuditLog.objects.create(
            user=request.user, action='email_template_preview_updated', module='settings',
            object_id=str(tpl.id),
            changes={'subject': rendered_subject, 'body': rendered_body},
            ip_address=get_client_ip(request),
        )
        logger.info('Email template "%s" preview updated by %s', tpl.name, request.user.email)
        return success('Email template preview updated successfully.', data={
            'template_name': tpl.name,
            'subject':       rendered_subject,
            'body':          rendered_body,
        })
        
    def delete(self, request, pk):
        try:
            tpl = EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return error('Email template not found.', http_status=status.HTTP_404_NOT_FOUND)

        if tpl.is_builtin:
            return error(
                f'"{tpl.display_name}" is a built-in template and cannot be deleted. '
                'You may disable it instead by setting is_active to false.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        name = tpl.name
        tpl.delete()

        AuditLog.objects.create(
            user=request.user, action='email_template_deleted', module='settings',
            changes={'name': name},
            ip_address=get_client_ip(request),
        )
        logger.info('Email template "%s" deleted by %s', name, request.user.email)
        return success(f'Email template "{name}" deleted successfully.')

# ─── Document Center ───────────────────────────────────────────────────────────

def _can_manage_docs(user) -> bool:
    """Only hr_admin and system_admin may upload / edit / delete documents."""
    return bool(user and user.role and user.role.name in ('hr_admin', 'system_admin'))


class DocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Document.objects
            .select_related('uploaded_by', 'branch')
            .filter(is_active=True)
        )

        # --- filter: category ---
        if category := request.query_params.get('category', '').strip():
            valid = {c for c, _ in Document.CATEGORY_CHOICES}
            if category not in valid:
                return error(f'Invalid category. Choose from: {", ".join(sorted(valid))}.')
            qs = qs.filter(category=category)

        # --- filter: branch ---
        if branch_raw := request.query_params.get('branch', '').strip():
            try:
                branch_id = int(branch_raw)
                if branch_id <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                return error('branch filter must be a positive integer ID.')
            qs = qs.filter(branch_id=branch_id)

        # --- filter: file_type (PDF, DOCX, …) ---
        if file_type := request.query_params.get('file_type', '').strip().upper():
            allowed_types = set(Document.MIME_TO_TYPE.values())
            if file_type not in allowed_types:
                return error(
                    f'Invalid file_type. Choose from: {", ".join(sorted(allowed_types))}.'
                )
            qs = qs.filter(file_type=file_type)

        # --- filter: search ---
        if search := request.query_params.get('search', '').strip():
            if len(search) > 100:
                return error('Search query must be under 100 characters.')
            qs = qs.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return success(
            'Documents retrieved successfully.',
            data=DocumentSerializer(qs, many=True, context={'request': request}).data,
        )

    def post(self, request):
        if not _can_manage_docs(request.user):
            return error(
                'You do not have permission to upload documents.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        if 'file' not in request.data:
            return error('file is required.')
        serializer = DocumentSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        uploaded_file = serializer.validated_data['file']
        try:
            doc = serializer.save(
                uploaded_by=request.user,
                file_name=uploaded_file.name,
                file_type=Document.MIME_TO_TYPE.get(uploaded_file.content_type, 'FILE'),
                file_size=uploaded_file.size,
                is_active=True,
            )
        except Exception as exc:
            logger.error('Document upload failed for %s: %s', request.user.email, exc, exc_info=True)
            return error('Failed to save document. Please try again.')
        try:
            AuditLog.objects.create(
                user=request.user, action='document_uploaded', module='documents',
                object_id=str(doc.id),
                changes={'title': doc.title, 'category': doc.category, 'file': doc.file_name},
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.warning('AuditLog write failed for document_uploaded id=%s', doc.id)
        logger.info('Document "%s" uploaded by %s', doc.title, request.user.email)
        return success(
            'Document uploaded successfully.',
            data=DocumentSerializer(doc, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Download requests authenticate via a short-lived URL token — no JWT needed.
        if self.request.method == 'GET' and self.request.query_params.get('t'):
            return []
        return super().get_permissions()

    def _get_doc(self, pk: int):
        try:
            return (
                Document.objects
                .select_related('uploaded_by', 'branch')
                .get(pk=pk, is_active=True)
            )
        except Document.DoesNotExist:
            return None

    def _stream_file(self, pk: int, token: str):
        try:
            data = signing.loads(token, salt='doc-dl', max_age=7200)
            if data.get('id') != pk:
                raise ValueError('pk mismatch')
        except Exception:
            return error('Invalid or expired download link.', http_status=status.HTTP_401_UNAUTHORIZED)

        try:
            doc = Document.objects.only('file', 'file_name', 'is_active').get(pk=pk, is_active=True)
        except Document.DoesNotExist:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)

        name  = doc.file.name
        parts = os.path.basename(name).rsplit('.', 1)
        fmt   = parts[1].lower() if len(parts) == 2 else ''

        try:
            # private_download_url signs the request with API key + secret,
            # bypassing any CDN-level access restrictions on the Cloudinary account.
            dl_url = cloudinary.utils.private_download_url(
                name, fmt,
                resource_type='raw',
                type='upload',
                attachment=False,
            )
            r = http_req.get(dl_url, stream=True, timeout=30)
            r.raise_for_status()
        except http_req.exceptions.HTTPError as exc:
            logger.error('Cloudinary download failed pk=%s status=%s', pk, exc.response.status_code)
            return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            logger.error('Document download error pk=%s: %s', pk, exc, exc_info=True)
            return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)

        content_type = r.headers.get('content-type', 'application/octet-stream')
        response = StreamingHttpResponse(
            r.iter_content(chunk_size=8192),
            content_type=content_type,
        )
        response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
        if 'content-length' in r.headers:
            response['Content-Length'] = r.headers['content-length']
        response['Cache-Control'] = 'no-store'
        return response

    def get(self, request, pk: int):
        token = request.query_params.get('t', '').strip()
        if token:
            return self._stream_file(pk, token)
        doc = self._get_doc(pk)
        if not doc:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success(
            'Document retrieved successfully.',
            data=DocumentSerializer(doc, context={'request': request}).data,
        )

    def patch(self, request, pk: int):
        if not _can_manage_docs(request.user):
            return error('You do not have permission to update documents.', http_status=status.HTTP_403_FORBIDDEN)
        doc = self._get_doc(pk)
        if not doc:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not request.data:
            return error('No fields provided to update.')
        serializer = DocumentSerializer(doc, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        if not serializer.validated_data:
            return error('No valid fields provided to update.')
        new_file = serializer.validated_data.get('file')
        old_file = doc.file if new_file else None
        file_meta = {}
        if new_file:
            file_meta = {
                'file_name': new_file.name,
                'file_type': Document.MIME_TO_TYPE.get(new_file.content_type, 'FILE'),
                'file_size': new_file.size,
            }
        try:
            updated = serializer.save(**file_meta)
        except Exception as exc:
            logger.error('Document update failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to update document. Please try again.')
        if old_file:
            try:
                old_file.delete(save=False)
            except Exception:
                logger.warning('Failed to delete old file from storage for document id=%s', updated.id)
        try:
            AuditLog.objects.create(
                user=request.user, action='document_updated', module='documents',
                object_id=str(updated.id),
                changes={k: v for k, v in request.data.items() if not hasattr(v, 'read')},
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.warning('AuditLog write failed for document_updated id=%s', updated.id)
        logger.info('Document "%s" updated by %s', updated.title, request.user.email)
        return success(
            'Document updated successfully.',
            data=DocumentSerializer(updated, context={'request': request}).data,
        )

    def delete(self, request, pk: int):
        if not _can_manage_docs(request.user):
            return error('You do not have permission to delete documents.', http_status=status.HTTP_403_FORBIDDEN)
        doc = self._get_doc(pk)
        if not doc:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        title = doc.title
        try:
            doc.is_active = False
            doc.save(update_fields=['is_active', 'updated_at'])
        except Exception as exc:
            logger.error('Document soft-delete failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to delete document. Please try again.')
        try:
            AuditLog.objects.create(
                user=request.user, action='document_deleted', module='documents',
                object_id=str(doc.id),
                changes={'title': title},
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.warning('AuditLog write failed for document_deleted id=%s', doc.id)
        logger.info('Document "%s" soft-deleted by %s', title, request.user.email)
        return success(f'Document "{title}" deleted successfully.')


class DocumentStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = (
            Document.objects
            .filter(is_active=True)
            .values('category')
            .annotate(n=Count('id'))
        )
        by_category = {row['category']: row['n'] for row in rows}
        return success('Document statistics retrieved.', data={
            'total': sum(by_category.values()),
            'by_category': {
                cat: by_category.get(cat, 0)
                for cat, _ in Document.CATEGORY_CHOICES
            },
        })


# ─── Company ──────────────────────────────────────────────────────────────────

class CompanyRetrieveUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        company = Company.objects.first()
        if not company:
            return success('No company info found.', data={})
        serializer = CompanySerializer(company, context={'request': request})
        return success('Company info retrieved.', data=serializer.data)

    def put(self, request):
        if not (request.user.role and request.user.role.name in ('hr_admin', 'system_admin')):
            return error(
                'You do not have permission to update company info.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        company = Company.objects.first()
        is_new  = company is None

        with transaction.atomic():
            serializer = CompanySerializer(
                company,
                data=request.data,
                partial=not is_new,
                context={'request': request},
            )
            if not serializer.is_valid():
                return error(first_error(serializer.errors), data=serializer.errors)

            # Replace old logo file when a new one is uploaded
            if not is_new and 'logo' in request.FILES and company.logo:
                company.logo.delete(save=False)

            instance = serializer.save(updated_by=request.user)

            # Handle explicit logo removal
            remove_logo = str(request.data.get('remove_logo', '')).lower() == 'true'
            if remove_logo and instance.logo:
                instance.logo.delete(save=False)
                instance.logo = None
                instance.save(update_fields=['logo'])

        AuditLog.objects.create(
            user=request.user,
            action='create' if is_new else 'update',
            module='company',
            object_id=str(instance.pk),
            ip_address=get_client_ip(request),
        )
        logger.info('Company info %s by %s', 'created' if is_new else 'updated', request.user.email)
        return success(
            'Company info saved successfully.',
            data=CompanySerializer(instance, context={'request': request}).data,
        )


# ─── Audit Log ────────────────────────────────────────────────────────────────

# ─── Employee List / Create ───────────────────────────────────────────────────

class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    _DENIED = 'You do not have permission to perform this action.'

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            User.objects
            .select_related('role')
            .filter(is_active__in=[True, False])
            .order_by('-date_joined')
        )

        search = request.query_params.get('search', '').strip()
        dept   = request.query_params.get('department', '').strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search)     |
                Q(employee_id__icontains=search)
            )
        if dept:
            qs = qs.filter(department=dept)

        return success('Employees retrieved.', data=[_employee_dict(u) for u in qs])

    def post(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)

        first_name      = (request.data.get('first_name')      or '').strip()
        last_name       = (request.data.get('last_name')       or '').strip()
        email           = (request.data.get('email')           or '').strip().lower()
        role_id         = request.data.get('role')
        department      = (request.data.get('department')      or '').strip()
        designation     = (request.data.get('designation')     or '').strip()
        branch          = (request.data.get('branch')          or '').strip()
        employee_type   = (request.data.get('employee_type')   or 'Permanent').strip()
        date_of_joining = (request.data.get('date_of_joining') or '').strip()
        phone           = (request.data.get('phone')           or '').strip()

        errs = {}
        if not first_name:      errs['first_name']      = 'First name is required.'
        if not last_name:       errs['last_name']       = 'Last name is required.'
        if not email:           errs['email']           = 'Email is required.'
        if not role_id:         errs['role']            = 'Role is required.'
        if not department:      errs['department']      = 'Department is required.'
        if not designation:     errs['designation']     = 'Designation is required.'
        if not branch:          errs['branch']          = 'Branch is required.'
        if not date_of_joining: errs['date_of_joining'] = 'Date of joining is required.'
        if errs:
            return error('Please fix the errors below.', data=errs)

        if User.objects.filter(email__iexact=email).exists():
            return error(
                'An account with this email already exists.',
                data={'email': 'Email already registered.'},
            )

        try:
            role = Role.objects.get(pk=role_id)
        except (Role.DoesNotExist, ValueError, TypeError):
            return error('Invalid role.', data={'role': 'Role not found.'})

        if role.name == 'system_admin':
            return error('system_admin cannot be assigned via employee creation.')

        import secrets, string as _string
        temp_password = ''.join(secrets.choice(_string.ascii_letters + _string.digits) for _ in range(12))

        count       = User.objects.count() + 1
        employee_id = f'RSS{str(count).zfill(5)}'
        full_name   = f'{first_name} {last_name}'

        with transaction.atomic():
            user = User.objects.create_user(
                email           = email,
                password        = temp_password,
                full_name       = full_name,
                role            = role,
                employee_id     = employee_id,
                department      = department,
                designation     = designation,
                branch          = branch,
                phone           = phone,
                date_of_joining = date_of_joining or None,
                must_change_password = True,
            )
            AuditLog.objects.create(
                user=request.user, action='employee_created', module='accounts',
                object_id=str(user.id),
                changes={
                    'name': full_name, 'email': email,
                    'department': department, 'designation': designation,
                    'role': role.name, 'employee_id': employee_id,
                },
                ip_address=get_client_ip(request),
            )

        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject=f'Welcome to Royal HRMS — Your Login Credentials',
                message='',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@royalhrms.com'),
                recipient_list=[email],
                html_message=(
                    f'<p>Hi <strong>{full_name}</strong>,</p>'
                    f'<p>Your Royal HRMS account has been created. Use the credentials below to log in:</p>'
                    f'<p><strong>Employee ID:</strong> {employee_id}<br>'
                    f'<strong>Login Email:</strong> {email}<br>'
                    f'<strong>Temporary Password:</strong> {temp_password}</p>'
                    f'<p>You will be asked to change your password on first login.</p>'
                    f'<p>— Royal HRMS Team</p>'
                ),
            )
        except Exception as exc:
            logger.error('Welcome email failed for %s: %s', email, exc)

        logger.info('Employee %s (%s) created by %s', employee_id, email, request.user.email)
        return success(
            f'{full_name} added successfully. Login credentials sent to {email}.',
            data=_employee_dict(user),
            http_status=status.HTTP_201_CREATED,
        )


class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        qs = AuditLog.objects.select_related('user', 'user__role').order_by('-created_at')

        module    = request.query_params.get('module', '').strip()
        action    = request.query_params.get('action', '').strip()
        search    = request.query_params.get('search', '').strip()
        date_from = request.query_params.get('date_from', '').strip()
        date_to   = request.query_params.get('date_to', '').strip()

        if module:
            qs = qs.filter(module=module)
        if action:
            qs = qs.filter(action__icontains=action)
        if search:
            qs = qs.filter(
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        try:
            page_size = min(int(request.query_params.get('page_size', 25)), 100)
            page_num  = max(int(request.query_params.get('page', 1)), 1)
        except (ValueError, TypeError):
            page_size, page_num = 25, 1

        paginator   = Paginator(qs, page_size)
        page_obj    = paginator.get_page(page_num)
        serializer  = AuditLogSerializer(page_obj.object_list, many=True)

        return success('Audit logs retrieved.', data={
            'count':       paginator.count,
            'page':        page_num,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     serializer.data,
        })
