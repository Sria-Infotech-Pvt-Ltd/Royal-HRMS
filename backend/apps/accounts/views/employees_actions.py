
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



# "Perform an action" modal's Confirmation reason options — new
# categorisation for this action, not previously defined anywhere.
CONFIRMATION_REASON_CHOICES = [
    ('probation_completed',  'Probation completed'),
    ('extended_probation',   'Extended probation'),
    ('other',                'Other'),
]


class EmployeeConfirmView(APIView):
    """POST /employees/<employee_id>/confirm/ — the Confirmation action
    (probation -> confirmed). A one-time flip, not a dated/effective-ranged
    record like Promotion/Salary — so it's logged via the existing generic
    AuditLog rather than a new dedicated history model (mirrors
    EmployeeRevealSensitiveView's own use of AuditLog for a similarly
    one-shot event)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.confirm'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if employee.employment_status == User.EMPLOYMENT_STATUS_CONFIRMED:
            return error('This employee is already confirmed.')

        effective_date_raw = (request.data.get('effective_date') or '').strip()
        if effective_date_raw:
            try:
                effective_date = datetime.strptime(effective_date_raw, '%Y-%m-%d').date()
            except ValueError:
                return error('effective_date must be in YYYY-MM-DD format.')
        else:
            effective_date = timezone.now().date()
        remarks = (request.data.get('remarks') or '').strip()
        # "Perform an action" modal's Reason field — Confirmation is a
        # one-shot flip with no dated history model of its own (see this
        # view's own docstring), so the reason is recorded on the AuditLog
        # entry rather than a new column, same as `remarks` already is.
        reason = (request.data.get('reason') or '').strip()
        if reason and reason not in dict(CONFIRMATION_REASON_CHOICES):
            return error('reason must be one of the recognised confirmation reasons.')

        employee.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        employee.confirmation_date = effective_date
        employee.save(update_fields=['employment_status', 'confirmation_date', 'updated_at'])

        AuditLog.objects.create(
            user       = request.user,
            action     = 'employee_confirmed',
            module     = 'employees',
            object_id  = str(employee.id),
            changes    = {
                'employee_id':       employee.employee_id,
                'full_name':         employee.full_name,
                'confirmation_date': effective_date.isoformat(),
                'remarks':           remarks,
                'reason':            reason,
            },
            branch     = employee.branch,
            ip_address = get_client_ip(request),
        )

        return success('Employee confirmed successfully.', data=_employee_dict(employee))


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

        records = (
            PromotionRecord.objects
            .filter(employee=employee)
            .select_related('promoted_by')
            .prefetch_related('salary_revisions')
        )
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
                # The CTC revision (if any) tagged as being for this specific
                # promotion — see EmployeeSalaryConfig.linked_promotion.
                'linked_ctc': (
                    str(next(iter(r.salary_revisions.all())).annual_ctc)
                    if r.salary_revisions.all() else None
                ),
            }
            for r in records
        ]
        return success('Promotion history retrieved.', data=data)


class EmployeeActionHistoryView(APIView):
    """GET /employees/<employee_id>/action-history/ — a real, unified
    lifecycle timeline for the Employee Drawer's "Action History" section:
    the original Hire (from the two-stage Hire flow's HireAction record
    when one exists — bulk-imported/directly-created employees have none,
    so that row falls back to their own date_of_joining/designation
    instead of inventing a reason) followed by every real PromotionRecord,
    in chronological order. Only the last row is marked "Current"."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _current_status_display(employee) -> str:
        """Same Active/Onboarding/Notice Period/Exited definition the
        Employee Directory table and EmployeeStatsView already use —
        deliberately not User.onboarding_status (the hiring *wizard's* own
        draft/submitted/complete progress, a different concept entirely)."""
        from apps.hrms.models import SEP_APPROVED

        if not employee.is_active:
            return 'Exited'
        if employee.must_change_password:
            return 'Onboarding'
        today = timezone.localdate()
        on_notice = employee.separation_requests.filter(
            status=SEP_APPROVED, proposed_last_working_day__gte=today,
        ).exists()
        return 'Notice Period' if on_notice else 'Active'

    def get(self, request, employee_id: str):
        is_self = request.user.employee_id == employee_id
        if not is_self and not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or (not is_self and _employee_out_of_branch_scope(request.user, employee)):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        rows = []
        hire_action = (
            HireAction.objects.filter(created_employee=employee)
            .select_related('position', 'position__org_unit')
            .first()
        )
        if hire_action:
            rows.append({
                'action_type':     'Hire',
                'reason_display':  hire_action.get_reason_display(),
                'position_title':  hire_action.position.title,
                'org_unit_name':   hire_action.position.org_unit.name,
                'status_display':  self._current_status_display(employee),
                'effective_from':  str(hire_action.effective_from),
            })
        elif employee.date_of_joining:
            current_placement = employee.placements.filter(effective_to__isnull=True).select_related(
                'position', 'position__org_unit',
            ).first()
            rows.append({
                'action_type':     'Hire',
                'reason_display':  '',
                'position_title':  current_placement.position.title if current_placement else employee.designation,
                'org_unit_name':   current_placement.position.org_unit.name if current_placement else employee.department,
                'status_display':  self._current_status_display(employee),
                'effective_from':  str(employee.date_of_joining),
            })

        for promo in PromotionRecord.objects.filter(employee=employee).order_by('effective_date'):
            rows.append({
                'action_type':     'Promotion',
                'reason_display':  f'{promo.previous_designation} → {promo.new_designation}',
                'position_title':  promo.new_designation,
                'org_unit_name':   '',
                'status_display':  '',
                'effective_from':  str(promo.effective_date),
            })

        for i, row in enumerate(rows):
            row['is_current'] = (i == len(rows) - 1)
            row['effective_to'] = '9999-12-31' if row['is_current'] else rows[i + 1]['effective_from']

        return success('Action history retrieved.', data=rows)


