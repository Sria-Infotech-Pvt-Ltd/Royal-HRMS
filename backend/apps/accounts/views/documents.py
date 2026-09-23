
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

        try:
            # doc.file.url signs the request with the storage's private key,
            # bypassing any CDN-level access restrictions on the account.
            dl_url = doc.file.url
            r = http_req.get(dl_url, stream=True, timeout=30)
            r.raise_for_status()
        except http_req.exceptions.HTTPError as exc:
            logger.error('Document storage download failed pk=%s status=%s', pk, exc.response.status_code)
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


