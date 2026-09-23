
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


class OnboardingSectionListCreateView(APIView):
    """
    HR-only settings screen for HR-created custom onboarding sections/tabs —
    the sibling of OnboardingFieldConfigView, but for whole sections rather
    than individual fields within one. GET lists every custom section; POST
    creates one, server-assigning its `step` (never client-submitted) so it
    can never collide with the 5 reserved built-in step numbers (0-4).
    """
    permission_classes = [HasSettingsPermission]

    def get(self, request):
        from apps.accounts.serializers import OnboardingSectionSerializer
        from core.cache_service import OnboardingSectionCacheService
        sections = sorted(OnboardingSectionCacheService.get_all(), key=lambda s: (s.order, s.label))
        return success(
            'Onboarding sections retrieved.',
            OnboardingSectionSerializer(sections, many=True).data,
        )

    def post(self, request):
        from django.db.models import Max

        from apps.accounts.serializers import (
            OnboardingSectionCreateSerializer,
            OnboardingSectionSerializer,
        )
        from core.cache_service import OnboardingSectionCacheService

        serializer = OnboardingSectionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        data = serializer.validated_data

        max_step = OnboardingSection.objects.aggregate(m=Max('step'))['m']
        next_step = max(max_step or 4, 4) + 1
        max_order = OnboardingSection.objects.aggregate(m=Max('order'))['m']

        section = OnboardingSection.objects.create(
            step=next_step,
            label=data['label'],
            icon=data['icon'],
            order=(max_order or 0) + 1,
        )
        OnboardingSectionCacheService.invalidate()
        logger.info('Created onboarding section "%s" (step %s) by %s', section.label, section.step, request.user.email)
        return success(
            'Section created.', OnboardingSectionSerializer(section).data,
            http_status=status.HTTP_201_CREATED,
        )


class OnboardingSectionDetailView(APIView):
    permission_classes = [HasSettingsPermission]

    def _get_section(self, pk) -> 'OnboardingSection | None':
        return OnboardingSection.objects.filter(pk=pk).first()

    def patch(self, request, pk):
        from apps.accounts.serializers import (
            OnboardingSectionSerializer,
            OnboardingSectionUpdateSerializer,
        )
        from core.cache_service import OnboardingSectionCacheService

        section = self._get_section(pk)
        if not section:
            return error('Section not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = OnboardingSectionUpdateSerializer(section, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        OnboardingSectionCacheService.invalidate()
        logger.info('Updated onboarding section "%s" by %s', section.label, request.user.email)
        return success('Section updated.', OnboardingSectionSerializer(section).data)

    def delete(self, request, pk):
        from core.cache_service import OnboardingSectionCacheService

        section = self._get_section(pk)
        if not section:
            return error('Section not found.', http_status=status.HTTP_404_NOT_FOUND)
        if OnboardingFieldConfig.objects.filter(step=section.step).exists():
            return error(
                f'"{section.label}" still has fields under it — delete or move them first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        section.delete()
        OnboardingSectionCacheService.invalidate()
        logger.info('Deleted onboarding section "%s" by %s', section.label, request.user.email)
        return success('Section deleted.')


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


class EducationExperienceFieldConfigView(APIView):
    """
    Show/require toggles for Education/Experience list-entry fields — see
    EducationExperienceFieldConfig's own docstring for what this does and
    doesn't cover (no add/remove, unlike OnboardingFieldConfigView).

    GET is open to any authenticated user (both onboarding wizards need it
    to decide what to show/require, same reasoning as
    OnboardingFieldConfigPublicView above); PATCH is HR-only.
    """
    def get_permissions(self):
        if self.request.method == 'PATCH':
            return [HasSettingsPermission()]
        return [IsAuthenticated()]

    def get(self, request):
        from apps.accounts.models import EducationExperienceFieldConfig as CFG
        from apps.accounts.serializers import EducationExperienceFieldConfigSerializer as Ser
        configs = list(CFG.objects.all().order_by('list_type', 'order'))
        data = {
            'education':  Ser([c for c in configs if c.list_type == CFG.LIST_EDUCATION], many=True).data,
            'experience': Ser([c for c in configs if c.list_type == CFG.LIST_EXPERIENCE], many=True).data,
        }
        return success('Education/Experience field configuration retrieved.', data=data)

    def patch(self, request, config_id: str):
        from apps.accounts.models import EducationExperienceFieldConfig as CFG
        from apps.accounts.serializers import EducationExperienceFieldConfigSerializer as Ser
        try:
            config = CFG.objects.get(pk=config_id)
        except (CFG.DoesNotExist, ValueError, ValidationError):
            return error('Field not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = Ser(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        logger.info(
            'Updated education/experience field "%s.%s" (visible=%s, required=%s) by %s',
            config.list_type, config.field_key, config.visible, config.required, request.user.email,
        )
        return success('Field updated.', Ser(config).data)


class OnboardingSectionPublicView(APIView):
    """
    Active custom onboarding sections — used by both onboarding wizards (the
    self-service one and the HR-on-behalf mirror) to render extra tabs
    beyond the 4 built-ins. Every onboarding employee needs this regardless
    of role, same reasoning as OnboardingFieldConfigPublicView above; only
    active sections are returned since (unlike a field) a section has no
    "hidden but shown while loading" ambiguity to guard against.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.serializers import OnboardingSectionSerializer
        from core.cache_service import OnboardingSectionCacheService

        sections = sorted(
            (s for s in OnboardingSectionCacheService.get_all() if s.is_active),
            key=lambda s: (s.order, s.label),
        )
        return success('Onboarding sections retrieved.', OnboardingSectionSerializer(sections, many=True).data)


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


