
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

        employee.reporting_manager_from_org_chart = False
        employee.save(update_fields=['reporting_manager', 'reporting_manager_from_org_chart', 'updated_at'])
        logger.info(
            'Reporting manager for %s set to %s by %s',
            employee.employee_id,
            employee.reporting_manager.full_name if employee.reporting_manager else 'None',
            request.user.email,
        )
        return success('Reporting manager updated.', data=_employee_dict(employee))


