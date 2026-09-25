
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

# Bank fields gated behind HR review when a self-service edit would overwrite
# an already-filled value — see the bank-change verification gate in
# _save_profile_step() and EmployeeProfile.submit_bank_change().
_BANK_FIELDS = frozenset((
    'account_number', 'ifsc_code', 'bank_name', 'bank_branch_name',
    'account_holder_name', 'account_type',
))


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


def _auto_assign_managers(employee: 'User') -> list:
    """
    Auto-assign hr and reporting_manager on the employee object (in memory only).

    HR (all roles): set from Branch.hr if available, otherwise first active hr
    user in the same branch.
    reporting_manager (non-managers only):
      - Requires both branch and department to be set.
      - Branch must have exactly 1 manager__team_lead (ambiguous if multiple).
      - Prefers dept manager (same branch).

    Returns a list of field names that were modified — caller must include them in save().
    """
    from apps.branch.models import Branch

    emp_branch = (employee.branch or '').strip()
    emp_dept   = (employee.department or '').strip()

    changed = []

    # HR assignment: try Branch.hr first, then first active hr user in same branch.
    if employee.hr_id is None and emp_branch:
        branch_obj = Branch.objects.select_related('hr').filter(
            branch_name__iexact=emp_branch
        ).first()
        hr_user = branch_obj.hr if branch_obj else None
        if not hr_user:
            hr_user = User.objects.filter(
                role__role_permissions__permission__codename='employees.edit',
                branch__iexact=emp_branch, is_active=True,
            ).first()
        if hr_user and hr_user.pk != employee.pk:
            employee.hr = hr_user
            changed.append('hr')

    # Managers are the reporting manager for others — they have none themselves.
    if employee.role and employee.role.can_manage_team:
        return changed

    # Need at least a branch to find a manager.
    if not emp_branch:
        return changed

    # Skip if reporting_manager already set.
    if employee.reporting_manager_id is not None:
        return changed

    assigned = None
    from_org_chart = False

    # 1. Org Unit chief in same branch (most specific — preferred).
    if emp_dept:
        from apps.accounts.services_approval import resolve_employee_org_unit_chief
        chief = resolve_employee_org_unit_chief(employee)
        if (
            chief and chief.pk != employee.pk
            and chief.is_active
            and (chief.branch or '').strip().lower() == emp_branch.lower()
        ):
            assigned = chief
            from_org_chart = True

    # 2. Fallback: first active manager in the branch (deterministic by id).
    #    Handles branches with multiple managers when no dept-level manager is set.
    if assigned is None:
        assigned = (
            User.objects
            .filter(role__can_manage_team=True, branch__iexact=emp_branch, is_active=True)
            .exclude(pk=employee.pk)
            .order_by('id')
            .first()
        )
        from_org_chart = False

    if assigned is not None:
        employee.reporting_manager = assigned
        employee.reporting_manager_from_org_chart = from_org_chart
        changed.append('reporting_manager')
        changed.append('reporting_manager_from_org_chart')

    return changed


def _document_dict(doc) -> dict:
    """Shared shape for a single EmployeeDocument, used by _employee_dict() and
    EmployeeProfileDocumentView so the profile page and the upload response always
    match the ApiDocument shape the frontend expects."""
    try:
        file_url = doc.file.url if doc.file else ''
    except Exception:
        logger.warning('Signed URL failed for employee document %s', doc.id, exc_info=True)
        file_url = ''
    from core.cache_service import DocumentTypeConfigCacheService
    return {
        'id':                    doc.id,
        'document_type':         doc.document_type,
        'document_type_display': DocumentTypeConfigCacheService.label_for(doc.document_type),
        'file':                  file_url,
        'file_name':             doc.file_name,
        'file_size':             doc.file_size,
        'uploaded_at':           doc.uploaded_at.isoformat() if doc.uploaded_at else '',
    }


def _custom_field_file_dict(v) -> dict:
    """Shared shape for a single CustomFieldFileValue — mirrors _document_dict()
    keyed by field_key instead of document_type, used by _employee_dict() so
    the HR Employee Detail page gets every step's file-type custom values in
    the one existing GET, same as `documents` today."""
    try:
        file_url = v.file.url if v.file else ''
    except Exception:
        logger.warning('Signed URL failed for custom field file %s', v.id, exc_info=True)
        file_url = ''
    return {
        'id':          v.id,
        'field_key':   v.field_key,
        'file':        file_url,
        'file_name':   v.file_name,
        'file_size':   v.file_size,
        'uploaded_at': v.uploaded_at.isoformat() if v.uploaded_at else '',
    }


