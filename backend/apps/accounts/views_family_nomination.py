"""
Family members and EPF nominees — two more genuinely unbounded add/remove
lists (same "bespoke onboarding step" family as Education/Experience in
views_education_experience.py, pulled out of the generic
OnboardingFieldConfig/_save_profile_step system for the same reason: neither
fits "one config row = one flat scalar value").

A nominee's name/relationship come from the employee's own FamilyMember list
(FK, not re-typed) — matching the mockup's own "pick from family" UX. There
is no server-side block on a nomination scheme's shares not summing to
100% — the mockup itself only ever *displays* that total, it never refuses
to save an incomplete one, and this app follows the same behavior.

Self-service locks once onboarding_status is COMPLETE, same convention as
views_education_experience.py; HR-on-behalf has no such lock.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, success

from apps.accounts.models import EPFNominee, FamilyMember, User

logger = logging.getLogger(__name__)

_SELF_LOCKED_MSG = 'Family/nomination details can no longer be edited here once onboarding is complete.'


def _self_locked(user: 'User') -> bool:
    return user.onboarding_status == User.ONBOARDING_COMPLETE


# ─── Family members ─────────────────────────────────────────────────────────

_VALID_RELATIONSHIPS = {key for key, _ in FamilyMember.RELATIONSHIP_CHOICES}
_VALID_GENDERS = {key for key, _ in FamilyMember.GENDER_CHOICES}


def family_dict(r: 'FamilyMember') -> dict:
    return {
        'id':             str(r.pk),
        'name':           r.name,
        'relationship':   r.relationship,
        'date_of_birth':  str(r.date_of_birth) if r.date_of_birth else '',
        'gender':         r.gender,
        'blood_group':    r.blood_group,
        'is_dependent':   r.is_dependent,
        'order':          r.order,
    }


def add_family_member(target_user: 'User', data: dict):
    """Returns (record, None) or (None, error_message)."""
    name = (data.get('name') or '').strip()
    if not name:
        return None, 'Name is required.'
    relationship = (data.get('relationship') or '').strip()
    if relationship and relationship not in _VALID_RELATIONSHIPS:
        return None, f'"{relationship}" is not a valid relationship.'
    gender = (data.get('gender') or '').strip()
    if gender and gender not in _VALID_GENDERS:
        return None, f'"{gender}" is not a valid gender.'
    max_order = FamilyMember.objects.filter(employee=target_user).count()
    record = FamilyMember.objects.create(
        employee=target_user,
        name=name,
        relationship=relationship,
        date_of_birth=data.get('date_of_birth') or None,
        gender=gender,
        blood_group=(data.get('blood_group') or '').strip(),
        is_dependent=bool(data.get('is_dependent')),
        order=max_order,
    )
    return record, None


def update_family_member(target_user: 'User', pk: str, data: dict):
    """Returns (record, None), (None, 'not_found'), or (None, error_message)."""
    record = FamilyMember.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return None, 'not_found'
    if 'name' in data and not (data.get('name') or '').strip():
        return None, 'Name is required.'
    if 'relationship' in data:
        relationship = (data.get('relationship') or '').strip()
        if relationship and relationship not in _VALID_RELATIONSHIPS:
            return None, f'"{relationship}" is not a valid relationship.'
    if 'gender' in data:
        gender = (data.get('gender') or '').strip()
        if gender and gender not in _VALID_GENDERS:
            return None, f'"{gender}" is not a valid gender.'
    for field in ('name', 'relationship', 'gender', 'blood_group'):
        if field in data:
            setattr(record, field, (data.get(field) or '').strip())
    if 'date_of_birth' in data:
        record.date_of_birth = data.get('date_of_birth') or None
    if 'is_dependent' in data:
        record.is_dependent = bool(data.get('is_dependent'))
    record.save()
    return record, None


def delete_family_member(target_user: 'User', pk: str) -> bool:
    record = FamilyMember.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return False
    record.delete()  # cascades to any EPFNominee rows pointing at this member
    return True


class FamilyMemberListView(APIView):
    """GET/POST /onboarding/family/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        records = FamilyMember.objects.filter(employee=request.user)
        return success('Family members retrieved.', data=[family_dict(r) for r in records])

    def post(self, request: Request) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = add_family_member(request.user, request.data)
        if err:
            return error(err)
        return success('Family member added.', data=family_dict(record), http_status=status.HTTP_201_CREATED)


