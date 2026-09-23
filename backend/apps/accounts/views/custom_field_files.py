
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

# ─── Custom Field File Values (file/image-type OnboardingFieldConfig fields) ──





class CustomFieldFileValueView(APIView):
    """
    GET    /onboarding/custom-file-fields/           → list all of this user's file-type custom values
    POST   /onboarding/custom-file-fields/           → upload a value for {field_key, file}
    GET    /onboarding/custom-file-fields/<value_id>/ → stream the file (signed storage proxy)
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
                dl_url = value.file.url
                r = http_req.get(dl_url, stream=True, timeout=30)
                r.raise_for_status()
            except http_req.exceptions.HTTPError as exc:
                logger.error('Custom field file storage fetch failed id=%s status=%s',
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