def _employee_dict(user: User) -> dict:
    parts = user.full_name.strip().split(' ', 1)
    first = parts[0]
    last  = parts[1] if len(parts) > 1 else ''
    if user.is_active and user.must_change_password:
        emp_status = 'onboarding'
    elif not user.is_active:
        emp_status = 'inactive'
    else:
        emp_status = 'active'

    try:
        p = user.profile
    except Exception:
        p = None

    profile_data = {
        # Personal
        'date_of_birth':     str(p.date_of_birth) if (p and p.date_of_birth) else '',
        'gender':            p.gender            if p else '',
        'marital_status':    p.marital_status    if p else '',
        'father_name':       p.father_name       if p else '',
        'blood_group':       p.blood_group       if p else '',
        'nationality':       p.nationality       if p else '',
        'current_address':   p.current_address   if p else '',
        'current_address_line2': p.current_address_line2 if p else '',
        'current_village':   p.current_village   if p else '',
        'current_district':  p.current_district  if p else '',
        'current_state':     p.current_state     if p else '',
        'current_pin_code':  p.current_pin_code  if p else '',
        'permanent_address': p.permanent_address if p else '',
        'permanent_address_line2': p.permanent_address_line2 if p else '',
        'permanent_village':  p.permanent_village  if p else '',
        'permanent_district': p.permanent_district if p else '',
        'permanent_state':    p.permanent_state    if p else '',
        'permanent_pin_code': p.permanent_pin_code if p else '',
        'permanent_same_as_current': p.permanent_same_as_current if p else False,
        # Education
        'highest_qualification': p.highest_qualification if p else '',
        'institution':           p.institution           if p else '',
        'year_of_passing':       p.year_of_passing       if p else None,
        'specialization':        p.specialization        if p else '',
        # Experience
        'total_experience_years': (
            str(p.total_experience_years) if (p and p.total_experience_years is not None) else ''
        ),
        'previous_employer':    p.previous_employer    if p else '',
        'previous_designation': p.previous_designation if p else '',
        'leaving_reason':       p.leaving_reason       if p else '',
        # Bank
        'account_holder_name': p.account_holder_name if p else '',
        'account_type':        p.account_type        if p else '',
        'account_number':      p.account_number      if p else '',
        'ifsc_code':           p.ifsc_code           if p else '',
        'bank_name':           p.bank_name           if p else '',
        'bank_branch_name':    p.bank_branch_name    if p else '',
        'bank_change_status':       p.bank_change_status       if p else '',
        'bank_change_requested_at': p.bank_change_requested_at if p else None,
        # PAN is otherwise write-only (never surfaced on any read view) —
        # this masked preview is always safe to include regardless of
        # viewer permission; the real value only ever comes back from
        # EmployeeRevealSensitiveView, gated by employees.view_sensitive.
        'pan_masked': (
            f'{p.pan_number[:5]}••••{p.pan_number[-1]}'
            if (p and p.pan_number and len(p.pan_number) >= 6) else ''
        ),
        # Aadhaar/PF number/passport are the same PII tier as PAN — masked
        # previews only here; real values come back exclusively from
        # EmployeeRevealSensitiveView, gated by employees.view_sensitive.
        'aadhaar_masked': (
            f'XXXX XXXX {p.aadhaar_number[-4:]}'
            if (p and p.aadhaar_number and len(p.aadhaar_number) >= 4) else ''
        ),
        'pf_masked': (
            f'••••{p.pf_number[-4:]}'
            if (p and p.pf_number and len(p.pf_number) >= 4) else ''
        ),
        # Statutory declarations — not PII-tier, safe to show plainly.
        'pf_covered':  p.pf_covered  if p else True,
        'esi_covered': p.esi_covered if p else False,
        'is_disabled':                   p.is_disabled                   if p else False,
        'disability_type':               p.disability_type               if p else '',
        'disability_percentage':         p.disability_percentage         if p else None,
        'disability_certificate_number': p.disability_certificate_number if p else '',
        'is_international_worker':      p.is_international_worker      if p else False,
        'international_worker_country': p.international_worker_country if p else '',
        'passport_expiry': str(p.passport_expiry) if (p and p.passport_expiry) else '',
        # Emergency Contact
        'emergency_name':         p.emergency_name         if p else '',
        'emergency_relationship': p.emergency_relationship if p else '',
        'emergency_phone':        p.emergency_phone        if p else '',
        'emergency_email':        p.emergency_email        if p else '',
        'personal_email':         p.personal_email         if p else '',
        # HR-created custom fields (Settings > Onboarding Fields) — see
        # OnboardingFieldConfig/EmployeeProfile.custom_field_values.
        'custom_field_values': (p.custom_field_values or {}) if p else {},
    }

    try:
        documents = [_document_dict(doc) for doc in user.employee_documents.all()]
    except Exception:
        documents = []
    try:
        custom_file_fields = [_custom_field_file_dict(v) for v in user.custom_field_files.all()]
    except Exception:
        custom_file_fields = []
    mgr = getattr(user, 'reporting_manager', None)
    _hr = getattr(user, 'hr', None)
    approver = getattr(user, 'reporting_approver', None)

    # Current Position/Org Unit — used by Employee Detail's "Reassign
    # Position" modal (PromotionTab.tsx) to prefill Org Unit/Position to
    # what this employee already holds, instead of always starting blank.
    # None for a Company Code Admin (no Position at all) or anyone with no
    # open Placement.
    current_placement = user.placements.filter(effective_to__isnull=True).select_related(
        'position', 'position__org_unit', 'position__org_unit__parent',
    ).first()
    current_org_unit = current_placement.position.org_unit if current_placement else None

    # The Employee Directory table shows the org unit's own name bold with
    # its immediate parent unit as a gray subtext (e.g. "AI & ML" / "Software
    # Services") — the real OrgUnit hierarchy, not a second copy of the same
    # department string.
    org_unit_name = current_org_unit.name if current_org_unit else None
    org_unit_parent_name = current_org_unit.parent.name if (current_org_unit and current_org_unit.parent) else None

    # The Employee Directory table shows "Last day dd/mm/yyyy" in place of a
    # reporting manager for anyone on notice period. Deliberately matches
    # EmployeeStatsView's own "notice_period" count below (SEP_APPROVED
    # only) — a merely-requested-but-not-yet-approved separation isn't a
    # confirmed exit yet, and showing a "Notice Period" row here for one
    # while the KPI card doesn't count it would be a real inconsistency.
    from apps.hrms.models import SEP_APPROVED

    today = timezone.localdate()
    active_separation = (
        user.separation_requests
        .filter(status=SEP_APPROVED, proposed_last_working_day__gte=today)
        .order_by('proposed_last_working_day')
        .first()
    )

    result = {
        'id':             user.employee_id,
        'uuid':           str(user.id),
        'employee_id':    user.employee_id,
        'first_name':     first,
        'last_name':      last,
        'full_name':      user.full_name,
        'email':          user.email,
        'phone':          user.phone,
        # Public ImageKit URL (or None) — same field name/shape as
        # MyProfileSerializer.profile_photo_url, so every consumer of this
        # dict (Employee Directory, Employee full-profile drawer/page) can
        # render the real uploaded photo instead of always falling back to
        # initials. profile_photo's storage backend (ImageKitStorage) is
        # public-by-design and already returns an absolute CDN URL, so no
        # request.build_absolute_uri() wrapping is needed here.
        'profile_photo_url': user.profile_photo.url if user.profile_photo else None,
        'department':     user.department,
        'designation':    user.designation,
        'position_id':    str(current_placement.position_id) if current_placement else None,
        'org_unit_id':    str(current_placement.position.org_unit_id) if current_placement else None,
        'branch':         user.branch,
        'work_location':  user.work_location,
        'employee_type':  user.employee_type,
        'role':           user.role.name         if user.role else '',
        'role_display':   user.role.display_name if user.role else '',
        'date_of_joining': str(user.date_of_joining) if user.date_of_joining else '',
        'date_joined':    user.date_joined.date().isoformat(),
        'is_active':      user.is_active,
        'status':         emp_status,
        'hr': {
            'id':   _hr.employee_id if _hr else None,
            'uuid': str(_hr.id)     if _hr else None,
            'name': _hr.full_name   if _hr else None,
        },
        'reporting_approver': {
            'id':   approver.employee_id if approver else None,
            'uuid': str(approver.id)     if approver else None,
            'name': approver.full_name   if approver else None,
        },
        'profile':            profile_data,
        'documents':          documents,
        'custom_file_fields': custom_file_fields,
        'onboarding_status':  user.onboarding_status,
        'employment_status':  user.employment_status,
        'confirmation_date':  user.confirmation_date.isoformat() if user.confirmation_date else None,
        'last_working_day':   active_separation.proposed_last_working_day.isoformat() if active_separation else None,
        'org_unit_name':        org_unit_name,
        'org_unit_parent_name': org_unit_parent_name,
        # Real Position.grade (e.g. "L2") this employee currently holds —
        # None when unassigned, rather than a fabricated pay-scale string.
        'position_grade': current_placement.position.grade if (current_placement and current_placement.position.grade) else None,
    }

    # Managers ARE the reporting manager for others — they have no reporting manager themselves.
    if not (user.role and user.role.can_manage_team):
        result['reporting_manager'] = {
            'id':   mgr.employee_id if mgr else None,
            'uuid': str(mgr.id)     if mgr else None,
            'name': mgr.full_name   if mgr else None,
            # True only when resolved from an actual placed chief in this
            # employee's Org Unit chain — see User.reporting_manager_from_org_chart.
            'from_org_chart': bool(mgr) and user.reporting_manager_from_org_chart,
        }

    return result


