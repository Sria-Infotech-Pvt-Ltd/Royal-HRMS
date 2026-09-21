"""
Company assets issued to an employee — another genuinely unbounded
add/remove list, same "bespoke onboarding step" shape as Education/
Experience/Family/Nominee. Optional at hire time (assets are normally
issued on the actual joining date, not during the wizard) — no
submission-blocking required-field gate here, matching the mockup.

Self-service locks once onboarding_status is COMPLETE, same convention as
the other bespoke steps; HR-on-behalf has no such lock.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, success

from apps.accounts.models import CompanyAsset, User

logger = logging.getLogger(__name__)

_SELF_LOCKED_MSG = 'Assets can no longer be edited here once onboarding is complete.'
_VALID_ASSET_TYPES = {key for key, _ in CompanyAsset.ASSET_TYPE_CHOICES}
_VALID_CONDITIONS = {key for key, _ in CompanyAsset.CONDITION_CHOICES}


def _self_locked(user: 'User') -> bool:
    return user.onboarding_status == User.ONBOARDING_COMPLETE


def asset_dict(r: 'CompanyAsset') -> dict:
    return {
        'id':          str(r.pk),
        'asset_type':  r.asset_type,
        'asset_type_display': r.get_asset_type_display(),
        'tag_number':  r.tag_number,
        'condition':   r.condition,
        'issued_at':   str(r.issued_at) if r.issued_at else '',
        'returned_at': str(r.returned_at) if r.returned_at else '',
        'order':       r.order,
    }


def add_asset(target_user: 'User', data: dict):
    """Returns (record, None) or (None, error_message)."""
    asset_type = (data.get('asset_type') or '').strip()
    if not asset_type:
        return None, 'Asset type is required.'
    if asset_type not in _VALID_ASSET_TYPES:
        return None, f'"{asset_type}" is not a valid asset type.'
    condition = (data.get('condition') or 'new').strip()
    if condition not in _VALID_CONDITIONS:
        return None, f'"{condition}" is not a valid condition.'
    max_order = CompanyAsset.objects.filter(employee=target_user).count()
    record = CompanyAsset.objects.create(
        employee=target_user,
        asset_type=asset_type,
        tag_number=(data.get('tag_number') or '').strip(),
        condition=condition,
        issued_at=data.get('issued_at') or None,
        order=max_order,
    )
    return record, None


def update_asset(target_user: 'User', pk: str, data: dict):
    """Returns (record, None), (None, 'not_found'), or (None, error_message)."""
    record = CompanyAsset.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return None, 'not_found'
    if 'asset_type' in data:
        asset_type = (data.get('asset_type') or '').strip()
        if not asset_type:
            return None, 'Asset type is required.'
        if asset_type not in _VALID_ASSET_TYPES:
            return None, f'"{asset_type}" is not a valid asset type.'
        record.asset_type = asset_type
    if 'condition' in data:
        condition = (data.get('condition') or '').strip()
        if condition not in _VALID_CONDITIONS:
            return None, f'"{condition}" is not a valid condition.'
        record.condition = condition
    if 'tag_number' in data:
        record.tag_number = (data.get('tag_number') or '').strip()
    if 'issued_at' in data:
        record.issued_at = data.get('issued_at') or None
    if 'returned_at' in data:
        record.returned_at = data.get('returned_at') or None
    record.save()
    return record, None


def delete_asset(target_user: 'User', pk: str) -> bool:
    record = CompanyAsset.objects.filter(pk=pk, employee=target_user).first()
    if not record:
        return False
    record.delete()
    return True


class AssetListView(APIView):
    """GET/POST /onboarding/assets/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        records = CompanyAsset.objects.filter(employee=request.user)
        return success('Assets retrieved.', data=[asset_dict(r) for r in records])

    def post(self, request: Request) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = add_asset(request.user, request.data)
        if err:
            return error(err)
        return success('Asset added.', data=asset_dict(record), http_status=status.HTTP_201_CREATED)


class AssetDetailView(APIView):
    """PATCH/DELETE /onboarding/assets/<id>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        record, err = update_asset(request.user, pk, request.data)
        if err == 'not_found':
            return error('Asset not found.', http_status=status.HTTP_404_NOT_FOUND)
        if err:
            return error(err)
        return success('Asset updated.', data=asset_dict(record))

    def delete(self, request: Request, pk: str) -> Response:
        if _self_locked(request.user):
            return error(_SELF_LOCKED_MSG, http_status=status.HTTP_403_FORBIDDEN)
        if not delete_asset(request.user, pk):
            return error('Asset not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Asset removed.')


class HREmployeeAssetListView(APIView):
    """GET/POST /onboarding/employees/<user_id>/assets/"""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        records = CompanyAsset.objects.filter(employee=target)
        return success('Assets retrieved.', data=[asset_dict(r) for r in records])

    def post(self, request: Request, user_id: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = add_asset(target, request.data)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_asset_added_by_hr', {})
        return success('Asset added.', data=asset_dict(record), http_status=status.HTTP_201_CREATED)


class HREmployeeAssetDetailView(APIView):
    """PATCH/DELETE /onboarding/employees/<user_id>/assets/<pk>/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        record, save_err = update_asset(target, pk, request.data)
        if save_err == 'not_found':
            return error('Asset not found.', http_status=status.HTTP_404_NOT_FOUND)
        if save_err:
            return error(save_err)
        _audit_hr_onboarding(request, target, 'onboarding_asset_updated_by_hr', {})
        return success('Asset updated.', data=asset_dict(record))

    def delete(self, request: Request, user_id: str, pk: str) -> Response:
        from apps.accounts.views_onboarding_hr import _audit_hr_onboarding, _resolve_onboarding_target
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if not delete_asset(target, pk):
            return error('Asset not found.', http_status=status.HTTP_404_NOT_FOUND)
        _audit_hr_onboarding(request, target, 'onboarding_asset_removed_by_hr', {})
        return success('Asset removed.')
