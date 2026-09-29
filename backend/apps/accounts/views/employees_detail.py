
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







# Personal/Education/Bank/Emergency EmployeeProfile fields editable via
# EmployeeDetailView.put() — see _employee_dict()'s profile_data above for
# the matching read-side list (date_of_birth/current_address excluded here,
# see the comment at the call site).
_PROFILE_FIELD_KEYS = frozenset({
    'gender', 'marital_status', 'father_name', 'blood_group', 'permanent_address',
    # current_* address sub-fields are excluded for the same reason
    # current_address itself already is (see the comment above _PROFILE_FIELD_KEYS'
    # call site) — permanent_* sub-fields follow permanent_address into this
    # page's editable set.
    'permanent_address_line2',
    'permanent_village', 'permanent_district', 'permanent_state', 'permanent_pin_code',
    'permanent_same_as_current',
    'highest_qualification', 'institution', 'year_of_passing', 'specialization',
    'total_experience_years', 'previous_employer', 'previous_designation', 'leaving_reason',
    'account_holder_name', 'account_type', 'account_number', 'ifsc_code',
    'bank_name', 'bank_branch_name',
    'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email',
    'personal_email',
    # uan_number/name_as_per_aadhar/esi_number were already declared on
    # EmployeeProfileSerializer and (for the first two) already rendered as
    # editable fields on this page's EPF/Statutory tab — but missing from
    # this whitelist meant they were silently dropped on every save via the
    # normal Edit flow. Only writable here going forward via
    # OnboardingApprovalView (HR approval time) or bulk import before this.
    'uan_number', 'name_as_per_aadhar', 'esi_number',
    'custom_field_values',
})