def _login_assessment_status(user) -> str:
    """Return the correct assessment_status string for the login response."""
    from django.db.models import Q as _Q
    from apps.assessments.models import CandidateAssignment
    from apps.recruitment.models import Candidate

    pending_statuses = [CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]

    candidate = Candidate.objects.filter(portal_user=user).first()
    if candidate:
        # Check both FKs — a recruited employee may have assignments on either
        if CandidateAssignment.objects.filter(
            _Q(candidate=candidate) | _Q(employee=user), status__in=pending_statuses,
        ).exists():
            return User.ASSESSMENT_PENDING
    else:
        if CandidateAssignment.objects.filter(employee=user, status__in=pending_statuses).exists():
            return User.ASSESSMENT_PENDING

    return User.ASSESSMENT_COMPLETE


def _parse_as_of(request):
    """Returns (date_or_None, error_response_or_None)."""
    raw = request.query_params.get('asOf')
    if not raw:
        return None, None
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, error('asOf must be a valid YYYY-MM-DD date.')


def _get_employee(identifier: str):
    """Look up an employee by employee_id code (e.g. EMP001)."""
    try:
        return (
            User.objects
            .select_related('role', 'profile', 'reporting_manager', 'hr')
            .prefetch_related('employee_documents')
            .prefetch_related('custom_field_files')
            .get(employee_id=identifier)
        )
    except User.DoesNotExist:
        return None


def _employee_out_of_branch_scope(requesting_user, employee) -> bool:
    """
    Mirrors the scoping already applied to EmployeeListCreateView.get():
    managers (role.can_manage_team) may only act on their own direct reports,
    and everyone else without settings.edit is scoped to their own branch.
    Returns True when the employee should be treated as not found for this
    requester.

    A submitted-but-not-yet-approved onboarding candidate has no
    employee.branch yet (it's only copied over from the linked Candidate at
    approval time) — fall back to the source candidate's branch so HR can
    still see/act on their own branch's pending submissions.
    """
    role = requesting_user.role
    if role and role.can_manage_team:
        return employee.reporting_manager_id != requesting_user.id
    if not _has_perm(requesting_user, 'settings.edit') and requesting_user.branch:
        employee_branch = employee.branch
        if not employee_branch:
            candidate = employee.candidate_portal.first()
            if candidate and candidate.branch:
                employee_branch = candidate.branch.branch_name
        return employee_branch != requesting_user.branch
    return False


def _mask_bank_fields(data: dict) -> dict:
    """Masks profile.account_number/profile.ifsc_code in place (e.g.
    '••••7734') — used when one user views another's record without
    employees.view_sensitive. Never applied to a user's own profile view or
    to the response of an edit they just performed themselves (see
    EmployeeDetailView.get()'s call site) — those legitimately need the real
    values. Bank fields live under the nested 'profile' dict, not top-level
    (see _employee_dict()'s profile_data/result split)."""
    profile = data.get('profile') or {}
    acct = profile.get('account_number') or ''
    ifsc = profile.get('ifsc_code') or ''
    profile['account_number'] = f'••••{acct[-4:]}' if len(acct) >= 4 else ('••••' if acct else '')
    profile['ifsc_code'] = '•' * len(ifsc) if ifsc else ''
    return data


# The 5 built-in step numbers (0-3 field steps + 4/Documents) are structural
# to the wizard — unlike which FIELDS live in each step, this isn't something
# HR customizes, so it stays a plain constant. HR *can* add custom sections
# on top (see OnboardingSection) — _valid_steps()/_step_labels() below widen
# these built-ins with whatever active custom sections currently exist.
_BUILTIN_STEPS = frozenset({0, 1, 2, 3, 4})

# Step 4 — Documents. pan_number is the one exception to "documents are
# handled separately via EmployeeDocument records": real-world onboarding
# captures the PAN *number* at the moment the PAN card proof is uploaded, not
# later — so the frontend saves it here, right before the upload request for
# that specific document. Not customizable, same reasoning as _BUILTIN_STEPS.
_STEP_4_FIELDS = frozenset({'pan_number'})

# Profile fields that are nullable in the DB (null=True).
# Empty string from the frontend is converted to None for these fields so they
# can be cleared properly. All other profile fields are CharField(blank=True)
# which stores '' — never None.
_NULLABLE_PROFILE_FIELDS = frozenset({
    'date_of_birth',
    'year_of_passing',
    'total_experience_years',
    'disability_percentage',
    'passport_expiry',
})


def _valid_steps() -> frozenset:
    from core.cache_service import OnboardingSectionCacheService
    return _BUILTIN_STEPS | OnboardingSectionCacheService.get_active_steps()


def _custom_field_steps() -> list:
    """Active custom section step numbers, sorted — the field-bearing steps
    beyond the 4 built-ins (0-3), i.e. excluding Documents (4) which is never
    customizable this way. OnboardingSection also holds label/icon-override
    rows for the 4 built-ins themselves (steps 0-3, seeded so their Settings
    tab can be renamed) — those are filtered out here so callers combining
    this with the literal [0, 1, 2, 3] prefix never double-count them."""
    from core.cache_service import OnboardingSectionCacheService
    return sorted(s for s in OnboardingSectionCacheService.get_active_steps() if s not in _BUILTIN_STEPS)


def _step_labels() -> dict:
    from core.cache_service import OnboardingSectionCacheService
    labels = dict(OnboardingFieldConfig.STEP_CHOICES)
    labels.update({s.step: s.label for s in OnboardingSectionCacheService.get_all() if s.is_active})
    return labels


