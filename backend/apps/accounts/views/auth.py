
from __future__ import annotations

import csv
import io
import logging
import os
import re
import secrets
import string
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests as http_req

PHONE_RE = re.compile(r'^(?:\+?91)?\d{10}$')
_PHONE_FORMAT_CHARS_RE = re.compile(r'[\s\-()./]')
NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:[ '\-][A-Za-z0-9]+)*$")
EMAIL_RE = re.compile(
    r'^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?'
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$'
)


def _is_valid_phone(raw: str) -> bool:
    """True if raw is a 10-digit number, with formatting (spaces/-/()/. /) and
    an optional +91/91 prefix stripped out first."""
    return bool(PHONE_RE.match(_PHONE_FORMAT_CHARS_RE.sub('', raw)))

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Exists, F, Max, OuterRef, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.file_validation import validate_file_content as _validate_file_content
from core.pagination import paginate, paginated_data
from core.permissions import HasSettingsPermission, has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success
from core.template_context import (
    candidate_context as _candidate_template_context,
    expense_context as _expense_template_context,
    leave_request_context as _leave_request_template_context,
    universal_context as _universal_template_context,
)
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication   


from apps.accounts.models import (
    ApprovalWorkflowRule,
    AuditLog,
    Company,
    CompanyDirector,
    CompanyGSTRegistration,
    Document,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeApprovalOverride,
    EmployeeCodeSettings,
    HireAction,
    JobTemplate,
    OnboardingFieldConfig,
    OnboardingSection,
    OrgUnit,
    OTPVerification,
    PasswordResetToken,
    Permission,
    Placement,
    Position,
    PromotionRecord,
    Role,
    RolePermission,
    SMTPSettings,
    User,
)
from apps.accounts.serializers import (
    ApprovalWorkflowRuleUpdateSerializer,
    AuditLogSerializer,
    ChangePasswordSerializer,
    CompanyDirectorSerializer,
    CompanyGSTRegistrationSerializer,
    CompanySerializer,
    DocumentSerializer,
    EmailTemplateAttachmentSerializer,
    EmailTemplateCategorySerializer,
    EmailTemplatePreviewSerializer,
    EmailTemplateSerializer,
    EmployeeBulkImportRowSerializer,
    EmployeeCodeSettingsSerializer,
    ForgotPasswordSerializer,
    JobTemplateSerializer,
    LoginSerializer,
    OrgUnitSerializer,
    PermissionSerializer,
    PlacementSerializer,
    PositionSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    SMTPSettingsSerializer,
    SMTPTestSerializer,
    VerifyOTPSerializer,
)
from apps.accounts.services_placement import assign_position, sync_from_position
from apps.accounts.throttles import ForgotPasswordRateThrottle, LoginRateThrottle, OTPVerifyRateThrottle, ResetPasswordRateThrottle
from apps.accounts.tokens import FreshClaimsTokenRefreshSerializer, RoleBasedRefreshToken
from apps.accounts.utils import send_otp_email, send_template_email, send_test_email

logger = logging.getLogger(__name__)

from apps.accounts.views.shared import *  # noqa: F401,F403












# ─── Custom permissions ────────────────────────────────────────────────────────
# (CanManageRoles lives in shared.py — used across auth/roles/smtp/email
# templates/employees_actions/approval_workflow, not just here.)



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

        return self._authenticate(request, email, password)

    def _authenticate(self, request, email, password):
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
                'onboarding_status':   user.onboarding_status,
                'assessment_status':   _login_assessment_status(user),
                'permissions':         permissions,
                'can_manage_team':     user.role.can_manage_team if user.role else False,
                'can_manage_branch':   user.role.can_manage_branch if user.role else False,
                'is_superuser':        user.is_superuser or 'settings.edit' in permissions,
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
        refresh_str = (
            request.COOKIES.get('royal_refresh_token')
            or request.data.get('refresh')
        )
        if not refresh_str:
            return error('Session expired. Please log in again.', http_status=status.HTTP_401_UNAUTHORIZED)

        serializer = FreshClaimsTokenRefreshSerializer(data={'refresh': refresh_str})
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
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        email = serializer.validated_data['email']

        return self._send_otp(email)

    def _send_otp(self, email):
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            # Same response regardless of whether the account exists, to
            # prevent attackers from enumerating registered email addresses
            # within a company they've already correctly identified.
            return success('OTP sent to your email address. It is valid for 10 minutes.')

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

        return self._verify(email, otp_input)

    def _verify(self, email, otp_input):
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
    throttle_classes   = [ResetPasswordRateThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        reset_token_id  = serializer.validated_data['reset_token']
        new_password    = serializer.validated_data['new_password']

        return self._reset(request, reset_token_id, new_password)

    def _reset(self, request, reset_token_id, new_password):
        try:
            token_obj = PasswordResetToken.objects.select_related('user').get(id=reset_token_id)
        except PasswordResetToken.DoesNotExist:
            return error('Invalid or expired reset token.')

        if not token_obj.is_valid():
            return error('This reset token has already been used or has expired.')

        user = token_obj.user
        is_activation = token_obj.purpose == PasswordResetToken.PURPOSE_INVITE

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
            user=user, action='account_activated' if is_activation else 'password_reset', module='accounts',
            ip_address=get_client_ip(request),
        )
        try:
            from apps.notifications.signals import _notify
            if is_activation:
                _notify(
                    user, 'Account Activated',
                    'Your account is now active. Welcome aboard!',
                    'account_activated', 'security', str(user.id), category='system',
                )
            else:
                _notify(
                    user, 'Password Reset',
                    'Your password was just reset. If you did not do this, contact HR immediately.',
                    'password_reset', 'security', str(user.id), category='system',
                )
        except Exception:
            logger.exception('Failed to send password-reset notification for %s', user.email)
        logger.info('Password reset for %s', user.email)
        return success(
            'Your account is now active. Please log in.' if is_activation else
            'Password has been reset successfully. Please log in with your new password.'
        )


class InviteCheckView(APIView):
    """GET /invite/<uuid:token>/ — public, unauthenticated check backing the
    new-hire activation page: is this link still good, and who is it for?
    Marks the invite Opened (first call only) so HR can see "did they even
    open the email" without that being conflated with actually setting a
    password (Activated, which only POST /reset-password/ produces)."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            token_obj = PasswordResetToken.objects.select_related('user').get(
                id=token, purpose=PasswordResetToken.PURPOSE_INVITE,
            )
        except (PasswordResetToken.DoesNotExist, ValueError):
            return error('This activation link is invalid.', http_status=status.HTTP_404_NOT_FOUND)

        if not token_obj.is_valid():
            return error(
                'This activation link has expired or was already used. Ask HR to resend your invite.',
                http_status=status.HTTP_410_GONE,
            )

        token_obj.mark_opened()
        return success('Invite is valid.', data={
            'full_name': token_obj.user.full_name,
            'email':     token_obj.user.email,
        })


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

        # Blacklist the refresh token so the old session cannot be reused
        refresh_str = request.COOKIES.get('royal_refresh_token')
        if refresh_str:
            try:
                RefreshToken(refresh_str).blacklist()
            except TokenError:
                pass

        AuditLog.objects.create(
            user=user, action='password_changed', module='accounts',
            ip_address=get_client_ip(request),
        )
        logger.info('Password changed for %s', user.email)
        resp = success('Password changed successfully. Please log in again with your new password.')
        resp.delete_cookie('royal_access_token', path='/')
        resp.delete_cookie('royal_refresh_token', path='/')
        return resp


