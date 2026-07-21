
from __future__ import annotations

import csv
import io
import logging
import os
import re
import secrets
import string
from collections import defaultdict
from datetime import datetime

import cloudinary.utils
import requests as http_req

PHONE_RE = re.compile(r'^\+?[\d\s\-()\./]{7,20}$')

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
from core.pagination import paginate, paginated_data
from core.permissions import HasSettingsPermission
from core.responses import error, first_error, get_client_ip, success
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import (
    ApprovalWorkflowRule,
    AuditLog,
    Company,
    Department,
    Designation,
    Document,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeApprovalOverride,
    EmployeeCodeSettings,
    OTPVerification,
    PasswordResetToken,
    Permission,
    Role,
    SMTPSettings,
    User,
)
from apps.accounts.serializers import (
    ApprovalWorkflowRuleUpdateSerializer,
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
    EmployeeBulkImportRowSerializer,
    EmployeeCodeSettingsSerializer,
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
from apps.accounts.utils import send_otp_email, send_template_email, send_test_email

logger = logging.getLogger(__name__)



def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if user.role.name == 'system_admin':
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _auto_assign_managers(employee: 'User') -> list:
    """
    Auto-assign hr and reporting_manager on the employee object (in memory only).

    HR (all roles): set from Branch.hr if available, otherwise first active hr
    user in the same branch.
    reporting_manager (non-managers only):
      - Requires both branch and department to be set.
      - Branch must have exactly 1 manager__team_lead (ambiguous if multiple).
      - Prefers dept manager (same branch).

    Returns a list of field names that were modified — caller must include them in save().
    """
    from apps.branch.models import Branch

    emp_branch = (employee.branch or '').strip()
    emp_dept   = (employee.department or '').strip()
    role_name  = (employee.role.name if employee.role else '').lower()

    changed = []

    # HR assignment: try Branch.hr first, then first active hr user in same branch.
    if employee.hr_id is None and emp_branch:
        branch_obj = Branch.objects.select_related('hr').filter(
            branch_name__iexact=emp_branch
        ).first()
        hr_user = branch_obj.hr if branch_obj else None
        if not hr_user:
            hr_user = User.objects.filter(
                role__name='hr_admin', branch__iexact=emp_branch, is_active=True
            ).first()
        if hr_user and hr_user.pk != employee.pk:
            employee.hr = hr_user
            changed.append('hr')

    # Managers are the reporting manager for others — they have none themselves.
    if role_name == 'manager__team_lead':
        return changed

    # Need at least a branch to find a manager.
    if not emp_branch:
        return changed

    # Skip if reporting_manager already set.
    if employee.reporting_manager_id is not None:
        return changed

    assigned = None

    # 1. Department manager in same branch (most specific — preferred).
    if emp_dept:
        dept = (
            Department.objects.select_related('manager')
            .filter(name__iexact=emp_dept, is_active=True)
            .first()
        )
        if (
            dept and dept.manager
            and dept.manager_id != employee.pk
            and dept.manager.is_active
            and (dept.manager.branch or '').strip().lower() == emp_branch.lower()
        ):
            assigned = dept.manager

    # 2. Fallback: first active manager in the branch (deterministic by id).
    #    Handles branches with multiple managers when no dept-level manager is set.
    if assigned is None:
        assigned = (
            User.objects
            .filter(role__name='manager__team_lead', branch__iexact=emp_branch, is_active=True)
            .exclude(pk=employee.pk)
            .order_by('id')
            .first()
        )

    if assigned is not None:
        employee.reporting_manager = assigned
        changed.append('reporting_manager')

    return changed


def _cloudinary_signed_url(file_field) -> str:
    """Return a short-lived signed Cloudinary download URL for a private file."""
    import os as _os
    import cloudinary.utils as _cu
    name  = file_field.name
    parts = _os.path.basename(name).rsplit('.', 1)
    fmt   = parts[1].lower() if len(parts) == 2 else 'raw'
    return _cu.private_download_url(name, fmt, resource_type='raw', type='upload', attachment=False)


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

    try:
        p = user.profile
    except Exception:
        p = None

    profile_data = {
        # Personal
        'date_of_birth':     str(p.date_of_birth) if (p and p.date_of_birth) else '',
        'gender':            p.gender            if p else '',
        'marital_status':    p.marital_status    if p else '',
        'father_name':       p.father_name       if p else '',
        'blood_group':       p.blood_group       if p else '',
        'current_address':   p.current_address   if p else '',
        'permanent_address': p.permanent_address if p else '',
        # Education
        'highest_qualification': p.highest_qualification if p else '',
        'institution':           p.institution           if p else '',
        'year_of_passing':       p.year_of_passing       if p else None,
        'specialization':        p.specialization        if p else '',
        # Experience
        'total_experience_years': (
            str(p.total_experience_years) if (p and p.total_experience_years is not None) else ''
        ),
        'previous_employer':    p.previous_employer    if p else '',
        'previous_designation': p.previous_designation if p else '',
        'leaving_reason':       p.leaving_reason       if p else '',
        # Bank
        'account_holder_name': p.account_holder_name if p else '',
        'account_type':        p.account_type        if p else '',
        'account_number':      p.account_number      if p else '',
        'ifsc_code':           p.ifsc_code           if p else '',
        'bank_name':           p.bank_name           if p else '',
        'bank_branch_name':    p.bank_branch_name    if p else '',
        # Emergency Contact
        'emergency_name':         p.emergency_name         if p else '',
        'emergency_relationship': p.emergency_relationship if p else '',
        'emergency_phone':        p.emergency_phone        if p else '',
        'emergency_email':        p.emergency_email        if p else '',
    }

    documents = []
    try:
        for doc in user.employee_documents.all():
            try:
                file_url = _cloudinary_signed_url(doc.file) if doc.file else ''
            except Exception:
                file_url = ''
            documents.append({
                'id':                   doc.id,
                'document_type':        doc.document_type,
                'document_type_display': doc.get_document_type_display(),
                'file':                 file_url,
                'file_name':            doc.file_name,
                'file_size':            doc.file_size,
                'uploaded_at':          doc.uploaded_at.isoformat() if doc.uploaded_at else '',
            })
    except Exception:
        documents = []
    role_name = (user.role.name if user.role else '').lower()
    mgr = getattr(user, 'reporting_manager', None)
    _hr = getattr(user, 'hr', None)

    result = {
        'id':             user.employee_id,
        'uuid':           str(user.id),
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
        'hr': {
            'id':   _hr.employee_id if _hr else None,
            'name': _hr.full_name   if _hr else None,
        },
        'profile':            profile_data,
        'documents':          documents,
        'onboarding_status':  user.onboarding_status,
    }

    # Managers ARE the reporting manager for others — they have no reporting manager themselves.
    if role_name != 'manager__team_lead':
        result['reporting_manager'] = {
            'id':   mgr.employee_id if mgr else None,
            'name': mgr.full_name   if mgr else None,
        }

    return result



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


def _login_assessment_status(user) -> str:
    """Return the correct assessment_status string for the login response."""
    from django.db.models import Q as _Q
    from apps.assessments.models import CandidateAssignment
    from apps.recruitment.models import Candidate

    pending_statuses = [CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]

    candidate = Candidate.objects.filter(portal_user=user).first()
    if candidate:
        # Check both FKs — a recruited employee may have assignments on either
        if CandidateAssignment.objects.filter(
            _Q(candidate=candidate) | _Q(employee=user), status__in=pending_statuses,
        ).exists():
            return User.ASSESSMENT_PENDING
    else:
        if CandidateAssignment.objects.filter(employee=user, status__in=pending_statuses).exists():
            return User.ASSESSMENT_PENDING

    return User.ASSESSMENT_COMPLETE


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
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
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
            # Return the same message regardless of whether the account exists
            # to prevent attackers from enumerating registered email addresses.
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


# ─── Role management ──────────────────────────────────────────────────────────

class RoleListCreateView(APIView):
    # GET is open to any authenticated user (needed for role-selector dropdowns
    # on the employee profile page). POST/mutating actions still require CanManageRoles.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Role.objects
            .prefetch_related('role_permissions__permission')
            .annotate(active_user_count=Count('users', filter=Q(users__is_active=True)))
            .order_by('id')
        )
        if (is_active_param := request.query_params.get('is_active', '').strip().lower()) in ('true', 'false'):
            qs = qs.filter(is_active=(is_active_param == 'true'))

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        return success('Roles retrieved successfully.', data=paginated_data(
            paginator, page_obj,
            RoleSerializer(page_obj.object_list, many=True).data,
        ))

    def post(self, request):
        if not CanManageRoles().has_permission(request, self):
            return error('You do not have permission to create roles.', http_status=status.HTTP_403_FORBIDDEN)
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

        _SYSTEM_ROLES = {'employee', 'hr_admin', 'system_admin'}
        if role.name in _SYSTEM_ROLES:
            return error(
                f'Role "{role.display_name}" is a system role and cannot be deleted.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

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
            object_id=str(pk),
            changes={'name': role_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" deleted by %s', role_name, request.user.email)
        return success(f'Role "{role_name}" deleted successfully.')

    def post(self, request, pk):
        return self.put(request, pk)


# ─── Permission CRUD ──────────────────────────────────────────────────────────

class PermissionListView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        qs = Permission.objects.all().order_by('module', 'action')
        page_obj, paginator = paginate(qs, request, default_page_size=100)
        serialized = PermissionSerializer(page_obj.object_list, many=True).data
        grouped: dict[str, list] = defaultdict(list)
        for perm in serialized:
            grouped[perm['module']].append(perm)
        return success('Permissions retrieved successfully.', data=paginated_data(paginator, page_obj, dict(grouped)))

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

    def patch(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = PermissionSerializer(perm, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Permission '{serializer.validated_data.get('codename', perm.codename)}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_updated', module='accounts',
            object_id=str(updated.id),
            changes={'codename': updated.codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" partially updated by %s', updated.codename, request.user.email)
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

    def post(self, request, pk):
        return self.put(request, pk)


# ─── Organisation Structure ────────────────────────────────────────────────────

class DepartmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'departments.view'):
            return error('You do not have permission to view departments.',
                         http_status=status.HTTP_403_FORBIDDEN)
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
        page_obj, paginator = paginate(qs, request, default_page_size=50)
        return success(
            'Departments retrieved successfully.',
            data=paginated_data(
                paginator, page_obj,
                DepartmentSerializer(page_obj.object_list, many=True, context=ctx).data,
            ),
        )

    def post(self, request):
        if not _has_perm(request.user, 'departments.create'):
            return error('You do not have permission to create departments.',
                         http_status=status.HTTP_403_FORBIDDEN)
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
    permission_classes = [IsAuthenticated]

    def _get(self, pk: int) -> Department | None:
        try:
            return Department.objects.prefetch_related('designations').get(pk=pk)
        except Department.DoesNotExist:
            return None

    def get(self, request, pk: int):
        if not _has_perm(request.user, 'departments.view'):
            return error('You do not have permission to view departments.',
                         http_status=status.HTTP_403_FORBIDDEN)
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Department retrieved.', data=DepartmentSerializer(dept).data)

    def _cascade_manager(self, dept: Department, old_manager_id) -> None:
        """When dept manager changes, update reporting_manager for employees in that dept
        who are also in the same branch as the new manager (same branch+dept rule)."""
        if dept.manager_id == old_manager_id:
            return
        qs = User.objects.filter(department__iexact=dept.name, is_active=True)
        if dept.manager_id and dept.manager:
            manager_branch = (dept.manager.branch or '').strip()
            if manager_branch:
                qs = qs.filter(branch__iexact=manager_branch)
            qs = qs.exclude(pk=dept.manager_id)
            qs.update(reporting_manager_id=dept.manager_id)
        else:
            qs.filter(reporting_manager_id=old_manager_id).update(reporting_manager=None)

    def put(self, request, pk: int):
        if not _has_perm(request.user, 'departments.edit'):
            return error('You do not have permission to edit departments.',
                         http_status=status.HTTP_403_FORBIDDEN)
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        old_manager_id = dept.manager_id
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
        self._cascade_manager(updated, old_manager_id)
        AuditLog.objects.create(
            user=request.user, action='dept_updated', module='accounts',
            object_id=str(updated.pk), changes={'name': updated.name},
            ip_address=get_client_ip(request),
        )
        return success('Department updated successfully.', data=DepartmentSerializer(updated).data)

    def patch(self, request, pk: int):
        if not _has_perm(request.user, 'departments.edit'):
            return error('You do not have permission to edit departments.',
                         http_status=status.HTTP_403_FORBIDDEN)
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
        old_manager_id = dept.manager_id
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
        self._cascade_manager(updated, old_manager_id)
        AuditLog.objects.create(
            user=request.user, action='dept_updated', module='accounts',
            object_id=str(updated.pk), changes={'name': updated.name},
            ip_address=get_client_ip(request),
        )
        return success('Department updated successfully.', data=DepartmentSerializer(updated).data)

    def delete(self, request, pk: int):
        if not _has_perm(request.user, 'departments.delete'):
            return error('You do not have permission to delete departments.',
                         http_status=status.HTTP_403_FORBIDDEN)
        dept = self._get(pk)
        if not dept:
            return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)

        active_employees = User.objects.filter(department=dept.name, is_active=True).count()
        if active_employees:
            return error(
                f'Cannot delete department "{dept.name}" — '
                f'{active_employees} active employee(s) belong to it. '
                'Reassign them first.',
                http_status=status.HTTP_409_CONFLICT,
            )

        if dept.designations.exists():
            return error(
                f'Cannot delete department "{dept.name}" — it has designations. '
                'Remove all designations first.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        name = dept.name
        dept_pk = dept.pk
        try:
            dept.delete()
        except ProtectedError:
            return error(
                f'Cannot delete department "{name}" — it is referenced by other records.',
                http_status=status.HTTP_409_CONFLICT,
            )
        AuditLog.objects.create(
            user=request.user, action='dept_deleted', module='accounts',
            object_id=str(dept_pk), changes={'name': name},
            ip_address=get_client_ip(request),
        )
        logger.info('Department "%s" deleted by %s', name, request.user.email)
        return success(f'Department "{name}" deleted successfully.')

    def post(self, request, pk: int):
        return self.put(request, pk)


class DesignationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'designations.view'):
            return error('You do not have permission to view designations.',
                         http_status=status.HTTP_403_FORBIDDEN)
        qs = Designation.objects.select_related('department').all()
        if dept_id := request.query_params.get('department'):
            try:
                dept_id = int(dept_id)
            except (TypeError, ValueError):
                return error('department filter must be a valid integer ID.')
            if not Department.objects.filter(pk=dept_id).exists():
                return error('Department not found.', http_status=status.HTTP_404_NOT_FOUND)
            qs = qs.filter(department_id=dept_id)
        page_obj, paginator = paginate(qs, request, default_page_size=50)
        return success(
            'Designations retrieved successfully.',
            data=paginated_data(
                paginator, page_obj,
                DesignationSerializer(page_obj.object_list, many=True).data,
            ),
        )

    def post(self, request):
        if not _has_perm(request.user, 'designations.create'):
            return error('You do not have permission to create designations.',
                         http_status=status.HTTP_403_FORBIDDEN)
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
    permission_classes = [IsAuthenticated]

    def _get(self, pk: int) -> Designation | None:
        try:
            return Designation.objects.select_related('department').get(pk=pk)
        except Designation.DoesNotExist:
            return None

    def get(self, request, pk: int):
        if not _has_perm(request.user, 'designations.view'):
            return error('You do not have permission to view designations.',
                         http_status=status.HTTP_403_FORBIDDEN)
        desig = self._get(pk)
        if not desig:
            return error('Designation not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Designation retrieved successfully.', data=DesignationSerializer(desig).data)

    def put(self, request, pk: int):
        if not _has_perm(request.user, 'designations.edit'):
            return error('You do not have permission to edit designations.',
                         http_status=status.HTTP_403_FORBIDDEN)
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
        if not _has_perm(request.user, 'designations.edit'):
            return error('You do not have permission to edit designations.',
                         http_status=status.HTTP_403_FORBIDDEN)
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
        if not _has_perm(request.user, 'designations.delete'):
            return error('You do not have permission to delete designations.',
                         http_status=status.HTTP_403_FORBIDDEN)
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

    def post(self, request, pk: int):
        return self.put(request, pk)


# ─── SMTP Settings ─────────────────────────────────────────────────────────────

class SMTPSettingsListCreateView(APIView):
    """GET  /api/settings/smtp/         — list all SMTP configs
       POST /api/settings/smtp/         — create a new SMTP config"""

    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        configs = SMTPSettings.objects.select_related('updated_by').order_by('name')
        page_obj, paginator = paginate(configs, request, default_page_size=20)
        return success(
            f'{paginator.count} SMTP configuration(s) found.',
            data=paginated_data(
                paginator, page_obj,
                SMTPSettingsSerializer(page_obj.object_list, many=True).data,
            ),
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
            msg += ' No SMTP config is currently active — outgoing emails will fail until another config is activated.'
        return success(msg)

    def post(self, request, pk: int):
        return self.put(request, pk)


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
            return error('Failed to send test email. Check the SMTP configuration and try again.')

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
        page_obj, paginator = paginate(cats, request, default_page_size=50)
        return success(
            'Categories retrieved successfully.',
            data=paginated_data(
                paginator, page_obj,
                EmailTemplateCategorySerializer(
                    page_obj.object_list, many=True, context={'template_counts': counts}
                ).data,
            ),
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

    def put(self, request, pk):
        cat = self._get_category(pk)
        if not cat:
            return error('Category not found.', http_status=status.HTTP_404_NOT_FOUND)
        if cat.is_builtin:
            return error('Built-in categories cannot be modified.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = EmailTemplateCategorySerializer(cat, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        updated = serializer.save()
        logger.info('Email template category "%s" fully updated by %s', updated.name, request.user.email)
        return success('Category updated successfully.', data=EmailTemplateCategorySerializer(updated).data)

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

    def post(self, request, pk):
        return self.put(request, pk)


class EmailTemplateListCreateView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            EmailTemplate.objects
            .select_related('updated_by')
            .prefetch_related('attachments')
            .all()
        )
        # Optional filter by type so the frontend can fetch one category at a time
        if tpl_type := request.query_params.get('type', '').strip():
            qs = qs.filter(template_type=tpl_type)

        page_obj, paginator = paginate(qs, request, default_page_size=20)

        category_map = dict(
            EmailTemplateCategory.objects.values_list('name', 'display_name')
        )
        ser_context = {'request': request, 'category_map': category_map}
        grouped: dict[str, list] = defaultdict(list)
        for tpl in page_obj.object_list:
            grouped[tpl.template_type].append(
                EmailTemplateSerializer(tpl, context=ser_context).data
            )
        return success(
            'Email templates retrieved successfully.',
            data=paginated_data(paginator, page_obj, dict(grouped)),
        )
    
    
    def post(self, request):
        if not CanManageRoles().has_permission(request, self):
            return error('You do not have permission to perform this action.',
                         http_status=status.HTTP_403_FORBIDDEN)

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

    _MAX_BYTES    = 10 * 1024 * 1024  # 10 MB
    _ALLOWED_MIME = EmailTemplateAttachment.ALLOWED_MIME_TYPES

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

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        return success(
            'Documents retrieved successfully.',
            data=paginated_data(
                paginator, page_obj,
                DocumentSerializer(page_obj.object_list, many=True, context={'request': request}).data,
            ),
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

    def put(self, request, pk: int):
        if not _can_manage_docs(request.user):
            return error('You do not have permission to update documents.', http_status=status.HTTP_403_FORBIDDEN)
        doc = self._get_doc(pk)
        if not doc:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = DocumentSerializer(doc, data=request.data, context={'request': request})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
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
            logger.error('Document full update failed pk=%s: %s', pk, exc, exc_info=True)
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
        logger.info('Document "%s" fully updated by %s', updated.title, request.user.email)
        return success(
            'Document updated successfully.',
            data=DocumentSerializer(updated, context={'request': request}).data,
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

    def post(self, request, pk: int):
        return self.put(request, pk)


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

    def patch(self, request):
        return self.put(request)


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
            .select_related('role', 'profile', 'reporting_manager')
            .prefetch_related('employee_documents')
            .filter(is_active__in=[True, False])
            .exclude(employee_id='')   # portal candidates have no employee_id until onboarding is approved
            .order_by('-date_joined')
        )

        # Non-system-admin users are always scoped to their own branch — cannot be overridden by query params
        role_name = request.user.role.name if request.user.role else ''
        if role_name != 'system_admin' and request.user.branch:
            qs = qs.filter(branch=request.user.branch)

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

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 20

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Employees retrieved.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     [_employee_dict(u) for u in page_obj.object_list],
        })

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

        # Length guards
        if first_name  and len(first_name)  > 150: errs['first_name']  = 'First name must be 150 characters or fewer.'
        if last_name   and len(last_name)   > 150: errs['last_name']   = 'Last name must be 150 characters or fewer.'
        if email       and len(email)       > 254: errs['email']       = 'Email must be 254 characters or fewer.'
        if phone       and len(phone)       > 20:  errs['phone']       = 'Phone must be 20 characters or fewer.'
        if phone       and 'phone' not in errs and not PHONE_RE.match(phone): errs['phone'] = 'Enter a valid phone number (digits, spaces, +, -, ( ) allowed).'
        if branch      and len(branch)      > 100: errs['branch']      = 'Branch must be 100 characters or fewer.'
        if department  and len(department)  > 100: errs['department']  = 'Department must be 100 characters or fewer.'
        if designation and len(designation) > 100: errs['designation'] = 'Designation must be 100 characters or fewer.'

        # Date format check
        if date_of_joining and 'date_of_joining' not in errs:
            try:
                datetime.strptime(date_of_joining, '%Y-%m-%d')
            except ValueError:
                errs['date_of_joining'] = 'Date of joining must be in YYYY-MM-DD format.'

        # Basic email format check
        if email and 'email' not in errs and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errs['email'] = 'Enter a valid email address.'

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

        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

        employee_id = EmployeeCodeSettings.generate_employee_id(
            first_name=first_name,
            last_name=last_name,
            date_of_joining=date_of_joining or None,
        )
        full_name = f'{first_name} {last_name}'

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
                date_of_joining  = date_of_joining or None,
                must_change_password = True,
                onboarding_status    = User.ONBOARDING_PENDING,
            )
            auto_fields = _auto_assign_managers(user)
            # Auto-assign creating HR admin as the employee's branch HR
            if (request.user.role and request.user.role.name == 'hr_admin'
                    and user.hr_id is None and user.pk != request.user.pk):
                user.hr = request.user
                auto_fields.append('hr')
            if auto_fields:
                user.save(update_fields=[*auto_fields, 'updated_at'])

            # Auto-allocate leave balances based on active leave policies
            from apps.hrms.views.leave import _allocate_leaves_for_employee
            _allocate_leaves_for_employee(user, user.date_of_joining)

            # Auto-assign all default assessments to the new employee
            from apps.assessments.models import (
                Assessment as _Assessment,
                AssessmentItem as _AssessmentItem,
                CandidateAssignment as _CandidateAssignment,
            )
            _default_assessments = list(
                _Assessment.objects.filter(is_active=True, is_default=True).prefetch_related('items')
            )
            _has_pending_assessment = False
            for _assessment in _default_assessments:
                _max_score = _assessment.items.filter(item_type=_AssessmentItem.TYPE_QUIZ).count()
                _, _created = _CandidateAssignment.objects.get_or_create(
                    employee=user,
                    assessment=_assessment,
                    defaults={'assigned_by': request.user, 'max_score': _max_score},
                )
                if _created:
                    _has_pending_assessment = True
            if _has_pending_assessment:
                user.assessment_status = User.ASSESSMENT_PENDING
                user.save(update_fields=['assessment_status', 'updated_at'])

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
            from apps.accounts.utils import (
                _get_smtp_connection, _build_message, _company_email_wrapper,
            )

            company      = Company.objects.first()
            company_name = company.company_name if company else 'Royal HRMS'
            logo_url     = company.logo.url if (company and company.logo) else ''
            website      = company.website  if company else ''
            address      = ', '.join(p for p in [
                getattr(company, 'address', ''),
                getattr(company, 'city',    ''),
                getattr(company, 'state',   ''),
            ] if p) if company else ''

            body = (
                f'<p>Hi <strong>{full_name}</strong>,</p>'
                f'<p>Your Royal HRMS account has been created.'
                f' Use the credentials below to log in:</p>'
                f'<p>'
                f'<strong>Employee ID:</strong> {employee_id}<br>'
                f'<strong>Login Email:</strong> {email}<br>'
                f'<strong>Temporary Password:</strong> {temp_password}'
                f'</p>'
                f'<p>You will be asked to change your password on first login.</p>'
                f'<p>— HR Team</p>'
            )
            html_body = _company_email_wrapper(body, company_name, logo_url, website, address)

            connection, from_email = _get_smtp_connection()
            msg = _build_message(
                subject='Welcome to Royal HRMS — Your Login Credentials',
                html_body=html_body,
                from_email=from_email,
                to=[email],
                connection=connection,
            )
            msg.send(fail_silently=False)
            logger.info('Welcome email sent to %s', email)
        except Exception as exc:
            logger.error('Welcome email failed for %s: %s', email, exc)

        logger.info('Employee %s (%s) created by %s', employee_id, email, request.user.email)
        return success(
            f'{full_name} added successfully. Login credentials sent to {email}.',
            data=_employee_dict(user),
            http_status=status.HTTP_201_CREATED,
        )


def _get_employee(identifier: str):
    """Look up an employee by employee_id code (e.g. EMP001)."""
    try:
        return (
            User.objects
            .select_related('role', 'profile', 'reporting_manager', 'hr')
            .prefetch_related('employee_documents')
            .get(employee_id=identifier)
        )
    except User.DoesNotExist:
        return None


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        auto_changed = _auto_assign_managers(employee)
        if auto_changed:
            employee.save(update_fields=auto_changed + ['updated_at'])
        return success('Employee retrieved.', data=_employee_dict(employee))

    def put(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        data          = request.data
        update_fields = ['updated_at']
        changes       = {}

        role_name = (data.get('role') or '').strip()
        if role_name:
            try:
                new_role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                return error(f'Role "{role_name}" does not exist.')
            old_role = employee.role.name if employee.role else None
            if old_role != new_role.name:
                changes['role'] = {'from': old_role, 'to': new_role.name}
            employee.role = new_role
            update_fields.append('role')

        for field in ('department', 'designation', 'branch', 'phone'):
            val = (data.get(field) or '').strip()
            if field in data:
                old_val = getattr(employee, field, '')
                if old_val != val:
                    changes[field] = {'from': old_val, 'to': val}
                setattr(employee, field, val)
                update_fields.append(field)

        full_name = (data.get('full_name') or '').strip()
        if full_name:
            if employee.full_name != full_name:
                changes['full_name'] = {'from': employee.full_name, 'to': full_name}
            employee.full_name = full_name
            update_fields.append('full_name')

        doj = (data.get('date_of_joining') or '').strip()
        if doj:
            try:
                datetime.strptime(doj, '%Y-%m-%d')
            except ValueError:
                return error('date_of_joining must be in YYYY-MM-DD format.')
            if str(employee.date_of_joining) != doj:
                changes['date_of_joining'] = {'from': str(employee.date_of_joining), 'to': doj}
            employee.date_of_joining = doj
            update_fields.append('date_of_joining')

        dob_raw = (data.get('date_of_birth') or '').strip()
        if dob_raw:
            try:
                datetime.strptime(dob_raw, '%Y-%m-%d')
            except ValueError:
                return error('date_of_birth must be in YYYY-MM-DD format.')
            from apps.accounts.models import EmployeeProfile
            profile, _ = EmployeeProfile.objects.get_or_create(user=employee)
            old_dob = str(profile.date_of_birth) if profile.date_of_birth else ''
            if old_dob != dob_raw:
                changes['date_of_birth'] = {'from': old_dob, 'to': dob_raw}
            profile.date_of_birth = dob_raw
            profile.save(update_fields=['date_of_birth', 'updated_at'])

        if len(update_fields) == 1:
            # Check if hr_id or reporting_manager_id will be set before bailing
            if 'hr_id' not in data and 'reporting_manager_id' not in data:
                return error('No updatable fields provided.')

        # Auto-assign null fields first — manual overrides below will overwrite if needed
        auto_changed = _auto_assign_managers(employee)
        for field in auto_changed:
            if field not in update_fields:
                update_fields.append(field)

        # Manual HR assignment (overrides auto-assign)
        if 'hr_id' in data:
            hr_val = data.get('hr_id')
            if hr_val:
                try:
                    hr_user = User.objects.get(pk=hr_val, is_active=True)
                except (User.DoesNotExist, Exception):
                    return error('HR user not found or is inactive.')
                if hr_user.pk == employee.pk:
                    return error('An employee cannot be their own HR.')
                employee.hr = hr_user
            else:
                employee.hr = None
            if 'hr' not in update_fields:
                update_fields.append('hr')

        # Manual reporting manager assignment (overrides auto-assign; blocked for managers)
        if 'reporting_manager_id' in data:
            current_role = (employee.role.name if employee.role else '').lower()
            if current_role == 'manager':
                return error('Managers do not have a reporting manager.')
            rm_val = data.get('reporting_manager_id')
            if rm_val:
                try:
                    rm_user = User.objects.get(pk=rm_val, is_active=True)
                except (User.DoesNotExist, Exception):
                    return error('Reporting manager not found or is inactive.')
                if rm_user.pk == employee.pk:
                    return error('An employee cannot be their own reporting manager.')
                employee.reporting_manager = rm_user
            else:
                employee.reporting_manager = None
            if 'reporting_manager' not in update_fields:
                update_fields.append('reporting_manager')

        if len(update_fields) == 1:
            return error('No updatable fields provided.')

        employee.save(update_fields=list(dict.fromkeys(update_fields)))

        if changes:
            AuditLog.objects.create(
                user       = request.user,
                action     = 'employee_updated',
                module     = 'employees',
                object_id  = str(employee.id),
                changes    = {
                    'employee_id': employee.employee_id,
                    'full_name':   employee.full_name,
                    **changes,
                },
                ip_address = get_client_ip(request),
            )

        employee = _get_employee(employee_id)
        return success('Employee updated successfully.', data=_employee_dict(employee))

    def patch(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if 'is_active' not in request.data:
            return error('is_active field is required.')

        raw = request.data.get('is_active')
        if isinstance(raw, bool):
            new_status = raw
        elif isinstance(raw, str) and raw.lower() in ('true', 'false'):
            new_status = raw.lower() == 'true'
        else:
            return error('is_active must be true or false.')

        if employee.id == request.user.id and not new_status:
            return error('You cannot deactivate your own account.')

        if not new_status:
            role_name = employee.role.name if employee.role else ''
            if role_name == 'system_admin':
                active_admins = User.objects.filter(
                    role__name='system_admin', is_active=True
                ).count()
                if active_admins <= 1:
                    return error('Cannot deactivate the only active system administrator.')

        old_status = employee.is_active
        if old_status == new_status:
            msg = 'Employee is already active.' if new_status else 'Employee is already inactive.'
            return success(msg, data=_employee_dict(employee))

        employee.is_active = new_status
        employee.save(update_fields=['is_active', 'updated_at'])

        action_label = 'employee_activated' if new_status else 'employee_deactivated'
        AuditLog.objects.create(
            user       = request.user,
            action     = action_label,
            module     = 'employees',
            object_id  = str(employee.id),
            changes    = {
                'employee_id': employee.employee_id,
                'full_name':   employee.full_name,
                'is_active':   {'from': old_status, 'to': new_status},
            },
            ip_address = get_client_ip(request),
        )

        verb = 'activated' if new_status else 'deactivated'
        return success(f'Employee {verb} successfully.', data=_employee_dict(employee))

    def delete(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.delete'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if employee.id == request.user.id:
            return error('You cannot delete your own account.')

        role_name = employee.role.name if employee.role else ''
        if role_name == 'system_admin':
            active_admins = User.objects.filter(role__name='system_admin', is_active=True).count()
            if active_admins <= 1:
                return error('Cannot delete the only active system administrator.')

        full_name    = employee.full_name
        emp_id_str   = employee.employee_id

        employee.is_active = False
        employee.save(update_fields=['is_active', 'updated_at'])

        AuditLog.objects.create(
            user       = request.user,
            action     = 'employee_deleted',
            module     = 'employees',
            object_id  = str(employee.id),
            changes    = {'employee_id': emp_id_str, 'full_name': full_name},
            ip_address = get_client_ip(request),
        )
        logger.info('Employee "%s" deactivated (deleted) by %s', full_name, request.user.email)
        return success(f'Employee "{full_name}" deleted successfully.')

    def post(self, request, employee_id: str):
        return self.put(request, employee_id)


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
            try:
                datetime.strptime(date_from, '%Y-%m-%d')
                qs = qs.filter(created_at__date__gte=date_from)
            except ValueError:
                return error('date_from must be in YYYY-MM-DD format.')
        if date_to:
            try:
                datetime.strptime(date_to, '%Y-%m-%d')
                qs = qs.filter(created_at__date__lte=date_to)
            except ValueError:
                return error('date_to must be in YYYY-MM-DD format.')

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


class EmployeeCodeSettingsView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        cfg = EmployeeCodeSettings.get()
        return success('Employee code settings retrieved.', data=EmployeeCodeSettingsSerializer(cfg).data)

    @transaction.atomic
    def put(self, request):
        cfg = EmployeeCodeSettings.objects.select_for_update().get_or_create(pk=1)[0]
        serializer = EmployeeCodeSettingsSerializer(cfg, data=request.data, partial=False)
        if not serializer.is_valid():
            return error('Please fix the errors below.', data=serializer.errors)
        serializer.save(updated_by=request.user)
        AuditLog.objects.create(
            user=request.user,
            action='employee_code_settings_updated',
            module='accounts',
            object_id='1',
            changes=dict(serializer.validated_data),
            ip_address=get_client_ip(request),
        )
        logger.info('Employee code settings updated by %s', request.user.email)
        return success('Employee code settings updated.', data=serializer.data)

    def patch(self, request):
        return self.put(request)


# ─── Onboarding — Employee fills their own profile ────────────────────────────


_STEP_REQUIRED_FIELDS = {
    # Step 0 — Personal Information
    0: {
        'date_of_birth':   'Date of Birth',
        'gender':          'Gender',
        'marital_status':  'Marital Status',
        'father_name':     "Father's Name",
        'current_address': 'Current Address',
    },
    # Step 1 — Education & Experience
    1: {
        'highest_qualification': 'Highest Qualification',
        'institution':           'Institution / University',
    },
    # Step 2 — Bank Details
    2: {
        'account_holder_name': 'Account Holder Name',
        'account_type':        'Account Type',
        'account_number':      'Account Number',
        'ifsc_code':           'IFSC Code',
        'bank_name':           'Bank Name',
        'bank_branch_name':    'Bank Branch Name',
    },
    # Step 3 — Emergency Contact
    3: {
        'emergency_name':         'Emergency Contact Name',
        'emergency_relationship': 'Relationship',
        'emergency_phone':        'Emergency Contact Phone',
    },
    # Step 4 — Documents (handled separately via EmployeeDocument records)
    4: {},
}

# All profile fields that belong to each step — prevents cross-step writes when
# the frontend sends the full form payload on every "Save & Continue" call.
_STEP_ALL_FIELDS: dict = {
    0: frozenset({
        'date_of_birth', 'gender', 'marital_status', 'father_name',
        'blood_group', 'current_address', 'permanent_address',
    }),
    1: frozenset({
        'highest_qualification', 'institution', 'year_of_passing', 'specialization',
        'total_experience_years', 'previous_employer', 'previous_designation', 'leaving_reason',
    }),
    2: frozenset({
        'account_number', 'ifsc_code', 'bank_name', 'bank_branch_name',
        'account_holder_name', 'account_type',
    }),
    3: frozenset({
        'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email',
    }),
    4: frozenset(),
}

# Profile fields that are nullable in the DB (null=True).
# Empty string from the frontend is converted to None for these fields so they
# can be cleared properly. All other profile fields are CharField(blank=True)
# which stores '' — never None.
_NULLABLE_PROFILE_FIELDS = frozenset({
    'date_of_birth',
    'year_of_passing',
    'total_experience_years',
})


def _field_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _compute_completed_steps(profile, user) -> list:
    """
    Derive which wizard steps (0-4) already satisfy their required fields,
    without persisting a separate progress field — completion is always
    recomputed from the profile/document data that is already saved.
    """
    completed = []
    for step, required in _STEP_REQUIRED_FIELDS.items():
        if step == 4 or not required:
            continue
        if all(_field_filled(getattr(profile, field, None)) for field in required):
            completed.append(step)

    from apps.accounts.models import EmployeeDocument as ED
    uploaded = set(ED.objects.filter(user=user).values_list('document_type', flat=True))
    required_docs = {ED.TYPE_PAN, ED.TYPE_AADHAAR, ED.TYPE_DEGREE}
    has_experience = (
        bool((profile.previous_employer or '').strip())
        or (profile.total_experience_years is not None and profile.total_experience_years > 0)
    )
    if has_experience:
        required_docs.add(ED.TYPE_EXPERIENCE)
    if required_docs.issubset(uploaded):
        completed.append(4)

    return completed


class EmployeeProfileView(APIView):
    """GET / PATCH the requesting user's own EmployeeProfile."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    def _get_or_create_profile(self, user):
        from apps.accounts.models import EmployeeProfile as EP
        profile, _ = EP.objects.get_or_create(user=user)
        return profile

    def get(self, request):
        from apps.accounts.serializers import EmployeeProfileSerializer
        profile = self._get_or_create_profile(request.user)
        return success('Profile retrieved.', data=EmployeeProfileSerializer(profile).data)

    def patch(self, request):
        from apps.accounts.serializers import EmployeeProfileSerializer
        if request.user.onboarding_status == User.ONBOARDING_COMPLETE:
            return error('Onboarding is already complete.')
        profile = self._get_or_create_profile(request.user)
        raw = dict(request.data)
        step_raw = raw.pop('step', [None])
        filled_data = {k: v for k, v in raw.items() if v not in ('', None)}

        step = None
        step_val = step_raw[0] if isinstance(step_raw, list) else step_raw
        if step_val not in (None, '', 'null'):
            try:
                step = int(step_val)
            except (ValueError, TypeError):
                return error('step must be an integer between 0 and 3.')

        if not filled_data:
            return success('Nothing to save.', data=EmployeeProfileSerializer(profile).data)

        if step is not None:
            required = _STEP_REQUIRED_FIELDS.get(step, {})
            missing = []
            for field, label in required.items():
                incoming = filled_data.get(field)
                saved    = getattr(profile, field, None)
                value    = incoming if incoming not in (None, '') else saved
                if not value or (isinstance(value, str) and not value.strip()):
                    missing.append(label)
            if missing:
                return error(
                    f'Please fill in the following required fields: {", ".join(missing)}.'
                )

        serializer = EmployeeProfileSerializer(profile, data=filled_data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        return success('Profile saved.', data=serializer.data)


class OnboardingView(APIView):
    """
    Unified employee self-service onboarding endpoint.

    /onboarding/             GET    → full profile summary
                             POST   → submit the completed wizard

    /onboarding/step/<n>/    GET    → fields for this step only
                             PATCH  → save step data
                             DELETE → clear all fields for this step
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    _VALID_STEPS = frozenset(_STEP_ALL_FIELDS.keys())

    @staticmethod
    def _get_or_create_profile(user):
        from apps.accounts.models import EmployeeProfile as EP
        return EP.objects.get_or_create(user=user)

    # ── GET ───────────────────────────────────────────────────────────────────

    def get(self, request, step: int = None):
        from apps.accounts.serializers import EmployeeProfileSerializer

        if step is None:
            profile, _ = self._get_or_create_profile(request.user)
            data = EmployeeProfileSerializer(profile).data
            data['completed_steps'] = _compute_completed_steps(profile, request.user)
            return success('Profile retrieved.', data=data)

        if step not in self._VALID_STEPS:
            return error(
                f'Invalid step {step}. Valid steps are 0 to 4.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if step == 4:
            from apps.accounts.models import EmployeeDocument as ED
            from apps.accounts.serializers import EmployeeDocumentSerializer
            try:
                docs = ED.objects.filter(user=request.user)
                return success(
                    'Step 4 documents retrieved.',
                    data=EmployeeDocumentSerializer(docs, many=True, context={'request': request}).data,
                )
            except Exception as exc:
                logger.error('OnboardingView GET step=4 doc fetch failed user=%s: %s',
                             request.user.pk, exc, exc_info=True)
                return error(
                    'Unable to retrieve documents. Please try again.',
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        try:
            profile, _ = self._get_or_create_profile(request.user)
            all_data   = EmployeeProfileSerializer(profile).data
        except Exception as exc:
            logger.error('OnboardingView GET step=%d failed user=%s: %s',
                         step, request.user.pk, exc, exc_info=True)
            return error(
                'Unable to retrieve profile data. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success(
            f'Step {step} data retrieved.',
            data={k: v for k, v in all_data.items() if k in _STEP_ALL_FIELDS[step]},
        )

    # ── POST — save step data or submit the completed wizard ─────────────────

    def post(self, request, step: int = None):
        if step is not None:
            if step not in self._VALID_STEPS:
                return error(
                    f'Invalid step {step}. Valid steps are 0 to 4.',
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            return _save_profile_step(request, step)
        return self._submit(request)

    # ── PUT — not supported ───────────────────────────────────────────────────

    def put(self, request, step: int = None):
        return error(
            'Use PATCH /onboarding/step/<n>/ to save step data.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # ── PATCH — save step data ─────────────────────────────────────────────────

    def patch(self, request, step: int = None):
        if step is None:
            return error(
                'Specify a step: PATCH /onboarding/step/<n>/',
                http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        if step not in self._VALID_STEPS:
            return error(
                f'Invalid step {step}. Valid steps are 0 to 4.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        return _save_profile_step(request, step)

    # ── DELETE — clear all fields for this step ───────────────────────────────

    def delete(self, request, step: int = None):
        if step is None:
            return error(
                'Specify a step to clear, e.g. DELETE /onboarding/step/0/.',
                http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        if step not in self._VALID_STEPS:
            return error(
                f'Invalid step {step}. Valid steps are 0 to 4.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        ob_status = request.user.onboarding_status
        if ob_status == User.ONBOARDING_COMPLETE:
            return error(
                'Onboarding is already complete and cannot be modified.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        if ob_status == User.ONBOARDING_SUBMITTED:
            return error(
                'Onboarding has been submitted and is awaiting approval. '
                'Contact HR if you need to make changes.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if step == 4:
            return success(
                'Step 4 documents are managed individually — '
                'use DELETE /api/onboarding/documents/<id>/ to remove a specific document.',
                data={},
            )

        step_fields = _STEP_ALL_FIELDS.get(step, frozenset())
        if not step_fields:
            return success(f'Step {step} has no profile fields to clear.', data={})

        from apps.accounts.models import EmployeeProfile as EP
        try:
            profile, _ = self._get_or_create_profile(request.user)
        except Exception as exc:
            logger.error('OnboardingView DELETE profile fetch failed user=%s step=%d: %s',
                         request.user.pk, step, exc, exc_info=True)
            return error(
                'Unable to retrieve profile. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            EP.objects.filter(pk=profile.pk).update(**{field: None for field in step_fields})
        except Exception as exc:
            logger.error('OnboardingView DELETE clear failed user=%s step=%d: %s',
                         request.user.pk, step, exc, exc_info=True)
            return error(
                'Failed to clear step data. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('Onboarding step %d cleared for user %s', step, request.user.email)
        return success(f'Step {step} data cleared successfully.')

    def _submit(self, request):
        if request.user.onboarding_status == User.ONBOARDING_COMPLETE:
            return error('Onboarding is already complete.')
        if request.user.onboarding_status == User.ONBOARDING_SUBMITTED:
            return error('Onboarding already submitted and awaiting approval.')

        from apps.accounts.models import EmployeeProfile as EP
        try:
            profile = EP.objects.get(user=request.user)
        except EP.DoesNotExist:
            return error('Please fill in your profile details before submitting.')

        missing = []
        if not profile.date_of_birth:
            missing.append('Date of Birth (Personal)')
        if not profile.gender:
            missing.append('Gender (Personal)')
        if not profile.marital_status:
            missing.append('Marital Status (Personal)')
        if not (profile.father_name or '').strip():
            missing.append("Father's Name (Personal)")
        if not (profile.current_address or '').strip():
            missing.append('Current Address (Personal)')
        if not (profile.highest_qualification or '').strip():
            missing.append('Highest Qualification (Education)')
        if not (profile.institution or '').strip():
            missing.append('Institution / University (Education)')
        if not profile.year_of_passing:
            missing.append('Year of Passing (Education)')
        if not (profile.account_holder_name or '').strip():
            missing.append('Account Holder Name (Bank Details)')
        if not profile.account_type:
            missing.append('Account Type (Bank Details)')
        if not (profile.account_number or '').strip():
            missing.append('Account Number (Bank Details)')
        if not (profile.ifsc_code or '').strip():
            missing.append('IFSC Code (Bank Details)')
        if not (profile.bank_name or '').strip():
            missing.append('Bank Name (Bank Details)')
        if not (profile.bank_branch_name or '').strip():
            missing.append('Bank Branch Name (Bank Details)')
        if not (profile.emergency_name or '').strip():
            missing.append('Emergency Contact Name (Emergency Contact)')
        if not (profile.emergency_relationship or '').strip():
            missing.append('Relationship (Emergency Contact)')
        if not (profile.emergency_phone or '').strip():
            missing.append('Emergency Contact Phone (Emergency Contact)')

        if missing:
            return error(
                f'Please complete the following required fields before submitting: '
                f'{", ".join(missing)}.'
            )

        from apps.accounts.models import EmployeeDocument as ED
        uploaded = set(
            ED.objects.filter(user=request.user).values_list('document_type', flat=True)
        )
        missing_docs = []
        if ED.TYPE_PAN not in uploaded:
            missing_docs.append('PAN Card')
        if ED.TYPE_AADHAAR not in uploaded:
            missing_docs.append('Aadhaar Card')
        if ED.TYPE_DEGREE not in uploaded:
            missing_docs.append('Degree Certificate')
        has_experience = (
            bool((profile.previous_employer or '').strip())
            or (profile.total_experience_years is not None and profile.total_experience_years > 0)
        )
        if has_experience and ED.TYPE_EXPERIENCE not in uploaded:
            missing_docs.append('Experience Certificate (required for experienced candidates)')
        if missing_docs:
            return error(
                f'Please upload the following required documents before submitting: '
                f'{", ".join(missing_docs)}.'
            )

        User.objects.filter(pk=request.user.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
        logger.info('User %s submitted onboarding wizard', request.user.email)

        # Notify HR in a background thread so SMTP latency doesn't delay the response
        import threading
        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''
        email_context = {
            'candidate_name':  request.user.full_name or request.user.email,
            'candidate_email': request.user.email,
            'company_name':    company_name,
            'portal_url':      portal_url,
        }
        if request.user.hr_id:
            hr_user = User.objects.filter(pk=request.user.hr_id, is_active=True).first()
            hr_targets = [(hr_user.email, hr_user.full_name or 'HR')] if hr_user and hr_user.email else []
        else:
            hr_targets = [
                (email, 'HR Team')
                for email in User.objects.filter(role__name='hr_admin', is_active=True)
                                         .exclude(email='')
                                         .values_list('email', flat=True)
            ]

        def _send_hr_notifications():
            for recipient_email, hr_name in hr_targets:
                try:
                    send_template_email(
                        recipient_email=recipient_email,
                        template_name='onboarding_submitted',
                        context={**email_context, 'hr_name': hr_name},
                    )
                except Exception:
                    logger.exception(
                        'Failed to send onboarding_submitted to %s for user %s',
                        recipient_email, email_context['candidate_email'],
                    )

        threading.Thread(target=_send_hr_notifications, daemon=True).start()

        return success('Onboarding submitted. Awaiting HR approval.')


def _save_profile_step(request, step: int):
    from apps.accounts.models import EmployeeProfile as EP
    from apps.accounts.serializers import EmployeeProfileSerializer

    # ── Status guard ───────────────────────────────────────────────────────────
    if request.user.onboarding_status == User.ONBOARDING_COMPLETE:
        return error(
            'Onboarding is already complete and cannot be modified.',
            http_status=status.HTTP_403_FORBIDDEN,
        )

    # ── Step range validation ──────────────────────────────────────────────────
    if step not in _STEP_REQUIRED_FIELDS:
        return error(
            f'Invalid step {step}. Valid steps are 0 to 4.',
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Request body must be a key-value mapping ───────────────────────────────
    if not hasattr(request.data, 'items'):
        return error(
            'Request body must be a JSON object.',
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Step 4 — document verification only (no profile fields to write) ───────
    if step == 4:
        from apps.accounts.models import EmployeeDocument as ED
        try:
            uploaded = set(
                ED.objects.filter(user=request.user).values_list('document_type', flat=True)
            )
        except Exception as exc:
            logger.error('_save_profile_step step=4 document query failed user=%s: %s',
                         request.user.pk, exc, exc_info=True)
            return error(
                'Unable to verify documents. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        missing_docs = []
        if ED.TYPE_PAN not in uploaded:
            missing_docs.append('PAN Card')
        if ED.TYPE_AADHAAR not in uploaded:
            missing_docs.append('Aadhaar Card')
        if ED.TYPE_DEGREE not in uploaded:
            missing_docs.append('Degree Certificate')

        # Experience letter required only when previous employer is on record
        try:
            profile, _ = EP.objects.get_or_create(user=request.user)
        except Exception as exc:
            logger.error('_save_profile_step step=4 profile fetch failed user=%s: %s',
                         request.user.pk, exc, exc_info=True)
            return error(
                'Unable to retrieve profile. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        has_experience = (
            bool((profile.previous_employer or '').strip())
            or (profile.total_experience_years is not None and profile.total_experience_years > 0)
        )
        if has_experience and ED.TYPE_EXPERIENCE not in uploaded:
            missing_docs.append('Experience Certificate (required for experienced candidates)')

        if missing_docs:
            return error(
                f'Please upload the following required documents: {", ".join(missing_docs)}.',
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return success('Documents verified. You can proceed to submit.')

    # ── Steps 0-3 — profile field save ────────────────────────────────────────
    try:
        profile, _ = EP.objects.get_or_create(user=request.user)
    except Exception as exc:
        logger.error('_save_profile_step profile fetch failed user=%s step=%d: %s',
                     request.user.pk, step, exc, exc_info=True)
        return error(
            'Unable to retrieve profile. Please try again.',
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    step_fields   = _STEP_ALL_FIELDS.get(step, frozenset())
    required_keys = frozenset(_STEP_REQUIRED_FIELDS[step].keys())

    filled_data: dict = {}
    for k, v in request.data.items():
        if k not in step_fields:
            continue
        if v in ('', None):
            if k in required_keys:
                continue  # let required-field validation catch the missing value
            filled_data[k] = None if k in _NULLABLE_PROFILE_FIELDS else ''
        else:
            filled_data[k] = v

    # Step-scoped "nothing to save" — only triggers when the request had no step
    # fields at all or all were required fields with empty values.
    if not filled_data:
        all_data  = EmployeeProfileSerializer(profile).data
        step_data = {k: v for k, v in all_data.items() if k in step_fields}
        return success('Nothing to save.', data=step_data)

    serializer = EmployeeProfileSerializer(profile, data=filled_data, partial=True)
    if not serializer.is_valid():
        return error(
            first_error(serializer.errors),
            data=serializer.errors,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        serializer.save()
    except Exception as exc:
        logger.error('_save_profile_step serializer.save failed user=%s step=%d: %s',
                     request.user.pk, step, exc, exc_info=True)
        return error(
            'Failed to save profile data. Please try again.',
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Move status to 'draft' (in-progress) on the very first step save
    if request.user.onboarding_status == User.ONBOARDING_PENDING:
        try:
            User.objects.filter(pk=request.user.pk).update(onboarding_status=User.ONBOARDING_DRAFT)
        except Exception as exc:
            logger.warning('_save_profile_step status→draft update failed user=%s: %s',
                           request.user.pk, exc, exc_info=True)

    # Return ONLY the fields for this step — never leak other steps' data
    all_data  = EmployeeProfileSerializer(profile).data
    step_data = {k: v for k, v in all_data.items() if k in step_fields}
    logger.info('Onboarding step %d saved for user %s', step, request.user.email)
    return success('Profile saved.', data=step_data)




# ─── Onboarding — Document upload / stream / delete ──────────────────────────

class EmployeeDocumentView(APIView):
    """
    GET  /onboarding/documents/           → list all documents for this user
    POST /onboarding/documents/           → upload a document
    GET  /onboarding/documents/<doc_id>/  → stream the file (Cloudinary signed proxy)
    DELETE /onboarding/documents/<doc_id>/ → delete a document
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def _get_doc(self, request, doc_id: str):
        from apps.accounts.models import EmployeeDocument as ED
        try:
            doc = ED.objects.get(id=doc_id)
        except ED.DoesNotExist:
            return None, error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        if doc.user_id != request.user.id and not _can_manage_docs(request.user):
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return doc, None

    def get(self, request, doc_id: str = None):
        from apps.accounts.models import EmployeeDocument as ED
        from apps.accounts.serializers import EmployeeDocumentSerializer

        # ── Detail: stream the file through a signed Cloudinary URL ─────────
        if doc_id:
            doc, err = self._get_doc(request, doc_id)
            if err:
                return err

            name  = doc.file.name
            parts = os.path.basename(name).rsplit('.', 1)
            fmt   = parts[1].lower() if len(parts) == 2 else ''

            try:
                dl_url = cloudinary.utils.private_download_url(
                    name, fmt,
                    resource_type='raw',
                    type='upload',
                    attachment=False,
                )
                r = http_req.get(dl_url, stream=True, timeout=30)
                r.raise_for_status()
            except http_req.exceptions.HTTPError as exc:
                logger.error('Employee doc Cloudinary fetch failed doc=%s status=%s',
                             doc_id, exc.response.status_code)
                return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)
            except Exception as exc:
                logger.error('Employee doc download error doc=%s: %s', doc_id, exc, exc_info=True)
                return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)

            content_type = 'application/pdf' if fmt == 'pdf' else r.headers.get('content-type', 'application/octet-stream')
            response = StreamingHttpResponse(r.iter_content(chunk_size=8192), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
            if 'content-length' in r.headers:
                response['Content-Length'] = r.headers['content-length']
            response['Cache-Control'] = 'no-store'
            return response

        # ── List: return all documents for this user ─────────────────────────
        docs = ED.objects.filter(user=request.user)
        return success('Documents retrieved.', data=EmployeeDocumentSerializer(docs, many=True, context={'request': request}).data)

    def post(self, request):
        from apps.accounts.models import EmployeeDocument as ED
        from apps.accounts.serializers import EmployeeDocumentSerializer
        if request.user.onboarding_status == User.ONBOARDING_COMPLETE:
            return error('Onboarding is already complete.')
        serializer = EmployeeDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']
        with transaction.atomic():
            doc = serializer.save(
                user=request.user,
                file_name=file_obj.name,
                file_size=file_obj.size,
            )
            ED.objects.filter(
                user=request.user,
                document_type=doc_type,
            ).exclude(pk=doc.pk).delete()
        return success('Document uploaded.', data=EmployeeDocumentSerializer(doc, context={'request': request}).data,
                       http_status=status.HTTP_201_CREATED)

    def delete(self, request, doc_id: str = None):
        if not doc_id:
            return error('Document ID is required.', http_status=status.HTTP_400_BAD_REQUEST)
        doc, err = self._get_doc(request, doc_id)
        if err:
            return err
        if doc.user_id != request.user.id:
            return error('Only the owner can delete their document.', http_status=status.HTTP_403_FORBIDDEN)
        if request.user.onboarding_status == User.ONBOARDING_COMPLETE:
            return error(
                'Onboarding is already complete. Contact HR to update documents.',
                http_status=status.HTTP_409_CONFLICT,
            )
        doc.delete()
        logger.info('Employee document %s deleted by %s', doc_id, request.user.email)
        return success('Document deleted.')




# ─── Onboarding — HR management (pipeline + approvals queue + approve/reject) ──


class OnboardingApprovalView(APIView):
    """
    Unified HR onboarding management endpoint.

    /onboarding/approvals/           GET → approvals queue (submitted, awaiting action)
                                         ?view=pipeline → full pipeline (pending+draft+submitted)
    /onboarding/approvals/<user_id>/ GET  → specific employee's full onboarding details
                                     POST → approve or reject
                                           body: {decision: 'approve'|'reject', remarks: ''}
    """
    permission_classes = [IsAuthenticated]

    # ── GET ───────────────────────────────────────────────────────────────────

    def get(self, request, user_id=None):
        if not _has_perm(request.user, 'onboarding.approve'):
            return error('You do not have permission to view onboarding approvals.',
                         http_status=status.HTTP_403_FORBIDDEN)

        if user_id is not None:
            return self._get_user_detail(request, user_id)

        view = request.query_params.get('view', 'approvals').strip().lower()
        return self._get_pipeline(request) if view == 'pipeline' else self._get_approvals_list(request)

    # ── POST — approve or reject a specific employee ──────────────────────────

    @transaction.atomic
    def post(self, request, user_id=None):
        if user_id is None:
            return error(
                'User ID is required. Use POST /onboarding/approvals/<user_id>/ to approve or reject.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if not _has_perm(request.user, 'onboarding.approve'):
            return error('You do not have permission to approve onboarding.',
                         http_status=status.HTTP_403_FORBIDDEN)

        try:
            target = User.objects.select_related('role').get(pk=user_id)
        except User.DoesNotExist:
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        if target.onboarding_status != User.ONBOARDING_SUBMITTED:
            return error('This user has not submitted their onboarding form.')

        role_name        = request.user.role.name if request.user.role else ''
        target_role_name = target.role.name if target.role else ''
        if role_name == 'hr_admin' and target_role_name in ('hr_admin', 'system_admin'):
            return error('HR admin can only approve employee onboarding.',
                         http_status=status.HTTP_403_FORBIDDEN)

        decision          = request.data.get('decision')
        remarks           = request.data.get('remarks', '')
        req_designation   = (request.data.get('designation')        or '').strip()
        req_department    = (request.data.get('department')         or '').strip()
        req_assessment_id = request.data.get('assessment_id')       or None
        req_manager_id    = request.data.get('reporting_manager_id')
        annual_ctc_raw    = (request.data.get('annual_ctc')         or '').strip()
        if decision not in ('approve', 'reject'):
            return error('decision must be "approve" or "reject".')
        if decision == 'approve':
            if not req_department:
                return error('Department is required to approve onboarding.')
            if not req_designation:
                return error('Designation is required to approve onboarding.')

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''
        # The onboarding-approved and assessment-assigned emails must land the
        # employee directly on the assessment page, not just the portal root —
        # otherwise they have to manually find their way there after logging in.
        assessments_portal_url = f'{portal_url.rstrip("/")}/onboarding/assessments' if portal_url else ''

        if decision == 'approve':
            from apps.recruitment.models import Candidate
            try:
                linked_candidate = Candidate.objects.select_related('branch').get(portal_user=target)
            except Candidate.DoesNotExist:
                linked_candidate = None

            needs_conversion = not target.role and not target.employee_id
            if needs_conversion:
                try:
                    employee_role = Role.objects.get(name='employee')
                except Role.DoesNotExist:
                    return error('Role "employee" not found. Create it in Roles settings first.')
                target.role = employee_role
                if not target.date_of_joining:
                    from django.utils import timezone as tz
                    target.date_of_joining = tz.now().date()
                _name_parts = (target.full_name or '').split(' ', 1)
                target.employee_id = EmployeeCodeSettings.generate_employee_id(
                    first_name=_name_parts[0] if _name_parts else '',
                    last_name=_name_parts[1] if len(_name_parts) > 1 else '',
                    date_of_joining=target.date_of_joining,
                )

                if linked_candidate and not target.branch and linked_candidate.branch:
                    target.branch = linked_candidate.branch.branch_name

            if req_designation:
                target.designation = req_designation
            elif not target.designation and linked_candidate and linked_candidate.position_applied:
                target.designation = linked_candidate.position_applied

            if req_department:
                target.department = req_department

            # Explicit reporting manager override — set before _auto_assign_managers so auto-assign skips it
            if req_manager_id:
                try:
                    manager_user = User.objects.get(pk=req_manager_id, is_active=True)
                    target.reporting_manager = manager_user
                except User.DoesNotExist:
                    return error('Reporting manager not found or is inactive.')

            target.onboarding_status    = User.ONBOARDING_COMPLETE
            target.must_change_password = False
            auto_fields = _auto_assign_managers(target)
            target.save(update_fields=list(dict.fromkeys([
                'onboarding_status', 'must_change_password',
                'role', 'employee_id', 'date_of_joining',
                'designation', 'department', 'branch',
                'reporting_manager', 'hr',
                *auto_fields,
            ])))

            if needs_conversion:
                # Auto-allocate leave balances after candidate→employee conversion
                from apps.hrms.views.leave import _allocate_leaves_for_employee
                _allocate_leaves_for_employee(target, target.date_of_joining)

            # Create initial salary config if CTC was provided at approval time
            if annual_ctc_raw:
                from decimal import Decimal as _Decimal
                from django.utils import timezone as _tz
                from apps.payroll.models import EmployeeSalaryConfig as _SalaryConfig
                try:
                    _annual_ctc = _Decimal(annual_ctc_raw)
                    _SalaryConfig.objects.filter(employee=target, is_active=True).update(is_active=False)
                    _SalaryConfig.objects.create(
                        employee=target,
                        annual_ctc=_annual_ctc,
                        effective_from=target.date_of_joining or _tz.now().date(),
                        is_active=True,
                    )
                    logger.info('EmployeeSalaryConfig created for %s via onboarding approval', target.email)
                except Exception:
                    logger.exception('Failed to create salary config for %s during onboarding approval', target.email)

            if linked_candidate:
                linked_candidate.status      = Candidate.STATUS_CONVERTED
                linked_candidate.hr_approved = True
                linked_candidate.save(update_fields=['status', 'hr_approved', 'updated_at'])

            # Auto-assign default assessments — employee must complete these to unlock full portal.
            # Works for both recruited candidates (candidate FK) and direct hires (employee FK).
            from apps.assessments.models import Assessment, AssessmentItem, CandidateAssignment
            from django.db.models import Q as _Q
            assigned_assessments = []
            assessments_to_assign = list(
                Assessment.objects.filter(is_active=True, is_default=True).prefetch_related('items')
            )
            # HR may pick a specific (possibly non-default) assessment in the approval
            # confirmation dialog — honor that choice, not just the global defaults.
            if req_assessment_id and not any(str(a.id) == str(req_assessment_id) for a in assessments_to_assign):
                selected_assessment = Assessment.objects.filter(
                    pk=req_assessment_id, is_active=True,
                ).prefetch_related('items').first()
                if selected_assessment:
                    assessments_to_assign.append(selected_assessment)
            for assessment in assessments_to_assign:
                max_score = assessment.items.filter(item_type=AssessmentItem.TYPE_QUIZ).count()
                if linked_candidate:
                    _, created = CandidateAssignment.objects.get_or_create(
                        candidate=linked_candidate,
                        assessment=assessment,
                        defaults={'assigned_by': request.user, 'max_score': max_score},
                    )
                else:
                    _, created = CandidateAssignment.objects.get_or_create(
                        employee=target,
                        assessment=assessment,
                        defaults={'assigned_by': request.user, 'max_score': max_score},
                    )
                if created:
                    assigned_assessments.append(assessment)

            # Set status PENDING if any assignment (new or pre-existing from recruitment step) is pending
            pending_filter = (
                _Q(candidate=linked_candidate) if linked_candidate else _Q(employee=target)
            )
            has_pending = CandidateAssignment.objects.filter(
                pending_filter,
                status__in=[CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS],
            ).exists()
            if has_pending and target.assessment_status != User.ASSESSMENT_PENDING:
                target.assessment_status = User.ASSESSMENT_PENDING
                target.save(update_fields=['assessment_status', 'updated_at'])

            AuditLog.objects.create(
                user=request.user, action='onboarding_approved', module='accounts',
                object_id=str(target.pk),
                changes={'target': target.email, 'remarks': remarks},
                ip_address=get_client_ip(request),
            )
            logger.info('Onboarding approved for %s by %s', target.email, request.user.email)

            try:
                send_template_email(
                    recipient_email=target.email,
                    template_name='onboarding_approved',
                    context={
                        'employee_name':    target.full_name,
                        'company_name':     company_name,
                        'employee_id':      target.employee_id or '',
                        'designation':      target.designation or '',
                        'department':       target.department  or '',
                        'date_of_joining':  str(target.date_of_joining) if target.date_of_joining else '',
                        'portal_url':       assessments_portal_url if has_pending else portal_url,
                        'has_assessments':  'true' if has_pending else 'false',
                        'assessment_count': str(len(assigned_assessments)),
                    },
                )
            except Exception:
                logger.exception('Failed to send onboarding approval email to %s', target.email)

            # Send individual assessment emails so the candidate knows exactly what to complete
            for assessment in assigned_assessments:
                try:
                    send_template_email(
                        recipient_email=target.email,
                        template_name='assessment_assigned',
                        context={
                            'candidate_name':   target.full_name,
                            'assessment_title': assessment.title,
                            'company_name':     company_name,
                            'portal_url':       assessments_portal_url or portal_url,
                        },
                    )
                except Exception:
                    logger.exception(
                        'Failed to send assessment_assigned email for "%s" to %s',
                        assessment.title, target.email,
                    )

            return success(f'{target.full_name} onboarding approved.')

        else:
            target.onboarding_status = User.ONBOARDING_REJECTED
            target.save(update_fields=['onboarding_status'])
            AuditLog.objects.create(
                user=request.user, action='onboarding_rejected', module='accounts',
                object_id=str(target.pk),
                changes={'target': target.email, 'remarks': remarks},
                ip_address=get_client_ip(request),
            )
            logger.info('Onboarding rejected for %s by %s', target.email, request.user.email)

            try:
                send_template_email(
                    recipient_email=target.email,
                    template_name='onboarding_rejected',
                    context={
                        'employee_name': target.full_name,
                        'company_name':  company_name,
                        'remarks':       remarks or 'Please contact HR for details.',
                        'portal_url':    portal_url,
                    },
                )
            except Exception:
                logger.exception('Failed to send onboarding rejection email to %s', target.email)

            return success(f'Onboarding sent back to {target.full_name} for corrections.')

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_pipeline(self, request):
        from apps.accounts.serializers import OnboardingPipelineSerializer
        from apps.recruitment.models import Candidate

        role_name = request.user.role.name if request.user.role else ''
        base_qs = (
            User.objects
            .filter(
                onboarding_status__in=[
                    User.ONBOARDING_PENDING,
                    User.ONBOARDING_DRAFT,
                    User.ONBOARDING_SUBMITTED,
                ],
                candidate_portal__isnull=False,
            )
            .select_related('role')
            .distinct()
            .order_by('-date_joined')
        )
        if role_name == 'hr_admin':
            base_qs = base_qs.exclude(role__name__in=['hr_admin', 'system_admin'])

        stats = {
            'pending':   base_qs.filter(onboarding_status=User.ONBOARDING_PENDING).count(),
            'draft':     base_qs.filter(onboarding_status=User.ONBOARDING_DRAFT).count(),
            'submitted': base_qs.filter(onboarding_status=User.ONBOARDING_SUBMITTED).count(),
        }

        status_param = request.query_params.get('status', '').strip()
        if status_param:
            allowed = {User.ONBOARDING_PENDING, User.ONBOARDING_DRAFT, User.ONBOARDING_SUBMITTED}
            if status_param not in allowed:
                return error(f'status must be one of: {", ".join(sorted(allowed))}.')
            base_qs = base_qs.filter(onboarding_status=status_param)

        page_obj, paginator = paginate(base_qs, request, default_page_size=20)
        user_ids = [u.pk for u in page_obj.object_list]
        candidates_by_user = {
            c.portal_user_id: c
            for c in Candidate.objects.filter(portal_user_id__in=user_ids)
        }
        data = paginated_data(
            paginator, page_obj,
            OnboardingPipelineSerializer(
                page_obj.object_list, many=True,
                context={'candidates_by_user': candidates_by_user},
            ).data,
        )
        data['stats'] = stats
        return success('Onboarding pipeline retrieved.', data=data)

    def _get_approvals_list(self, request):
        from apps.accounts.serializers import OnboardingApprovalSerializer
        from apps.recruitment.models import Candidate

        role_name = request.user.role.name if request.user.role else ''
        qs = (
            User.objects
            .filter(onboarding_status__in=[User.ONBOARDING_SUBMITTED, User.ONBOARDING_REJECTED])
            .select_related('role', 'profile')
            .prefetch_related('employee_documents')
            .order_by('date_joined')
        )
        if role_name == 'hr_admin':
            qs = qs.exclude(role__name__in=['hr_admin', 'system_admin'])

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        user_ids = [u.pk for u in page_obj.object_list]
        candidates_by_user = {
            c.portal_user_id: c
            for c in Candidate.objects.select_related('branch').filter(portal_user_id__in=user_ids)
        }
        return success('Onboarding approvals retrieved.', data=paginated_data(
            paginator, page_obj,
            OnboardingApprovalSerializer(
                page_obj.object_list, many=True,
                context={
                    'request': request,
                    'candidates_by_user': candidates_by_user,
                    'use_cloudinary_url': True,
                },
            ).data,
        ))

    def _get_user_detail(self, request, user_id):
        from apps.accounts.serializers import OnboardingApprovalSerializer
        from apps.recruitment.models import Candidate

        try:
            target = (
                User.objects
                .select_related('role', 'profile')
                .prefetch_related('employee_documents')
                .get(pk=user_id)
            )
        except User.DoesNotExist:
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        candidates_by_user = {
            c.portal_user_id: c
            for c in Candidate.objects.select_related('branch').filter(portal_user=target)
        }
        return success(
            'Onboarding details retrieved.',
            data=OnboardingApprovalSerializer(
                target,
                context={
                    'request': request,
                    'candidates_by_user': candidates_by_user,
                    'use_cloudinary_url': True,
                },
            ).data,
        )


# ─── My Profile ───────────────────────────────────────────────────────────────

OnboardingApprovalsListView = OnboardingApprovalView


class MyProfileView(APIView):
    """GET / PATCH the authenticated user's own profile (post-onboarding)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import EmployeeProfile
        from apps.accounts.serializers import MyProfileSerializer
        EmployeeProfile.objects.get_or_create(user=request.user)
        user = User.objects.select_related('role', 'profile').get(pk=request.user.pk)
        return success('Profile retrieved.', MyProfileSerializer(user).data)

    def patch(self, request):
        from apps.accounts.models import EmployeeProfile
        from apps.accounts.serializers import MyProfileUpdateSerializer
        serializer = MyProfileUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        data = serializer.validated_data

        if 'phone' in data:
            request.user.phone = data['phone']
            request.user.save(update_fields=['phone', 'updated_at'])

        profile_fields = [
            'current_address', 'permanent_address',
            'emergency_name', 'emergency_relationship',
            'emergency_phone', 'emergency_email',
        ]
        profile_data = {k: v for k, v in data.items() if k in profile_fields}
        if profile_data:
            profile, _ = EmployeeProfile.objects.get_or_create(user=request.user)
            for key, value in profile_data.items():
                setattr(profile, key, value)
            profile.save(update_fields=list(profile_data.keys()) + ['updated_at'])

        logger.info('Profile updated by %s', request.user.email)
        return success('Profile updated successfully.')


# ─── HR & Manager dropdown lists ─────────────────────────────────────────────

class HRListView(APIView):
    """GET list of active HR users for a given branch — for the HR assignment dropdown.
    Query param: branch (required) — e.g. ?branch=Mumbai HQ
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        branch = (request.query_params.get('branch') or '').strip()
        # Filter by permission so any role named hr/hr_admin/etc. is included
        hrs = User.objects.filter(
            role__role_permissions__permission__codename='onboarding.approve',
            is_active=True,
        ).select_related('role').distinct()
        if branch:
            hrs = hrs.filter(
                Q(branch__iexact=branch) | Q(managed_branches__branch_name__iexact=branch)
            ).distinct()
        hrs = hrs.order_by('full_name')
        data = [
            {'id': str(u.id), 'employee_id': u.employee_id, 'full_name': u.full_name,
             'department': u.department, 'branch': u.branch}
            for u in hrs
        ]
        # If the requesting user is hr_admin but not in the results (e.g. role FK mismatch),
        # include them so the picker always has at least the current HR visible.
        requester_is_hr = (request.user.role and request.user.role.name == 'hr_admin')
        if requester_is_hr and not any(d['id'] == str(request.user.id) for d in data):
            data.insert(0, {
                'id': str(request.user.id),
                'employee_id': request.user.employee_id,
                'full_name': request.user.full_name,
                'department': request.user.department,
                'branch': request.user.branch,
            })
        return success('HR users retrieved.', data=data)


class ManagerListView(APIView):
    """GET list of active managers — optionally filtered by branch.
    Query param: branch (optional) — e.g. ?branch=Mumbai HQ
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        branch = (request.query_params.get('branch') or '').strip()
        if not branch:
            return error('branch query parameter is required.')
        # Filter by permission so any role named manager/team_lead/etc. is included
        managers = (
            User.objects
            .filter(
                role__role_permissions__permission__codename='leave.approve',
                is_active=True,
                branch__iexact=branch,
            )
            .select_related('role')
            .distinct()
            .order_by('full_name')
        )
        data = [
            {'id': str(u.id), 'employee_id': u.employee_id, 'full_name': u.full_name,
             'department': u.department, 'branch': u.branch}
            for u in managers
        ]
        return success('Managers retrieved.', data=data)


# ─── Reporting Manager ────────────────────────────────────────────────────────

class EmployeeReportingManagerView(APIView):
    """PATCH to assign or clear a reporting manager for a specific employee."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if employee.role and employee.role.name.lower() == 'manager':
            return error('Managers do not have a reporting manager.')

        manager_id = request.data.get('reporting_manager_id')

        if manager_id is None:
            employee.reporting_manager = None
        else:
            try:
                manager = User.objects.get(id=manager_id, is_active=True)
            except (User.DoesNotExist, Exception):
                return error('Reporting manager not found or is inactive.')

            if manager.id == employee.id:
                return error('An employee cannot be their own reporting manager.')

            employee.reporting_manager = manager

        employee.save(update_fields=['reporting_manager', 'updated_at'])
        logger.info(
            'Reporting manager for %s set to %s by %s',
            employee.employee_id,
            employee.reporting_manager.full_name if employee.reporting_manager else 'None',
            request.user.email,
        )
        return success('Reporting manager updated.', data=_employee_dict(employee))


# ─── Global Approval Workflow Rules ──────────────────────────────────────────

_WORKFLOW_ORDER = [
    ApprovalWorkflowRule.WORKFLOW_LEAVE,
    ApprovalWorkflowRule.WORKFLOW_EXPENSE,
    ApprovalWorkflowRule.WORKFLOW_RESIGNATION,
    ApprovalWorkflowRule.WORKFLOW_LOAN,
]


def _ensure_default_rules():
    """Create default rules for any workflow types that don't have one yet.
    Never overwrites existing rules — safe to call on every request."""
    existing = set(ApprovalWorkflowRule.objects.values_list('workflow_type', flat=True))
    missing  = [wf for wf in _WORKFLOW_ORDER if wf not in existing]
    if not missing:
        return
    l1 = ApprovalWorkflowRule.ROLE_REPORTING_MANAGER
    l2 = ApprovalWorkflowRule.ROLE_HR_MANAGER
    ApprovalWorkflowRule.objects.bulk_create([
        ApprovalWorkflowRule(workflow_type=wf, l1_approver_role=l1, l2_approver_role=l2)
        for wf in missing
    ])


def _serialize_rule(rule: ApprovalWorkflowRule) -> dict:
    role_labels = dict(ApprovalWorkflowRule.APPROVER_ROLE_CHOICES)
    return {
        'workflow_type':      rule.workflow_type,
        'workflow_label':     rule.get_workflow_type_display(),
        'l1_approver_role':   rule.l1_approver_role,
        'l1_approver_label':  role_labels.get(rule.l1_approver_role, ''),
        'l2_approver_role':   rule.l2_approver_role,
        'l2_approver_label':  role_labels.get(rule.l2_approver_role, '') if rule.l2_approver_role else '',
    }


class ApprovalWorkflowRuleView(APIView):
    """GET all global workflow rules; PATCH a single rule."""
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        _ensure_default_rules()
        rules = {r.workflow_type: r for r in ApprovalWorkflowRule.objects.all()}
        data  = [_serialize_rule(rules[wf]) for wf in _WORKFLOW_ORDER if wf in rules]
        return success('Approval rules retrieved.', data=data)

    def patch(self, request):
        serializer = ApprovalWorkflowRuleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data = serializer.validated_data
        _ensure_default_rules()

        rule = ApprovalWorkflowRule.objects.get(workflow_type=data['workflow_type'])
        rule.l1_approver_role = data['l1_approver_role']
        rule.l2_approver_role = data.get('l2_approver_role', '')
        rule.updated_by       = request.user
        rule.save(update_fields=['l1_approver_role', 'l2_approver_role', 'updated_by', 'updated_at'])

        logger.info('Approval rule for %s updated by %s', data['workflow_type'], request.user.email)
        return success('Approval rule updated.', data=_serialize_rule(rule))


# ─── Employee Approval Matrix ─────────────────────────────────────────────────

def _resolve_rule_approver(role_str: str, employee):
    """Resolve a role string to the actual User for a given employee."""
    if role_str in ('reporting_manager', 'rm', 'manager'):
        return getattr(employee, 'reporting_manager', None)
    if role_str in ('hr', 'hr_manager', 'hr_admin'):
        return getattr(employee, 'hr', None)
    return None


def _build_matrix_row(rule: ApprovalWorkflowRule, override, employee=None) -> dict:
    role_labels = dict(ApprovalWorkflowRule.APPROVER_ROLE_CHOICES)

    # Per-employee override takes priority; otherwise resolve from employee's FK fields
    if override and override.l1_override:
        l1_id, l1_name, l1_is_override = str(override.l1_override.id), override.l1_override.full_name, True
    else:
        l1_user = _resolve_rule_approver(rule.l1_approver_role, employee) if employee else None
        l1_id   = str(l1_user.id) if l1_user else None
        l1_name = l1_user.full_name if l1_user else None
        l1_is_override = False

    if override and override.l2_override:
        l2_id, l2_name, l2_is_override = str(override.l2_override.id), override.l2_override.full_name, True
    else:
        l2_user = _resolve_rule_approver(rule.l2_approver_role, employee) if employee else None
        l2_id   = str(l2_user.id) if l2_user else None
        l2_name = l2_user.full_name if l2_user else None
        l2_is_override = False

    return {
        'workflow_type':     rule.workflow_type,
        'workflow_label':    rule.get_workflow_type_display(),
        'l1_approver_role':  rule.l1_approver_role,
        'l1_approver_label': role_labels.get(rule.l1_approver_role, ''),
        'l1_approver_id':    l1_id,
        'l1_approver_name':  l1_name,
        'l1_is_override':    l1_is_override,
        'l2_approver_role':  rule.l2_approver_role,
        'l2_approver_label': role_labels.get(rule.l2_approver_role, '') if rule.l2_approver_role else '',
        'l2_approver_id':    l2_id,
        'l2_approver_name':  l2_name,
        'l2_is_override':    l2_is_override,
    }


class EmployeeApprovalMatrixView(APIView):
   
    permission_classes = [IsAuthenticated]
    _valid_types = [c[0] for c in ApprovalWorkflowRule.WORKFLOW_CHOICES]

    # ── helpers ──────────────────────────────────────────────────────────────

    def _resolve_user(self, uid):
        if uid is None:
            return None, None
        try:
            return User.objects.get(id=uid, is_active=True), None
        except (User.DoesNotExist, Exception):
            return None, f'User {uid} not found or inactive.'

    def _validate_workflow(self, workflow_type):
        if workflow_type not in self._valid_types:
            return f'workflow_type must be one of: {", ".join(self._valid_types)}.'
        return None

    # ── read ─────────────────────────────────────────────────────────────────

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        _ensure_default_rules()
        rules = {r.workflow_type: r for r in ApprovalWorkflowRule.objects.all()}
        overrides = {
            o.workflow_type: o
            for o in EmployeeApprovalOverride.objects
                        .filter(employee=employee)
                        .select_related('l1_override', 'l2_override')
        }

        workflow_type = request.query_params.get('workflow_type')
        if workflow_type:
            err = self._validate_workflow(workflow_type)
            if err:
                return error(err)
            if workflow_type not in rules:
                return error('Rule not found.', http_status=status.HTTP_404_NOT_FOUND)
            return success(
                'Approval matrix row retrieved.',
                data=_build_matrix_row(rules[workflow_type], overrides.get(workflow_type), employee),
            )

        data = [
            _build_matrix_row(rules[wf], overrides.get(wf), employee)
            for wf in _WORKFLOW_ORDER if wf in rules
        ]
        return success('Approval matrix retrieved.', data=data)

    # ── create / update ───────────────────────────────────────────────────────

    def _upsert(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        workflow_type = request.data.get('workflow_type')
        err = self._validate_workflow(workflow_type)
        if err:
            return error(err)

        l1_user, l1_err = self._resolve_user(request.data.get('l1_override_id'))
        if l1_err:
            return error(l1_err)
        l2_user, l2_err = self._resolve_user(request.data.get('l2_override_id'))
        if l2_err:
            return error(l2_err)

        override, _ = EmployeeApprovalOverride.objects.get_or_create(
            employee=employee, workflow_type=workflow_type,
        )
        override.l1_override = l1_user
        override.l2_override = l2_user
        override.updated_by  = request.user
        override.save(update_fields=['l1_override', 'l2_override', 'updated_by', 'updated_at'])

        _ensure_default_rules()
        rule = ApprovalWorkflowRule.objects.get(workflow_type=workflow_type)
        override.refresh_from_db()
        return success('Approval matrix updated.', data=_build_matrix_row(rule, override, employee))

    def post(self, request, employee_id: str):
        return self._upsert(request, employee_id)

    def put(self, request, employee_id: str):
        return self._upsert(request, employee_id)

    def patch(self, request, employee_id: str):
        return self._upsert(request, employee_id)

    # ── delete ────────────────────────────────────────────────────────────────

    def delete(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        workflow_type = request.query_params.get('workflow_type')
        err = self._validate_workflow(workflow_type)
        if err:
            return error(err)

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        EmployeeApprovalOverride.objects.filter(
            employee=employee, workflow_type=workflow_type
        ).delete()

        _ensure_default_rules()
        rule = ApprovalWorkflowRule.objects.get(workflow_type=workflow_type)
        return success(
            f'Override for "{workflow_type}" cleared. Global default is now active.',
            data=_build_matrix_row(rule, None, employee),
        )


# ── Employee Bulk Import ───────────────────────────────────────────────────────

_EMP_IMPORT_COL_MAP = {
    'first name': 'first_name', 'firstname': 'first_name', 'first_name': 'first_name',
    'last name':  'last_name',  'lastname':  'last_name',  'last_name':  'last_name',
    'work email': 'email', 'email': 'email', 'work_email': 'email',
    'email address': 'email', 'email_address': 'email',
    'phone': 'phone', 'mobile': 'phone', 'phone number': 'phone',
    'phone_number': 'phone', 'mobile number': 'phone',
    'role': 'role',
    'department': 'department', 'dept': 'department',
    'designation': 'designation',
    'branch': 'branch', 'branch name': 'branch', 'branch_name': 'branch',
    'employee type': 'employee_type', 'employee_type': 'employee_type',
    'emp type': 'employee_type', 'type': 'employee_type',
    'date of joining': 'date_of_joining', 'date_of_joining': 'date_of_joining',
    'joining date': 'date_of_joining', 'doj': 'date_of_joining',
    'gender': 'gender', 'sex': 'gender',
    'dob': 'date_of_birth', 'date of birth': 'date_of_birth',
    'date_of_birth': 'date_of_birth', 'birth date': 'date_of_birth',
    'birthdate': 'date_of_birth',
    'blood group': 'blood_group', 'blood_group': 'blood_group', 'blood': 'blood_group',
    'address': 'address', 'current address': 'address', 'current_address': 'address',
}

_EMP_MAX_IMPORT_ROWS  = 1000
_EMP_MAX_IMPORT_BYTES = 5 * 1024 * 1024
_EMP_ALLOWED_ROLES    = frozenset({'system_admin', 'hr_admin'})


def _normalize_employee_import_headers(row_dict: dict) -> dict:
    out = {}
    for key, value in row_dict.items():
        mapped = _EMP_IMPORT_COL_MAP.get(key.strip().lower())
        if mapped:
            out[mapped] = value
    return out


def _emp_xlsx_cell_to_str(value) -> str:
    import datetime as _dt
    if isinstance(value, _dt.datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, _dt.date):
        return value.strftime('%Y-%m-%d')
    return str(value).strip() if value is not None else ''


def _parse_employee_xlsx_rows(file_obj) -> tuple:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = iter(ws.iter_rows(values_only=True))
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return [], 'The XLSX file has no header row.'
        headers = [str(h).strip() if h is not None else '' for h in header_row]
        rows = []
        for raw in rows_iter:
            if all(v is None or str(v).strip() == '' for v in raw):
                continue
            rows.append({headers[i]: _emp_xlsx_cell_to_str(raw[i]) for i in range(len(headers))})
        wb.close()
        return rows, None
    except Exception as exc:
        return [], f'Could not parse XLSX file: {exc}'


def _parse_employee_csv_rows(file_obj) -> tuple:
    try:
        text = file_obj.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            if all((v or '').strip() == '' for v in row.values()):
                continue
            rows.append({k: (v or '').strip() for k, v in row.items()})
        return rows, None
    except Exception as exc:
        return [], f'Could not parse CSV file: {exc}'


class EmployeeBulkImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser]

    def post(self, request):
        role_name = (request.user.role.name if request.user.role else '')
        if role_name not in _EMP_ALLOWED_ROLES:
            return error(
                'Only System Admin and HR Admin can perform bulk employee import.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return error('No file uploaded. Please attach a CSV or XLSX file.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size > _EMP_MAX_IMPORT_BYTES:
            return error('File too large. Maximum allowed size is 5 MB.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        filename = (uploaded_file.name or '').lower()
        if filename.endswith('.xlsx'):
            rows, parse_error = _parse_employee_xlsx_rows(uploaded_file)
        elif filename.endswith('.csv'):
            rows, parse_error = _parse_employee_csv_rows(uploaded_file)
        else:
            return error('Unsupported file format. Please upload a CSV or XLSX file.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        if parse_error:
            return error(parse_error, http_status=status.HTTP_400_BAD_REQUEST)
        if not rows:
            return error('The file contains no data rows.',
                         http_status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > _EMP_MAX_IMPORT_ROWS:
            return error(
                f'File contains {len(rows)} rows. '
                f'Maximum allowed per import is {_EMP_MAX_IMPORT_ROWS}.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-load lookup tables once for the entire batch.
        from apps.branch.models import Branch as _Branch
        from apps.accounts.models import EmployeeProfile

        # branch: lower_name → exact branch_name stored on User
        branch_map: dict = {}
        for b in _Branch.objects.only('branch_name', 'branch_code'):
            branch_map[b.branch_name.strip().lower()] = b.branch_name.strip()
            if b.branch_code:
                branch_map[b.branch_code.strip().lower()] = b.branch_name.strip()

        # department: lower_name → exact name
        dept_map: dict = {
            d.lower(): d
            for d in Department.objects.filter(is_active=True).values_list('name', flat=True)
        }

        # designation: lower_name → set of lower dept names it belongs to
        desig_dept_map: dict = {}
        for desig_name, dept_name in (
            Designation.objects
            .filter(is_active=True)
            .select_related('department')
            .values_list('name', 'department__name')
        ):
            desig_dept_map.setdefault(desig_name.lower(), set()).add(dept_name.lower())

        # role: lower_name/lower_display → Role obj
        role_map: dict = {}
        for r in Role.objects.filter(is_active=True):
            role_map[r.name.lower()]         = r
            role_map[r.display_name.lower()] = r

        # Pre-load existing emails for DB-level duplicate detection.
        existing_emails: set = set(
            User.objects.values_list('email', flat=True)
        )
        seen_emails: set = set()

        created_ids:  list = []
        created_rows: list = []
        row_errors:   list = []
        skipped_rows: list = []

        for idx, raw_row in enumerate(rows, start=2):
            row_data = _normalize_employee_import_headers(raw_row)
            ser = EmployeeBulkImportRowSerializer(data=row_data)

            if not ser.is_valid():
                for field, msgs in ser.errors.items():
                    row_errors.append({
                        'row':     idx,
                        'field':   field,
                        'message': msgs[0] if isinstance(msgs, list) else str(msgs),
                    })
                continue

            vd    = ser.validated_data
            email = vd['email']

            # Duplicates are skipped silently — not treated as failures.
            if email in existing_emails or email in seen_emails:
                skipped_rows.append({
                    'row':        idx,
                    'identifier': email,
                    'reason':     'Already exists',
                })
                continue

            # Branch existence check.
            branch_raw  = vd['branch']
            branch_name = branch_map.get(branch_raw.lower())
            if branch_name is None:
                row_errors.append({
                    'row':        idx,
                    'field':      'branch',
                    'identifier': email,
                    'message':    f'Branch "{branch_raw}" not found.',
                })
                continue

            # Department existence check.
            dept_raw  = vd['department']
            dept_name = dept_map.get(dept_raw.lower())
            if dept_name is None:
                row_errors.append({
                    'row':        idx,
                    'field':      'department',
                    'identifier': email,
                    'message':    f'Department "{dept_raw}" not found.',
                })
                continue

            # Designation existence + belongs-to-department check.
            desig_raw = vd['designation']
            dept_set  = desig_dept_map.get(desig_raw.lower(), set())
            if not dept_set:
                row_errors.append({
                    'row':        idx,
                    'field':      'designation',
                    'identifier': email,
                    'message':    f'Designation "{desig_raw}" not found.',
                })
                continue
            if dept_name.lower() not in dept_set:
                row_errors.append({
                    'row':        idx,
                    'field':      'designation',
                    'identifier': email,
                    'message':    (
                        f'Designation "{desig_raw}" does not belong to '
                        f'department "{dept_name}".'
                    ),
                })
                continue

            # Role existence check.
            role_raw = vd['role']
            role_obj = role_map.get(role_raw.lower())
            if role_obj is None:
                row_errors.append({
                    'row':        idx,
                    'field':      'role',
                    'identifier': email,
                    'message':    f'Role "{role_raw}" not found.',
                })
                continue
            if role_obj.name == 'system_admin':
                row_errors.append({
                    'row':        idx,
                    'field':      'role',
                    'identifier': email,
                    'message':    'system_admin cannot be assigned via bulk import.',
                })
                continue

            # Create the employee.
            try:
                temp_password = ''.join(
                    secrets.choice(string.ascii_letters + string.digits)
                    for _ in range(12)
                )
                employee_id = EmployeeCodeSettings.generate_employee_id()
                full_name   = f'{vd["first_name"]} {vd["last_name"]}'

                user = User.objects.create_user(
                    email                = email,
                    password             = temp_password,
                    full_name            = full_name,
                    role                 = role_obj,
                    employee_id          = employee_id,
                    department           = dept_name,
                    designation          = desig_raw,
                    branch               = branch_name,
                    phone                = vd.get('phone') or '',
                    date_of_joining      = vd.get('date_of_joining'),
                    must_change_password = True,
                    onboarding_status    = User.ONBOARDING_PENDING,
                )

                auto_fields = _auto_assign_managers(user)
                if auto_fields:
                    user.save(update_fields=[*auto_fields, 'updated_at'])

                # Create EmployeeProfile if optional personal fields are present.
                gender  = vd.get('gender') or ''
                dob     = vd.get('date_of_birth')
                blood   = vd.get('blood_group') or ''
                address = vd.get('address') or ''
                if any([gender, dob, blood, address]):
                    EmployeeProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'gender':          gender,
                            'date_of_birth':   dob,
                            'blood_group':     blood,
                            'current_address': address,
                        },
                    )

                seen_emails.add(email)
                created_ids.append(employee_id)
                created_rows.append({'row': idx, 'identifier': email,
                                     'employee_id': employee_id})
                logger.info('Bulk import: employee %s (%s) created', employee_id, email)

            except Exception as exc:
                logger.error('Bulk import row %d failed (%s): %s', idx, email, exc)
                row_errors.append({
                    'row':        idx,
                    'field':      'general',
                    'identifier': email,
                    'message':    'Failed to create employee. Please verify the row data.',
                })

        total_rows    = len(rows)
        created_count = len(created_ids)
        skipped_count = len(skipped_rows)
        fail_count    = len(row_errors)

        AuditLog.objects.create(
            user       = request.user,
            action     = 'bulk_employee_import',
            module     = 'accounts',
            changes    = {
                'total_rows': total_rows,
                'created':    created_count,
                'skipped':    skipped_count,
                'failed':     fail_count,
            },
            ip_address = get_client_ip(request),
        )

        logger.info(
            'Bulk employee import by %s: %d created, %d skipped, %d failed (total %d)',
            request.user.email, created_count, skipped_count, fail_count, total_rows,
        )

        return success(
            'Bulk import completed.',
            data={
                'total_rows':           total_rows,
                'created':              created_count,
                'skipped':              skipped_count,
                'failed':               fail_count,
                'created_employee_ids': created_ids,
                'created_rows':         created_rows,
                'skipped_rows':         skipped_rows,
                'errors':               row_errors,
            },
        )
