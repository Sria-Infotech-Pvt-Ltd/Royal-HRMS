
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
from django.db.models import Count, F, Max, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
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
    Department,
    Designation,
    Document,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeApprovalOverride,
    EmployeeCodeSettings,
    OnboardingFieldConfig,
    OTPVerification,
    PasswordResetToken,
    Permission,
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
    PermissionSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    SMTPSettingsSerializer,
    SMTPTestSerializer,
    VerifyOTPSerializer,
)
from apps.accounts.throttles import ForgotPasswordRateThrottle, LoginRateThrottle, OTPVerifyRateThrottle
from apps.accounts.tokens import FreshClaimsTokenRefreshSerializer, RoleBasedRefreshToken
from apps.accounts.utils import send_otp_email, send_template_email, send_test_email

logger = logging.getLogger(__name__)



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

    changed = []

    # HR assignment: try Branch.hr first, then first active hr user in same branch.
    if employee.hr_id is None and emp_branch:
        branch_obj = Branch.objects.select_related('hr').filter(
            branch_name__iexact=emp_branch
        ).first()
        hr_user = branch_obj.hr if branch_obj else None
        if not hr_user:
            hr_user = User.objects.filter(
                role__role_permissions__permission__codename='employees.edit',
                branch__iexact=emp_branch, is_active=True,
            ).first()
        if hr_user and hr_user.pk != employee.pk:
            employee.hr = hr_user
            changed.append('hr')

    # Managers are the reporting manager for others — they have none themselves.
    if employee.role and employee.role.can_manage_team:
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
            .filter(role__can_manage_team=True, branch__iexact=emp_branch, is_active=True)
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
    return _cu.private_download_url(name, fmt, resource_type='raw', type='authenticated', attachment=False)


def _document_dict(doc) -> dict:
    """Shared shape for a single EmployeeDocument, used by _employee_dict() and
    EmployeeProfileDocumentView so the profile page and the upload response always
    match the ApiDocument shape the frontend expects."""
    try:
        file_url = _cloudinary_signed_url(doc.file) if doc.file else ''
    except Exception:
        logger.warning('Cloudinary signed URL failed for employee document %s', doc.id, exc_info=True)
        file_url = ''
    from core.cache_service import DocumentTypeConfigCacheService
    return {
        'id':                    doc.id,
        'document_type':         doc.document_type,
        'document_type_display': DocumentTypeConfigCacheService.label_for(doc.document_type),
        'file':                  file_url,
        'file_name':             doc.file_name,
        'file_size':             doc.file_size,
        'uploaded_at':           doc.uploaded_at.isoformat() if doc.uploaded_at else '',
    }


def _custom_field_file_dict(v) -> dict:
    """Shared shape for a single CustomFieldFileValue — mirrors _document_dict()
    keyed by field_key instead of document_type, used by _employee_dict() so
    the HR Employee Detail page gets every step's file-type custom values in
    the one existing GET, same as `documents` today."""
    try:
        file_url = _cloudinary_signed_url(v.file) if v.file else ''
    except Exception:
        logger.warning('Cloudinary signed URL failed for custom field file %s', v.id, exc_info=True)
        file_url = ''
    return {
        'id':          v.id,
        'field_key':   v.field_key,
        'file':        file_url,
        'file_name':   v.file_name,
        'file_size':   v.file_size,
        'uploaded_at': v.uploaded_at.isoformat() if v.uploaded_at else '',
    }


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
        # HR-created custom fields (Settings > Onboarding Fields) — see
        # OnboardingFieldConfig/EmployeeProfile.custom_field_values.
        'custom_field_values': (p.custom_field_values or {}) if p else {},
    }

    try:
        documents = [_document_dict(doc) for doc in user.employee_documents.all()]
    except Exception:
        documents = []
    try:
        custom_file_fields = [_custom_field_file_dict(v) for v in user.custom_field_files.all()]
    except Exception:
        custom_file_fields = []
    mgr = getattr(user, 'reporting_manager', None)
    _hr = getattr(user, 'hr', None)
    approver = getattr(user, 'reporting_approver', None)

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
            'uuid': str(_hr.id)     if _hr else None,
            'name': _hr.full_name   if _hr else None,
        },
        'reporting_approver': {
            'id':   approver.employee_id if approver else None,
            'uuid': str(approver.id)     if approver else None,
            'name': approver.full_name   if approver else None,
        },
        'profile':            profile_data,
        'documents':          documents,
        'custom_file_fields': custom_file_fields,
        'onboarding_status':  user.onboarding_status,
    }

    # Managers ARE the reporting manager for others — they have no reporting manager themselves.
    if not (user.role and user.role.can_manage_team):
        result['reporting_manager'] = {
            'id':   mgr.employee_id if mgr else None,
            'uuid': str(mgr.id)     if mgr else None,
            'name': mgr.full_name   if mgr else None,
        }

    return result


# ─── Custom permissions ────────────────────────────────────────────────────────

class CanManageRoles(BasePermission):
    """Only users holding settings.edit may manage roles, permissions, and settings."""
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, _) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and _has_perm(request.user, 'settings.edit')
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

class PublicCompanyBrandingView(APIView):
    """
    Unauthenticated — lets the login page show a company's own logo, name,
    and accent color before the user has entered a password (see
    frontend app/login/page.tsx). Deliberately returns only branding
    fields, nothing sensitive. Company-code existence is not treated as
    secret here — the login form already requires the caller to know it
    before authenticating at all, and LoginView's own error message is
    already generic to avoid confirming a code via failed-login timing;
    this is the same class of disclosure as a "workspace lookup" page on
    any other multi-tenant product with branded per-tenant logins.
    """
    permission_classes     = [AllowAny]
    authentication_classes = []

    def get(self, request, company_code):
        from apps.tenants.models import Client

        try:
            client = Client.objects.get(company_code__iexact=company_code, is_active=True)
        except Client.DoesNotExist:
            return error('Company not found.', http_status=status.HTTP_404_NOT_FOUND)

        with client:
            company = Company.objects.first()
            logo_url = None
            if company and company.logo:
                logo_url = request.build_absolute_uri(company.logo.url)
            return success('OK', data={
                'company_name': (company.company_name if company else '') or client.company_name,
                'logo_url':     logo_url,
                'brand_color':  (company.brand_color if company else '') or '',
            })