def _step_configs(step: int) -> list:
    """All OnboardingFieldConfig rows for steps 0-3, any visibility — cached."""
    from core.cache_service import OnboardingFieldConfigCacheService
    return OnboardingFieldConfigCacheService.get_for_step(step)


def _step_all_field_keys(step: int) -> frozenset:
    if step == 4:
        return _STEP_4_FIELDS
    keys = frozenset(c.field_key for c in _step_configs(step))
    if step == 0:
        # permanent_same_as_current has no OnboardingFieldConfig row of its
        # own (it's a structural toggle, not a collectible field HR would
        # reorder/hide/require) — added explicitly so the request-filtering
        # loop below doesn't silently drop it.
        keys = keys | {'permanent_same_as_current'}
    return keys


def _step_required_configs(step: int) -> list:
    """Visible AND required configs for a step — what actually gates completion.
    Checking both (not just `required`) means a field HR hid can never block
    submission, even if `required` was left on from before it was hidden."""
    if step == 4:
        return []
    return [c for c in _step_configs(step) if c.visible and c.required]


def _step_custom_field_keys(step: int) -> frozenset:
    """Custom field_keys for a step, EXCLUDING file-type ones — file values
    live in CustomFieldFileValue, never in EmployeeProfile.custom_field_values,
    so a JSON-body request touching one of these keys must be dropped rather
    than merged (same trust-boundary pattern as MyProfileView.patch's
    step-scoping below)."""
    if step == 4:
        return frozenset()
    return frozenset(
        c.field_key for c in _step_configs(step)
        if c.is_custom and c.field_type != OnboardingFieldConfig.TYPE_FILE
    )


def _step_file_field_keys(step: int) -> frozenset:
    """The file-type custom field_keys _step_custom_field_keys() excludes —
    used wherever a caller needs to handle them separately (they have no real
    EmployeeProfile column and no custom_field_values entry; their values
    live entirely in CustomFieldFileValue rows)."""
    if step == 4:
        return frozenset()
    return frozenset(
        c.field_key for c in _step_configs(step)
        if c.is_custom and c.field_type == OnboardingFieldConfig.TYPE_FILE
    )


def _field_value(profile, config: 'OnboardingFieldConfig'):
    if config.is_custom:
        if config.field_type == OnboardingFieldConfig.TYPE_FILE:
            from apps.accounts.models import CustomFieldFileValue
            return CustomFieldFileValue.objects.filter(
                user=profile.user, field_key=config.field_key
            ).exists() or None
        return (profile.custom_field_values or {}).get(config.field_key)
    return getattr(profile, config.field_key, None)


def _file_type_custom_field_keys() -> frozenset:
    """All is_custom field_keys (any step) whose field_type is 'file' — used
    to strip file-type keys out of any custom_field_values JSON payload
    before merging, since file values live in CustomFieldFileValue and never
    belong in this dict (see _field_value())."""
    from core.cache_service import OnboardingFieldConfigCacheService
    return frozenset(
        c.field_key for c in OnboardingFieldConfigCacheService.get_all()
        if c.is_custom and c.field_type == OnboardingFieldConfig.TYPE_FILE
    )


def _missing_required(profile, step: int) -> list:
    """Human-readable '<label> (<step name>)' strings for required-but-empty
    fields in this step — same format the old hardcoded _submit() checks used."""
    step_label = _step_labels().get(step, '')
    missing = []
    for c in _step_required_configs(step):
        if not _field_filled(_field_value(profile, c)):
            missing.append(f'{c.label} ({step_label})' if step_label else c.label)
    return missing


def _step_is_complete(profile, step: int) -> bool:
    return not _missing_required(profile, step)


def _extract_step_data(profile, all_data: dict, step: int) -> dict:
    """
    Built-in field values come from `all_data` (an EmployeeProfileSerializer
    .data dict); custom field values have no serializer field of their own,
    so they're read out of profile.custom_field_values and flattened in
    alongside the built-in ones — the frontend doesn't need to know which is
    which.
    """
    step_fields = _step_all_field_keys(step)
    custom_keys = _step_custom_field_keys(step)
    data = {k: v for k, v in all_data.items() if k in step_fields}
    for key in custom_keys:
        data[key] = (profile.custom_field_values or {}).get(key)
    # Not an OnboardingFieldConfig-driven field (no HR-configurable step it
    # belongs to) but the bank step's own UI needs it on every response to
    # know whether to show "pending HR review" instead of the live values.
    if 'account_number' in step_fields:
        data['bank_change_status'] = all_data.get('bank_change_status')
        data['bank_change_requested_at'] = all_data.get('bank_change_requested_at')
    return data


def _field_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _missing_required_docs(user) -> list:
    """
    Human-readable labels for required-but-not-yet-uploaded document types
    (visible+required DocumentTypeConfig rows the user has no
    EmployeeDocument for) — the Step-5 equivalent of _missing_required()
    above. Single shared implementation for what used to be three duplicated
    hardcoded PAN/Aadhaar/Degree/conditional-Experience checks (in this
    function, _save_profile_step's step-4 branch, and OnboardingView._submit)
    — document types and their required-ness are now configurable per
    company via DocumentTypeConfig, so there is no hardcoded type list left
    to check against, and no conditional experience-based special case
    (dropped in favor of a plain per-type required flag, same as every other
    onboarding field).
    """
    from apps.accounts.models import EmployeeDocument as ED
    from core.cache_service import DocumentTypeConfigCacheService
    uploaded = set(ED.objects.filter(user=user).values_list('document_type', flat=True))
    return [
        c.label for c in DocumentTypeConfigCacheService.get_all()
        if c.visible and c.required and c.type_key not in uploaded
    ]


def _missing_education_experience(user) -> list:
    """
    Human-readable labels for the one required Education check — the
    bespoke-step equivalent of _missing_required_docs() above, now that
    Education/Experience are their own components (views_education_experience.py),
    not generic OnboardingFieldConfig step 1. At least one EducationRecord
    with institution filled must exist — matches step 1's original
    required=True fields' intent (some education must be on file), just
    checked against "any one entry in the list" instead of one hardcoded
    scalar. Experience stays fully optional, matching step 1's original
    config too (none of those 4 fields were required).
    """
    from apps.accounts.models import EducationRecord
    has_valid_education = EducationRecord.objects.filter(employee=user).exclude(institution='').exists()
    return [] if has_valid_education else ['At least one education entry (institution name)']


