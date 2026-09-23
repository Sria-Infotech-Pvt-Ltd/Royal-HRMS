
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

        # The Settings > Email Templates page has no "next page" control — it
        # fetches once and groups everything client-side by template_type. A
        # 20-row default silently truncated the flat (pre-grouping) queryset
        # once the template count passed 20, dropping entire categories
        # (recruitment, reminder, wish) off the response with no error.
        # Matches EmailTemplateCategoryListCreateView's default_page_size=50
        # for the same reason.
        page_obj, paginator = paginate(qs, request, default_page_size=100)

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
        content_error = _validate_file_content(file, file.content_type)
        if content_error:
            return error(content_error)
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
            if _validate_file_content(f, f.content_type):
                logger.warning('Attachment "%s" rejected — content does not match declared type "%s".', f.name, f.content_type)
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
            from apps.hrms.views.leave_shared import _can_approve_at_stage
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


