
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

# ─── Global Approval Workflow Rules ──────────────────────────────────────────
# (_WORKFLOW_ORDER lives in shared.py — used by _ensure_default_rules/
# _serialize_rule there too, not just EmployeeApprovalMatrixView below.)






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


# (_EMP_IMPORT_COL_MAP lives in shared.py — used by
# _normalize_employee_import_headers there. _EMP_MAX_IMPORT_ROWS/BYTES moved
# to bulk_import.py, the only place that actually uses them.)

