
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

# ── Employee Bulk Import ───────────────────────────────────────────────────────

_EMP_MAX_IMPORT_ROWS  = 1000
_EMP_MAX_IMPORT_BYTES = 5 * 1024 * 1024




class EmployeeBulkImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser]

    def post(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(
                'Only System Admin and HR Admin can perform bulk employee import.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return error('No file uploaded. Please attach a CSV or XLSX file.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        if uploaded_file.size > _EMP_MAX_IMPORT_BYTES:
            return error('File too large. Maximum allowed size is 5 MB.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        filename = (uploaded_file.name or '').lower()
        if filename.endswith('.xlsx'):
            rows, parse_error = _parse_employee_xlsx_rows(uploaded_file)
        elif filename.endswith('.csv'):
            rows, parse_error = _parse_employee_csv_rows(uploaded_file)
        else:
            return error('Unsupported file format. Please upload a CSV or XLSX file.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        if parse_error:
            return error(parse_error, http_status=status.HTTP_400_BAD_REQUEST)
        if not rows:
            return error('The file contains no data rows.',
                         http_status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > _EMP_MAX_IMPORT_ROWS:
            return error(
                f'File contains {len(rows)} rows. '
                f'Maximum allowed per import is {_EMP_MAX_IMPORT_ROWS}.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-load lookup tables once for the entire batch.
        from apps.branch.models import Branch as _Branch
        from apps.accounts.models import EmployeeProfile

        # branch: lower_name → exact branch_name stored on User
        branch_map: dict = {}
        for b in _Branch.objects.only('branch_name', 'branch_code'):
            branch_map[b.branch_name.strip().lower()] = b.branch_name.strip()
            if b.branch_code:
                branch_map[b.branch_code.strip().lower()] = b.branch_name.strip()

        # role: lower_name/lower_display → Role obj
        role_map: dict = {}
        for r in Role.objects.filter(is_active=True):
            role_map[r.name.lower()]         = r
            role_map[r.display_name.lower()] = r

        # (lower org unit name, lower position title) → list of matching
        # active Position ids — more than one hit (e.g. two same-titled
        # seats in the same unit) is treated as ambiguous, same as zero.
        position_map: dict = {}
        for pos_id, unit_name, title in Position.objects.filter(is_active=True).values_list(
            'id', 'org_unit__name', 'title',
        ):
            position_map.setdefault((unit_name.lower(), title.lower()), []).append(pos_id)

        # Pre-load existing emails for DB-level duplicate detection.
        existing_emails: set = set(
            User.objects.values_list('email', flat=True)
        )
        seen_emails: set = set()

        created_ids:  list = []
        created_rows: list = []
        row_errors:   list = []
        skipped_rows: list = []

        for idx, raw_row in enumerate(rows, start=2):
            row_data = _normalize_employee_import_headers(raw_row)
            ser = EmployeeBulkImportRowSerializer(data=row_data)

            if not ser.is_valid():
                for field, msgs in ser.errors.items():
                    row_errors.append({
                        'row':     idx,
                        'field':   field,
                        'message': msgs[0] if isinstance(msgs, list) else str(msgs),
                    })
                continue

            vd    = ser.validated_data
            email = vd['email']

            # Duplicates are skipped silently — not treated as failures.
            if email in existing_emails or email in seen_emails:
                skipped_rows.append({
                    'row':        idx,
                    'identifier': email,
                    'reason':     'Already exists',
                })
                continue

            # Branch existence check.
            branch_raw  = vd['branch']
            branch_name = branch_map.get(branch_raw.lower())
            if branch_name is None:
                row_errors.append({
                    'row':        idx,
                    'field':      'branch',
                    'identifier': email,
                    'message':    f'Company Code "{branch_raw}" not found.',
                })
                continue

            # Org Unit + Position — department/designation get derived from
            # the Position after the employee is created, same as Create
            # Employee's own Position picker.
            unit_raw  = vd['org_unit']
            title_raw = vd['position_title']
            matches = position_map.get((unit_raw.lower(), title_raw.lower()), [])
            if not matches:
                row_errors.append({
                    'row':        idx,
                    'field':      'position',
                    'identifier': email,
                    'message':    f'No active position "{title_raw}" found in org unit "{unit_raw}".',
                })
                continue
            if len(matches) > 1:
                row_errors.append({
                    'row':        idx,
                    'field':      'position',
                    'identifier': email,
                    'message':    f'"{title_raw}" in org unit "{unit_raw}" matches more than one position.',
                })
                continue
            position_id_for_row = matches[0]

            # Role existence check.
            role_raw = vd['role']
            role_obj = role_map.get(role_raw.lower())
            if role_obj is None:
                row_errors.append({
                    'row':        idx,
                    'field':      'role',
                    'identifier': email,
                    'message':    f'Role "{role_raw}" not found.',
                })
                continue
            if role_obj.role_permissions.filter(permission__codename='settings.edit').exists():
                row_errors.append({
                    'row':        idx,
                    'field':      'role',
                    'identifier': email,
                    'message':    f'"{role_obj.display_name}" cannot be assigned via bulk import.',
                })
                continue

            # Create the employee.
            try:
                temp_password = ''.join(
                    secrets.choice(string.ascii_letters + string.digits)
                    for _ in range(12)
                )
                employee_id = EmployeeCodeSettings.generate_employee_id(
                    first_name=vd['first_name'],
                    last_name=vd['last_name'],
                    date_of_joining=vd.get('date_of_joining'),
                )
                full_name   = f'{vd["first_name"]} {vd["last_name"]}'

                user = User.objects.create_user(
                    email                = email,
                    password             = temp_password,
                    full_name            = full_name,
                    role                 = role_obj,
                    employee_id          = employee_id,
                    branch               = branch_name,
                    phone                = vd.get('phone') or '',
                    employee_type        = vd.get('employee_type') or 'Permanent',
                    date_of_joining      = vd.get('date_of_joining'),
                    must_change_password = True,
                    onboarding_status    = User.ONBOARDING_PENDING,
                )

                if position_id_for_row is not None:
                    assign_position(
                        user, Position.objects.get(pk=position_id_for_row),
                        effective_from=vd.get('date_of_joining') or timezone.localdate(),
                        created_by=request.user,
                    )

                auto_fields = _auto_assign_managers(user)
                if auto_fields:
                    user.save(update_fields=[*auto_fields, 'updated_at'])

                # Create EmployeeProfile with any optional fields present in the import sheet.
                gender          = vd.get('gender') or ''
                dob             = vd.get('date_of_birth')
                blood           = vd.get('blood_group') or ''
                address         = vd.get('address') or ''
                uan_number      = vd.get('uan_number') or ''
                aadhar_name     = vd.get('name_as_per_aadhar') or ''
                if any([gender, dob, blood, address, uan_number, aadhar_name]):
                    EmployeeProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'gender':              gender,
                            'date_of_birth':       dob,
                            'blood_group':         blood,
                            'current_address':     address,
                            'uan_number':          uan_number,
                            'name_as_per_aadhar':  aadhar_name,
                        },
                    )

                # Create salary config if annual_ctc was provided in the import sheet.
                annual_ctc_import = vd.get('annual_ctc') or ''
                if annual_ctc_import:
                    from decimal import Decimal as _Decimal, InvalidOperation
                    from apps.payroll.models import EmployeeSalaryConfig as _SC
                    try:
                        ctc_value = _Decimal(str(annual_ctc_import).replace(',', ''))
                        _SC.objects.create(
                            employee=user,
                            annual_ctc=ctc_value,
                            effective_from=user.date_of_joining or user.date_joined.date(),
                            is_active=True,
                        )
                    except InvalidOperation:
                        logger.warning(
                            'Invalid annual_ctc value "%s" for %s — skipping salary config',
                            annual_ctc_import, email,
                        )
                        row_errors.append({
                            'row':     idx,
                            'field':   'annual_ctc',
                            'message': f'"{annual_ctc_import}" is not a valid number — salary config was not created for this employee.',
                        })
                    except Exception:
                        logger.warning('Could not create salary config for %s from import', email)

                # Auto-allocate leave balances based on active leave policies —
                # same step EmployeeListCreateView.post() does for a single
                # employee; this bulk path re-implements creation separately
                # and had been missing it entirely.
                from apps.hrms.views.leave import _allocate_leaves_for_employee
                _allocate_leaves_for_employee(user, user.date_of_joining)

                seen_emails.add(email)
                created_ids.append(employee_id)
                created_rows.append({'row': idx, 'identifier': email,
                                     'employee_id': employee_id})
                logger.info('Bulk import: employee %s (%s) created', employee_id, email)

            except Exception as exc:
                logger.error('Bulk import row %d failed (%s): %s', idx, email, exc)
                row_errors.append({
                    'row':        idx,
                    'field':      'general',
                    'identifier': email,
                    'message':    'Failed to create employee. Please verify the row data.',
                })

        total_rows    = len(rows)
        created_count = len(created_ids)
        skipped_count = len(skipped_rows)
        fail_count    = len(row_errors)

        AuditLog.objects.create(
            user       = request.user,
            action     = 'bulk_employee_import',
            module     = 'accounts',
            changes    = {
                'total_rows': total_rows,
                'created':    created_count,
                'skipped':    skipped_count,
                'failed':     fail_count,
            },
            ip_address = get_client_ip(request),
        )

        logger.info(
            'Bulk employee import by %s: %d created, %d skipped, %d failed (total %d)',
            request.user.email, created_count, skipped_count, fail_count, total_rows,
        )

        return success(
            'Bulk import completed.',
            data={
                'total_rows':           total_rows,
                'created':              created_count,
                'skipped':              skipped_count,
                'failed':               fail_count,
                'created_employee_ids': created_ids,
                'created_rows':         created_rows,
                'skipped_rows':         skipped_rows,
                'errors':               row_errors,
            },
        )


# ─── Employee Bulk Import — Sample Template ───────────────────────────────────

# Replaced by _has_perm check below — 'employees.create' covers both system_admin and HR.


class EmployeeBulkImportSampleView(APIView):
    """
    GET /api/employees/bulk-import/sample/?format=csv
    GET /api/employees/bulk-import/sample/?format=xlsx

    Download a sample import template for Employee Bulk Import.
    Headers are identical to the column aliases accepted by EmployeeBulkImportView.
    Permission mirrors the upload endpoint (system_admin / hr_admin only).
    """
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')
    authentication_classes = [JWTAuthentication]        

    _HEADERS = [
        'First Name', 'Last Name', 'Work Email', 'Mobile Number',
        'Role', 'Org Unit', 'Position', 'Company Code', 'Employee Type',
        'Date of Joining', 'Gender', 'Date of Birth', 'Blood Group', 'Address',
    ]
    _SAMPLE_ROWS = [
        [
            'John', 'Doe', 'john.doe@company.com', '9876543210',
            'Employee', 'Engineering', 'Software Engineer', 'Mumbai HQ', 'Permanent',
            '2026-01-15', 'Male', '1995-06-20', 'B+', '123 Main Street, Mumbai',
        ],
        [
            'Jane', 'Smith', 'jane.smith@company.com', '9123456789',
            'HR Admin', 'Human Resources', 'HR Manager', 'Delhi Branch', 'Permanent',
            '2026-02-01', 'Female', '1990-03-15', 'A+', '456 Park Avenue, Delhi',
        ],
    ]

    def get(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(
                'You do not have permission to download the employee import template.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        from core.file_utils import build_sample_csv, build_sample_xlsx, _CSV_MIME, _XLSX_MIME

        fmt = request.query_params.get('format', 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(self._HEADERS, self._SAMPLE_ROWS, 'Employee Import')
            filename = 'employee_import_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(self._HEADERS, self._SAMPLE_ROWS)
            filename = 'employee_import_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
