
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

# ─── My Profile ───────────────────────────────────────────────────────────────



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
            'current_address', 'current_address_line2', 'current_village', 'current_district', 'current_state', 'current_pin_code',
            'permanent_address', 'permanent_address_line2', 'permanent_village', 'permanent_district', 'permanent_state', 'permanent_pin_code',
            'permanent_same_as_current',
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


class MyEmploymentLetterPdfView(APIView):
    """Streams a real, on-demand-rendered employment verification letter PDF
    for the caller's own record (see services_employment_letter.py — mirrors
    payroll's MyPayslipPdfView pattern). Backs the ESS Employment tab's
    "Employment verification letter" download row."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.services_employment_letter import render_employment_letter_pdf

        pdf_bytes = render_employment_letter_pdf(request.user)
        filename = f'employment-letter-{request.user.employee_id or request.user.pk}.pdf'
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        AuditLog.objects.create(
            user=request.user, action='employment_letter_downloaded', module='accounts',
            object_id=str(request.user.pk),
            changes={'employee_id': request.user.employee_id or ''},
            branch=request.user.branch or '',
            ip_address=get_client_ip(request),
        )
        return response