def _compute_completed_steps(profile, user) -> list:
    """
    Derive which wizard steps already satisfy their required fields,
    without persisting a separate progress field — completion is always
    recomputed from the profile/document/education data that is already
    saved. `1` (the old generic Education & Experience step) is
    deliberately absent from field_steps — Education is now its own
    bespoke step (see _missing_education_experience above), reported here
    under its own sentinel `-2`, mirroring how Documents reports as `4`
    and Face ID would as `-1` if it round-tripped through this at all.
    """
    field_steps = [0, 2, 3] + _custom_field_steps()
    completed = [step for step in field_steps if _step_is_complete(profile, step)]
    if not _missing_required_docs(user):
        completed.append(4)
    if not _missing_education_experience(user):
        completed.append(-2)
    return completed


def _submit_onboarding(target_user):
    """
    Validate and submit target_user's onboarding wizard. Extracted from
    OnboardingView._submit so HREmployeeOnboardingView (HR completing
    onboarding on someone else's behalf) gets identical required-field/
    document/face-ID validation with no duplicated logic — see
    OnboardingView._submit, now a one-line delegator to this function.
    """
    if target_user.onboarding_status == User.ONBOARDING_COMPLETE:
        return error('Onboarding is already complete.')
    if target_user.onboarding_status == User.ONBOARDING_SUBMITTED:
        return error('Onboarding already submitted and awaiting approval.')

    from apps.accounts.models import EmployeeProfile as EP
    try:
        profile = EP.objects.get(user=target_user)
    except EP.DoesNotExist:
        return error('Please fill in your profile details before submitting.')

    missing = []
    for step in [0, 2, 3] + _custom_field_steps():
        missing.extend(_missing_required(profile, step))

    if missing:
        return error(
            f'Please complete the following required fields before submitting: '
            f'{", ".join(missing)}.'
        )

    missing_education = _missing_education_experience(target_user)
    if missing_education:
        return error(
            f'Please complete the following before submitting: '
            f'{", ".join(missing_education)}.'
        )

    missing_docs = _missing_required_docs(target_user)
    if missing_docs:
        return error(
            f'Please upload the following required documents before submitting: '
            f'{", ".join(missing_docs)}.'
        )

    # Face ID registration — only required when the admin's org-wide
    # "Face ID Verification" toggle (Attendance Settings) is mandatory.
    # Approval isn't required at this point, only that a request was
    # submitted — same "uploaded, not yet approved, is enough" bar as
    # the documents check above.
    from apps.attendance.services_face_matching import is_face_verification_mandatory
    if is_face_verification_mandatory():
        from apps.attendance.models import FaceRegistrationRequest
        has_face_registration = FaceRegistrationRequest.objects.filter(employee=target_user).exists()
        if not has_face_registration:
            return error(
                'Please complete Face ID registration before submitting your onboarding profile.'
            )

    User.objects.filter(pk=target_user.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)
    logger.info('User %s submitted onboarding wizard', target_user.email)

    # Notify HR via Celery so SMTP latency doesn't delay the response.
    from apps.accounts.tasks import send_onboarding_submitted_notification_task

    def _queue_hr_notification(user_id=target_user.pk):
        try:
            # retry=False + ignore_result=True — bounds broker/backend
            # retries so a down Redis can't block this request; see the
            # referral-submission dispatch in recruitment/views.py.
            send_onboarding_submitted_notification_task.apply_async(
                args=[user_id], retry=False, ignore_result=True,
            )
        except Exception as exc:
            logger.error(
                'Failed to queue onboarding_submitted notification for user %s: %s',
                user_id, exc, exc_info=True,
            )

    transaction.on_commit(_queue_hr_notification)

    return success('Onboarding submitted. Awaiting HR approval.')


