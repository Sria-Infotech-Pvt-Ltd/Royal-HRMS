"""
Education and Work Experience — both genuinely unbounded add/remove lists
(a qualification can repeat — two Bachelor's degrees, two "Other"
certifications — same as a person can have any number of previous jobs) —
pulled out of the generic OnboardingFieldConfig/_save_profile_step system
entirely, the same way Documents and Face ID already are, because neither
fits that system's "one config row = one flat scalar value" model.

Self-service and HR-on-behalf share the same target_user-parameterized
helper functions below, mirroring _save_profile_step(request, step,
target_user=None)'s own convention — each view class only resolves the
target employee (itself, or via views_onboarding_hr._resolve_onboarding_target)
and calls into these.

Self-service editing locks once onboarding_status is COMPLETE, matching
MyProfileUpdateSerializer's existing, deliberate exclusion of these same
fields from post-onboarding self-edit. HR-on-behalf editing has no such
lock (HR can always correct an employee's record, same as every other HR
onboarding endpoint in views_onboarding_hr.py).
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, success

from apps.accounts.models import (
    EDUCATION_LEVEL_CHOICES, EducationExperienceFieldConfig, EducationRecord, User, WorkExperienceRecord,
)
from apps.accounts.services_education_experience import sync_legacy_education_experience_fields

logger = logging.getLogger(__name__)

_VALID_LEVELS = {key for key, _ in EDUCATION_LEVEL_CHOICES}
_SELF_LOCKED_MSG = 'Education/experience can no longer be edited here once onboarding is complete.'


def _self_locked(user: 'User') -> bool:
    return user.onboarding_status == User.ONBOARDING_COMPLETE


def _missing_configured_field(list_type: str, get_effective_value) -> str | None:
    """First required+visible EducationExperienceFieldConfig field (for
    `list_type`) whose effective value is blank — `get_effective_value`
    resolves one field_key to what its value would actually end up being
    (the submitted value if present, else the existing record's current
    value for an update). A hidden field is never enforced as required —
    HR can't require something nobody has anywhere to fill in."""
    required_rows = EducationExperienceFieldConfig.objects.filter(
        list_type=list_type, visible=True, required=True,
    )
    for row in required_rows:
        value = get_effective_value(row.field_key)
        if isinstance(value, str):
            value = value.strip()
        if not value:
            return f'{row.label} is required.'
    return None


# ─── Education (unbounded list) ────────────────────────────────────────────

def education_dict(r: 'EducationRecord') -> dict:
    return {
        'id':                 str(r.pk),
        'level':              r.level,
        'level_display':      r.display_label(),
        'custom_level_label': r.custom_level_label,
        'institution':        r.institution,
        'specialization':     r.specialization,
        'percentage':         r.percentage,
        'start_date':         str(r.start_date) if r.start_date else '',
        'end_date':           str(r.end_date) if r.end_date else '',
        'order':              r.order,
    }


def _validate_education_level(data: dict) -> str | None:
    level = (data.get('level') or '').strip()
    if level and level not in _VALID_LEVELS:
        return f'"{level}" is not a valid education level.'
    return None


def add_education(target_user: 'User', data: dict):
    """Returns (record, None) or (None, error_message)."""
    level = (data.get('level') or '').strip()
    if not level:
        return None, 'Level is required.'
    err = _validate_education_level(data)
    if err:
        return None, err
    err = _missing_configured_field(
        EducationExperienceFieldConfig.LIST_EDUCATION,
        lambda field_key: data.get(field_key),
    )
    if err:
        return None, err
    max_order = EducationRecord.objects.filter(employee=target_user).count()
    record = EducationRecord.objects.create(
        employee=target_user,
        level=level,
        custom_level_label=(data.get('custom_level_label') or '').strip(),
        institution=(data.get('institution') or '').strip(),
        specialization=(data.get('specialization') or '').strip(),
        percentage=(data.get('percentage') or '').strip(),
        start_date=data.get('start_date') or None,
        end_date=data.get('end_date') or None,
        order=max_order,
    )
    sync_legacy_education_experience_fields(target_user)
    return record, None


def update_education(target_user: 'User', pk: str, data: dict):
    """Returns (record, None), (None, 'not_found'), or (None, error_message)."""
    record = EducationRecord.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return None, 'not_found'
    if 'level' in data and not (data.get('level') or '').strip():
        return None, 'Level is required.'
    err = _validate_education_level(data)
    if err:
        return None, err
    err = _missing_configured_field(
        EducationExperienceFieldConfig.LIST_EDUCATION,
        lambda field_key: data.get(field_key, getattr(record, field_key, None)),
    )
    if err:
        return None, err
    for field in ('level', 'custom_level_label', 'institution', 'specialization', 'percentage'):
        if field in data:
            setattr(record, field, (data.get(field) or '').strip())
    for field in ('start_date', 'end_date'):
        if field in data:
            setattr(record, field, data.get(field) or None)
    record.save()
    sync_legacy_education_experience_fields(target_user)
    return record, None