class EmployeeAuditTrailView(APIView):
    """GET /employees/<employee_id>/audit-trail/ — the Employee Drawer's
    "Audit Trail" section. Self-viewers (ESS "My Profile" → "Open full
    employee profile") get a real AuditLog row recorded for their own view
    every time this is called, then see their own record's most recent
    entries — mirrors EmployeeActionHistoryView's is_self bypass so an
    ordinary employee (who normally lacks audit.view) can see who/when their
    own record was looked at, without exposing the org-wide audit log. A
    viewer with audit.view (HR/Admin) can look up anyone's trail without
    logging a "view" event for themselves — only the self-service path
    is itself an event worth recording."""

    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        is_self = request.user.employee_id == employee_id
        if not is_self and not _has_perm(request.user, 'audit.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or (not is_self and _employee_out_of_branch_scope(request.user, employee)):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if is_self:
            AuditLog.objects.create(
                user=request.user, action='profile_viewed_self', module='employees',
                object_id=str(employee.id), branch=employee.branch or '',
            )

        rows = (
            AuditLog.objects
            .filter(module='employees', object_id=str(employee.id))
            .select_related('user', 'user__role')
            .order_by('-created_at')[:5]
        )
        return success('Audit trail retrieved.', data=AuditLogSerializer(rows, many=True).data)


class EmployeeRevealSensitiveView(APIView):
    """POST /employees/<employee_id>/reveal-sensitive/ — returns unmasked
    PAN/Aadhaar/bank details for one employee. The employee list/detail
    surfaces show these fields masked by default; this is the only path
    that returns the real values, gated by employees.view_sensitive
    (distinct from employees.view, which only lets you see the record at
    all) and logged to AuditLog every time, matching how every other
    reveal-worthy action in this app is audited (see branch/views.py)."""

    permission_classes = [IsAuthenticated]

    _FIELD_MAP = {
        'pan_number':          'pan_number',
        'name_as_per_aadhar':  'name_as_per_aadhar',
        'aadhaar_number':      'aadhaar_number',
        'account_number':      'account_number',
        'ifsc_code':           'ifsc_code',
        'pf_number':           'pf_number',
        'passport_number':     'passport_number',
    }

    def post(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.view_sensitive'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        requested = [f for f in (request.data.get('fields') or []) if f in self._FIELD_MAP]
        if not requested:
            return error('No valid fields requested.')

        profile = getattr(employee, 'profile', None)
        data = {f: (getattr(profile, self._FIELD_MAP[f], '') or '') if profile else '' for f in requested}

        AuditLog.objects.create(
            user=request.user, action='sensitive_reveal', module='employees',
            object_id=str(employee.id),
            changes={'fields': requested},
            ip_address=get_client_ip(request),
        )
        return success('Sensitive fields revealed.', data=data)


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
        object_id = request.query_params.get('object_id', '').strip()

        if module:
            qs = qs.filter(module=module)
        if object_id:
            # Per-record trail (e.g. Employee Detail's Audit Trail tab, keyed
            # by the employee's UUID — see AuditLog.objects.create(...,
            # object_id=str(employee.id), ...) at every employees-module call
            # site). Always paired with module in practice by the caller, but
            # not required here — object_id alone is still a meaningful filter.
            qs = qs.filter(object_id=object_id)
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
