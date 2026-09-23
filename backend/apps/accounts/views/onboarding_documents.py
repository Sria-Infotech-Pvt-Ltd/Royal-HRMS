
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

# ─── Onboarding — Document upload / stream / delete ──────────────────────────

class EmployeeDocumentView(APIView):
    """
    GET  /onboarding/documents/           → list all documents for this user
    POST /onboarding/documents/           → upload a document
    GET  /onboarding/documents/<doc_id>/  → stream the file (signed storage proxy)
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

        # ── Detail: stream the file through a signed storage URL ─────────────
        if doc_id:
            doc, err = self._get_doc(request, doc_id)
            if err:
                return err

            name  = doc.file.name
            parts = os.path.basename(name).rsplit('.', 1)
            fmt   = parts[1].lower() if len(parts) == 2 else ''

            try:
                dl_url = doc.file.url
                r = http_req.get(dl_url, stream=True, timeout=30)
                r.raise_for_status()
            except http_req.exceptions.HTTPError as exc:
                logger.error('Employee doc storage fetch failed doc=%s status=%s',
                             doc_id, exc.response.status_code)
                return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)
            except Exception as exc:
                logger.error('Employee doc download error doc=%s: %s', doc_id, exc, exc_info=True)
                return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)

            # Audit who actually opened this specific sensitive document (PAN
            # card, Aadhaar, bank proof, etc.) — separate from and in addition
            # to the existing permission check above, which only records who
            # is *allowed* to view it, not who actually did and when. Logged
            # only once the fetch from storage has actually succeeded, so
            # a 404/permission-denied/upstream-error attempt above never
            # creates a misleading "viewed" record.
            AuditLog.objects.create(
                user=request.user, action='document_viewed', module='accounts',
                object_id=str(doc.id),
                changes={
                    'document_type': doc.document_type,
                    'document_owner': doc.user.email,
                    'file_name': doc.file_name,
                },
                ip_address=get_client_ip(request),
            )

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




