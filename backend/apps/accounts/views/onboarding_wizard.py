
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



# ─── Onboarding — Employee fills their own profile ────────────────────────────
# (_BUILTIN_STEPS/_STEP_4_FIELDS/_NULLABLE_PROFILE_FIELDS live in shared.py —
# used by the step-helper functions that live there too.)































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

        if step not in _valid_steps():
            return error(
                f'Invalid step {step}.',
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
            if step not in _valid_steps():
                return error(
                    f'Invalid step {step}.',
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
        if step not in _valid_steps():
            return error(
                f'Invalid step {step}.',
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
        if step not in _valid_steps():
            return error(
                f'Invalid step {step}.',
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
        return _submit_onboarding(request.user)