class FamilyMemberDetailView(APIView):
    """PATCH/DELETE /onboarding/family/<id>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = update_family_member(request.user, pk, request.data)
        if err == 'not_found':
            return error('Family member not found.', http_status=status.HTTP_404_NOT_FOUND)
        if err:
            return error(err)
        return success('Family member updated.', data=family_dict(record))

    def delete(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        if not delete_family_member(request.user, pk):
            return error('Family member not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Family member removed.')


class HREmployeeFamilyMemberListView(APIView):
    """GET/POST /onboarding/employees/<user_id>/family/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        records = FamilyMember.objects.filter(employee=target)
        return success('Family members retrieved.', data=[family_dict(r) for r in records])

    def post(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = add_family_member(target, request.data)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_family_member_added_by_hr', {})
        return success('Family member added.', data=family_dict(record), http_status=status.HTTP_201_CREATED)


class HREmployeeFamilyMemberDetailView(APIView):
    """PATCH/DELETE /onboarding/employees/<user_id>/family/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = update_family_member(target, pk, request.data)
        if save_err == 'not_found':
            return error('Family member not found.', http_status=status.HTTP_404_NOT_FOUND)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_family_member_updated_by_hr', {})
        return success('Family member updated.', data=family_dict(record))

    def delete(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if not delete_family_member(target, pk):
            return error('Family member not found.', http_status=status.HTTP_404_NOT_FOUND)
        _audit_hr_onboarding(request, target, 'onboarding_family_member_removed_by_hr', {})
        return success('Family member removed.')


# ─── EPF nominees ────────────────────────────────────────────────────────────

_VALID_SCHEMES = {key for key, _ in EPFNominee.SCHEME_CHOICES}


def nominee_dict(r: 'EPFNominee') -> dict:
    return {
        'id':               str(r.pk),
        'family_member':    str(r.family_member_id),
        'family_member_name': r.family_member.name,
        'relationship':     r.family_member.relationship,
        'scheme':           r.scheme,
        'share_percentage': r.share_percentage,
        'order':            r.order,
    }


def add_nominee(target_user: 'User', data: dict):
    """Returns (record, None) or (None, error_message)."""
    family_member_id = (data.get('family_member') or '').strip()
    if not family_member_id:
        return None, 'A nominee must be selected from the family list.'
    family_member = FamilyMember.objects.filter(pk=family_member_id, employee=target_user).first()
    if not family_member:
        return None, 'That family member was not found for this employee.'
    scheme = (data.get('scheme') or 'epf_eps').strip()
    if scheme not in _VALID_SCHEMES:
        return None, f'"{scheme}" is not a valid nomination scheme.'
    try:
        share = int(data.get('share_percentage') or 0)
    except (TypeError, ValueError):
        return None, 'Share % must be a number.'
    share = max(0, min(100, share))
    max_order = EPFNominee.objects.filter(employee=target_user).count()
    record = EPFNominee.objects.create(
        employee=target_user, family_member=family_member,
        scheme=scheme, share_percentage=share, order=max_order,
    )
    return record, None


def update_nominee(target_user: 'User', pk: str, data: dict):
    """Returns (record, None), (None, 'not_found'), or (None, error_message)."""
    record = EPFNominee.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return None, 'not_found'
    if 'family_member' in data:
        family_member = FamilyMember.objects.filter(pk=data.get('family_member'), employee=target_user).first()
        if not family_member:
            return None, 'That family member was not found for this employee.'
        record.family_member = family_member
    if 'scheme' in data:
        scheme = (data.get('scheme') or '').strip()
        if scheme not in _VALID_SCHEMES:
            return None, f'"{scheme}" is not a valid nomination scheme.'
        record.scheme = scheme
    if 'share_percentage' in data:
        try:
            share = int(data.get('share_percentage') or 0)
        except (TypeError, ValueError):
            return None, 'Share % must be a number.'
        record.share_percentage = max(0, min(100, share))
    record.save()
    return record, None


def delete_nominee(target_user: 'User', pk: str) -> bool:
    record = EPFNominee.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return False
    record.delete()
    return True


class NomineeListView(APIView):
    """GET/POST /onboarding/nominees/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        records = EPFNominee.objects.filter(employee=request.user).select_related('family_member')
        return success('Nominees retrieved.', data=[nominee_dict(r) for r in records])

    def post(self, request: Request) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = add_nominee(request.user, request.data)
        if err:
            return error(err)
        return success('Nominee added.', data=nominee_dict(record), http_status=status.HTTP_201_CREATED)


class NomineeDetailView(APIView):
    """PATCH/DELETE /onboarding/nominees/<id>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = update_nominee(request.user, pk, request.data)
        if err == 'not_found':
            return error('Nominee not found.', http_status=status.HTTP_404_NOT_FOUND)
        if err:
            return error(err)
        return success('Nominee updated.', data=nominee_dict(record))

    def delete(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        if not delete_nominee(request.user, pk):
            return error('Nominee not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Nominee removed.')


class HREmployeeNomineeListView(APIView):
    """GET/POST /onboarding/employees/<user_id>/nominees/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        records = EPFNominee.objects.filter(employee=target).select_related('family_member')
        return success('Nominees retrieved.', data=[nominee_dict(r) for r in records])

    def post(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = add_nominee(target, request.data)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_nominee_added_by_hr', {})
        return success('Nominee added.', data=nominee_dict(record), http_status=status.HTTP_201_CREATED)


class HREmployeeNomineeDetailView(APIView):
    """PATCH/DELETE /onboarding/employees/<user_id>/nominees/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = update_nominee(target, pk, request.data)
        if save_err == 'not_found':
            return error('Nominee not found.', http_status=status.HTTP_404_NOT_FOUND)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_nominee_updated_by_hr', {})
        return success('Nominee updated.', data=nominee_dict(record))

    def delete(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if not delete_nominee(target, pk):
            return error('Nominee not found.', http_status=status.HTTP_404_NOT_FOUND)
        _audit_hr_onboarding(request, target, 'onboarding_nominee_removed_by_hr', {})
        return success('Nominee removed.')
