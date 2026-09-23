
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

# ─── Employee List / Create ───────────────────────────────────────────────────

class EmployeeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    _DENIED = 'You do not have permission to perform this action.'

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            User.objects
            .select_related('role', 'profile', 'reporting_manager')
            .prefetch_related('employee_documents')
            .prefetch_related('custom_field_files')
            .filter(is_active__in=[True, False])
            .exclude(employee_id='')   # portal candidates have no employee_id until onboarding is approved
            .order_by('-date_joined')
        )

        # Managers (role.can_manage_team) only see their own direct reports — not
        # every employee in the branch — matching the scoping already applied to
        # Attendance, Expenses, and the Leave approval queues for the same role.
        # Everyone else without settings.edit is scoped to their own branch, and
        # cannot be overridden by query params.
        #
        # Exception: picking a KT handover assignee for the viewer's OWN
        # separation request. A manager/HR can't assign their own handover to
        # their own report (see SeparationHandoverTaskListCreateView.post), so
        # locking this search to "your own team" would leave them with zero
        # valid candidates. own_separation_request must name a request where
        # they ARE the separating employee — can't be used to see someone
        # else's team.
        from apps.hrms.models import SEP_REJECTED, SeparationRequest

        role = request.user.role
        own_sep_request_id = request.query_params.get('own_separation_request', '').strip()
        widen_for_own_separation = bool(own_sep_request_id) and SeparationRequest.objects.filter(
            id=own_sep_request_id, employee=request.user,
        ).exclude(status=SEP_REJECTED).exists()

        if role and role.can_manage_team and not widen_for_own_separation:
            qs = qs.filter(reporting_manager=request.user)
        elif not _has_perm(request.user, 'settings.edit') and request.user.branch:
            qs = qs.filter(branch=request.user.branch)
        if widen_for_own_separation:
            qs = qs.exclude(reporting_manager=request.user)

        search       = request.query_params.get('search', '').strip()
        dept         = request.query_params.get('department', '').strip()
        branch_param = request.query_params.get('branch', '').strip()
        status_param = request.query_params.get('status', '').strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search)     |
                Q(employee_id__icontains=search)
            )
        if dept:
            # Matches by the real OrgUnit an employee currently holds via
            # Placement (what the dropdown is actually built from — see
            # EmployeeStatsView.department_names), OR the legacy `department`
            # string for anyone with no Position/Placement at all.
            qs = qs.filter(
                Q(department=dept) |
                Q(placements__effective_to__isnull=True, placements__position__org_unit__name=dept)
            ).distinct()
        if branch_param:
            qs = qs.filter(branch=branch_param)
        if status_param:
            # Mirrors the same "Notice Period" definition used everywhere
            # else (EmployeeStatsView, _employee_dict) — an approved,
            # not-yet-completed separation. Filtering active/probation
            # excludes anyone on notice period, matching the table row's own
            # display precedence (a notice-period row shows that pill
            # instead of Active/Probation, so the filters stay mutually
            # exclusive with what's actually shown).
            from apps.hrms.models import SEP_APPROVED
            today = timezone.localdate()
            notice_period_q = Q(
                separation_requests__status=SEP_APPROVED,
                separation_requests__proposed_last_working_day__gte=today,
            )
            if status_param == 'inactive':
                qs = qs.filter(is_active=False)
            elif status_param == 'active':
                qs = qs.filter(
                    is_active=True, must_change_password=False, employment_status=User.EMPLOYMENT_STATUS_CONFIRMED,
                ).exclude(notice_period_q)
            elif status_param == 'onboarding':
                qs = qs.filter(is_active=True, must_change_password=True)
            elif status_param == 'probation':
                qs = qs.filter(
                    is_active=True, must_change_password=False, employment_status=User.EMPLOYMENT_STATUS_PROBATION,
                ).exclude(notice_period_q)
            elif status_param == 'notice_period':
                qs = qs.filter(is_active=True).filter(notice_period_q).distinct()
            else:
                return error('status must be one of: active, onboarding, probation, notice_period, inactive.')

        # Used to check "does anyone currently report to this person, or have
        # them as HR" before a caller re-roles/re-branches them elsewhere —
        # only the count matters, so callers pass page_size=1.
        if reporting_manager_id := request.query_params.get('reporting_manager_id', '').strip():
            qs = qs.filter(reporting_manager_id=reporting_manager_id, is_active=True)
        if hr_id := request.query_params.get('hr_id', '').strip():
            qs = qs.filter(hr_id=hr_id, is_active=True)

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 20

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Employees retrieved.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     [_employee_dict(u) for u in page_obj.object_list],
        })

    def post(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(self._DENIED, http_status=status.HTTP_403_FORBIDDEN)

        first_name      = (request.data.get('first_name')      or '').strip()
        last_name       = (request.data.get('last_name')       or '').strip()
        email           = (request.data.get('email')           or '').strip().lower()
        role_id         = request.data.get('role')
        branch          = (request.data.get('branch')          or '').strip()
        date_of_joining = (request.data.get('date_of_joining') or '').strip()
        phone           = (request.data.get('phone')           or '').strip()
        employee_type   = (request.data.get('employee_type')   or '').strip() or 'Permanent'
        hr_id                 = (request.data.get('hr_id')                 or '').strip()
        reporting_manager_id  = (request.data.get('reporting_manager_id')  or '').strip()
        # Every role is hired onto a Position, department/designation are
        # always derived from it (via assign_position()'s sync) — except a
        # Branch Admin, who oversees every department in the branch rather
        # than sitting in one seat, so they keep the original free-text
        # designation entry and no department at all. Matched by capability,
        # not a hardcoded role name, same as everywhere else this distinction
        # is made (see applyLeaderRole on the frontend).
        position_id     = (request.data.get('position')        or '').strip()
        designation     = (request.data.get('designation')     or '').strip()

        role_for_dept_check = None
        if role_id:
            try:
                role_for_dept_check = Role.objects.filter(pk=role_id).first()
            except (ValueError, ValidationError):
                role_for_dept_check = None
        is_branch_admin_role = bool(role_for_dept_check and role_for_dept_check.can_manage_branch)

        errs = {}
        if not first_name:      errs['first_name']      = 'First name is required.'
        if not last_name:       errs['last_name']       = 'Last name is required.'
        if not email:           errs['email']           = 'Email is required.'
        if not role_id:         errs['role']            = 'Role is required.'
        if is_branch_admin_role:
            if not designation: errs['designation'] = 'Designation is required.'
        elif not position_id:
            errs['position'] = 'Position is required.'
        if not branch:          errs['branch']          = 'Company Code is required.'
        if not date_of_joining: errs['date_of_joining'] = 'Date of joining is required.'

        # Length guards
        if first_name  and len(first_name)  > 150: errs['first_name']  = 'First name must be 150 characters or fewer.'
        if last_name   and len(last_name)   > 150: errs['last_name']   = 'Last name must be 150 characters or fewer.'
        if email       and len(email)       > 254: errs['email']       = 'Email must be 254 characters or fewer.'
        if phone       and len(phone)       > 20:  errs['phone']       = 'Phone must be 20 characters or fewer.'
        if branch      and len(branch)      > 100: errs['branch']      = 'Branch must be 100 characters or fewer.'
        if designation and len(designation) > 100: errs['designation'] = 'Designation must be 100 characters or fewer.'

        # Branch must match an active branch in the master Branch list. A free-text
        # value that doesn't match exactly (e.g. "Hyderabad HQ" vs the real
        # "Hyderabad") silently breaks HR/manager auto-assignment below, which
        # matches on this exact string — so it's rejected here instead of saved.
        branch_obj = None
        if branch and 'branch' not in errs:
            from apps.branch.models import Branch
            branch_obj = Branch.objects.filter(
                branch_name__iexact=branch, status=Branch.STATUS_ACTIVE,
            ).first()
            if branch_obj is None:
                errs['branch'] = 'Select a valid, active branch from the list.'

        position_obj = None
        if position_id:
            try:
                position_obj = Position.objects.select_related(
                    'org_unit', 'job_template',
                ).get(pk=position_id, is_active=True)
            except (Position.DoesNotExist, ValueError, ValidationError):
                errs['position'] = 'Select a valid, active position.'

        # Name format check — letters with single space/hyphen/apostrophe separators only
        if first_name and 'first_name' not in errs and not NAME_RE.match(first_name):
            errs['first_name'] = 'First name may only contain letters, numbers, spaces, hyphens and apostrophes.'
        if last_name  and 'last_name'  not in errs and not NAME_RE.match(last_name):
            errs['last_name']  = 'Last name may only contain letters, numbers, spaces, hyphens and apostrophes.'

        # Phone format check — exactly 10 digits, optional +91/91 prefix
        if phone and 'phone' not in errs and not _is_valid_phone(phone):
            errs['phone'] = 'Enter a valid 10-digit phone number (optionally prefixed with +91).'

        # Date format check
        if date_of_joining and 'date_of_joining' not in errs:
            try:
                datetime.strptime(date_of_joining, '%Y-%m-%d')
            except ValueError:
                errs['date_of_joining'] = 'Date of joining must be in YYYY-MM-DD format.'

        # Email format check
        if email and 'email' not in errs and not EMAIL_RE.match(email):
            errs['email'] = 'Enter a valid email address.'

        if errs:
            return error('Please fix the errors below.', data=errs)

        # Store the canonical Branch.branch_name casing, not whatever the
        # client sent — keeps this byte-for-byte consistent with lookups
        # elsewhere (HR/manager auto-assignment, geofencing, reports).
        branch     = branch_obj.branch_name
        # Department stays blank at creation for every non-Branch-Admin role —
        # assign_position() below fills it in from the Position.
        department = ''

        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            field_msg = (
                f'This email is already registered in the {existing_user.branch} branch.'
                if existing_user.branch and existing_user.branch != branch
                else 'Email already registered.'
            )
            return error(
                'An account with this email already exists.',
                data={'email': field_msg},
            )

        try:
            role = Role.objects.get(pk=role_id)
        except (Role.DoesNotExist, ValueError, TypeError):
            return error('Invalid role.', data={'role': 'Role not found.'})

        if role.role_permissions.filter(permission__codename='settings.edit').exists():
            return error(f'"{role.display_name}" cannot be assigned via employee creation.')

        selected_hr = None
        if hr_id:
            try:
                selected_hr = User.objects.get(pk=hr_id, is_active=True)
            except (User.DoesNotExist, ValueError, ValidationError):
                return error('HR user not found or is inactive.', data={'hr_id': 'Invalid HR selected.'})

        selected_manager = None
        if reporting_manager_id:
            if role.can_manage_team:
                return error(
                    'Managers do not have a reporting manager.',
                    data={'reporting_manager_id': 'Not applicable for this role.'},
                )
            try:
                selected_manager = User.objects.get(pk=reporting_manager_id, is_active=True)
            except (User.DoesNotExist, ValueError, ValidationError):
                return error(
                    'Reporting manager not found or is inactive.',
                    data={'reporting_manager_id': 'Invalid manager selected.'},
                )

        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

        employee_id = EmployeeCodeSettings.generate_employee_id(
            first_name=first_name,
            last_name=last_name,
            date_of_joining=date_of_joining or None,
        )
        full_name = f'{first_name} {last_name}'

        with transaction.atomic():
            user = User.objects.create_user(
                email           = email,
                password        = temp_password,
                full_name       = full_name,
                role            = role,
                employee_id     = employee_id,
                department      = department,
                designation     = designation,
                branch          = branch,
                phone           = phone,
                employee_type   = employee_type,
                date_of_joining  = date_of_joining or None,
                must_change_password = True,
                onboarding_status    = User.ONBOARDING_PENDING,
            )
            if position_obj is not None:
                assign_position(
                    user, position_obj,
                    effective_from=(
                        datetime.strptime(date_of_joining, '%Y-%m-%d').date()
                        if date_of_joining else timezone.localdate()
                    ),
                    created_by=request.user,
                )
                user.refresh_from_db()
                # Reflect the position-derived values in the audit log below
                # and in the welcome-email/response payload, instead of the
                # blank/manual strings that were submitted alongside it.
                department, designation = user.department, user.designation

            manual_fields = []
            if selected_hr is not None:
                user.hr = selected_hr
                manual_fields.append('hr')
            if selected_manager is not None:
                user.reporting_manager = selected_manager
                user.reporting_manager_from_org_chart = False
                manual_fields.append('reporting_manager')
                manual_fields.append('reporting_manager_from_org_chart')

            # _auto_assign_managers() only fills in fields left unset above, so an
            # explicit hr_id/reporting_manager_id from the form always wins.
            auto_fields = _auto_assign_managers(user)
            # Auto-assign creating HR admin as the employee's branch HR
            if (_has_perm(request.user, 'employees.edit')
                    and user.hr_id is None and user.pk != request.user.pk):
                user.hr = request.user
                auto_fields.append('hr')
            auto_fields = list(dict.fromkeys(manual_fields + auto_fields))
            if auto_fields:
                user.save(update_fields=[*auto_fields, 'updated_at'])

            # Auto-allocate leave balances based on active leave policies
            from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
            _allocate_leaves_for_employee(user, user.date_of_joining)

            # Auto-assign all default assessments to the new employee
            from apps.assessments.models import (
                Assessment as _Assessment,
                AssessmentItem as _AssessmentItem,
                CandidateAssignment as _CandidateAssignment,
            )
            _default_assessments = list(
                _Assessment.objects.filter(is_active=True, is_default=True).prefetch_related('items')
            )
            _has_pending_assessment = False
            for _assessment in _default_assessments:
                _max_score = _assessment.items.filter(item_type=_AssessmentItem.TYPE_QUIZ).count()
                _, _created = _CandidateAssignment.objects.get_or_create(
                    employee=user,
                    assessment=_assessment,
                    defaults={'assigned_by': request.user, 'max_score': _max_score},
                )
                if _created:
                    _has_pending_assessment = True
            if _has_pending_assessment:
                user.assessment_status = User.ASSESSMENT_PENDING
                user.save(update_fields=['assessment_status', 'updated_at'])

            # Auto-assign the company's default weekly-off pattern — without
            # this, a new employee has no pattern at all and every actual day
            # off shows as an unexplained absence until HR manually assigns
            # one (see Attendance -> Weekly Off Assignment to change it later
            # for this employee specifically, e.g. a different rest day).
            # date_of_joining is still the raw 'YYYY-MM-DD' string validated
            # above — create_user() never converts it, and assign_weekly_off
            # does date arithmetic on effective_from, so it must be parsed
            # here rather than read back off user.date_of_joining.
            from apps.attendance.models import WeeklyDayPolicy
            from apps.attendance.services_hr import assign_weekly_off
            _default_policy = WeeklyDayPolicy.objects.filter(is_default=True, is_active=True).first()
            if _default_policy is not None:
                assign_weekly_off(
                    employee_id, _default_policy,
                    datetime.strptime(date_of_joining, '%Y-%m-%d').date(),
                    actor=request.user,
                )

            AuditLog.objects.create(
                user=request.user, action='employee_created', module='accounts',
                object_id=str(user.id),
                changes={
                    'name': full_name, 'email': email,
                    'department': department, 'designation': designation,
                    'role': role.name, 'employee_id': employee_id,
                },
                branch=user.branch,
                ip_address=get_client_ip(request),
            )

        try:
            from apps.accounts.utils import (
                _get_smtp_connection, _build_message, _company_email_wrapper,
                _get_company_branding,
            )

            company_name, logo_url, website, address = _get_company_branding()
            company_name = company_name or 'Aira HRMS'

            body = (
                f'<p>Hi <strong>{full_name}</strong>,</p>'
                f'<p>Your {company_name} account has been created.'
                f' Use the credentials below to log in:</p>'
                f'<p>'
                f'<strong>Employee ID:</strong> {employee_id}<br>'
                f'<strong>Login Email:</strong> {email}<br>'
                f'<strong>Temporary Password:</strong> {temp_password}'
                f'</p>'
                f'<p>You will be asked to change your password on first login.</p>'
                f'<p>— HR Team</p>'
            )
            html_body = _company_email_wrapper(body, company_name, logo_url, website, address)

            connection, from_email, _smtp = _get_smtp_connection()
            msg = _build_message(
                subject=f'Welcome to {company_name} — Your Login Credentials',
                html_body=html_body,
                from_email=from_email,
                to=[email],
                connection=connection,
            )
            msg.send(fail_silently=False)
            logger.info('Welcome email sent to %s', email)
            email_sent = True
        except Exception as exc:
            logger.error('Welcome email failed for %s: %s', email, exc)
            email_sent = False

        logger.info('Employee %s (%s) created by %s', employee_id, email, request.user.email)
        # The account itself was created successfully either way — only the
        # message differs, so whoever's reading the response knows whether
        # they still need to share the credentials with the new hire
        # themselves (email failures are silent otherwise: this request
        # still returns 201, and the account is fully usable).
        message = (
            f'{full_name} added successfully. Login credentials sent to {email}.'
            if email_sent else
            f'{full_name} added successfully, but the welcome email could not be sent. '
            f'Share their login credentials manually — check Settings → SMTP.'
        )
        return success(
            message,
            data=_employee_dict(user),
            http_status=status.HTTP_201_CREATED,
        )


class EmployeeStatsView(APIView):
    """
    Dashboard counts for the Employees page header cards.

    Computed directly from the full queryset (not a single page) — the
    frontend used to derive these from the currently loaded page of results,
    which under-counted everything once there was more than one page.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        base_qs = User.objects.filter(is_active__in=[True, False]).exclude(employee_id='')

        role = request.user.role
        if role and role.can_manage_team:
            base_qs = base_qs.filter(reporting_manager=request.user)
        elif not _has_perm(request.user, 'settings.edit') and request.user.branch:
            base_qs = base_qs.filter(branch=request.user.branch)

        # branch_names/department_names always come from base_qs (ignores the
        # branch filter below) so the branch dropdown never shrinks to just
        # the currently-selected branch once one is picked.
        branch_names = list(
            base_qs.exclude(branch='').values_list('branch', flat=True).distinct().order_by('branch')
        )
        # The legacy `department` string is blank for anyone hired onto a
        # real Position (assign_position() only back-fills it when the
        # Position's OrgUnit chain has an is_department_level ancestor,
        # which this tenant's org structure doesn't use) — so the dropdown
        # must be built from the real OrgUnit each employee currently holds
        # via Placement, not that mostly-empty field. Legacy `department`
        # values are still unioned in, for any employee placed the old way
        # (no Position/Placement at all) who'd otherwise disappear from the
        # filter entirely.
        org_unit_names = set(
            Placement.objects.filter(employee__in=base_qs, effective_to__isnull=True)
            .exclude(position__org_unit__isnull=True)
            .values_list('position__org_unit__name', flat=True)
        )
        legacy_department_names = set(base_qs.exclude(department='').values_list('department', flat=True))
        department_names = sorted(org_unit_names | legacy_department_names)

        qs = base_qs
        branch_filter = request.query_params.get('branch', '').strip()
        if branch_filter and branch_filter != 'all':
            qs = qs.filter(branch=branch_filter)

        from datetime import date
        from apps.hrms.models import SeparationRequest, SEP_APPROVED

        today = date.today()
        active_qs = qs.filter(is_active=True)
        # "Onboarding / Probation" — either still going through the wizard
        # (must_change_password, same signal EmployeeListCreateView.get()'s
        # own status filter uses) or already onboarded but not yet
        # confirmed (employment_status='probation', see the Confirmation
        # action — apps/accounts/views.py:EmployeeConfirmView).
        onboarding_or_probation_qs = active_qs.filter(
            Q(must_change_password=True) | Q(employment_status=User.EMPLOYMENT_STATUS_PROBATION)
        )
        notice_period_count = active_qs.filter(
            separation_requests__status=SEP_APPROVED,
            separation_requests__proposed_last_working_day__gte=today,
        ).distinct().count()
        new_this_month = active_qs.filter(
            date_of_joining__year=today.year, date_of_joining__month=today.month,
        ).count()

        # Same real-OrgUnit source as department_names above, scoped to the
        # branch-filtered qs instead of base_qs for the "TOTAL HEADCOUNT —
        # across N org units" caption.
        departments_count = len(set(
            Placement.objects.filter(employee__in=qs, effective_to__isnull=True)
            .exclude(position__org_unit__isnull=True)
            .values_list('position__org_unit_id', flat=True)
        ) | set(qs.exclude(department='').values_list('department', flat=True)))

        return success('Employee statistics retrieved.', data={
            'total':             qs.count(),
            'active':            qs.filter(is_active=True, must_change_password=False).count(),
            'onboarding':        qs.filter(is_active=True, must_change_password=True).count(),
            'departments':       departments_count,
            'branch_names':      branch_names,
            'department_names':  department_names,
            'new_this_month':          new_this_month,
            'onboarding_or_probation': onboarding_or_probation_qs.count(),
            'needs_reporting_manager': onboarding_or_probation_qs.filter(reporting_manager__isnull=True).count(),
            'notice_period':           notice_period_count,
        })