class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        # Self-view bypass — mirrors EmployeeAuditTrailView/
        # EmployeeActionHistoryView's own is_self pattern. This endpoint is
        # the one the ESS "My Profile" → "Open full employee profile" drawer
        # (mode="self") deliberately reuses (see EmployeeFullRecordBody.tsx —
        # "the same employee record and layout used by Admin, with
        # self-service permissions"), but a plain employee role never holds
        # employees.view (an HR/admin permission for looking up OTHER
        # people's records) — without this bypass, every self-view request
        # 403'd before ever reaching the self-view-aware masking logic below,
        # leaving that whole drawer blank for any non-admin employee.
        is_self = request.user.employee_id == employee_id
        if not is_self and not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or (not is_self and _employee_out_of_branch_scope(request.user, employee)):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        auto_changed = _auto_assign_managers(employee)
        if auto_changed:
            employee.save(update_fields=auto_changed + ['updated_at'])
        data = _employee_dict(employee)
        # Bank details are only masked when viewing SOMEONE ELSE's record
        # without employees.view_sensitive — self-view always sees the real
        # values, matching every other self-service surface in this app.
        if not is_self and not _has_perm(request.user, 'employees.view_sensitive'):
            data = _mask_bank_fields(data)
        return success('Employee retrieved.', data=data)

    def put(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        data          = request.data
        update_fields = ['updated_at']
        changes       = {}
        # full_name/phone/date_of_joining are shown as read-only on the
        # employee detail page once onboarding is complete ("set by system,
        # not editable" — see PROFILE_SECTIONS in the frontend's _data.ts).
        # That was previously a front-end-only convention with no matching
        # check here, so any direct API call could silently overwrite them
        # even after the UI stopped offering a way to. Enforced here now so
        # the lock is real, not just an absent button.
        locked = employee.onboarding_status == User.ONBOARDING_COMPLETE

        role_name = (data.get('role') or '').strip()
        if role_name:
            try:
                new_role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                return error(f'Role "{role_name}" does not exist.')
            if new_role.role_permissions.filter(permission__codename='settings.edit').exists():
                return error(f'"{new_role.display_name}" cannot be assigned via employee edit.')
            old_role = employee.role.name if employee.role else None
            if old_role != new_role.name:
                changes['role'] = {'from': old_role, 'to': new_role.name}
            employee.role = new_role
            update_fields.append('role')

        # department/designation are Position-derived only — set exclusively
        # via assign_position() below (position_obj), never by direct edit.
        for field in ('branch',):
            val = (data.get(field) or '').strip()
            if field in data:
                old_val = getattr(employee, field, '')
                if old_val != val:
                    changes[field] = {'from': old_val, 'to': val}
                setattr(employee, field, val)
                update_fields.append(field)

        position_id = (data.get('position') or '').strip()
        position_obj = None
        if position_id:
            try:
                position_obj = Position.objects.select_related(
                    'org_unit', 'job_template',
                ).get(pk=position_id, is_active=True)
            except (Position.DoesNotExist, ValueError, ValidationError):
                return error('Select a valid, active position.', data={'position': 'Position not found.'})

        if 'phone' in data:
            phone = (data.get('phone') or '').strip()
            if locked and phone != employee.phone:
                return error(
                    'Phone number is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
            if employee.phone != phone:
                changes['phone'] = {'from': employee.phone, 'to': phone}
            employee.phone = phone
            update_fields.append('phone')

        if 'work_location' in data:
            # "Org assignment" action (Perform an action modal) — a plain
            # descriptive field with no locking/onboarding rule attached,
            # unlike phone/employee_type/full_name above.
            work_location = (data.get('work_location') or '').strip()
            if employee.work_location != work_location:
                changes['work_location'] = {'from': employee.work_location, 'to': work_location}
            employee.work_location = work_location
            update_fields.append('work_location')

        if 'employee_type' in data:
            employee_type = (data.get('employee_type') or '').strip()
            if locked and employee_type != employee.employee_type:
                return error(
                    'Employee type is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
            if employee.employee_type != employee_type:
                changes['employee_type'] = {'from': employee.employee_type, 'to': employee_type}
            employee.employee_type = employee_type
            update_fields.append('employee_type')

        full_name = (data.get('full_name') or '').strip()
        if full_name:
            if locked and full_name != employee.full_name:
                return error(
                    'Full name is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
            if employee.full_name != full_name:
                changes['full_name'] = {'from': employee.full_name, 'to': full_name}
            employee.full_name = full_name
            update_fields.append('full_name')

        doj = (data.get('date_of_joining') or '').strip()
        if doj:
            try:
                datetime.strptime(doj, '%Y-%m-%d')
            except ValueError:
                return error('date_of_joining must be in YYYY-MM-DD format.')
            if locked and doj != str(employee.date_of_joining):
                return error(
                    'Date of joining is locked once onboarding is complete and can no longer be changed here.',
                    http_status=status.HTTP_409_CONFLICT,
                )
            if str(employee.date_of_joining) != doj:
                changes['date_of_joining'] = {'from': str(employee.date_of_joining), 'to': doj}
            employee.date_of_joining = doj
            update_fields.append('date_of_joining')

        dob_raw = (data.get('date_of_birth') or '').strip()
        if dob_raw:
            try:
                datetime.strptime(dob_raw, '%Y-%m-%d')
            except ValueError:
                return error('date_of_birth must be in YYYY-MM-DD format.')
            from apps.accounts.models import EmployeeProfile
            profile, _ = EmployeeProfile.objects.get_or_create(user=employee)
            old_dob = str(profile.date_of_birth) if profile.date_of_birth else ''
            if old_dob != dob_raw:
                changes['date_of_birth'] = {'from': old_dob, 'to': dob_raw}
            profile.date_of_birth = dob_raw
            profile.save(update_fields=['date_of_birth', 'updated_at'])

        # Personal/Education/Bank/Emergency EmployeeProfile fields — previously
        # displayed on this page's edit form but silently dropped on save (no
        # write path existed for any of them). Reuses EmployeeProfileSerializer
        # (already handles validation, encryption, and the bank-details-changed
        # audit alert via _changed_by) rather than 23 more manual field blocks.
        # date_of_birth/current_address are deliberately excluded — the former
        # already has its own block above, the latter isn't part of this page's
        # editable set today.
        profile_saved = False
        if _PROFILE_FIELD_KEYS & set(data.keys()):
            from apps.accounts.models import EmployeeProfile
            from apps.accounts.serializers import EmployeeProfileSerializer
            profile, _ = EmployeeProfile.objects.get_or_create(user=employee)
            profile_update = {k: v for k, v in data.items() if k in _PROFILE_FIELD_KEYS}
            if 'custom_field_values' in profile_update:
                file_keys = _file_type_custom_field_keys()
                merged = dict(profile.custom_field_values or {})
                merged.update({
                    k: v for k, v in (profile_update['custom_field_values'] or {}).items()
                    if k not in file_keys
                })
                profile_update['custom_field_values'] = merged
            serializer = EmployeeProfileSerializer(profile, data=profile_update, partial=True)
            if not serializer.is_valid():
                return error(first_error(serializer.errors), data=serializer.errors)
            profile._changed_by = request.user
            serializer.save()
            profile_saved = True

        if len(update_fields) == 1 and not profile_saved and position_obj is None:
            # Check if hr_id, reporting_manager_id, or reporting_approver_id will be set before bailing
            if 'hr_id' not in data and 'reporting_manager_id' not in data and 'reporting_approver_id' not in data:
                return error('No updatable fields provided.')

        # Auto-assign null fields first — manual overrides below will overwrite if needed
        auto_changed = _auto_assign_managers(employee)
        for field in auto_changed:
            if field not in update_fields:
                update_fields.append(field)

        # Manual HR assignment (overrides auto-assign)
        if 'hr_id' in data:
            hr_val = data.get('hr_id')
            if hr_val:
                try:
                    hr_user = User.objects.get(pk=hr_val, is_active=True)
                except (User.DoesNotExist, Exception):
                    return error('HR user not found or is inactive.')
                if hr_user.pk == employee.pk:
                    return error('An employee cannot be their own HR.')
                employee.hr = hr_user
            else:
                employee.hr = None
            if 'hr' not in update_fields:
                update_fields.append('hr')

        # Manual reporting manager assignment (overrides auto-assign; blocked for managers)
        if 'reporting_manager_id' in data:
            if employee.role and employee.role.can_manage_team:
                return error('Managers do not have a reporting manager.')
            rm_val = data.get('reporting_manager_id')
            if rm_val:
                try:
                    rm_user = User.objects.get(pk=rm_val, is_active=True)
                except (User.DoesNotExist, Exception):
                    return error('Reporting manager not found or is inactive.')
                if rm_user.pk == employee.pk:
                    return error('An employee cannot be their own reporting manager.')
                employee.reporting_manager = rm_user
            else:
                employee.reporting_manager = None
            employee.reporting_manager_from_org_chart = False
            if 'reporting_manager' not in update_fields:
                update_fields.append('reporting_manager')
            if 'reporting_manager_from_org_chart' not in update_fields:
                update_fields.append('reporting_manager_from_org_chart')

        # Manual reporting approver assignment — the designated approver for a
        # Manager/HR employee's own requests (e.g. separation) in place of a
        # reporting_manager, which isn't applicable to those roles.
        if 'reporting_approver_id' in data:
            ra_val = data.get('reporting_approver_id')
            if ra_val:
                try:
                    ra_user = User.objects.get(pk=ra_val, is_active=True)
                except (User.DoesNotExist, Exception):
                    return error('Reporting approver not found or is inactive.')
                if ra_user.pk == employee.pk:
                    return error('An employee cannot be their own reporting approver.')
                employee.reporting_approver = ra_user
            else:
                employee.reporting_approver = None
            if 'reporting_approver' not in update_fields:
                update_fields.append('reporting_approver')

        if len(update_fields) == 1 and not profile_saved and position_obj is None:
            return error('No updatable fields provided.')

        # Promotion (Employee > Promotion screen) piggybacks on this same
        # generic PUT — it sends only {designation, role} today, same as any
        # other employee edit, so effective_date/remarks are optional and
        # default sensibly when absent rather than being required.
        effective_date_raw = (data.get('effective_date') or '').strip()
        if effective_date_raw:
            try:
                effective_date = datetime.strptime(effective_date_raw, '%Y-%m-%d').date()
            except ValueError:
                return error('effective_date must be in YYYY-MM-DD format.')
        else:
            effective_date = timezone.now().date()
        remarks = (data.get('remarks') or '').strip()
        # "Perform an action" modal's Reason field (Promotion/Org assignment) —
        # validated against PromotionRecord.REASON_CHOICES so an unrecognised
        # value never silently gets stored; blank stays blank for every other
        # caller of this same PUT (plain field edits carry no reason at all).
        reason_raw = (data.get('reason') or '').strip()
        if reason_raw and reason_raw not in dict(PromotionRecord.REASON_CHOICES):
            return error('reason must be one of the recognised action reasons.')
        if reason_raw:
            changes['reason'] = reason_raw

        if position_obj is not None:
            # "Reassign Position" — a dated event like a promotion, not a
            # plain field edit. assign_position() closes the employee's
            # prior placement (if any) and this position's prior holder
            # (if any), then syncs designation/department from the new
            # position; folded into `changes` here so the existing
            # PromotionRecord logic below picks up a resulting designation
            # change exactly as it would for a manual designation edit.
            old_designation, old_department = employee.designation, employee.department
            assign_position(employee, position_obj, effective_from=effective_date, created_by=request.user)
            # Only refresh the two fields assign_position's sync may have
            # changed — a bare refresh_from_db() would also discard the
            # pending in-memory `role` change (set earlier in this method,
            # not yet saved) by resetting it back to the stale DB value.
            employee.refresh_from_db(fields=[
                'designation', 'department',
                'designation_synced_from_position', 'department_synced_from_position',
            ])
            if employee.designation != old_designation:
                changes['designation'] = {'from': old_designation, 'to': employee.designation}
            if employee.department != old_department:
                changes['department'] = {'from': old_department, 'to': employee.department}
            update_fields = [f for f in update_fields if f not in ('designation', 'department')]

        promotion_changed = 'designation' in changes or 'role' in changes

        with transaction.atomic():
            employee.save(update_fields=list(dict.fromkeys(update_fields)))

            if changes:
                AuditLog.objects.create(
                    user       = request.user,
                    action     = 'employee_updated',
                    module     = 'employees',
                    object_id  = str(employee.id),
                    changes    = {
                        'employee_id': employee.employee_id,
                        'full_name':   employee.full_name,
                        **changes,
                    },
                    branch     = employee.branch,
                    ip_address = get_client_ip(request),
                )

            if promotion_changed:
                desig_change  = changes.get('designation', {})
                role_change   = changes.get('role', {})
                current_role_name = employee.role.name if employee.role else ''
                PromotionRecord.objects.create(
                    employee              = employee,
                    previous_designation  = desig_change.get('from', employee.designation) or '',
                    new_designation       = desig_change.get('to', employee.designation) or '',
                    previous_role         = role_change.get('from', current_role_name) or '',
                    new_role              = role_change.get('to', current_role_name) or '',
                    effective_date        = effective_date,
                    remarks               = remarks,
                    promoted_by           = request.user,
                    reason                = reason_raw,
                )

        employee = _get_employee(employee_id)
        return success('Employee updated successfully.', data=_employee_dict(employee))

    def patch(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if 'is_active' not in request.data:
            return error('is_active field is required.')

        raw = request.data.get('is_active')
        if isinstance(raw, bool):
            new_status = raw
        elif isinstance(raw, str) and raw.lower() in ('true', 'false'):
            new_status = raw.lower() == 'true'
        else:
            return error('is_active must be true or false.')

        if employee.id == request.user.id and not new_status:
            return error('You cannot deactivate your own account.')

        if not new_status:
            if employee.role and employee.role.role_permissions.filter(permission__codename='settings.edit').exists():
                active_admins = User.objects.filter(
                    role__role_permissions__permission__codename='settings.edit',
                    is_active=True,
                ).distinct().count()
                if active_admins <= 1:
                    return error('Cannot deactivate the only active administrator with full org-wide access.')

        old_status = employee.is_active
        if old_status == new_status:
            msg = 'Employee is already active.' if new_status else 'Employee is already inactive.'
            return success(msg, data=_employee_dict(employee))

        employee.is_active = new_status
        employee.save(update_fields=['is_active', 'updated_at'])

        if not new_status:
            # Deactivation is the closest thing this codebase has to
            # "employee separated" today (no dedicated separation/offboarding
            # model exists yet) — purge their stored face biometric data here
            # rather than retaining it indefinitely for someone no longer employed.
            from apps.attendance.services_face_lifecycle import purge_face_data_for_employee
            purge_face_data_for_employee(employee)

            # Same reasoning — close their open Placement so the seat they
            # held stops being reported as filled. Position.holder resolves
            # purely by placement date range with no is_active check, so
            # without this the position stayed permanently "occupied" by a
            # deactivated employee.
            from apps.accounts.services_placement import vacate_employee
            vacate_employee(employee)

        action_label = 'employee_activated' if new_status else 'employee_deactivated'
        AuditLog.objects.create(
            user       = request.user,
            action     = action_label,
            module     = 'employees',
            object_id  = str(employee.id),
            changes    = {
                'employee_id': employee.employee_id,
                'full_name':   employee.full_name,
                'is_active':   {'from': old_status, 'to': new_status},
            },
            branch     = employee.branch,
            ip_address = get_client_ip(request),
        )

        verb = 'activated' if new_status else 'deactivated'
        return success(f'Employee {verb} successfully.', data=_employee_dict(employee))

    def delete(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.delete'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if employee.id == request.user.id:
            return error('You cannot delete your own account.')

        if not employee.is_active:
            return error(f'Employee "{employee.full_name}" is already deactivated.')

        if employee.role and employee.role.role_permissions.filter(permission__codename='settings.edit').exists():
            active_admins = User.objects.filter(
                role__role_permissions__permission__codename='settings.edit',
                is_active=True,
            ).distinct().count()
            if active_admins <= 1:
                return error('Cannot delete the only active administrator with full org-wide access.')

        full_name    = employee.full_name
        emp_id_str   = employee.employee_id
        emp_branch   = employee.branch

        employee.is_active = False
        employee.save(update_fields=['is_active', 'updated_at'])

        # Same reasoning as EmployeeDetailView.patch's deactivation path above.
        from apps.attendance.services_face_lifecycle import purge_face_data_for_employee
        purge_face_data_for_employee(employee)

        from apps.accounts.services_placement import vacate_employee
        vacate_employee(employee)

        AuditLog.objects.create(
            user       = request.user,
            action     = 'employee_deleted',
            module     = 'employees',
            object_id  = str(employee.id),
            changes    = {'employee_id': emp_id_str, 'full_name': full_name},
            branch     = emp_branch,
            ip_address = get_client_ip(request),
        )
        logger.info('Employee "%s" deactivated (deleted) by %s', full_name, request.user.email)
        # Not a real "deleted successfully" — this is a soft delete
        # (is_active=False) that keeps the full record, including PII, for
        # statutory retention (see the Consent & Retention section of the
        # employee record: retained N years after exit, non-statutory
        # fields only erasable separately/later). Saying "deleted" here was
        # actively misleading — the record is fully intact and still
        # queryable/exportable, just marked inactive.
        return success(f'Employee "{full_name}" deactivated. Record retained for statutory compliance.')

    def post(self, request, employee_id: str):
        return self.put(request, employee_id)


class EmployeeBankChangeReviewView(APIView):
    """
    POST /employees/<employee_id>/bank-change/approve/
    POST /employees/<employee_id>/bank-change/reject/

    HR review step for a self-service bank detail change — see
    EmployeeProfile.submit_bank_change()/approve_bank_change()/
    reject_bank_change() and the bank-change verification gate in
    _save_profile_step() (views/shared.py). Approving copies the pending_*
    values onto the live columns payroll reads; rejecting discards them and
    leaves the previous bank details untouched.
    """
    permission_classes = [IsAuthenticated]

    def _decide(self, request, employee_id: str, *, approve: bool):
        from apps.accounts.models import EmployeeProfile
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if not employee:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        profile = getattr(employee, 'profile', None)
        if not profile or profile.bank_change_status != EmployeeProfile.BANK_CHANGE_PENDING:
            return error('There is no pending bank detail change for this employee.')

        if approve:
            profile.approve_bank_change(actor=request.user)
            action, message = 'bank_change_approved', 'Bank detail change approved.'
        else:
            profile.reject_bank_change(actor=request.user)
            action, message = 'bank_change_rejected', 'Bank detail change rejected.'

        AuditLog.objects.create(
            user=request.user, action=action, module='employees',
            object_id=str(employee.id),
            changes={'employee': employee.employee_id or employee.email},
            branch=employee.branch, ip_address=get_client_ip(request),
        )
        logger.info('%s for %s by %s', action, employee.email, request.user.email)
        return success(message)

    def post(self, request, employee_id: str, decision: str):
        if decision == 'approve':
            return self._decide(request, employee_id, approve=True)
        if decision == 'reject':
            return self._decide(request, employee_id, approve=False)
        return error('Invalid decision.', http_status=status.HTTP_400_BAD_REQUEST)
