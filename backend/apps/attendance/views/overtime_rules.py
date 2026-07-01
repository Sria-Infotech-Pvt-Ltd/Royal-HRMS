from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from apps.attendance.models import OvertimePolicy
from apps.attendance.serializers import (
    OvertimePolicyCreateSerializer,
    OvertimePolicyListSerializer,
    OvertimePolicyRetrieveSerializer,
    OvertimePolicyUpdateSerializer,
)

logger = logging.getLogger(__name__)

_PERM_DENIED = 'You do not have permission to perform this action.'


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class OvertimePolicyListCreateView(APIView):
    """
    GET  /api/attendance/overtime-rules/  — paginated list
    POST /api/attendance/overtime-rules/  — create new policy
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            OvertimePolicy.objects
            .select_related('created_by', 'updated_by')
            .all()
        )

        is_active_param = request.query_params.get('is_active')
        if is_active_param is not None:
            qs = qs.filter(is_active=is_active_param.lower() == 'true')

        is_default_param = request.query_params.get('is_default')
        if is_default_param is not None:
            qs = qs.filter(is_default=is_default_param.lower() == 'true')

        approval_type = request.query_params.get('approval_type')
        if approval_type:
            qs = qs.filter(approval_type=approval_type)

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(policy_code__icontains=search)

        page_obj, paginator = paginate(qs, request)
        serializer = OvertimePolicyListSerializer(page_obj, many=True)

        return success(
            'Overtime policies retrieved successfully.',
            data=paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if not data.get('policy_code'):
            count = OvertimePolicy.objects.count()
            data['policy_code'] = f'OT-{count + 1:03d}'

        serializer = OvertimePolicyCreateSerializer(data=data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        policy = serializer.save(created_by=request.user, updated_by=request.user)
        logger.info('Overtime policy created — code=%s by user=%s', policy.policy_code, request.user.email)

        return success(
            'Overtime policy created successfully.',
            data=OvertimePolicyRetrieveSerializer(policy).data,
            http_status=status.HTTP_201_CREATED,
        )


class OvertimePolicyDetailView(APIView):
    """
    GET    /api/attendance/overtime-rules/<pk>/ — retrieve
    PUT    /api/attendance/overtime-rules/<pk>/ — full update
    PATCH  /api/attendance/overtime-rules/<pk>/ — partial update
    DELETE /api/attendance/overtime-rules/<pk>/ — soft delete
    """

    permission_classes = [IsAuthenticated]

    def _get_policy(self, pk: str) -> OvertimePolicy | None:
        try:
            return (
                OvertimePolicy.objects
                .select_related('created_by', 'updated_by')
                .get(pk=pk)
            )
        except (OvertimePolicy.DoesNotExist, ValueError):
            return None

    def get(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Overtime policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success(
            'Overtime policy retrieved successfully.',
            data=OvertimePolicyRetrieveSerializer(policy).data,
        )

    def put(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Overtime policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = OvertimePolicyUpdateSerializer(policy, data=request.data, partial=False)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        policy = serializer.save(updated_by=request.user)
        logger.info('Overtime policy updated (full) — code=%s by user=%s', policy.policy_code, request.user.email)
        return success('Overtime policy updated successfully.', data=OvertimePolicyRetrieveSerializer(policy).data)

    def patch(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Overtime policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = OvertimePolicyUpdateSerializer(policy, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        policy = serializer.save(updated_by=request.user)
        logger.info('Overtime policy updated (partial) — code=%s by user=%s', policy.policy_code, request.user.email)
        return success('Overtime policy updated successfully.', data=OvertimePolicyRetrieveSerializer(policy).data)

    def delete(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.delete'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Overtime policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        if policy.is_default:
            return error(
                'Cannot deactivate the default overtime policy. '
                'Assign another policy as default before removing this one.',
                http_status=status.HTTP_409_CONFLICT,
            )
        if not policy.is_active:
            return error('Overtime policy is already inactive.', http_status=status.HTTP_409_CONFLICT)
        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        logger.info('Overtime policy deactivated — code=%s by user=%s', policy.policy_code, request.user.email)
        return success('Overtime policy deactivated successfully.')