def _save_profile_step(request, step: int, target_user=None):
    """
    target_user: whose EmployeeProfile is being saved — defaults to
    request.user (self-service, the only caller before HREmployeeOnboardingView
    existed). When HR/Admin is completing onboarding on someone else's behalf,
    target_user is the employee, while request.user remains the acting HR/Admin
    — used only where the actor themselves matters (profile._changed_by below),
    never for whose data is being read/written.
    """
    from apps.accounts.models import EmployeeProfile as EP
    from apps.accounts.serializers import EmployeeProfileSerializer

    target_user = target_user or request.user

    # ── Status guard ───────────────────────────────────────────────────────────
    if target_user.onboarding_status == User.ONBOARDING_COMPLETE:
        return error(
            'Onboarding is already complete and cannot be modified.',
            http_status=status.HTTP_403_FORBIDDEN,
        )

    # ── Step range validation ──────────────────────────────────────────────────
    if step not in _valid_steps():
        return error(
            f'Invalid step {step}.',
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Request body must be a key-value mapping ───────────────────────────────
    if not hasattr(request.data, 'items'):
        return error(
            'Request body must be a JSON object.',
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    # ── Step 4 — document verification, plus PAN capture ───────────────────────
    if step == 4:
        # A request carrying pan_number is the frontend saving/validating the
        # number right before it uploads the PAN card file — a distinct action
        # from the "have all documents been uploaded" check below, so it's
        # handled and returned on its own rather than falling into that check
        # (which would otherwise demand the file already be uploaded first).
        if 'pan_number' in request.data:
            from apps.accounts.models import (
                EmployeeProfile as _EP,
                find_conflicting_pan_profile,
                normalize_and_validate_pan,
            )
            raw_pan = (request.data.get('pan_number') or '').strip()
            if not raw_pan:
                return error('PAN number is required.', http_status=status.HTTP_400_BAD_REQUEST)
            try:
                pan_value = normalize_and_validate_pan(raw_pan)
            except ValueError as exc:
                return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
            profile, _ = _EP.objects.get_or_create(user=target_user)
            conflict = find_conflicting_pan_profile(pan_value, exclude_profile_pk=profile.pk)
            if conflict:
                return error(
                    f'This PAN is already registered to {conflict.user.full_name} '
                    f'({conflict.user.employee_id or conflict.user.email}).',
                    http_status=status.HTTP_409_CONFLICT,
                )
            profile.pan_number = pan_value
            profile.save(update_fields=['pan_number', 'updated_at'])
            return success('PAN number saved.', data={'pan_number': pan_value})

        try:
            missing_docs = _missing_required_docs(target_user)
        except Exception as exc:
            logger.error('_save_profile_step step=4 document query failed user=%s: %s',
                         target_user.pk, exc, exc_info=True)
            return error(
                'Unable to verify documents. Please try again.',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if missing_docs:
            return error(
                f'Please upload the following required documents: {", ".join(missing_docs)}.',
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return success('Documents verified. You can proceed to submit.')

    # ── Steps 0-3 — profile field save ────────────────────────────────────────
    try:
        profile, _ = EP.objects.get_or_create(user=target_user)
    except Exception as exc:
        logger.error('_save_profile_step profile fetch failed user=%s step=%d: %s',
                     target_user.pk, step, exc, exc_info=True)
        return error(
            'Unable to retrieve profile. Please try again.',
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    step_fields   = _step_all_field_keys(step)
    required_keys = frozenset(c.field_key for c in _step_required_configs(step))
    custom_keys   = _step_custom_field_keys(step)
    file_keys     = _step_file_field_keys(step)

    filled_data: dict = {}
    custom_updates: dict = {}
    # Required built-in keys the request explicitly submitted as blank —
    # kept apart from "key absent from this request entirely" so the
    # required-field gate below can tell "the employee just cleared this
    # field and saved" (must fail, regardless of whatever value is still
    # sitting in the DB from an earlier save) from "this request didn't
    # touch this field at all" (should fall back to that earlier value —
    # a field filled in a previous save still counts as satisfied).
    cleared_required_keys: set = set()
    for k, v in request.data.items():
        if k not in step_fields:
            continue
        if k in file_keys:
            # File-type custom fields never ride along in this JSON body —
            # their bytes go through the dedicated multipart upload endpoint,
            # and their presence has no real EmployeeProfile column or
            # custom_field_values entry to write here (see _field_value()).
            continue
        if k in custom_keys:
            # No serializer-level type coercion for custom fields (they're
            # HR-defined at runtime, not real columns) — stored as submitted,
            # empty value included; the required-field gate below catches a
            # blank one the same way it does built-in fields.
            custom_updates[k] = v
            continue
        if v in ('', None):
            if k in required_keys:
                cleared_required_keys.add(k)
                continue  # don't persist blank over a real prior value — the gate below still catches it as missing
            filled_data[k] = None if k in _NULLABLE_PROFILE_FIELDS else ''
        else:
            filled_data[k] = v

    if custom_updates:
        merged = dict(profile.custom_field_values or {})
        merged.update(custom_updates)
        filled_data['custom_field_values'] = merged

    # Required-field gate — a step save must never report success while any
    # visible+required field for this step would still end up blank
    # afterward. Checked against the EFFECTIVE post-save value (this
    # request's own data if it provided one, else whatever's already on the
    # profile), not just what's live in this one request, since a field
    # filled in an earlier save still counts as satisfied. Previously this
    # only got enforced client-side (see the wizard's own saveSection()) and
    # again at final submission (_missing_required, called from
    # _submit_onboarding) — meaning a request that skipped or raced past the
    # frontend's own check (or called this endpoint directly) could "save"
    # step 0 empty and still land on step 1's Save & Continue reporting
    # success, silently unlocking the next step with nothing actually filled
    # in. Enforcing it here too closes that gap the same way every other
    # required-field check in this codebase already works in two places,
    # not one.
    def _effective_value(config):
        if config.is_custom:
            return custom_updates.get(config.field_key, _field_value(profile, config))
        if config.field_key in cleared_required_keys:
            return ''
        if config.field_key in filled_data:
            return filled_data[config.field_key]
        return getattr(profile, config.field_key, None)

    step_label = _step_labels().get(step, '')
    missing = [
        f'{c.label} ({step_label})' if step_label else c.label
        for c in _step_required_configs(step)
        if not _field_filled(_effective_value(c))
    ]
    if missing:
        return error(
            f'Please fill in: {", ".join(missing)}.',
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Step-scoped "nothing to save" — only triggers when the request had no step
    # fields at all or all were required fields with empty values.
    if not filled_data:
        all_data  = EmployeeProfileSerializer(profile).data
        step_data = _extract_step_data(profile, all_data, step)
        return success('Nothing to save.', data=step_data)

    # ── Bank-change verification gate ───────────────────────────────────────
    # Self-service editing of ALREADY-FILLED bank details (the same
    # empty->filled vs filled->different distinction _alert_bank_details_
    # changed() on the model already draws) is held for HR review instead of
    # writing straight to the columns payroll reads from — see
    # EmployeeProfile.submit_bank_change(). First-time entry and any HR-
    # assisted save (HREmployeeOnboardingView, target_user != request.user)
    # skip this and save directly, same as before this gate existed.
    bank_change_requested = False
    if target_user == request.user:
        incoming_bank = {k: filled_data.pop(k) for k in list(filled_data) if k in _BANK_FIELDS}
        if incoming_bank:
            # Per-FIELD, not per-request: a field with no existing live value
            # (first-time entry) or an unchanged value writes straight
            # through, even when submitted alongside a genuine overwrite of a
            # different bank field in the same request. Treating the whole
            # request as "one overwrite" the moment ANY bank field already
            # had a value meant filling in Account Type/Bank Name/Branch for
            # the first time — while also correcting an already-filled
            # Account Number — sent ALL of them to pending, so the
            # first-time fields never actually got saved and kept failing
            # the step's own required-field check forever.
            overwrite_fields = {
                k: v for k, v in incoming_bank.items()
                if getattr(profile, k, '') and v != getattr(profile, k, '')
            }
            direct_fields = {k: v for k, v in incoming_bank.items() if k not in overwrite_fields}
            if overwrite_fields:
                profile.submit_bank_change(overwrite_fields)
                bank_change_requested = True
            if direct_fields:
                filled_data.update(direct_fields)

    if not filled_data and bank_change_requested:
        all_data  = EmployeeProfileSerializer(profile).data
        step_data = _extract_step_data(profile, all_data, step)
        return success(
            'Bank detail change submitted — your previous details remain active on payroll until HR approves this change.',
            data=step_data,
        )

    serializer = EmployeeProfileSerializer(profile, data=filled_data, partial=True)
    if not serializer.is_valid():
        return error(
            first_error(serializer.errors),
            data=serializer.errors,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        profile._changed_by = request.user
        serializer.save()
    except Exception as exc:
        logger.error('_save_profile_step serializer.save failed user=%s step=%d: %s',
                     target_user.pk, step, exc, exc_info=True)
        return error(
            'Failed to save profile data. Please try again.',
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Move status to 'draft' (in-progress) on the very first step save
    if target_user.onboarding_status == User.ONBOARDING_PENDING:
        try:
            User.objects.filter(pk=target_user.pk).update(onboarding_status=User.ONBOARDING_DRAFT)
        except Exception as exc:
            logger.warning('_save_profile_step status→draft update failed user=%s: %s',
                           target_user.pk, exc, exc_info=True)

    # Return ONLY the fields for this step — never leak other steps' data
    all_data  = EmployeeProfileSerializer(profile).data
    step_data = _extract_step_data(profile, all_data, step)
    logger.info('Onboarding step %d saved for user %s', step, target_user.email)
    message = (
        'Profile saved. Your bank detail change was submitted for HR review — '
        'your previous details remain active on payroll until it is approved.'
        if bank_change_requested else 'Profile saved.'
    )
    return success(message, data=step_data)


def _can_manage_employee_documents(user, employee) -> bool:
    """
    True for the employee themself, their specifically assigned reporting
    manager or HR (falling back to branch match only when the employee has
    no HR assigned), system_admin, or a Branch Admin (unconditional access
    within their own branch). Mirrors the assigned-employee scoping used for
    leave/expense — a blanket documents.create grant should not let any HR
    act on any employee company-wide.
    """
    if employee.id == user.id:
        return True
    if not _has_perm(user, 'documents.create'):
        return False
    if _has_perm(user, 'settings.edit'):
        return True
    if user.role and getattr(user.role, 'can_manage_branch', False):
        branch = (getattr(user, 'branch', '') or '').strip()
        return not branch or (getattr(employee, 'branch', '') or '').strip() == branch
    if user.role and getattr(user.role, 'can_manage_team', False):
        return employee.reporting_manager_id == user.id
    if employee.hr_id:
        return employee.hr_id == user.id
    branch = (getattr(user, 'branch', '') or '').strip()
    return not branch or (getattr(employee, 'branch', '') or '').strip() == branch


def _get_document_type_config(type_key: str):
    """Return the visible DocumentTypeConfig row for type_key, or None. Every
    document upload endpoint validates against this before accepting a file
    — document_type no longer has a `choices=` enum (see DocumentTypeConfig),
    so this is the only thing standing between an upload and an arbitrary
    string being stored as a document type."""
    from core.cache_service import DocumentTypeConfigCacheService
    for c in DocumentTypeConfigCacheService.get_all():
        if c.type_key == type_key and c.visible:
            return c
    return None


def _get_file_field_config(field_key: str):
    """Return the OnboardingFieldConfig row for field_key if it's a visible,
    is_custom=True, field_type='file' field; else None. Every upload/list
    endpoint below validates against this before touching CustomFieldFileValue,
    so a request can't create a file value for a field that doesn't exist,
    isn't custom, or isn't a file-type field."""
    from core.cache_service import OnboardingFieldConfigCacheService
    for c in OnboardingFieldConfigCacheService.get_all():
        if c.field_key == field_key and c.is_custom and c.field_type == OnboardingFieldConfig.TYPE_FILE and c.visible:
            return c
    return None


def _self_can_write_custom_file(user, config) -> bool:
    """Self-service write rule for a file-type custom field — mirrors the
    Emergency-only-after-onboarding rule MyProfileView.patch already applies
    to text-type custom fields: Emergency-step fields stay editable forever,
    every other step is only writable while still mid-wizard."""
    if config.step == OnboardingFieldConfig.STEP_EMERGENCY:
        return True
    return user.onboarding_status != User.ONBOARDING_COMPLETE


_WORKFLOW_ORDER = [
    ApprovalWorkflowRule.WORKFLOW_LEAVE,
    ApprovalWorkflowRule.WORKFLOW_EXPENSE,
    ApprovalWorkflowRule.WORKFLOW_ATTENDANCE_CORRECTION,
]


def _ensure_default_rules():
    """Create default rules for any workflow types that don't have one yet.
    Never overwrites existing rules — safe to call on every request."""
    existing = set(ApprovalWorkflowRule.objects.values_list('workflow_type', flat=True))
    missing  = [wf for wf in _WORKFLOW_ORDER if wf not in existing]
    if not missing:
        return
    manager_role = Role.objects.filter(can_manage_team=True, is_active=True).first()
    hr_role      = None
    perm = Permission.objects.filter(codename='leave.approve').first()
    if perm:
        rp = RolePermission.objects.filter(permission=perm, role__is_active=True).select_related('role').first()
        if rp:
            hr_role = rp.role
    ApprovalWorkflowRule.objects.bulk_create([
        ApprovalWorkflowRule(workflow_type=wf, l1_approver_role=manager_role, l2_approver_role=hr_role)
        for wf in missing
    ])


def _serialize_rule(rule: ApprovalWorkflowRule) -> dict:
    return {
        'workflow_type':      rule.workflow_type,
        'workflow_label':     rule.get_workflow_type_display(),
        'l1_approver_role':   rule.l1_approver_role_id,
        'l1_approver_label':  rule.l1_approver_role.display_name if rule.l1_approver_role else '',
        'l2_approver_role':   rule.l2_approver_role_id,
        'l2_approver_label':  rule.l2_approver_role.display_name if rule.l2_approver_role else '',
    }


def _resolve_rule_approver(role, employee):
    """Resolve a Role FK to the actual User approver for a given employee.

    Roles with can_manage_team=True resolve via employee.reporting_manager;
    all other roles resolve via employee.hr. Validates the assigned person
    still holds the expected capability.
    """
    if role is None:
        return None
    if role.can_manage_team:
        rm = getattr(employee, 'reporting_manager', None)
        if rm and rm.role and rm.role.can_manage_team:
            return rm
        return None
    else:
        hr_user = getattr(employee, 'hr', None)
        if hr_user and _has_perm(hr_user, 'leave.approve'):
            return hr_user
        return None


def _build_matrix_row(rule: ApprovalWorkflowRule, override, employee=None) -> dict:
    # Per-employee override takes priority; otherwise resolve from employee's FK fields
    if override and override.l1_override:
        l1_id, l1_name, l1_is_override = str(override.l1_override.id), override.l1_override.full_name, True
    else:
        l1_user = _resolve_rule_approver(rule.l1_approver_role, employee) if employee else None
        l1_id   = str(l1_user.id) if l1_user else None
        l1_name = l1_user.full_name if l1_user else None
        l1_is_override = False

    if override and override.l2_override:
        l2_id, l2_name, l2_is_override = str(override.l2_override.id), override.l2_override.full_name, True
    else:
        l2_user = _resolve_rule_approver(rule.l2_approver_role, employee) if employee else None
        l2_id   = str(l2_user.id) if l2_user else None
        l2_name = l2_user.full_name if l2_user else None
        l2_is_override = False

    return {
        'workflow_type':     rule.workflow_type,
        'workflow_label':    rule.get_workflow_type_display(),
        'l1_approver_role':  rule.l1_approver_role_id,
        'l1_approver_label': rule.l1_approver_role.display_name if rule.l1_approver_role else '',
        'l1_approver_id':    l1_id,
        'l1_approver_name':  l1_name,
        'l1_is_override':    l1_is_override,
        'l2_approver_role':  rule.l2_approver_role_id,
        'l2_approver_label': rule.l2_approver_role.display_name if rule.l2_approver_role else '',
        'l2_approver_id':    l2_id,
        'l2_approver_name':  l2_name,
        'l2_is_override':    l2_is_override,
    }


_EMP_IMPORT_COL_MAP = {
    'first name': 'first_name', 'firstname': 'first_name', 'first_name': 'first_name',
    'last name':  'last_name',  'lastname':  'last_name',  'last_name':  'last_name',
    'work email': 'email', 'email': 'email', 'work_email': 'email',
    'email address': 'email', 'email_address': 'email',
    'phone': 'phone', 'mobile': 'phone', 'phone number': 'phone',
    'phone_number': 'phone', 'mobile number': 'phone',
    'role': 'role',
    # Org Unit + Position resolve to a real Position, with department/
    # designation derived from it (same as Create Employee's own Position
    # picker) — a "Department"/"Designation" column is not recognized here;
    # EmployeeBulkImportRowSerializer has no such fields, so those columns
    # would be silently dropped rather than actually doing anything.
    'org unit': 'org_unit', 'org_unit': 'org_unit', 'organisation unit': 'org_unit',
    'position': 'position_title', 'position title': 'position_title', 'position_title': 'position_title',
    # 'branch'/'branch name' kept for any pre-existing template already in
    # use — 'company code' is the current column name (see the sample
    # template's own _HEADERS below), both accepted indefinitely.
    'branch': 'branch', 'branch name': 'branch', 'branch_name': 'branch',
    'company code': 'branch', 'company_code': 'branch', 'company code name': 'branch',
    'employee type': 'employee_type', 'employee_type': 'employee_type',
    'emp type': 'employee_type', 'type': 'employee_type',
    'date of joining': 'date_of_joining', 'date_of_joining': 'date_of_joining',
    'joining date': 'date_of_joining', 'doj': 'date_of_joining',
    'gender': 'gender', 'sex': 'gender',
    'dob': 'date_of_birth', 'date of birth': 'date_of_birth',
    'date_of_birth': 'date_of_birth', 'birth date': 'date_of_birth',
    'birthdate': 'date_of_birth',
    'blood group': 'blood_group', 'blood_group': 'blood_group', 'blood': 'blood_group',
    'address': 'address', 'current address': 'address', 'current_address': 'address',
    'uan': 'uan_number', 'uan number': 'uan_number', 'uan_number': 'uan_number',
    'pf uan': 'uan_number', 'epf uan': 'uan_number',
    'name as per aadhar': 'name_as_per_aadhar', 'name_as_per_aadhar': 'name_as_per_aadhar',
    'aadhar name': 'name_as_per_aadhar', 'aadhaar name': 'name_as_per_aadhar',
    'basic salary': 'basic_salary', 'basic_salary': 'basic_salary', 'basic': 'basic_salary',
    'annual ctc': 'annual_ctc', 'annual_ctc': 'annual_ctc', 'ctc': 'annual_ctc',
}


def _normalize_employee_import_headers(row_dict: dict) -> dict:
    out = {}
    for key, value in row_dict.items():
        mapped = _EMP_IMPORT_COL_MAP.get(key.strip().lower())
        if mapped:
            out[mapped] = value
    return out


def _emp_xlsx_cell_to_str(value) -> str:
    import datetime as _dt
    if isinstance(value, _dt.datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, _dt.date):
        return value.strftime('%Y-%m-%d')
    return str(value).strip() if value is not None else ''


def _parse_employee_xlsx_rows(file_obj) -> tuple:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = iter(ws.iter_rows(values_only=True))
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return [], 'The XLSX file has no header row.'
        headers = [str(h).strip() if h is not None else '' for h in header_row]
        rows = []
        for raw in rows_iter:
            if all(v is None or str(v).strip() == '' for v in raw):
                continue
            rows.append({headers[i]: _emp_xlsx_cell_to_str(raw[i]) for i in range(len(headers))})
        wb.close()
        return rows, None
    except Exception as exc:
        return [], f'Could not parse XLSX file: {exc}'


def _parse_employee_csv_rows(file_obj) -> tuple:
    try:
        text = file_obj.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            if all((v or '').strip() == '' for v in row.values()):
                continue
            rows.append({k: (v or '').strip() for k, v in row.items()})
        return rows, None
    except Exception as exc:
        return [], f'Could not parse CSV file: {exc}'


class CanManageRoles(BasePermission):
    """Only users holding settings.edit may manage roles, permissions, and settings."""
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, _) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and _has_perm(request.user, 'settings.edit')
        )


__all__ = [
    'CanManageRoles',
    '_BUILTIN_STEPS',
    '_STEP_4_FIELDS',
    '_NULLABLE_PROFILE_FIELDS',
    '_WORKFLOW_ORDER',
    '_EMP_IMPORT_COL_MAP',
    '_auto_assign_managers',
    '_document_dict',
    '_custom_field_file_dict',
    '_employee_dict',
    '_login_assessment_status',
    '_parse_as_of',
    '_get_employee',
    '_employee_out_of_branch_scope',
    '_mask_bank_fields',
    '_valid_steps',
    '_custom_field_steps',
    '_step_labels',
    '_step_configs',
    '_step_all_field_keys',
    '_step_required_configs',
    '_step_custom_field_keys',
    '_step_file_field_keys',
    '_field_value',
    '_file_type_custom_field_keys',
    '_missing_required',
    '_step_is_complete',
    '_extract_step_data',
    '_field_filled',
    '_missing_required_docs',
    '_missing_education_experience',
    '_compute_completed_steps',
    '_submit_onboarding',
    '_save_profile_step',
    '_can_manage_employee_documents',
    '_get_document_type_config',
    '_get_file_field_config',
    '_self_can_write_custom_file',
    '_ensure_default_rules',
    '_serialize_rule',
    '_resolve_rule_approver',
    '_build_matrix_row',
    '_normalize_employee_import_headers',
    '_emp_xlsx_cell_to_str',
    '_parse_employee_xlsx_rows',
    '_parse_employee_csv_rows',
    'PHONE_RE',
    'NAME_RE',
    'EMAIL_RE',
    '_PHONE_FORMAT_CHARS_RE',
]