class LoginView(APIView):
    permission_classes      = [AllowAny]
    authentication_classes  = []
    throttle_classes        = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        company_code = serializer.validated_data['company_code']
        email        = serializer.validated_data['email']
        password     = serializer.validated_data['password']

        from apps.tenants.models import Client
        try:
            client = Client.objects.get(company_code__iexact=company_code, is_active=True)
        except Client.DoesNotExist:
            return error('Invalid company code, email, or password.', http_status=status.HTTP_401_UNAUTHORIZED)

        # Everything from here on must run against THIS company's schema —
        # activated for the rest of this view (user lookup, password check,
        # audit log, token generation), reset automatically on the way out.
        with client:
            return self._authenticate(request, client, email, password)

    def _authenticate(self, request, client, email, password):
        try:
            user = (
                User.objects
                    .select_related('role')
                    .prefetch_related('role__role_permissions__permission')
                    .get(email__iexact=email)
            )
        except User.DoesNotExist:
            return error('Invalid company code, email, or password.', http_status=status.HTTP_401_UNAUTHORIZED)

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
            return error('Invalid company code, email, or password.', http_status=status.HTTP_401_UNAUTHORIZED)

        ip = get_client_ip(request)
        user.reset_failed_login(ip_address=ip)

        refresh = RoleBasedRefreshToken.for_user(user)
        # Carried through to every access token derived from this refresh
        # token (SimpleJWT copies custom claims on refresh) — this is what
        # apps.tenants.middleware.TenantSchemaMiddleware reads to scope every
        # later request to this company's schema.
        refresh['company_schema'] = client.schema_name
        refresh['company_code']   = client.company_code

        AuditLog.objects.create(
            user=user, action='login', module='accounts', ip_address=ip,
        )
        logger.info('User %s logged in from %s', email, ip)

        permissions = (
            [rp.permission.codename for rp in user.role.role_permissions.all()]
            if user.role else []
        )

        # This company's own logo/accent color, for the dashboard shell —
        # same Company row PublicCompanyBrandingView reads pre-login.
        company = Company.objects.first()
        company_logo_url = (
            request.build_absolute_uri(company.logo.url)
            if company and company.logo else None
        )
        company_brand_color = (company.brand_color if company else '') or ''

        resp = success('Login successful.', data={
            'user': {
                'id':                  str(user.id),
                'company_code':        client.company_code,
                'company_name':        client.company_name,
                'company_logo_url':    company_logo_url,
                'company_brand_color': company_brand_color,
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

        company_code = serializer.validated_data['company_code']
        email        = serializer.validated_data['email']

        from apps.tenants.models import Client
        try:
            client = Client.objects.get(company_code__iexact=company_code, is_active=True)
        except Client.DoesNotExist:
            return error('Invalid company code.', http_status=status.HTTP_404_NOT_FOUND)

        # Everything from here on must run against THIS company's schema —
        # User/OTPVerification both live per-tenant, same reasoning as
        # LoginView.
        with client:
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

        company_code = serializer.validated_data['company_code']
        email        = serializer.validated_data['email']
        otp_input    = serializer.validated_data['otp']

        from apps.tenants.models import Client
        try:
            client = Client.objects.get(company_code__iexact=company_code, is_active=True)
        except Client.DoesNotExist:
            return error('Invalid company code.', http_status=status.HTTP_404_NOT_FOUND)

        # User/OTPVerification/PasswordResetToken all live per-tenant.
        with client:
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

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        company_code    = serializer.validated_data['company_code']
        reset_token_id  = serializer.validated_data['reset_token']
        new_password    = serializer.validated_data['new_password']

        from apps.tenants.models import Client
        try:
            client = Client.objects.get(company_code__iexact=company_code, is_active=True)
        except Client.DoesNotExist:
            return error('Invalid company code.', http_status=status.HTTP_404_NOT_FOUND)

        # PasswordResetToken/User both live per-tenant.
        with client:
            return self._reset(request, reset_token_id, new_password)

    def _reset(self, request, reset_token_id, new_password):
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

    @staticmethod
    def _check_conflict(role: Role, expected_updated_at: str | None):
        """
        Optimistic-concurrency guard for permission edits.

        Permission saves do a full delete-then-recreate of the role's
        permission set (see RoleSerializer._sync_permissions) — with no
        version check, a second save based on stale data silently wins and
        reverts an earlier save (e.g. two admins/tabs editing the same role
        around the same time). When the client sends back the updated_at it
        loaded the role at, reject the write if the role has changed since.
        Optional — a request without expected_updated_at skips the check
        (used by the is_active-only PATCH, which never touches permissions).
        """
        if not expected_updated_at:
            return None
        from django.utils.dateparse import parse_datetime
        expected_dt = parse_datetime(expected_updated_at)
        if expected_dt and expected_dt != role.updated_at:
            return error(
                'This role was changed by someone else since you loaded it. '
                'Reload the page and try again.',
                http_status=status.HTTP_409_CONFLICT,
            )
        return None

    def put(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        conflict = self._check_conflict(role, request.data.get('expected_updated_at'))
        if conflict:
            return conflict

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

        # A real flag, not a hardcoded name set — role names can be (and have
        # been) renamed from Settings, which would silently defeat a
        # name-based check. is_system_role is set once, at provisioning, and
        # survives any later rename.
        if role.is_system_role:
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
    # GET is open to any authenticated user — same reasoning as
    # RoleListCreateView.get() above: viewing the permission catalog is what
    # lets the Roles & Permissions page render at all (it fetches roles and
    # permissions together), and read-only visibility into what a role *can*
    # be granted isn't itself a privilege. POST (creating a new permission
    # codename) still requires CanManageRoles, checked explicitly below.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Permission.objects.all().order_by('module', 'action')
        page_obj, paginator = paginate(qs, request, default_page_size=100)
        serialized = PermissionSerializer(page_obj.object_list, many=True).data
        grouped: dict[str, list] = defaultdict(list)
        for perm in serialized:
            grouped[perm['module']].append(perm)
        return success('Permissions retrieved successfully.', data=paginated_data(paginator, page_obj, dict(grouped)))

    def post(self, request):
        if not CanManageRoles().has_permission(request, self):
            return error('You do not have permission to create permissions.', http_status=status.HTTP_403_FORBIDDEN)
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

        # Department has no branch FK of its own — it's a company-wide master
        # list — so "departments at this branch" is derived from which
        # departments actually have an active employee there.
        branch = (request.query_params.get('branch') or '').strip()
        if branch:
            dept_names_in_branch = (
                User.objects
                .filter(is_active=True, branch__iexact=branch)
                .exclude(department='')
                .values_list('department', flat=True)
                .distinct()
            )
            qs = qs.filter(name__in=list(dept_names_in_branch))

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


def _build_org_chart_group(users_qs, branch_label: str) -> dict:
    """
    Build one branch's {root, departments} tree from an already branch-
    filtered (or unfiltered, for the "no branch set" bucket) active-user
    queryset.

    Department head is derived per branch group, not from the single
    company-wide Department.manager field — a real multi-branch company has
    a different Engineering Manager per branch, which one global FK can't
    represent. Head = the sole can_manage_team-role person in this
    department within this branch; ambiguous (0 or 2+ such people) falls
    back to Department.manager only if that person actually belongs to this
    branch, and otherwise leaves head unset rather than guessing.
    """
    roots = list(users_qs.filter(reporting_manager__isnull=True).order_by('full_name')[:2])
    root = None
    if len(roots) == 1:
        root = {
            'id': str(roots[0].id), 'employee_id': roots[0].employee_id,
            'name': roots[0].full_name, 'designation': roots[0].designation,
        }

    members_by_dept: dict = defaultdict(list)
    managers_by_dept: dict = defaultdict(list)
    for u in (
        users_qs.exclude(department='')
        .select_related('role')
        .only('id', 'employee_id', 'full_name', 'designation', 'department', 'role__can_manage_team')
        .order_by('full_name')
    ):
        entry = {'id': str(u.id), 'employee_id': u.employee_id, 'name': u.full_name, 'designation': u.designation}
        members_by_dept[u.department].append(entry)
        if u.role and u.role.can_manage_team:
            managers_by_dept[u.department].append(entry)

    depts = (
        Department.objects
        .filter(is_active=True, name__in=list(members_by_dept.keys()))
        .select_related('manager')
    )
    departments = []
    for dept in depts:
        members = members_by_dept.get(dept.name, [])
        managers = managers_by_dept.get(dept.name, [])
        head = managers[0] if len(managers) == 1 else None
        if head is None and dept.manager_id and dept.manager and (dept.manager.branch or '').strip().lower() == (branch_label or '').strip().lower():
            head = {
                'id': str(dept.manager_id), 'employee_id': dept.manager.employee_id,
                'name': dept.manager.full_name, 'designation': dept.manager.designation,
            }
        if head is not None:
            members = [m for m in members if m['id'] != head['id']]
        departments.append({'id': dept.pk, 'label': dept.name, 'head': head, 'members': members})

    return {'branch': branch_label, 'root': root, 'departments': departments}


class OrgChartView(APIView):
    """
    GET /org-chart/ — read-only company structure for the Organisation Chart
    page. Built entirely from existing data (Department.manager,
    User.reporting_manager, User.department, Role.can_manage_team) — no
    dedicated org-chart model.

    Gated on org_chart.view, not employees.view — an org chart is
    company-directory information (industry-standard: visible to every
    employee), not employee-management data, so it's deliberately a
    separate, broader permission (seeded on every role, see migration 0086)
    rather than reusing the admin-tier "can browse/manage the employee list"
    gate.

    Response is always a list of per-branch {branch, root, departments}
    groups, never a single flat structure — a real multi-branch company has
    a different manager (and often the same department name) per branch, so
    merging them into one tree would misrepresent who actually manages whom.

    - settings.edit (system_admin-tier): unrestricted. ?branch=<name> scopes
      to one branch's group; omitted or "all" returns one group per branch
      (only branches that actually have people), for the "All Branches"
      dropdown option — plus an "Unassigned" group for anyone with no
      branch set at all, so a data gap doesn't just silently vanish them.
    - Everyone else (HR included — deliberately widened past its normal
      "only my assigned employees" rule; see _can_manage_employee_documents
      above, a structural chart needs the full shape of what a role
      oversees, not a personal caseload): always exactly one group, their
      own branch. Any ?branch= they send is ignored — branch access is a
      permission decision, never a client-supplied one.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.branch.models import Branch

        user = request.user
        if not _has_perm(user, 'org_chart.view'):
            return error('You do not have permission to view the org chart.',
                         http_status=status.HTTP_403_FORBIDDEN)

        if not _has_perm(user, 'settings.edit'):
            own_branch = (getattr(user, 'branch', '') or '').strip()
            users_qs = User.objects.filter(is_active=True)
            if own_branch:
                users_qs = users_qs.filter(branch__iexact=own_branch)
            group = _build_org_chart_group(users_qs, own_branch)
            return success('Org chart retrieved.', data={'scope': 'branch', 'groups': [group]})

        # The branch list itself is NOT returned here — the frontend's branch
        # dropdown reads it from the existing BranchListCreateView (/branches/),
        # the one place that already lists branches company-wide. This query
        # is only for building the groups below, not for exposing a second,
        # duplicate "what branches exist" source in this endpoint's response.
        all_branches = list(
            Branch.objects.filter(status=Branch.STATUS_ACTIVE).order_by('branch_name').values_list('branch_name', flat=True)
        )
        requested = (request.query_params.get('branch') or '').strip()

        if requested and requested.lower() != 'all':
            matched = next((b for b in all_branches if b.lower() == requested.lower()), requested)
            group = _build_org_chart_group(User.objects.filter(is_active=True, branch__iexact=matched), matched)
            return success('Org chart retrieved.', data={'scope': 'company', 'groups': [group]})

        groups = []
        for b in all_branches:
            group = _build_org_chart_group(User.objects.filter(is_active=True, branch__iexact=b), b)
            if group['departments']:
                groups.append(group)
        unassigned = _build_org_chart_group(
            User.objects.filter(is_active=True).filter(Q(branch='') | Q(branch__isnull=True)), 'Unassigned',
        )
        if unassigned['departments']:
            groups.append(unassigned)

        return success('Org chart retrieved.', data={'scope': 'company', 'groups': groups})


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


# ─── Template variable resolution (single source of truth for auto-fill) ─────
#
# Every "approve/reject/decide + send email" modal in the frontend used to
# hand-build its own small, inconsistently-cased list of "variables I can
# auto-fill" — anything outside that list showed as an empty box the human
# had to type in by hand, even when the real value was already known
# server-side. This endpoint is the fix: given an entity, it returns every
# variable this codebase knows how to resolve for it, under BOTH the
# lowercase snake_case names newer templates use AND the legacy UPPER_CASE
# names older ones use — so any template, existing or future, that
# references a variable matching a real field on the entity gets it for
# free. Only genuinely custom, non-derivable variables should ever need
# manual entry after this.


class ResolveTemplateVariablesView(APIView):
    """
    POST /api/settings/email-templates/resolve-context/
    Body: { "entity_type": "candidate" | "leave_request" | "expense", "entity_id": "..." }

    Returns every known variable this codebase can resolve for the entity —
    used by the approve/reject/decide send-email modals to auto-fill
    template variables instead of leaving them as manual empty boxes.
    """
    permission_classes = [IsAuthenticated]
    _DENIED = 'You do not have permission to perform this action.'

    def post(self, request):
        entity_type = request.data.get('entity_type', '')
        entity_id   = request.data.get('entity_id', '')
        if not entity_type or not entity_id:
            return error('entity_type and entity_id are required.')

        if entity_type == 'candidate':
            if not (_has_perm(request.user, 'recruitment.approve') or _has_perm(request.user, 'recruitment.edit')):
                return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)
            from apps.recruitment.models import Candidate
            try:
                candidate = Candidate.objects.select_related('branch').get(pk=entity_id)
            except (Candidate.DoesNotExist, ValueError, ValidationError):
                return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
            context = _candidate_template_context(candidate, actor=request.user)

        elif entity_type == 'leave_request':
            if not _has_perm(request.user, 'leave.approve'):
                return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)
            from apps.hrms.models import LeaveRequest, REQ_PENDING
            from apps.hrms.views.leave import _can_approve_at_stage
            try:
                leave_request = LeaveRequest.objects.select_related('employee').get(pk=entity_id)
            except (LeaveRequest.DoesNotExist, ValueError, ValidationError):
                return error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)
            # Holding leave.approve isn't enough on its own — same as the real
            # approve/reject endpoint, only the request's designated approver
            # at its current stage (or system_admin) may see its details.
            stage = 'l1' if leave_request.status == REQ_PENDING else 'l2'
            if not _can_approve_at_stage(request.user, leave_request, stage):
                return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)
            context = _leave_request_template_context(leave_request)

        elif entity_type == 'expense':
            if not _has_perm(request.user, 'expenses.approve'):
                return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)
            from apps.hrms.models import Expense
            from apps.hrms.views.expenses import _can_access_expense
            lookup = {'expense_number': entity_id} if str(entity_id).isdigit() else {'pk': entity_id}
            try:
                expense = Expense.objects.select_related('employee').get(**lookup)
            except (Expense.DoesNotExist, ValueError, ValidationError):
                return error('Expense not found.', http_status=status.HTTP_404_NOT_FOUND)
            # Same per-record scoping the real approve/reject endpoint uses —
            # holding expenses.approve alone would let any approver pull any
            # other manager's team's expense details.
            if not _can_access_expense(request.user, expense):
                return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)
            context = _expense_template_context(expense)

        else:
            return error(f'Unknown entity_type "{entity_type}".')

        return success('Template variables resolved.', data={'context': {**_universal_template_context(), **context}})


# ─── Document Center ───────────────────────────────────────────────────────────


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
        if not _has_perm(request.user, 'documents.create'):
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
                branch=doc.branch.branch_name if doc.branch else '',
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
            # pk arrives as a str (URL uses <str:pk>) but the signed payload's
            # 'id' is a JSON-decoded int — compare as strings so a valid token
            # for this document is never rejected as a mismatch.
            if str(data.get('id')) != str(pk):
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
                type='authenticated',
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
        if not _has_perm(request.user, 'documents.edit'):
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
                branch=updated.branch.branch_name if updated.branch else '',
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
        if not _has_perm(request.user, 'documents.edit'):
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
                branch=updated.branch.branch_name if updated.branch else '',
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
        if not _has_perm(request.user, 'documents.delete'):
            return error('You do not have permission to delete documents.', http_status=status.HTTP_403_FORBIDDEN)
        doc = self._get_doc(pk)
        if not doc:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        title = doc.title
        doc_branch = doc.branch.branch_name if doc.branch else ''
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
                branch=doc_branch,
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
        from core.cache_service import CompanyCacheService
        company = CompanyCacheService.get()
        if not company:
            return success('No company info found.', data={})
        serializer = CompanySerializer(company, context={'request': request})
        return success('Company info retrieved.', data=serializer.data)

    def put(self, request):
        if not _has_perm(request.user, 'settings.edit'):
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


# ─── Company Financial Year ───────────────────────────────────────────────────

class CompanyFinancialYearView(APIView):
    """
    GET  /api/settings/company/financial-year/
        Any authenticated user. Returns the configured start month plus
        dynamically computed previous, current, and next FY labels.

    PUT  /api/settings/company/financial-year/
        system_admin only. Accepts { "financial_year_start_month": "April" }.
        Persists the change, busts the FY cache, and writes an audit log.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.utils import get_company_financial_year_config
        data = get_company_financial_year_config()
        return success('Financial year configuration retrieved.', data)

    def put(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error(
                'Only system administrators can update the financial year configuration.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        new_month = str(request.data.get('financial_year_start_month', '')).strip()
        valid_months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December',
        ]
        if new_month not in valid_months:
            return error(
                f'Invalid month "{new_month}". Must be one of: {", ".join(valid_months)}.'
            )

        company = Company.objects.first()
        if not company:
            return error('Company record not found. Set up company info first.', http_status=404)

        old_month = company.financial_year_start_month

        if old_month != new_month:
            with transaction.atomic():
                company.financial_year_start_month = new_month
                company.updated_by = request.user
                company.save(update_fields=['financial_year_start_month', 'updated_by', 'updated_at'])

            AuditLog.objects.create(
                user=request.user,
                action='update',
                module='company_financial_year',
                object_id=str(company.pk),
                ip_address=get_client_ip(request),
                changes={
                    'financial_year_start_month': {'old': old_month, 'new': new_month},
                },
            )
            logger.info(
                'Financial year start month changed from %s to %s by %s',
                old_month, new_month, request.user.email,
            )

        from apps.accounts.utils import get_financial_years
        from core.cache_service import FinancialYearCacheService
        from datetime import date as _date
        today = _date.today()
        data = {
            'financial_year_start_month': new_month,
            **get_financial_years(today, new_month),
        }
        FinancialYearCacheService.set(data)

        return success('Financial year configuration updated.', data)


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
            .prefetch_related('custom_field_files')
            .filter(is_active__in=[True, False])
            .exclude(employee_id='')   # portal candidates have no employee_id until onboarding is approved
            .order_by('-date_joined')
        )

        # Managers (role.can_manage_team) only see their own direct reports — not
        # every employee in the branch — matching the scoping already applied to
        # Attendance, Expenses, and the Leave approval queues for the same role.
        # Everyone else without settings.edit is scoped to their own branch, and
        # cannot be overridden by query params.
        #
        # Exception: picking a KT handover assignee for the viewer's OWN
        # separation request. A manager/HR can't assign their own handover to
        # their own report (see SeparationHandoverTaskListCreateView.post), so
        # locking this search to "your own team" would leave them with zero
        # valid candidates. own_separation_request must name a request where
        # they ARE the separating employee — can't be used to see someone
        # else's team.
        from apps.hrms.models import SEP_REJECTED, SeparationRequest

        role = request.user.role
        own_sep_request_id = request.query_params.get('own_separation_request', '').strip()
        widen_for_own_separation = bool(own_sep_request_id) and SeparationRequest.objects.filter(
            id=own_sep_request_id, employee=request.user,
        ).exclude(status=SEP_REJECTED).exists()

        if role and role.can_manage_team and not widen_for_own_separation:
            qs = qs.filter(reporting_manager=request.user)
        elif not _has_perm(request.user, 'settings.edit') and request.user.branch:
            qs = qs.filter(branch=request.user.branch)
        if widen_for_own_separation:
            qs = qs.exclude(reporting_manager=request.user)

        search       = request.query_params.get('search', '').strip()
        dept         = request.query_params.get('department', '').strip()
        branch_param = request.query_params.get('branch', '').strip()
        status_param = request.query_params.get('status', '').strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search)     |
                Q(employee_id__icontains=search)
            )
        if dept:
            qs = qs.filter(department=dept)
        if branch_param:
            qs = qs.filter(branch=branch_param)
        if status_param:
            if status_param == 'inactive':
                qs = qs.filter(is_active=False)
            elif status_param == 'active':
                qs = qs.filter(is_active=True, must_change_password=False)
            elif status_param == 'onboarding':
                qs = qs.filter(is_active=True, must_change_password=True)
            else:
                return error('status must be one of: active, onboarding, inactive.')

        # Used to check "does anyone currently report to this person, or have
        # them as HR" before a caller re-roles/re-branches them elsewhere —
        # only the count matters, so callers pass page_size=1.
        if reporting_manager_id := request.query_params.get('reporting_manager_id', '').strip():
            qs = qs.filter(reporting_manager_id=reporting_manager_id, is_active=True)
        if hr_id := request.query_params.get('hr_id', '').strip():
            qs = qs.filter(hr_id=hr_id, is_active=True)

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
        date_of_joining = (request.data.get('date_of_joining') or '').strip()
        phone           = (request.data.get('phone')           or '').strip()
        hr_id                 = (request.data.get('hr_id')                 or '').strip()
        reporting_manager_id  = (request.data.get('reporting_manager_id')  or '').strip()

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
        if branch      and len(branch)      > 100: errs['branch']      = 'Branch must be 100 characters or fewer.'
        if department  and len(department)  > 100: errs['department']  = 'Department must be 100 characters or fewer.'
        if designation and len(designation) > 100: errs['designation'] = 'Designation must be 100 characters or fewer.'

        # Branch must match an active branch in the master Branch list. A free-text
        # value that doesn't match exactly (e.g. "Hyderabad HQ" vs the real
        # "Hyderabad") silently breaks HR/manager auto-assignment below, which
        # matches on this exact string — so it's rejected here instead of saved.
        branch_obj = None
        if branch and 'branch' not in errs:
            from apps.branch.models import Branch
            branch_obj = Branch.objects.filter(
                branch_name__iexact=branch, status=Branch.STATUS_ACTIVE,
            ).first()
            if branch_obj is None:
                errs['branch'] = 'Select a valid, active branch from the list.'

        # Department must match the master Department list for the same reason —
        # an unrecognized free-text value (e.g. "IT" when no such Department
        # exists) would silently fall out of every department-scoped dropdown
        # and report built on this field.
        dept_obj = None
        if department and 'department' not in errs:
            dept_obj = Department.objects.filter(name__iexact=department, is_active=True).first()
            if dept_obj is None:
                errs['department'] = 'Select a valid, active department from the list.'

        # Name format check — letters with single space/hyphen/apostrophe separators only
        if first_name and 'first_name' not in errs and not NAME_RE.match(first_name):
            errs['first_name'] = 'First name may only contain letters, numbers, spaces, hyphens and apostrophes.'
        if last_name  and 'last_name'  not in errs and not NAME_RE.match(last_name):
            errs['last_name']  = 'Last name may only contain letters, numbers, spaces, hyphens and apostrophes.'

        # Phone format check — exactly 10 digits, optional +91/91 prefix
        if phone and 'phone' not in errs and not _is_valid_phone(phone):
            errs['phone'] = 'Enter a valid 10-digit phone number (optionally prefixed with +91).'

        # Date format check
        if date_of_joining and 'date_of_joining' not in errs:
            try:
                datetime.strptime(date_of_joining, '%Y-%m-%d')
            except ValueError:
                errs['date_of_joining'] = 'Date of joining must be in YYYY-MM-DD format.'

        # Email format check
        if email and 'email' not in errs and not EMAIL_RE.match(email):
            errs['email'] = 'Enter a valid email address.'

        if errs:
            return error('Please fix the errors below.', data=errs)

        # Store the canonical Branch.branch_name / Department.name casing, not
        # whatever the client sent — keeps these fields byte-for-byte consistent
        # with lookups elsewhere (HR/manager auto-assignment, geofencing, the
        # department dropdown's branch filter, reports).
        branch     = branch_obj.branch_name
        department = dept_obj.name

        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            field_msg = (
                f'This email is already registered in the {existing_user.branch} branch.'
                if existing_user.branch and existing_user.branch != branch
                else 'Email already registered.'
            )
            return error(
                'An account with this email already exists.',
                data={'email': field_msg},
            )

        try:
            role = Role.objects.get(pk=role_id)
        except (Role.DoesNotExist, ValueError, TypeError):
            return error('Invalid role.', data={'role': 'Role not found.'})

        if role.role_permissions.filter(permission__codename='settings.edit').exists():
            return error(f'"{role.display_name}" cannot be assigned via employee creation.')

        selected_hr = None
        if hr_id:
            try:
                selected_hr = User.objects.get(pk=hr_id, is_active=True)
            except (User.DoesNotExist, ValueError, ValidationError):
                return error('HR user not found or is inactive.', data={'hr_id': 'Invalid HR selected.'})

        selected_manager = None
        if reporting_manager_id:
            if role.can_manage_team:
                return error(
                    'Managers do not have a reporting manager.',
                    data={'reporting_manager_id': 'Not applicable for this role.'},
                )
            try:
                selected_manager = User.objects.get(pk=reporting_manager_id, is_active=True)
            except (User.DoesNotExist, ValueError, ValidationError):
                return error(
                    'Reporting manager not found or is inactive.',
                    data={'reporting_manager_id': 'Invalid manager selected.'},
                )

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
            manual_fields = []
            if selected_hr is not None:
                user.hr = selected_hr
                manual_fields.append('hr')
            if selected_manager is not None:
                user.reporting_manager = selected_manager
                manual_fields.append('reporting_manager')

            # _auto_assign_managers() only fills in fields left unset above, so an
            # explicit hr_id/reporting_manager_id from the form always wins.
            auto_fields = _auto_assign_managers(user)
            # Auto-assign creating HR admin as the employee's branch HR
            if (_has_perm(request.user, 'employees.edit')
                    and user.hr_id is None and user.pk != request.user.pk):
                user.hr = request.user
                auto_fields.append('hr')
            auto_fields = list(dict.fromkeys(manual_fields + auto_fields))
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
                branch=user.branch,
                ip_address=get_client_ip(request),
            )

        try:
            from apps.accounts.utils import (
                _get_smtp_connection, _build_message, _company_email_wrapper,
                _get_company_branding,
            )
            from apps.tenants.utils import get_current_company_code

            company_name, logo_url, website, address = _get_company_branding()
            company_name = company_name or 'Royal HRMS'
            # Captured before `connection` below is reassigned to the SMTP
            # connection object — get_current_company_code() needs the real
            # (Django DB) `connection` name, not this local shadow of it.
            company_code = get_current_company_code()
            company_code_line = (
                f'<strong>Company ID:</strong> {company_code}<br>' if company_code else ''
            )

            body = (
                f'<p>Hi <strong>{full_name}</strong>,</p>'
                f'<p>Your Royal HRMS account has been created.'
                f' Use the credentials below to log in:</p>'
                f'<p>'
                f'{company_code_line}'
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


class EmployeeStatsView(APIView):
    """
    Dashboard counts for the Employees page header cards.

    Computed directly from the full queryset (not a single page) — the
    frontend used to derive these from the currently loaded page of results,
    which under-counted everything once there was more than one page.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        base_qs = User.objects.filter(is_active__in=[True, False]).exclude(employee_id='')

        role = request.user.role
        if role and role.can_manage_team:
            base_qs = base_qs.filter(reporting_manager=request.user)
        elif not _has_perm(request.user, 'settings.edit') and request.user.branch:
            base_qs = base_qs.filter(branch=request.user.branch)

        # branch_names/department_names always come from base_qs (ignores the
        # branch filter below) so the branch dropdown never shrinks to just
        # the currently-selected branch once one is picked.
        branch_names = list(
            base_qs.exclude(branch='').values_list('branch', flat=True).distinct().order_by('branch')
        )
        department_names = list(
            base_qs.exclude(department='').values_list('department', flat=True).distinct().order_by('department')
        )

        qs = base_qs
        branch_filter = request.query_params.get('branch', '').strip()
        if branch_filter and branch_filter != 'all':
            qs = qs.filter(branch=branch_filter)

        return success('Employee statistics retrieved.', data={
            'total':             qs.count(),
            'active':            qs.filter(is_active=True, must_change_password=False).count(),
            'onboarding':        qs.filter(is_active=True, must_change_password=True).count(),
            'departments':       qs.exclude(department='').values('department').distinct().count(),
            'branch_names':      branch_names,
            'department_names':  department_names,
        })


def _get_employee(identifier: str):
    """Look up an employee by employee_id code (e.g. EMP001)."""
    try:
        return (
            User.objects
            .select_related('role', 'profile', 'reporting_manager', 'hr')
            .prefetch_related('employee_documents')
            .prefetch_related('custom_field_files')
            .get(employee_id=identifier)
        )
    except User.DoesNotExist:
        return None


def _employee_out_of_branch_scope(requesting_user, employee) -> bool:
    """
    Mirrors the scoping already applied to EmployeeListCreateView.get():
    managers (role.can_manage_team) may only act on their own direct reports,
    and everyone else without settings.edit is scoped to their own branch.
    Returns True when the employee should be treated as not found for this
    requester.

    A submitted-but-not-yet-approved onboarding candidate has no
    employee.branch yet (it's only copied over from the linked Candidate at
    approval time) — fall back to the source candidate's branch so HR can
    still see/act on their own branch's pending submissions.
    """
    role = requesting_user.role
    if role and role.can_manage_team:
        return employee.reporting_manager_id != requesting_user.id
    if not _has_perm(requesting_user, 'settings.edit') and requesting_user.branch:
        employee_branch = employee.branch
        if not employee_branch:
            candidate = employee.candidate_portal.first()
            if candidate and candidate.branch:
                employee_branch = candidate.branch.branch_name
        return employee_branch != requesting_user.branch
    return False


def _resolve_designation(name: str, department_name: str):
    """Best-effort lookup of a Designation row by name — Designation.name is
    only unique per-department, so prefer a match in the given department
    and fall back to any active match by name (mirrors the department-blind
    string comparison User.designation already uses elsewhere in this view).
    Returns None if the name doesn't resolve to any active Designation row
    at all (e.g. legacy free-text data predating the Designation table)."""
    if not name:
        return None
    return (
        Designation.objects.filter(name=name, department__name=department_name, is_active=True).first()
        or Designation.objects.filter(name=name, is_active=True).first()
    )


def _check_promotion_hierarchy(employee, old_designation: str, new_designation: str):
    """
    Reject a designation change that isn't a genuine promotion, using
    Designation.level (higher = more senior). Returns an error Response, or
    None if the change is allowed.

    level=0 means "not yet configured" for that designation — the check is
    skipped (not enforced) unless BOTH the old and new designation have a
    real level assigned, so this validation can't brick every promotion the
    moment the field is added, before anyone has had a chance to assign
    real levels.

    Levels are only comparable WITHIN the same department's hierarchy — a
    level-3 Engineering designation is never treated as outranking a
    level-1 Finance designation just because 3 > 1. A designation change
    that crosses departments has no comparable ladder in this data model,
    so the level check is skipped (not enforced) for it, same as the
    level=0 "unconfigured" case above.
    """
    new_desig = _resolve_designation(new_designation, employee.department)
    old_desig = _resolve_designation(old_designation, employee.department)
    if not new_desig or not old_desig or new_desig.level == 0 or old_desig.level == 0:
        return None
    if new_desig.department_id != old_desig.department_id:
        return None
    if new_desig.level == old_desig.level:
        return error(
            f'"{new_designation}" is the same level as the employee\'s current designation '
            f'"{old_designation}". Select a higher designation to promote this employee.',
        )
    if new_desig.level < old_desig.level:
        return error(
            f'"{new_designation}" is a lower designation than the employee\'s current designation '
            f'"{old_designation}". Promotions must move to a higher designation.',
        )
    return None


# Personal/Education/Bank/Emergency EmployeeProfile fields editable via
# EmployeeDetailView.put() — see _employee_dict()'s profile_data above for
# the matching read-side list (date_of_birth/current_address excluded here,
# see the comment at the call site).
_PROFILE_FIELD_KEYS = frozenset({
    'gender', 'marital_status', 'father_name', 'blood_group', 'permanent_address',
    'highest_qualification', 'institution', 'year_of_passing', 'specialization',
    'total_experience_years', 'previous_employer', 'previous_designation', 'leaving_reason',
    'account_holder_name', 'account_type', 'account_number', 'ifsc_code',
    'bank_name', 'bank_branch_name',
    'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email',
    # uan_number/name_as_per_aadhar/esi_number were already declared on
    # EmployeeProfileSerializer and (for the first two) already rendered as
    # editable fields on this page's EPF/Statutory tab — but missing from
    # this whitelist meant they were silently dropped on every save via the
    # normal Edit flow. Only writable here going forward via
    # OnboardingApprovalView (HR approval time) or bulk import before this.
    'uan_number', 'name_as_per_aadhar', 'esi_number',
    'custom_field_values',
})


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        auto_changed = _auto_assign_managers(employee)
        if auto_changed:
            employee.save(update_fields=auto_changed + ['updated_at'])
        return success('Employee retrieved.', data=_employee_dict(employee))

    def put(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        data          = request.data
        update_fields = ['updated_at']
        changes       = {}
        # full_name/phone/date_of_joining are shown as read-only on the
        # employee detail page once onboarding is complete ("set by system,
        # not editable" — see PROFILE_SECTIONS in the frontend's _data.ts).
        # That was previously a front-end-only convention with no matching
        # check here, so any direct API call could silently overwrite them
        # even after the UI stopped offering a way to. Enforced here now so
        # the lock is real, not just an absent button.
        locked = employee.onboarding_status == User.ONBOARDING_COMPLETE

        role_name = (data.get('role') or '').strip()
        if role_name:
            try:
                new_role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                return error(f'Role "{role_name}" does not exist.')
            if new_role.role_permissions.filter(permission__codename='settings.edit').exists():
                return error(f'"{new_role.display_name}" cannot be assigned via employee edit.')
            old_role = employee.role.name if employee.role else None
            if old_role != new_role.name:
                changes['role'] = {'from': old_role, 'to': new_role.name}
            employee.role = new_role
            update_fields.append('role')

        for field in ('department', 'designation', 'branch'):
            val = (data.get(field) or '').strip()
            if field in data:
                old_val = getattr(employee, field, '')
                if field == 'designation' and val:
                    if not Designation.objects.filter(name=val, is_active=True).exists():
                        return error(f'Designation "{val}" does not exist.')
                    if val != old_val:
                        hierarchy_error = _check_promotion_hierarchy(employee, old_val, val)
                        if hierarchy_error:
                            return hierarchy_error
                if old_val != val:
                    changes[field] = {'from': old_val, 'to': val}
                setattr(employee, field, val)
                update_fields.append(field)

        if 'phone' in data:
            phone = (data.get('phone') or '').strip()
            if locked and phone != employee.phone:
                return error(
                    'Phone number is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
            if employee.phone != phone:
                changes['phone'] = {'from': employee.phone, 'to': phone}
            employee.phone = phone
            update_fields.append('phone')

        full_name = (data.get('full_name') or '').strip()
        if full_name:
            if locked and full_name != employee.full_name:
                return error(
                    'Full name is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
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
            if locked and doj != str(employee.date_of_joining):
                return error(
                    'Date of joining is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
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

        # Personal/Education/Bank/Emergency EmployeeProfile fields — previously
        # displayed on this page's edit form but silently dropped on save (no
        # write path existed for any of them). Reuses EmployeeProfileSerializer
        # (already handles validation, encryption, and the bank-details-changed
        # audit alert via _changed_by) rather than 23 more manual field blocks.
        # date_of_birth/current_address are deliberately excluded — the former
        # already has its own block above, the latter isn't part of this page's
        # editable set today.
        profile_saved = False
        if _PROFILE_FIELD_KEYS & set(data.keys()):
            from apps.accounts.models import EmployeeProfile
            from apps.accounts.serializers import EmployeeProfileSerializer
            profile, _ = EmployeeProfile.objects.get_or_create(user=employee)
            profile_update = {k: v for k, v in data.items() if k in _PROFILE_FIELD_KEYS}
            if 'custom_field_values' in profile_update:
                file_keys = _file_type_custom_field_keys()
                merged = dict(profile.custom_field_values or {})
                merged.update({
                    k: v for k, v in (profile_update['custom_field_values'] or {}).items()
                    if k not in file_keys
                })
                profile_update['custom_field_values'] = merged
            serializer = EmployeeProfileSerializer(profile, data=profile_update, partial=True)
            if not serializer.is_valid():
                return error(first_error(serializer.errors), data=serializer.errors)
            profile._changed_by = request.user
            serializer.save()
            profile_saved = True

        if len(update_fields) == 1 and not profile_saved:
            # Check if hr_id, reporting_manager_id, or reporting_approver_id will be set before bailing
            if 'hr_id' not in data and 'reporting_manager_id' not in data and 'reporting_approver_id' not in data:
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
            if employee.role and employee.role.can_manage_team:
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

        # Manual reporting approver assignment — the designated approver for a
        # Manager/HR employee's own requests (e.g. separation) in place of a
        # reporting_manager, which isn't applicable to those roles.
        if 'reporting_approver_id' in data:
            ra_val = data.get('reporting_approver_id')
            if ra_val:
                try:
                    ra_user = User.objects.get(pk=ra_val, is_active=True)
                except (User.DoesNotExist, Exception):
                    return error('Reporting approver not found or is inactive.')
                if ra_user.pk == employee.pk:
                    return error('An employee cannot be their own reporting approver.')
                employee.reporting_approver = ra_user
            else:
                employee.reporting_approver = None
            if 'reporting_approver' not in update_fields:
                update_fields.append('reporting_approver')

        if len(update_fields) == 1 and not profile_saved:
            return error('No updatable fields provided.')

        # Promotion (Employee > Promotion screen) piggybacks on this same
        # generic PUT — it sends only {designation, role} today, same as any
        # other employee edit, so effective_date/remarks are optional and
        # default sensibly when absent rather than being required.
        effective_date_raw = (data.get('effective_date') or '').strip()
        if effective_date_raw:
            try:
                effective_date = datetime.strptime(effective_date_raw, '%Y-%m-%d').date()
            except ValueError:
                return error('effective_date must be in YYYY-MM-DD format.')
        else:
            effective_date = timezone.now().date()
        remarks = (data.get('remarks') or '').strip()

        promotion_changed = 'designation' in changes or 'role' in changes

        with transaction.atomic():
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
                    branch     = employee.branch,
                    ip_address = get_client_ip(request),
                )

            if promotion_changed:
                desig_change  = changes.get('designation', {})
                role_change   = changes.get('role', {})
                current_role_name = employee.role.name if employee.role else ''
                PromotionRecord.objects.create(
                    employee              = employee,
                    previous_designation  = desig_change.get('from', employee.designation) or '',
                    new_designation       = desig_change.get('to', employee.designation) or '',
                    previous_role         = role_change.get('from', current_role_name) or '',
                    new_role              = role_change.get('to', current_role_name) or '',
                    effective_date        = effective_date,
                    remarks               = remarks,
                    promoted_by           = request.user,
                )

        employee = _get_employee(employee_id)
        return success('Employee updated successfully.', data=_employee_dict(employee))

    def patch(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
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
            if employee.role and employee.role.role_permissions.filter(permission__codename='settings.edit').exists():
                active_admins = User.objects.filter(
                    role__role_permissions__permission__codename='settings.edit',
                    is_active=True,
                ).distinct().count()
                if active_admins <= 1:
                    return error('Cannot deactivate the only active administrator with full org-wide access.')

        old_status = employee.is_active
        if old_status == new_status:
            msg = 'Employee is already active.' if new_status else 'Employee is already inactive.'
            return success(msg, data=_employee_dict(employee))

        employee.is_active = new_status
        employee.save(update_fields=['is_active', 'updated_at'])

        if not new_status:
            # Deactivation is the closest thing this codebase has to
            # "employee separated" today (no dedicated separation/offboarding
            # model exists yet) — purge their stored face biometric data here
            # rather than retaining it indefinitely for someone no longer employed.
            from apps.attendance.services_face_lifecycle import purge_face_data_for_employee
            purge_face_data_for_employee(employee)

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
            branch     = employee.branch,
            ip_address = get_client_ip(request),
        )

        verb = 'activated' if new_status else 'deactivated'
        return success(f'Employee {verb} successfully.', data=_employee_dict(employee))

    def delete(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.delete'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if employee.id == request.user.id:
            return error('You cannot delete your own account.')

        if employee.role and employee.role.role_permissions.filter(permission__codename='settings.edit').exists():
            active_admins = User.objects.filter(
                role__role_permissions__permission__codename='settings.edit',
                is_active=True,
            ).distinct().count()
            if active_admins <= 1:
                return error('Cannot delete the only active administrator with full org-wide access.')

        full_name    = employee.full_name
        emp_id_str   = employee.employee_id
        emp_branch   = employee.branch

        employee.is_active = False
        employee.save(update_fields=['is_active', 'updated_at'])

        # Same reasoning as EmployeeDetailView.patch's deactivation path above.
        from apps.attendance.services_face_lifecycle import purge_face_data_for_employee
        purge_face_data_for_employee(employee)

        AuditLog.objects.create(
            user       = request.user,
            action     = 'employee_deleted',
            module     = 'employees',
            object_id  = str(employee.id),
            changes    = {'employee_id': emp_id_str, 'full_name': full_name},
            branch     = emp_branch,
            ip_address = get_client_ip(request),
        )
        logger.info('Employee "%s" deactivated (deleted) by %s', full_name, request.user.email)
        return success(f'Employee "{full_name}" deleted successfully.')

    def post(self, request, employee_id: str):
        return self.put(request, employee_id)


class EmployeePromotionHistoryView(APIView):
    """GET /employees/<employee_id>/promotions/ — persisted promotion history
    for one employee (Employee > Promotion tab's history table). Read-only;
    PromotionRecord rows are created exclusively by EmployeeDetailView.put()."""

    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        records = PromotionRecord.objects.filter(employee=employee).select_related('promoted_by')
        data = [
            {
                'id':                   str(r.id),
                'previous_designation': r.previous_designation,
                'new_designation':      r.new_designation,
                'previous_role':        r.previous_role,
                'new_role':             r.new_role,
                'role_changed':         r.previous_role != r.new_role,
                'effective_date':       str(r.effective_date),
                'remarks':              r.remarks,
                'promoted_by':          r.promoted_by.full_name if r.promoted_by_id else '—',
                'created_at':           r.created_at.isoformat(),
            }
            for r in records
        ]
        return success('Promotion history retrieved.', data=data)


class AuditLogListView(APIView):
    # audit.view, not settings.edit — this was requiring CanManageRoles
    # (settings.edit), but audit logs are read-only for every viewer (no
    # create/edit/delete path exists here or anywhere else — that's the
    # point of an audit trail), and the frontend's own nav config
    # (navConfig.ts) already assumes audit.view is what gates this page.
    # settings.edit holders (system_admin) still see everything via the
    # scope filter below regardless.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'audit.view'):
            return error('You do not have permission to view audit logs.', http_status=status.HTTP_403_FORBIDDEN)
        qs = AuditLog.objects.select_related('user', 'user__role').order_by('-created_at')

        # HR/Branch Admin (no settings.edit) only sees events regarding their
        # own branch — filtered on the event's target branch (AuditLog.branch),
        # not the acting user's own branch. Those differ whenever someone
        # outside the branch acts on it (e.g. a system_admin editing a
        # branch's employee) — filtering on the actor's branch would hide
        # that from the branch's own HR entirely. system_admin sees everything.
        if not _has_perm(request.user, 'settings.edit') and request.user.branch:
            qs = qs.filter(branch__iexact=request.user.branch)

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


# Step numbers are structural to the wizard (5 steps, 0-4) — unlike which
# FIELDS live in each step, this isn't something HR customizes, so it stays a
# plain constant rather than being derived from OnboardingFieldConfig (which
# only covers steps 0-3; step 4/Documents is a separate file-upload flow).
_VALID_STEPS = frozenset({0, 1, 2, 3, 4})

# Step 4 — Documents. pan_number is the one exception to "documents are
# handled separately via EmployeeDocument records": real-world onboarding
# captures the PAN *number* at the moment the PAN card proof is uploaded, not
# later — so the frontend saves it here, right before the upload request for
# that specific document. Not customizable, same reasoning as _VALID_STEPS.
_STEP_4_FIELDS = frozenset({'pan_number'})

# Profile fields that are nullable in the DB (null=True).
# Empty string from the frontend is converted to None for these fields so they
# can be cleared properly. All other profile fields are CharField(blank=True)
# which stores '' — never None.
_NULLABLE_PROFILE_FIELDS = frozenset({
    'date_of_birth',
    'year_of_passing',
    'total_experience_years',
})

_STEP_LABELS = dict(OnboardingFieldConfig.STEP_CHOICES)


def _step_configs(step: int) -> list:
    """All OnboardingFieldConfig rows for steps 0-3, any visibility — cached."""
    from core.cache_service import OnboardingFieldConfigCacheService
    return OnboardingFieldConfigCacheService.get_for_step(step)


def _step_all_field_keys(step: int) -> frozenset:
    if step == 4:
        return _STEP_4_FIELDS
    return frozenset(c.field_key for c in _step_configs(step))


def _step_required_configs(step: int) -> list:
    """Visible AND required configs for a step — what actually gates completion.
    Checking both (not just `required`) means a field HR hid can never block
    submission, even if `required` was left on from before it was hidden."""
    if step == 4:
        return []
    return [c for c in _step_configs(step) if c.visible and c.required]


def _step_custom_field_keys(step: int) -> frozenset:
    """Custom field_keys for a step, EXCLUDING file-type ones — file values
    live in CustomFieldFileValue, never in EmployeeProfile.custom_field_values,
    so a JSON-body request touching one of these keys must be dropped rather
    than merged (same trust-boundary pattern as MyProfileView.patch's
    step-scoping below)."""
    if step == 4:
        return frozenset()
    return frozenset(
        c.field_key for c in _step_configs(step)
        if c.is_custom and c.field_type != OnboardingFieldConfig.TYPE_FILE
    )


def _step_file_field_keys(step: int) -> frozenset:
    """The file-type custom field_keys _step_custom_field_keys() excludes —
    used wherever a caller needs to handle them separately (they have no real
    EmployeeProfile column and no custom_field_values entry; their values
    live entirely in CustomFieldFileValue rows)."""
    if step == 4:
        return frozenset()
    return frozenset(
        c.field_key for c in _step_configs(step)
        if c.is_custom and c.field_type == OnboardingFieldConfig.TYPE_FILE
    )


def _field_value(profile, config: 'OnboardingFieldConfig'):
    if config.is_custom:
        if config.field_type == OnboardingFieldConfig.TYPE_FILE:
            from apps.accounts.models import CustomFieldFileValue
            return CustomFieldFileValue.objects.filter(
                user=profile.user, field_key=config.field_key
            ).exists() or None
        return (profile.custom_field_values or {}).get(config.field_key)
    return getattr(profile, config.field_key, None)


def _file_type_custom_field_keys() -> frozenset:
    """All is_custom field_keys (any step) whose field_type is 'file' — used
    to strip file-type keys out of any custom_field_values JSON payload
    before merging, since file values live in CustomFieldFileValue and never
    belong in this dict (see _field_value())."""
    from core.cache_service import OnboardingFieldConfigCacheService
    return frozenset(
        c.field_key for c in OnboardingFieldConfigCacheService.get_all()
        if c.is_custom and c.field_type == OnboardingFieldConfig.TYPE_FILE
    )


def _missing_required(profile, step: int) -> list:
    """Human-readable '<label> (<step name>)' strings for required-but-empty
    fields in this step — same format the old hardcoded _submit() checks used."""
    step_label = _STEP_LABELS.get(step, '')
    missing = []
    for c in _step_required_configs(step):
        if not _field_filled(_field_value(profile, c)):
            missing.append(f'{c.label} ({step_label})' if step_label else c.label)
    return missing


def _step_is_complete(profile, step: int) -> bool:
    return not _missing_required(profile, step)


def _extract_step_data(profile, all_data: dict, step: int) -> dict:
    """
    Built-in field values come from `all_data` (an EmployeeProfileSerializer
    .data dict); custom field values have no serializer field of their own,
    so they're read out of profile.custom_field_values and flattened in
    alongside the built-in ones — the frontend doesn't need to know which is
    which.
    """
    step_fields = _step_all_field_keys(step)
    custom_keys = _step_custom_field_keys(step)
    data = {k: v for k, v in all_data.items() if k in step_fields}
    for key in custom_keys:
        data[key] = (profile.custom_field_values or {}).get(key)
    return data


def _field_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _missing_required_docs(user) -> list:
    """
    Human-readable labels for required-but-not-yet-uploaded document types
    (visible+required DocumentTypeConfig rows the user has no
    EmployeeDocument for) — the Step-5 equivalent of _missing_required()
    above. Single shared implementation for what used to be three duplicated
    hardcoded PAN/Aadhaar/Degree/conditional-Experience checks (in this
    function, _save_profile_step's step-4 branch, and OnboardingView._submit)
    — document types and their required-ness are now configurable per
    company via DocumentTypeConfig, so there is no hardcoded type list left
    to check against, and no conditional experience-based special case
    (dropped in favor of a plain per-type required flag, same as every other
    onboarding field).
    """
    from apps.accounts.models import EmployeeDocument as ED
    from core.cache_service import DocumentTypeConfigCacheService
    uploaded = set(ED.objects.filter(user=user).values_list('document_type', flat=True))
    return [
        c.label for c in DocumentTypeConfigCacheService.get_all()
        if c.visible and c.required and c.type_key not in uploaded
    ]


def _compute_completed_steps(profile, user) -> list:
    """
    Derive which wizard steps (0-4) already satisfy their required fields,
    without persisting a separate progress field — completion is always
    recomputed from the profile/document data that is already saved.
    """
    completed = [step for step in range(4) if _step_is_complete(profile, step)]
    if not _missing_required_docs(user):
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
            missing = []
            for c in _step_required_configs(step):
                incoming = filled_data.get(c.field_key)
                saved    = _field_value(profile, c)
                value    = incoming if incoming not in (None, '') else saved
                if not _field_filled(value):
                    missing.append(c.label)
            if missing:
                return error(
                    f'Please fill in the following required fields: {", ".join(missing)}.'
                )

        serializer = EmployeeProfileSerializer(profile, data=filled_data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        profile._changed_by = request.user
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

        if step not in _VALID_STEPS:
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
            data=_extract_step_data(profile, all_data, step),
        )

    # ── POST — save step data or submit the completed wizard ─────────────────

    def post(self, request, step: int = None):
        if step is not None:
            if step not in _VALID_STEPS:
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
        if step not in _VALID_STEPS:
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
        if step not in _VALID_STEPS:
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

        step_fields = _step_all_field_keys(step)
        if not step_fields:
            return success(f'Step {step} has no profile fields to clear.', data={})
        custom_keys = _step_custom_field_keys(step)
        file_keys   = _step_file_field_keys(step)
        builtin_keys = step_fields - custom_keys - file_keys

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
            if builtin_keys:
                EP.objects.filter(pk=profile.pk).update(**{field: None for field in builtin_keys})
            if custom_keys:
                remaining = {k: v for k, v in (profile.custom_field_values or {}).items() if k not in custom_keys}
                EP.objects.filter(pk=profile.pk).update(custom_field_values=remaining)
            if file_keys:
                from apps.accounts.models import CustomFieldFileValue
                CustomFieldFileValue.objects.filter(user=request.user, field_key__in=file_keys).delete()
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
        for step in range(4):
            missing.extend(_missing_required(profile, step))

        if missing:
            return error(
                f'Please complete the following required fields before submitting: '
                f'{", ".join(missing)}.'
            )

        missing_docs = _missing_required_docs(request.user)
        if missing_docs:
            return error(
                f'Please upload the following required documents before submitting: '
                f'{", ".join(missing_docs)}.'
            )

        # Face ID registration — only required when the admin's org-wide
        # "Face ID Verification" toggle (Attendance Settings) is mandatory.
        # Approval isn't required at this point, only that a request was
        # submitted — same "uploaded, not yet approved, is enough" bar as
        # the documents check above.
        from apps.attendance.services_face_matching import is_face_verification_mandatory
        if is_face_verification_mandatory():
            from apps.attendance.models import FaceRegistrationRequest
            has_face_registration = FaceRegistrationRequest.objects.filter(employee=request.user).exists()
            if not has_face_registration:
                return error(
                    'Please complete Face ID registration before submitting your onboarding profile.'
                )

        User.objects.filter(pk=request.user.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
        logger.info('User %s submitted onboarding wizard', request.user.email)

        # Notify HR via Celery so SMTP latency doesn't delay the response.
        from django.db import connection
        from apps.accounts.tasks import send_onboarding_submitted_notification_task

        def _queue_hr_notification(user_id=request.user.pk, schema_name=connection.schema_name):
            try:
                # retry=False + ignore_result=True — bounds broker/backend
                # retries so a down Redis can't block this request; see the
                # referral-submission dispatch in recruitment/views.py.
                send_onboarding_submitted_notification_task.apply_async(
                    args=[schema_name, user_id], retry=False, ignore_result=True,
                )
            except Exception as exc:
                logger.error(
                    'Failed to queue onboarding_submitted notification for user %s: %s',
                    user_id, exc, exc_info=True,
                )

        transaction.on_commit(_queue_hr_notification)

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
    if step not in _VALID_STEPS:
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

    # ── Step 4 — document verification, plus PAN capture ───────────────────────
    if step == 4:
        # A request carrying pan_number is the frontend saving/validating the
        # number right before it uploads the PAN card file — a distinct action
        # from the "have all documents been uploaded" check below, so it's
        # handled and returned on its own rather than falling into that check
        # (which would otherwise demand the file already be uploaded first).
        if 'pan_number' in request.data:
            from apps.accounts.models import (
                EmployeeProfile as _EP,
                find_conflicting_pan_profile,
                normalize_and_validate_pan,
            )
            raw_pan = (request.data.get('pan_number') or '').strip()
            if not raw_pan:
                return error('PAN number is required.', http_status=status.HTTP_400_BAD_REQUEST)
            try:
                pan_value = normalize_and_validate_pan(raw_pan)
            except ValueError as exc:
                return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
            profile, _ = _EP.objects.get_or_create(user=request.user)
            conflict = find_conflicting_pan_profile(pan_value, exclude_profile_pk=profile.pk)
            if conflict:
                return error(
                    f'This PAN is already registered to {conflict.user.full_name} '
                    f'({conflict.user.employee_id or conflict.user.email}).',
                    http_status=status.HTTP_409_CONFLICT,
                )
            profile.pan_number = pan_value
            profile.save(update_fields=['pan_number', 'updated_at'])
            return success('PAN number saved.', data={'pan_number': pan_value})

        try:
            missing_docs = _missing_required_docs(request.user)
        except Exception as exc:
            logger.error('_save_profile_step step=4 document query failed user=%s: %s',
                         request.user.pk, exc, exc_info=True)
            return error(
                'Unable to verify documents. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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

    step_fields   = _step_all_field_keys(step)
    required_keys = frozenset(c.field_key for c in _step_required_configs(step))
    custom_keys   = _step_custom_field_keys(step)
    file_keys     = _step_file_field_keys(step)

    filled_data: dict = {}
    custom_updates: dict = {}
    for k, v in request.data.items():
        if k not in step_fields:
            continue
        if k in file_keys:
            # File-type custom fields never ride along in this JSON body —
            # their bytes go through the dedicated multipart upload endpoint,
            # and their presence has no real EmployeeProfile column or
            # custom_field_values entry to write here (see _field_value()).
            continue
        if k in custom_keys:
            # No serializer-level type coercion for custom fields (they're
            # HR-defined at runtime, not real columns) — stored as submitted,
            # empty value included. Required-ness is checked separately by
            # _missing_required at step-complete/submit time, same as
            # built-in fields' "let required-field validation catch it" below.
            custom_updates[k] = v
            continue
        if v in ('', None):
            if k in required_keys:
                continue  # let required-field validation catch the missing value
            filled_data[k] = None if k in _NULLABLE_PROFILE_FIELDS else ''
        else:
            filled_data[k] = v

    if custom_updates:
        merged = dict(profile.custom_field_values or {})
        merged.update(custom_updates)
        filled_data['custom_field_values'] = merged

    # Step-scoped "nothing to save" — only triggers when the request had no step
    # fields at all or all were required fields with empty values.
    if not filled_data:
        all_data  = EmployeeProfileSerializer(profile).data
        step_data = _extract_step_data(profile, all_data, step)
        return success('Nothing to save.', data=step_data)

    serializer = EmployeeProfileSerializer(profile, data=filled_data, partial=True)
    if not serializer.is_valid():
        return error(
            first_error(serializer.errors),
            data=serializer.errors,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        profile._changed_by = request.user
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
    step_data = _extract_step_data(profile, all_data, step)
    logger.info('Onboarding step %d saved for user %s', step, request.user.email)
    return success('Profile saved.', data=step_data)


# ─── Onboarding Field Configuration ────────────────────────────────────────────

class OnboardingFieldConfigView(APIView):
    """
    HR-only settings screen for the onboarding wizard's field configuration
    (steps 0-3 — Documents/step 4 is a separate file-upload flow, not covered
    here). GET lists every field (built-in + custom); POST creates a custom
    field; PATCH updates one; DELETE removes a custom field (built-in fields
    can only be hidden via PATCH, never deleted).
    """
    permission_classes = [HasSettingsPermission]

    def get(self, request):
        from apps.accounts.serializers import OnboardingFieldConfigSerializer
        from core.cache_service import OnboardingFieldConfigCacheService
        configs = sorted(OnboardingFieldConfigCacheService.get_all(), key=lambda c: (c.step, c.order))
        return success(
            'Onboarding field configuration retrieved.',
            OnboardingFieldConfigSerializer(configs, many=True).data,
        )

    def post(self, request):
        from apps.accounts.serializers import (
            OnboardingFieldConfigCreateSerializer,
            OnboardingFieldConfigSerializer,
        )
        from core.cache_service import OnboardingFieldConfigCacheService

        serializer = OnboardingFieldConfigCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        data = serializer.validated_data

        base_key = re.sub(r'[^a-z0-9]+', '_', data['label'].lower()).strip('_') or 'field'
        field_key = f'custom_{base_key}'
        suffix = 1
        while OnboardingFieldConfig.objects.filter(field_key=field_key).exists():
            suffix += 1
            field_key = f'custom_{base_key}_{suffix}'

        max_order = OnboardingFieldConfig.objects.filter(step=data['step']).aggregate(m=Max('order'))['m']
        config = OnboardingFieldConfig.objects.create(
            field_key=field_key,
            label=data['label'],
            field_type=data['field_type'],
            options=data.get('options') or [],
            allow_multiple=data.get('allow_multiple', False),
            step=data['step'],
            order=(max_order or 0) + 1,
            visible=True,
            required=data.get('required', False),
            is_custom=True,
            is_locked=False,
        )
        OnboardingFieldConfigCacheService.invalidate()
        logger.info('Created custom onboarding field "%s" by %s', field_key, request.user.email)
        return success(
            'Custom field created.', OnboardingFieldConfigSerializer(config).data,
            http_status=status.HTTP_201_CREATED,
        )

    def patch(self, request, field_key: str):
        from apps.accounts.serializers import (
            OnboardingFieldConfigSerializer,
            OnboardingFieldConfigUpdateSerializer,
        )
        from core.cache_service import OnboardingFieldConfigCacheService

        config = OnboardingFieldConfig.objects.filter(field_key=field_key).first()
        if not config:
            return error('Field not found.', http_status=status.HTTP_404_NOT_FOUND)

        if config.is_locked and ({'visible', 'required'} & set(request.data.keys())):
            return error(
                f'"{config.label}" is a locked field — its visibility and requirement can\'t be changed.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OnboardingFieldConfigUpdateSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        OnboardingFieldConfigCacheService.invalidate()
        logger.info('Updated onboarding field "%s" by %s', field_key, request.user.email)
        return success('Field updated.', OnboardingFieldConfigSerializer(config).data)

    def delete(self, request, field_key: str):
        from core.cache_service import OnboardingFieldConfigCacheService

        config = OnboardingFieldConfig.objects.filter(field_key=field_key).first()
        if not config:
            return error('Field not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not config.is_custom:
            return error(
                'Built-in fields can\'t be deleted — hide them instead.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        config.delete()
        OnboardingFieldConfigCacheService.invalidate()
        logger.info('Deleted custom onboarding field "%s" by %s', field_key, request.user.email)
        return success('Custom field deleted.')


class OnboardingFieldConfigPublicView(APIView):
    """
    Every field (visible AND hidden) grouped by step — used by the wizard,
    the self-service Profile page, and the HR Employee Detail page, each of
    which filters to `visible` client-side rather than here. Returning only
    visible fields would make "hidden" indistinguishable from "config hasn't
    loaded yet" for callers that need to tell the two apart (Profile/Employee
    pages fall back to "show it" while loading — a hidden field would then
    incorrectly show forever, since it never appears in the response at all
    for them to find visible=false on). Every onboarding employee needs this
    regardless of role — not gated behind settings.view, same reasoning as
    FaceVerificationStatusView.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.serializers import OnboardingFieldConfigSerializer
        from core.cache_service import OnboardingFieldConfigCacheService

        by_step: dict = defaultdict(list)
        for c in OnboardingFieldConfigCacheService.get_all():
            by_step[c.step].append(c)

        data = {
            str(step): OnboardingFieldConfigSerializer(
                sorted(fields, key=lambda c: c.order), many=True,
            ).data
            for step, fields in by_step.items()
        }
        return success('Onboarding field configuration retrieved.', data=data)


# ─── Document Type Configuration (onboarding Step 5) ──────────────────────────

class DocumentTypeConfigView(APIView):
    """
    HR-only settings screen for onboarding Step 5 (Documents) — sibling of
    OnboardingFieldConfigView for the document-type list. GET lists every
    type (built-in + custom); POST creates a custom type; PATCH updates one;
    DELETE removes a custom type (built-in types can only be hidden via
    PATCH, never deleted — deleting one would orphan already-uploaded
    EmployeeDocument rows referencing it).
    """
    permission_classes = [HasSettingsPermission]

    def get(self, request):
        from apps.accounts.serializers import DocumentTypeConfigSerializer
        from core.cache_service import DocumentTypeConfigCacheService
        configs = sorted(DocumentTypeConfigCacheService.get_all(), key=lambda c: c.order)
        return success(
            'Document type configuration retrieved.',
            DocumentTypeConfigSerializer(configs, many=True).data,
        )

    def post(self, request):
        from apps.accounts.models import DocumentTypeConfig
        from apps.accounts.serializers import (
            DocumentTypeConfigCreateSerializer,
            DocumentTypeConfigSerializer,
        )
        from core.cache_service import DocumentTypeConfigCacheService

        serializer = DocumentTypeConfigCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        data = serializer.validated_data

        base_key = re.sub(r'[^a-z0-9]+', '_', data['label'].lower()).strip('_') or 'document'
        type_key = f'custom_{base_key}'
        suffix = 1
        while DocumentTypeConfig.objects.filter(type_key=type_key).exists():
            suffix += 1
            type_key = f'custom_{base_key}_{suffix}'

        max_order = DocumentTypeConfig.objects.aggregate(m=Max('order'))['m']
        config = DocumentTypeConfig.objects.create(
            type_key=type_key,
            label=data['label'],
            order=(max_order or 0) + 1,
            visible=True,
            required=data.get('required', False),
            allow_multiple=data.get('allow_multiple', False),
            is_custom=True,
            is_locked=False,
        )
        DocumentTypeConfigCacheService.invalidate()
        logger.info('Created custom document type "%s" by %s', type_key, request.user.email)
        return success(
            'Document type created.', DocumentTypeConfigSerializer(config).data,
            http_status=status.HTTP_201_CREATED,
        )

    def patch(self, request, type_key: str):
        from apps.accounts.models import DocumentTypeConfig
        from apps.accounts.serializers import (
            DocumentTypeConfigSerializer,
            DocumentTypeConfigUpdateSerializer,
        )
        from core.cache_service import DocumentTypeConfigCacheService

        config = DocumentTypeConfig.objects.filter(type_key=type_key).first()
        if not config:
            return error('Document type not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = DocumentTypeConfigUpdateSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        DocumentTypeConfigCacheService.invalidate()
        logger.info('Updated document type "%s" by %s', type_key, request.user.email)
        return success('Document type updated.', DocumentTypeConfigSerializer(config).data)

    def delete(self, request, type_key: str):
        from apps.accounts.models import DocumentTypeConfig
        from core.cache_service import DocumentTypeConfigCacheService

        config = DocumentTypeConfig.objects.filter(type_key=type_key).first()
        if not config:
            return error('Document type not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not config.is_custom:
            return error(
                'Built-in document types can\'t be deleted — hide them instead.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        config.delete()
        DocumentTypeConfigCacheService.invalidate()
        logger.info('Deleted custom document type "%s" by %s', type_key, request.user.email)
        return success('Document type deleted.')


class DocumentTypeConfigPublicView(APIView):
    """
    Every document type (visible AND hidden), sorted by order — used by the
    wizard, the self-service Profile page, and the HR Employee Detail page,
    each of which filters to `visible` client-side. Same
    hidden-vs-not-loaded-yet reasoning as OnboardingFieldConfigPublicView.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.serializers import DocumentTypeConfigSerializer
        from core.cache_service import DocumentTypeConfigCacheService
        configs = sorted(DocumentTypeConfigCacheService.get_all(), key=lambda c: c.order)
        return success(
            'Document type configuration retrieved.',
            DocumentTypeConfigSerializer(configs, many=True).data,
        )


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
        if doc.user_id != request.user.id and not _has_perm(request.user, 'employees.edit'):
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
                    type='authenticated',
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
        type_config = _get_document_type_config(doc_type)
        if not type_config:
            return error('Invalid document type.', http_status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            doc = serializer.save(
                user=request.user,
                file_name=file_obj.name[:255],
                file_size=file_obj.size,
            )
            if not type_config.allow_multiple:
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


def _can_manage_employee_documents(user, employee) -> bool:
    """
    True for the employee themself, their specifically assigned reporting
    manager or HR (falling back to branch match only when the employee has
    no HR assigned), system_admin, or a Branch Admin (unconditional access
    within their own branch). Mirrors the assigned-employee scoping used for
    leave/expense — a blanket documents.create grant should not let any HR
    act on any employee company-wide.
    """
    if employee.id == user.id:
        return True
    if not _has_perm(user, 'documents.create'):
        return False
    if _has_perm(user, 'settings.edit'):
        return True
    if user.role and getattr(user.role, 'can_manage_branch', False):
        branch = (getattr(user, 'branch', '') or '').strip()
        return not branch or (getattr(employee, 'branch', '') or '').strip() == branch
    if user.role and getattr(user.role, 'can_manage_team', False):
        return employee.reporting_manager_id == user.id
    if employee.hr_id:
        return employee.hr_id == user.id
    branch = (getattr(user, 'branch', '') or '').strip()
    return not branch or (getattr(employee, 'branch', '') or '').strip() == branch


class EmployeeProfileDocumentView(APIView):
    """
    POST /employees/<employee_id>/documents/ → upload or replace a document on
    an employee's profile (the Employee Profile page's "Documents" tab).

    Distinct from /onboarding/documents/, which is self-service-only (always
    saves against request.user) and permanently locks once onboarding_status
    is complete — so it can never be used by HR/admin to manage documents on
    an active employee's profile after onboarding, which is the normal state
    for everyone this feature actually targets.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, employee_id: str):
        from apps.accounts.models import EmployeeDocument as ED
        from apps.accounts.serializers import EmployeeDocumentSerializer

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if not _can_manage_employee_documents(request.user, employee):
            return error('You do not have permission to upload documents for this employee.',
                         http_status=status.HTTP_403_FORBIDDEN)

        serializer = EmployeeDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']
        type_config = _get_document_type_config(doc_type)
        if not type_config:
            return error('Invalid document type.', http_status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            doc = serializer.save(
                user=employee,
                file_name=file_obj.name,
                file_size=file_obj.size,
            )
            # Upsert by type (unless allow_multiple) — a re-upload of the
            # same document_type replaces the previous file rather than
            # accumulating duplicates.
            if not type_config.allow_multiple:
                ED.objects.filter(user=employee, document_type=doc_type).exclude(pk=doc.pk).delete()

        try:
            AuditLog.objects.create(
                user=request.user, action='document_uploaded', module='documents',
                object_id=str(doc.id),
                changes={'employee': employee.employee_id, 'document_type': doc_type},
                branch=employee.branch,
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.warning('AuditLog write failed for document_uploaded id=%s', doc.id)

        logger.info('Document %s uploaded for %s by %s', doc_type, employee.email, request.user.email)
        return success(
            'Document uploaded.',
            data=EmployeeDocumentSerializer(doc, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


def _get_document_type_config(type_key: str):
    """Return the visible DocumentTypeConfig row for type_key, or None. Every
    document upload endpoint validates against this before accepting a file
    — document_type no longer has a `choices=` enum (see DocumentTypeConfig),
    so this is the only thing standing between an upload and an arbitrary
    string being stored as a document type."""
    from core.cache_service import DocumentTypeConfigCacheService
    for c in DocumentTypeConfigCacheService.get_all():
        if c.type_key == type_key and c.visible:
            return c
    return None


# ─── Custom Field File Values (file/image-type OnboardingFieldConfig fields) ──

def _get_file_field_config(field_key: str):
    """Return the OnboardingFieldConfig row for field_key if it's a visible,
    is_custom=True, field_type='file' field; else None. Every upload/list
    endpoint below validates against this before touching CustomFieldFileValue,
    so a request can't create a file value for a field that doesn't exist,
    isn't custom, or isn't a file-type field."""
    from core.cache_service import OnboardingFieldConfigCacheService
    for c in OnboardingFieldConfigCacheService.get_all():
        if c.field_key == field_key and c.is_custom and c.field_type == OnboardingFieldConfig.TYPE_FILE and c.visible:
            return c
    return None


def _self_can_write_custom_file(user, config) -> bool:
    """Self-service write rule for a file-type custom field — mirrors the
    Emergency-only-after-onboarding rule MyProfileView.patch already applies
    to text-type custom fields: Emergency-step fields stay editable forever,
    every other step is only writable while still mid-wizard."""
    if config.step == OnboardingFieldConfig.STEP_EMERGENCY:
        return True
    return user.onboarding_status != User.ONBOARDING_COMPLETE


class CustomFieldFileValueView(APIView):
    """
    GET    /onboarding/custom-file-fields/           → list all of this user's file-type custom values
    POST   /onboarding/custom-file-fields/           → upload a value for {field_key, file}
    GET    /onboarding/custom-file-fields/<value_id>/ → stream the file (Cloudinary signed proxy)
    DELETE /onboarding/custom-file-fields/<value_id>/ → delete a value

    Reads are unrestricted by step (Personal/Education/Bank file fields still
    need to render read-only on the self-service Profile page); only writes
    are step-gated via _self_can_write_custom_file(). By-id GET/DELETE also
    serve HR (via the employees.edit permission check below), the same way
    EmployeeDocumentView's single by-id route already serves both self and HR
    for real documents — no separate HR-only stream/delete route needed.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def _get_value(self, request, value_id: str):
        from apps.accounts.models import CustomFieldFileValue
        try:
            value = CustomFieldFileValue.objects.get(id=value_id)
        except CustomFieldFileValue.DoesNotExist:
            return None, error('File not found.', http_status=status.HTTP_404_NOT_FOUND)
        if value.user_id != request.user.id and not _has_perm(request.user, 'employees.edit'):
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return value, None

    def get(self, request, value_id: str = None):
        from apps.accounts.models import CustomFieldFileValue
        from apps.accounts.serializers import CustomFieldFileValueSerializer

        if value_id:
            value, err = self._get_value(request, value_id)
            if err:
                return err

            name  = value.file.name
            parts = os.path.basename(name).rsplit('.', 1)
            fmt   = parts[1].lower() if len(parts) == 2 else ''

            try:
                dl_url = cloudinary.utils.private_download_url(
                    name, fmt,
                    resource_type='raw',
                    type='authenticated',
                    attachment=False,
                )
                r = http_req.get(dl_url, stream=True, timeout=30)
                r.raise_for_status()
            except http_req.exceptions.HTTPError as exc:
                logger.error('Custom field file Cloudinary fetch failed id=%s status=%s',
                             value_id, exc.response.status_code)
                return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)
            except Exception as exc:
                logger.error('Custom field file download error id=%s: %s', value_id, exc, exc_info=True)
                return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)

            content_type = 'application/pdf' if fmt == 'pdf' else r.headers.get('content-type', 'application/octet-stream')
            response = StreamingHttpResponse(r.iter_content(chunk_size=8192), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{value.file_name}"'
            if 'content-length' in r.headers:
                response['Content-Length'] = r.headers['content-length']
            response['Cache-Control'] = 'no-store'
            return response

        values = CustomFieldFileValue.objects.filter(user=request.user)
        return success('Custom field files retrieved.',
                       data=CustomFieldFileValueSerializer(values, many=True, context={'request': request}).data)

    def post(self, request):
        from apps.accounts.models import CustomFieldFileValue
        from apps.accounts.serializers import CustomFieldFileValueSerializer

        field_key = (request.data.get('field_key') or '').strip()
        config = _get_file_field_config(field_key)
        if not config:
            return error('Invalid field_key — not a file-type custom field.', http_status=status.HTTP_400_BAD_REQUEST)
        if not _self_can_write_custom_file(request.user, config):
            return error(
                f'"{config.label}" can no longer be edited here. Contact HR to update it.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CustomFieldFileValueSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        with transaction.atomic():
            value = serializer.save(
                user=request.user,
                field_key=field_key,
                file_name=file_obj.name[:255],
                file_size=file_obj.size,
            )
            if not config.allow_multiple:
                CustomFieldFileValue.objects.filter(
                    user=request.user, field_key=field_key,
                ).exclude(pk=value.pk).delete()

        return success(
            'File uploaded.',
            data=CustomFieldFileValueSerializer(value, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )

    def delete(self, request, value_id: str = None):
        if not value_id:
            return error('File ID is required.', http_status=status.HTTP_400_BAD_REQUEST)
        value, err = self._get_value(request, value_id)
        if err:
            return err
        config = _get_file_field_config(value.field_key)
        if value.user_id == request.user.id:
            if config and not _self_can_write_custom_file(request.user, config):
                return error(
                    'This field can no longer be edited here. Contact HR to update it.',
                    http_status=status.HTTP_403_FORBIDDEN,
                )
        elif not _has_perm(request.user, 'employees.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        value.delete()
        logger.info('Custom field file %s (%s) deleted by %s', value_id, value.field_key, request.user.email)
        return success('File deleted.')


class EmployeeCustomFieldFileValueView(APIView):
    """
    GET  /employees/<employee_id>/custom-file-fields/ → list a managed employee's file-type custom values
    POST /employees/<employee_id>/custom-file-fields/ → upload/replace a value for {field_key, file}

    HR-side equivalent of CustomFieldFileValueView — no step restriction
    (HR can manage any of the 4 steps' file fields, matching the existing
    "HR Employee Detail: all steps editable" rule for text-type custom
    fields). By-id GET/DELETE reuse CustomFieldFileValueView's own route
    (the employees.edit permission check there already covers HR), so this
    view only needs list + upload.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request, employee_id: str):
        from apps.accounts.models import CustomFieldFileValue
        from apps.accounts.serializers import CustomFieldFileValueSerializer

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_employee_documents(request.user, employee):
            return error('You do not have permission to view files for this employee.',
                         http_status=status.HTTP_403_FORBIDDEN)

        values = CustomFieldFileValue.objects.filter(user=employee)
        return success('Custom field files retrieved.',
                       data=CustomFieldFileValueSerializer(values, many=True, context={'request': request}).data)

    def post(self, request, employee_id: str):
        from apps.accounts.models import CustomFieldFileValue
        from apps.accounts.serializers import CustomFieldFileValueSerializer

        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_employee_documents(request.user, employee):
            return error('You do not have permission to upload files for this employee.',
                         http_status=status.HTTP_403_FORBIDDEN)

        field_key = (request.data.get('field_key') or '').strip()
        config = _get_file_field_config(field_key)
        if not config:
            return error('Invalid field_key — not a file-type custom field.', http_status=status.HTTP_400_BAD_REQUEST)

        serializer = CustomFieldFileValueSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        with transaction.atomic():
            value = serializer.save(
                user=employee,
                field_key=field_key,
                file_name=file_obj.name[:255],
                file_size=file_obj.size,
            )
            if not config.allow_multiple:
                CustomFieldFileValue.objects.filter(
                    user=employee, field_key=field_key,
                ).exclude(pk=value.pk).delete()

        try:
            AuditLog.objects.create(
                user=request.user, action='custom_field_file_uploaded', module='documents',
                object_id=str(value.id),
                changes={'employee': employee.employee_id, 'field_key': field_key},
                branch=employee.branch,
                ip_address=get_client_ip(request),
            )
        except Exception:
            logger.warning('AuditLog write failed for custom_field_file_uploaded id=%s', value.id)

        logger.info('Custom field file %s uploaded for %s by %s', field_key, employee.email, request.user.email)
        return success(
            'File uploaded.',
            data=CustomFieldFileValueSerializer(value, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


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

        if _employee_out_of_branch_scope(request.user, target):
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        if target.onboarding_status != User.ONBOARDING_SUBMITTED:
            return error('This user has not submitted their onboarding form.')

        if not _has_perm(request.user, 'settings.edit') and _has_perm(target, 'employees.view'):
            return error('HR admin can only approve employee onboarding.',
                         http_status=status.HTTP_403_FORBIDDEN)

        decision           = request.data.get('decision')
        remarks            = request.data.get('remarks', '')
        req_designation    = (request.data.get('designation')        or '').strip()
        req_department     = (request.data.get('department')         or '').strip()
        # assessment_ids (list) is the current contract; assessment_id (single)
        # is accepted too for any older caller still sending one value.
        req_assessment_ids = request.data.get('assessment_ids')
        if not isinstance(req_assessment_ids, list):
            single = request.data.get('assessment_id')
            req_assessment_ids = [single] if single else []
        req_assessment_ids     = [str(a) for a in req_assessment_ids if a]
        req_manager_id         = request.data.get('reporting_manager_id')
        annual_ctc_raw         = (request.data.get('annual_ctc')          or '').strip()
        req_uan_number         = (request.data.get('uan_number')          or '').strip()
        req_name_as_per_aadhar = (request.data.get('name_as_per_aadhar')  or '').strip()
        req_pan_number         = (request.data.get('pan_number')          or '').strip()
        if decision not in ('approve', 'reject'):
            return error('decision must be "approve" or "reject".')
        if decision == 'approve':
            if not req_department:
                return error('Department is required to approve onboarding.')
            if not req_designation:
                return error('Designation is required to approve onboarding.')
            if req_pan_number:
                # Validated before any state changes below — an invalid/duplicate
                # PAN must reject the whole approval, not just skip saving it.
                from apps.accounts.models import find_conflicting_pan_profile, normalize_and_validate_pan
                try:
                    req_pan_number = normalize_and_validate_pan(req_pan_number)
                except ValueError as exc:
                    return error(str(exc))
                existing_profile = getattr(target, 'profile', None)
                conflict = find_conflicting_pan_profile(
                    req_pan_number,
                    exclude_profile_pk=existing_profile.pk if existing_profile else None,
                )
                if conflict:
                    return error(
                        f'This PAN is already registered to {conflict.user.full_name} '
                        f'({conflict.user.employee_id or conflict.user.email}).'
                    )

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''

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

            # Save UAN / Aadhar name / PAN provided by HR at approval time.
            if req_uan_number or req_name_as_per_aadhar or req_pan_number:
                from apps.accounts.models import EmployeeProfile as _Profile
                profile, _ = _Profile.objects.get_or_create(user=target)
                profile_fields = []
                if req_uan_number:
                    profile.uan_number = req_uan_number
                    profile_fields.append('uan_number')
                if req_name_as_per_aadhar:
                    profile.name_as_per_aadhar = req_name_as_per_aadhar
                    profile_fields.append('name_as_per_aadhar')
                if req_pan_number:
                    profile.pan_number = req_pan_number
                    profile_fields.append('pan_number')
                if profile_fields:
                    profile_fields.append('updated_at')
                    profile.save(update_fields=profile_fields)

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

                # Auto-create the referral bonus record on conversion so referrers
                # are never missed. (A duplicate auto-creation existed in
                # CandidateStatusView.patch() in the recruitment app, but that
                # view's own status whitelist excludes STATUS_CONVERTED, so it
                # was dead code — this is the only place a candidate is ever
                # actually marked converted.)
                if linked_candidate.referral_by_id:
                    from apps.recruitment.models import ReferralBonus
                    _, _bonus_created = ReferralBonus.objects.get_or_create(
                        candidate=linked_candidate,
                        defaults={'referrer': linked_candidate.referral_by, 'bonus_amount': 0},
                    )
                    if _bonus_created:
                        logger.info(
                            'Referral bonus record created for referrer %s (candidate %s)',
                            linked_candidate.referral_by_id, linked_candidate.pk,
                        )

            # Auto-assign default assessments — employee must complete these to unlock full portal.
            # Works for both recruited candidates (candidate FK) and direct hires (employee FK).
            from apps.assessments.models import Assessment, AssessmentItem, CandidateAssignment
            from django.db.models import Q as _Q
            assigned_assessments = []
            assessments_to_assign = list(
                Assessment.objects.filter(is_active=True, is_default=True).prefetch_related('items')
            )
            # HR may pick one or more specific (possibly non-default) assessments
            # in the approval confirmation dialog — honor that choice, not just
            # the global defaults. A branch/role can have several relevant
            # tests, so this is a list, not a single value.
            if req_assessment_ids:
                already_ids = {str(a.id) for a in assessments_to_assign}
                new_ids = [aid for aid in req_assessment_ids if aid not in already_ids]
                if new_ids:
                    selected_assessments = Assessment.objects.filter(
                        pk__in=new_ids, is_active=True,
                    ).prefetch_related('items')
                    assessments_to_assign.extend(selected_assessments)
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
                branch=target.branch,
                ip_address=get_client_ip(request),
            )
            logger.info('Onboarding approved for %s by %s', target.email, request.user.email)

            # Dispatch via Celery so 1-3 sequential SMTP round-trips never sit in
            # this request's response path — see send_onboarding_submitted_notification_task's
            # dispatch (onboarding wizard submission, above) for the same rationale.
            from django.db import connection
            from apps.accounts.tasks import send_onboarding_approved_notification_task

            def _queue_approval_notification(
                user_id=target.pk,
                assessment_ids=[a.id for a in assigned_assessments],
                has_pending_=has_pending,
                schema_name=connection.schema_name,
            ):
                try:
                    send_onboarding_approved_notification_task.apply_async(
                        args=[schema_name, user_id, assessment_ids, has_pending_], retry=False, ignore_result=True,
                    )
                except Exception as exc:
                    logger.error(
                        'Failed to queue onboarding_approved notification for user %s: %s',
                        user_id, exc, exc_info=True,
                    )

            transaction.on_commit(_queue_approval_notification)

            return success(f'{target.full_name} onboarding approved.')

        else:
            target.onboarding_status = User.ONBOARDING_REJECTED
            target.save(update_fields=['onboarding_status'])
            AuditLog.objects.create(
                user=request.user, action='onboarding_rejected', module='accounts',
                object_id=str(target.pk),
                changes={'target': target.email, 'remarks': remarks},
                branch=target.branch,
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
        if not _has_perm(request.user, 'settings.edit'):
            base_qs = base_qs.exclude(role__role_permissions__permission__codename='settings.edit')

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

        qs = (
            User.objects
            .filter(onboarding_status__in=[User.ONBOARDING_SUBMITTED, User.ONBOARDING_REJECTED])
            .select_related('role', 'profile')
            .prefetch_related('employee_documents')
            .prefetch_related('custom_field_files')
            .order_by('date_joined')
        )
        role = request.user.role
        if not _has_perm(request.user, 'settings.edit'):
            qs = qs.exclude(role__role_permissions__permission__codename='settings.edit')
            # Same scoping as EmployeeListCreateView.get(): managers only see
            # their direct reports; everyone else is scoped to their own branch.
            if role and role.can_manage_team:
                qs = qs.filter(reporting_manager=request.user)
            elif request.user.branch:
                # A submitted candidate who hasn't been approved yet has no
                # User.branch (that's only copied over from the linked
                # Candidate at approval time) — fall back to the source
                # candidate's branch so HR still sees their own branch's
                # pending submissions.
                qs = qs.filter(
                    Q(branch=request.user.branch) |
                    Q(branch='', candidate_portal__branch__branch_name=request.user.branch)
                ).distinct()

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
                .prefetch_related('custom_field_files')
                .get(pk=user_id)
            )
        except User.DoesNotExist:
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        if _employee_out_of_branch_scope(request.user, target):
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
        return success('Profile retrieved.', MyProfileSerializer(user, context={'request': request}).data)

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

        # Self-service can only edit Emergency-category custom fields (see
        # MyProfileUpdateSerializer's custom_field_values docstring) — filtered
        # here against OnboardingFieldConfig rather than trusted from the
        # request, so a crafted request can't edit a Bank/Personal/Education
        # custom field through this endpoint.
        incoming_custom = data.get('custom_field_values') or {}
        if incoming_custom:
            from apps.accounts.models import OnboardingFieldConfig
            allowed_keys = set(
                OnboardingFieldConfig.objects.filter(
                    step=OnboardingFieldConfig.STEP_EMERGENCY, is_custom=True,
                ).exclude(field_type=OnboardingFieldConfig.TYPE_FILE)
                .values_list('field_key', flat=True)
            )
            incoming_custom = {k: v for k, v in incoming_custom.items() if k in allowed_keys}

        if profile_data or incoming_custom:
            profile, _ = EmployeeProfile.objects.get_or_create(user=request.user)
            for key, value in profile_data.items():
                setattr(profile, key, value)
            update_fields = list(profile_data.keys())
            if incoming_custom:
                merged = dict(profile.custom_field_values or {})
                merged.update(incoming_custom)
                profile.custom_field_values = merged
                update_fields.append('custom_field_values')
            profile.save(update_fields=update_fields + ['updated_at'])

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
        if not branch:
            return error('branch query parameter is required.')
        # Filter by permission so any role named hr/hr_admin/etc. is included.
        # Org-wide (settings.edit) roles are explicitly excluded — system_admin
        # is seeded with every permission (including onboarding.approve) so it
        # would otherwise match here too, even though an org-wide admin isn't
        # a branch's actual HR contact. Permission-based so this correctly
        # excludes any future role granted settings.edit, not just this name.
        hrs = (
            User.objects
            .filter(
                role__role_permissions__permission__codename='onboarding.approve',
                is_active=True,
            )
            .exclude(role__role_permissions__permission__codename='settings.edit')
            .filter(Q(branch__iexact=branch) | Q(managed_branches__branch_name__iexact=branch))
            .select_related('role')
            .distinct()
            .order_by('full_name')
        )
        data = [
            {'id': str(u.id), 'employee_id': u.employee_id, 'full_name': u.full_name,
             'department': u.department, 'branch': u.branch}
            for u in hrs
        ]
        return success('HR users retrieved.', data=data)


class ManagerListView(APIView):
    """GET list of active managers — filtered by department and/or branch.
    Query params: department (optional), branch (optional) — at least one is
    required. e.g. ?department=Engineering or ?branch=Mumbai HQ or both.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        department = (request.query_params.get('department') or '').strip()
        branch     = (request.query_params.get('branch') or '').strip()
        if not department and not branch:
            return error('department or branch query parameter is required.')
        managers = (
            User.objects
            .filter(role__can_manage_team=True, is_active=True)
            .select_related('role')
        )
        if department:
            managers = managers.filter(department__iexact=department)
        if branch:
            managers = managers.filter(branch__iexact=branch)
        managers = managers.order_by('full_name')
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

        if employee.role and employee.role.can_manage_team:
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
    ApprovalWorkflowRule.WORKFLOW_ATTENDANCE_CORRECTION,
]


def _ensure_default_rules():
    """Create default rules for any workflow types that don't have one yet.
    Never overwrites existing rules — safe to call on every request."""
    existing = set(ApprovalWorkflowRule.objects.values_list('workflow_type', flat=True))
    missing  = [wf for wf in _WORKFLOW_ORDER if wf not in existing]
    if not missing:
        return
    manager_role = Role.objects.filter(can_manage_team=True, is_active=True).first()
    hr_role      = None
    perm = Permission.objects.filter(codename='leave.approve').first()
    if perm:
        rp = RolePermission.objects.filter(permission=perm, role__is_active=True).select_related('role').first()
        if rp:
            hr_role = rp.role
    ApprovalWorkflowRule.objects.bulk_create([
        ApprovalWorkflowRule(workflow_type=wf, l1_approver_role=manager_role, l2_approver_role=hr_role)
        for wf in missing
    ])


def _serialize_rule(rule: ApprovalWorkflowRule) -> dict:
    return {
        'workflow_type':      rule.workflow_type,
        'workflow_label':     rule.get_workflow_type_display(),
        'l1_approver_role':   rule.l1_approver_role_id,
        'l1_approver_label':  rule.l1_approver_role.display_name if rule.l1_approver_role else '',
        'l2_approver_role':   rule.l2_approver_role_id,
        'l2_approver_label':  rule.l2_approver_role.display_name if rule.l2_approver_role else '',
    }


class ApprovalWorkflowRuleView(APIView):
    """GET all global workflow rules; PATCH a single rule."""
    permission_classes = [IsAuthenticated, CanManageRoles]

    def get(self, request):
        _ensure_default_rules()
        from core.cache_service import ApprovalWorkflowCacheService
        data = [
            _serialize_rule(rule)
            for wf in _WORKFLOW_ORDER
            if (rule := ApprovalWorkflowCacheService.get_rule(wf)) is not None
        ]
        return success('Approval rules retrieved.', data=data)

    def patch(self, request):
        serializer = ApprovalWorkflowRuleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data = serializer.validated_data
        _ensure_default_rules()

        rule = ApprovalWorkflowRule.objects.select_related(
            'l1_approver_role', 'l2_approver_role'
        ).get(workflow_type=data['workflow_type'])
        rule.l1_approver_role = data['l1_approver_role']
        rule.l2_approver_role = data.get('l2_approver_role') or None
        rule.updated_by       = request.user
        rule.save(update_fields=['l1_approver_role', 'l2_approver_role', 'updated_by', 'updated_at'])

        from core.cache_service import ApprovalWorkflowCacheService
        ApprovalWorkflowCacheService.invalidate(data['workflow_type'])

        logger.info('Approval rule for %s updated by %s', data['workflow_type'], request.user.email)
        return success('Approval rule updated.', data=_serialize_rule(rule))


# ─── Employee Approval Matrix ─────────────────────────────────────────────────

def _resolve_rule_approver(role, employee):
    """Resolve a Role FK to the actual User approver for a given employee.

    Roles with can_manage_team=True resolve via employee.reporting_manager;
    all other roles resolve via employee.hr. Validates the assigned person
    still holds the expected capability.
    """
    if role is None:
        return None
    if role.can_manage_team:
        rm = getattr(employee, 'reporting_manager', None)
        if rm and rm.role and rm.role.can_manage_team:
            return rm
        return None
    else:
        hr_user = getattr(employee, 'hr', None)
        if hr_user and _has_perm(hr_user, 'leave.approve'):
            return hr_user
        return None


def _build_matrix_row(rule: ApprovalWorkflowRule, override, employee=None) -> dict:
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
        'l1_approver_role':  rule.l1_approver_role_id,
        'l1_approver_label': rule.l1_approver_role.display_name if rule.l1_approver_role else '',
        'l1_approver_id':    l1_id,
        'l1_approver_name':  l1_name,
        'l1_is_override':    l1_is_override,
        'l2_approver_role':  rule.l2_approver_role_id,
        'l2_approver_label': rule.l2_approver_role.display_name if rule.l2_approver_role else '',
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
        rules = {
            r.workflow_type: r
            for r in ApprovalWorkflowRule.objects.select_related('l1_approver_role', 'l2_approver_role')
        }
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
    'uan': 'uan_number', 'uan number': 'uan_number', 'uan_number': 'uan_number',
    'pf uan': 'uan_number', 'epf uan': 'uan_number',
    'name as per aadhar': 'name_as_per_aadhar', 'name_as_per_aadhar': 'name_as_per_aadhar',
    'aadhar name': 'name_as_per_aadhar', 'aadhaar name': 'name_as_per_aadhar',
    'basic salary': 'basic_salary', 'basic_salary': 'basic_salary', 'basic': 'basic_salary',
    'annual ctc': 'annual_ctc', 'annual_ctc': 'annual_ctc', 'ctc': 'annual_ctc',
}

_EMP_MAX_IMPORT_ROWS  = 1000
_EMP_MAX_IMPORT_BYTES = 5 * 1024 * 1024


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
        if not _has_perm(request.user, 'employees.create'):
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
            if role_obj.role_permissions.filter(permission__codename='settings.edit').exists():
                row_errors.append({
                    'row':        idx,
                    'field':      'role',
                    'identifier': email,
                    'message':    f'"{role_obj.display_name}" cannot be assigned via bulk import.',
                })
                continue

            # Create the employee.
            try:
                temp_password = ''.join(
                    secrets.choice(string.ascii_letters + string.digits)
                    for _ in range(12)
                )
                employee_id = EmployeeCodeSettings.generate_employee_id(
                    first_name=vd['first_name'],
                    last_name=vd['last_name'],
                    date_of_joining=vd.get('date_of_joining'),
                )
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

                # Create EmployeeProfile with any optional fields present in the import sheet.
                gender          = vd.get('gender') or ''
                dob             = vd.get('date_of_birth')
                blood           = vd.get('blood_group') or ''
                address         = vd.get('address') or ''
                uan_number      = vd.get('uan_number') or ''
                aadhar_name     = vd.get('name_as_per_aadhar') or ''
                if any([gender, dob, blood, address, uan_number, aadhar_name]):
                    EmployeeProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'gender':              gender,
                            'date_of_birth':       dob,
                            'blood_group':         blood,
                            'current_address':     address,
                            'uan_number':          uan_number,
                            'name_as_per_aadhar':  aadhar_name,
                        },
                    )

                # Create salary config if annual_ctc was provided in the import sheet.
                annual_ctc_import = vd.get('annual_ctc') or ''
                if annual_ctc_import:
                    from decimal import Decimal as _Decimal, InvalidOperation
                    from apps.payroll.models import EmployeeSalaryConfig as _SC
                    try:
                        ctc_value = _Decimal(str(annual_ctc_import).replace(',', ''))
                        _SC.objects.create(
                            employee=user,
                            annual_ctc=ctc_value,
                            effective_from=user.date_of_joining or user.date_joined.date(),
                            is_active=True,
                        )
                    except InvalidOperation:
                        logger.warning(
                            'Invalid annual_ctc value "%s" for %s — skipping salary config',
                            annual_ctc_import, email,
                        )
                        row_errors.append({
                            'row':     idx,
                            'field':   'annual_ctc',
                            'message': f'"{annual_ctc_import}" is not a valid number — salary config was not created for this employee.',
                        })
                    except Exception:
                        logger.warning('Could not create salary config for %s from import', email)

                # Auto-allocate leave balances based on active leave policies —
                # same step EmployeeListCreateView.post() does for a single
                # employee; this bulk path re-implements creation separately
                # and had been missing it entirely.
                from apps.hrms.views.leave import _allocate_leaves_for_employee
                _allocate_leaves_for_employee(user, user.date_of_joining)

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


# ─── Employee Bulk Import — Sample Template ───────────────────────────────────

# Replaced by _has_perm check below — 'employees.create' covers both system_admin and HR.


class EmployeeBulkImportSampleView(APIView):
    """
    GET /api/employees/bulk-import/sample/?format=csv
    GET /api/employees/bulk-import/sample/?format=xlsx

    Download a sample import template for Employee Bulk Import.
    Headers are identical to the column aliases accepted by EmployeeBulkImportView.
    Permission mirrors the upload endpoint (system_admin / hr_admin only).
    """
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')
    authentication_classes = [JWTAuthentication]        

    _HEADERS = [
        'First Name', 'Last Name', 'Work Email', 'Mobile Number',
        'Role', 'Department', 'Designation', 'Branch', 'Employee Type',
        'Date of Joining', 'Gender', 'Date of Birth', 'Blood Group', 'Address',
    ]
    _SAMPLE_ROWS = [
        [
            'John', 'Doe', 'john.doe@company.com', '9876543210',
            'Employee', 'Engineering', 'Software Engineer', 'Mumbai HQ', 'Permanent',
            '2026-01-15', 'Male', '1995-06-20', 'B+', '123 Main Street, Mumbai',
        ],
        [
            'Jane', 'Smith', 'jane.smith@company.com', '9123456789',
            'HR Admin', 'Human Resources', 'HR Manager', 'Delhi Branch', 'Permanent',
            '2026-02-01', 'Female', '1990-03-15', 'A+', '456 Park Avenue, Delhi',
        ],
    ]

    def get(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(
                'You do not have permission to download the employee import template.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        from core.file_utils import build_sample_csv, build_sample_xlsx, _CSV_MIME, _XLSX_MIME

        fmt = request.query_params.get('format', 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(self._HEADERS, self._SAMPLE_ROWS, 'Employee Import')
            filename = 'employee_import_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(self._HEADERS, self._SAMPLE_ROWS)
            filename = 'employee_import_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
