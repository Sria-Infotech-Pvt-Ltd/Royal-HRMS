"""
Late Mark & LOP Policy views.

Endpoints
---------
GET  /api/attendance/late-mark-lop/          List all active policies (paginated).
POST /api/attendance/late-mark-lop/          Create a new policy.
GET  /api/attendance/late-mark-lop/<pk>/     Retrieve a single policy.
PUT  /api/attendance/late-mark-lop/<pk>/     Full update.
PATCH /api/attendance/late-mark-lop/<pk>/    Partial update.
DELETE /api/attendance/late-mark-lop/<pk>/   Soft-delete (is_active=False).
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from apps.attendance.models import LateMarkLOPPolicy
from apps.attendance.serializers import (
    LateMarkLOPPolicyCreateSerializer,
    LateMarkLOPPolicyListSerializer,
    LateMarkLOPPolicyRetrieveSerializer,
    LateMarkLOPPolicyUpdateSerializer,
)

logger = logging.getLogger(__name__)

_PERM_DENIED = 'You do not have permission to perform this action.'


class LateMarkLOPPolicyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            LateMarkLOPPolicy.objects
            .filter(is_active=True)
            .select_related('created_by', 'updated_by')
            .order_by('-is_default', 'name')
        )

        is_default = request.query_params.get('is_default')
        if is_default is not None:
            qs = qs.filter(is_default=(is_default.lower() == 'true'))

        page_obj, paginator = paginate(qs, request)
        serializer = LateMarkLOPPolicyListSerializer(page_obj, many=True)
        return success(
            'Late mark/LOP policies retrieved successfully.',
            data=paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if not data.get('policy_code'):
            existing_count = LateMarkLOPPolicy.objects.count()
            data['policy_code'] = f'LM-{existing_count + 1:03d}'

        serializer = LateMarkLOPPolicyCreateSerializer(data=data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        policy = serializer.save(
            created_by=request.user,
            updated_by=request.user,
        )
        logger.info(
            'LateMarkLOPPolicy created: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Late mark/LOP policy created successfully.',
            data=LateMarkLOPPolicyRetrieveSerializer(policy).data,
            http_status=status.HTTP_201_CREATED,
        )


class LateMarkLOPPolicyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk) -> LateMarkLOPPolicy | None:
        try:
            return (
                LateMarkLOPPolicy.objects
                .select_related('created_by', 'updated_by')
                .get(pk=pk)
            )
        except (LateMarkLOPPolicy.DoesNotExist, ValueError):
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_object(pk)
        if policy is None:
            return error('Late mark/LOP policy not found.', http_status=status.HTTP_404_NOT_FOUND)

        return success(
            'Late mark/LOP policy retrieved successfully.',
            data=LateMarkLOPPolicyRetrieveSerializer(policy).data,
        )

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, *, partial: bool):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_object(pk)
        if policy is None:
            return error('Late mark/LOP policy not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = LateMarkLOPPolicyUpdateSerializer(
            policy, data=request.data, partial=partial,
        )
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        policy = serializer.save(updated_by=request.user)
        logger.info(
            'LateMarkLOPPolicy updated: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Late mark/LOP policy updated successfully.',
            data=LateMarkLOPPolicyRetrieveSerializer(policy).data,
        )

    def delete(self, request, pk):
        if not _has_perm(request.user, 'attendance.delete'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_object(pk)
        if policy is None:
            return error('Late mark/LOP policy not found.', http_status=status.HTTP_404_NOT_FOUND)

        if policy.is_default:
            return error(
                'Cannot delete the default late mark/LOP policy. '
                'Assign another policy as default before deleting this one.',
                http_status=status.HTTP_409_CONFLICT,
            )
        if not policy.is_active:
            return error('Late mark/LOP policy is already inactive.', http_status=status.HTTP_409_CONFLICT)

        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        logger.info(
            'LateMarkLOPPolicy soft-deleted: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success('Late mark/LOP policy deleted successfully.')