def delete_education(target_user: 'User', pk: str) -> bool:
    record = EducationRecord.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return False
    record.delete()
    sync_legacy_education_experience_fields(target_user)
    return True


class EducationListView(APIView):
    """GET/POST /onboarding/education/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        records = EducationRecord.objects.filter(employee=request.user)
        return success('Education retrieved.', data=[education_dict(r) for r in records])

    def post(self, request: Request) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = add_education(request.user, request.data)
        if err:
            return error(err)
        return success('Education entry added.', data=education_dict(record), http_status=status.HTTP_201_CREATED)


class EducationDetailView(APIView):
    """PATCH/DELETE /onboarding/education/<id>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = update_education(request.user, pk, request.data)
        if err == 'not_found':
            return error('Education entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        if err:
            return error(err)
        return success('Education entry updated.', data=education_dict(record))

    def delete(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        if not delete_education(request.user, pk):
            return error('Education entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Education entry removed.')


class HREmployeeEducationListView(APIView):
    """GET/POST /onboarding/employees/<user_id>/education/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        records = EducationRecord.objects.filter(employee=target)
        return success('Education retrieved.', data=[education_dict(r) for r in records])

    def post(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = add_education(target, request.data)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_education_added_by_hr', {})
        return success('Education entry added.', data=education_dict(record), http_status=status.HTTP_201_CREATED)


class HREmployeeEducationDetailView(APIView):
    """PATCH/DELETE /onboarding/employees/<user_id>/education/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = update_education(target, pk, request.data)
        if save_err == 'not_found':
            return error('Education entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_education_updated_by_hr', {})
        return success('Education entry updated.', data=education_dict(record))

    def delete(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if not delete_education(target, pk):
            return error('Education entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        _audit_hr_onboarding(request, target, 'onboarding_education_removed_by_hr', {})
        return success('Education entry removed.')


# ─── Work Experience (unbounded list) ──────────────────────────────────────

_VALID_EMPLOYMENT_TYPES = {key for key, _ in WorkExperienceRecord.EMPLOYMENT_TYPE_CHOICES}


def experience_dict(r: 'WorkExperienceRecord') -> dict:
    return {
        'id':                    str(r.pk),
        'employer_name':         r.employer_name,
        'designation':           r.designation,
        'employment_type':       r.employment_type,
        'employment_type_display': r.get_employment_type_display() if r.employment_type else '',
        'start_date':            str(r.start_date) if r.start_date else '',
        'end_date':              str(r.end_date) if r.end_date else '',
        'is_current':            r.end_date is None,
        'responsibilities':      r.responsibilities,
        'reason_for_leaving':    r.reason_for_leaving,
        'order':                 r.order,
    }


def _validate_employment_type(data: dict) -> str | None:
    """Returns an error message, or None if absent/valid."""
    value = (data.get('employment_type') or '').strip()
    if value and value not in _VALID_EMPLOYMENT_TYPES:
        return f'"{value}" is not a valid employment type.'
    return None


def add_experience(target_user: 'User', data: dict):
    """Returns (record, None) or (None, error_message)."""
    employer_name = (data.get('employer_name') or '').strip()
    if not employer_name:
        return None, 'Employer name is required.'
    err = _validate_employment_type(data)
    if err:
        return None, err
    is_current = bool(data.get('is_current'))
    err = _missing_configured_field(
        EducationExperienceFieldConfig.LIST_EXPERIENCE,
        # end_date=null legitimately means "currently working here" — never
        # treat that as a missing required field when is_current is set.
        lambda field_key: 'current' if (field_key == 'end_date' and is_current) else data.get(field_key),
    )
    if err:
        return None, err
    max_order = WorkExperienceRecord.objects.filter(employee=target_user).count()
    # is_current, when truthy, wins over any end_date also sent — matches
    # the checkbox's own intent ("currently working here" overrides a stray
    # leftover date rather than the other way round).
    record = WorkExperienceRecord.objects.create(
        employee=target_user,
        employer_name=employer_name,
        designation=(data.get('designation') or '').strip(),
        employment_type=(data.get('employment_type') or '').strip(),
        start_date=data.get('start_date') or None,
        end_date=None if is_current else (data.get('end_date') or None),
        responsibilities=(data.get('responsibilities') or '').strip(),
        reason_for_leaving=(data.get('reason_for_leaving') or '').strip(),
        order=max_order,
    )
    sync_legacy_education_experience_fields(target_user)
    return record, None


def update_experience(target_user: 'User', pk: str, data: dict):
    """Returns (record, None), (None, 'not_found'), or (None, error_message)."""
    record = WorkExperienceRecord.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return None, 'not_found'
    if 'employer_name' in data and not (data.get('employer_name') or '').strip():
        return None, 'Employer name is required.'
    err = _validate_employment_type(data)
    if err:
        return None, err
    effective_is_current = data['is_current'] if 'is_current' in data else record.end_date is None

    def _effective_value(field_key):
        if field_key == 'end_date':
            if effective_is_current:
                return 'current'
            return data.get('end_date') if 'end_date' in data else record.end_date
        return data.get(field_key, getattr(record, field_key, None))

    err = _missing_configured_field(EducationExperienceFieldConfig.LIST_EXPERIENCE, _effective_value)
    if err:
        return None, err
    for field in ('employer_name', 'designation', 'employment_type', 'responsibilities', 'reason_for_leaving'):
        if field in data:
            setattr(record, field, (data.get(field) or '').strip())
    if 'is_current' in data and data.get('is_current'):
        record.end_date = None
    elif 'end_date' in data:
        record.end_date = data.get('end_date') or None
    if 'start_date' in data:
        record.start_date = data.get('start_date') or None
    record.save()
    sync_legacy_education_experience_fields(target_user)
    return record, None


def delete_experience(target_user: 'User', pk: str) -> bool:
    record = WorkExperienceRecord.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return False
    record.delete()
    sync_legacy_education_experience_fields(target_user)
    return True


def get_total_experience_years(target_user: 'User'):
    """No longer manually settable — always derived from this employee's
    WorkExperienceRecord entries (date ranges, merged for any overlap) by
    sync_legacy_education_experience_fields(), called after every
    add/update/delete of an entry. This just reads the already-computed
    value back."""
    from apps.accounts.models import EmployeeProfile
    profile, _ = EmployeeProfile.objects.get_or_create(user=target_user)
    return profile.total_experience_years


class ExperienceListView(APIView):
    """GET/POST /onboarding/experience/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        records = WorkExperienceRecord.objects.filter(employee=request.user)
        return success('Experience retrieved.', data=[experience_dict(r) for r in records])

    def post(self, request: Request) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = add_experience(request.user, request.data)
        if err:
            return error(err, data={'employer_name': err})
        return success('Experience entry added.', data=experience_dict(record), http_status=status.HTTP_201_CREATED)


class ExperienceDetailView(APIView):
    """PATCH/DELETE /onboarding/experience/<id>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = update_experience(request.user, pk, request.data)
        if err == 'not_found':
            return error('Experience entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        if err:
            return error(err)
        return success('Experience entry updated.', data=experience_dict(record))

    def delete(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        if not delete_experience(request.user, pk):
            return error('Experience entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Experience entry removed.')


class TotalExperienceView(APIView):
    """GET /onboarding/experience/summary/ — the aggregate years-of-experience
    number. Read-only: it's derived from this employee's WorkExperienceRecord
    entries (see services_education_experience._compute_total_experience_years),
    recomputed after every add/update/delete of one — never entered directly."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success('Total experience retrieved.', data={'total_experience_years': get_total_experience_years(request.user)})


# ─── HR-on-behalf mirrors ───────────────────────────────────────────────────

class HREmployeeExperienceListView(APIView):
    """GET/POST /onboarding/employees/<user_id>/experience/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        records = WorkExperienceRecord.objects.filter(employee=target)
        return success('Experience retrieved.', data=[experience_dict(r) for r in records])

    def post(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = add_experience(target, request.data)
        if save_err:
            return error(save_err, data={'employer_name': save_err})
        _audit_hr_onboarding(request, target, 'onboarding_experience_added_by_hr', {})
        return success('Experience entry added.', data=experience_dict(record), http_status=status.HTTP_201_CREATED)


class HREmployeeExperienceDetailView(APIView):
    """PATCH/DELETE /onboarding/employees/<user_id>/experience/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = update_experience(target, pk, request.data)
        if save_err == 'not_found':
            return error('Experience entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_experience_updated_by_hr', {})
        return success('Experience entry updated.', data=experience_dict(record))

    def delete(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if not delete_experience(target, pk):
            return error('Experience entry not found.', http_status=status.HTTP_404_NOT_FOUND)
        _audit_hr_onboarding(request, target, 'onboarding_experience_removed_by_hr', {})
        return success('Experience entry removed.')


class HREmployeeTotalExperienceView(APIView):
    """GET /onboarding/employees/<user_id>/experience/summary/ — read-only,
    same as TotalExperienceView above."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        return success('Total experience retrieved.', data={'total_experience_years': get_total_experience_years(target)})
