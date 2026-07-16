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

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from apps.attendance.models import LateMarkLOPPolicy
from apps.attendance.serializers import (
    LateMarkLOPPolicyCreateSerializer,
    LateMarkLOPPolicyListSerializer,
    LateMarkLOPPolicyRetrieveSerializer,
    LateMarkLOPPolicyUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    return user.is_superuser or user.has_perm(f'attendance.{codename}')


class LateMarkLOPPolicyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        if not _has_perm(request.user, 'view_latemarkloppolicy'):
            return error('You do not have permission to view late mark/LOP policies.', status=403)

        qs = (
            LateMarkLOPPolicy.objects
            .filter(is_active=True)
            .select_related('created_by', 'updated_by')
            .order_by('-is_default', 'name')
        )

        is_default = request.query_params.get('is_default')
        if is_default is not None:
            qs = qs.filter(is_default=(is_default.lower() == 'true'))

        page = paginate(request, qs)
        serializer = LateMarkLOPPolicyListSerializer(page, many=True)
        return success(
            'Late mark/LOP policies retrieved successfully.',
            paginated_data(request, qs, serializer.data),
        )

    def post(self, request: Request) -> Response:
        if not _has_perm(request.user, 'add_latemarkloppolicy'):
            return error('You do not have permission to create late mark/LOP policies.', status=403)

        serializer = LateMarkLOPPolicyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return first_error(serializer.errors)

        # Auto-generate policy_code when omitted
        if not serializer.validated_data.get('policy_code'):
            existing_count = LateMarkLOPPolicy.objects.count()
            serializer.validated_data['policy_code'] = f'LM-{existing_count + 1:03d}'

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
            LateMarkLOPPolicyRetrieveSerializer(policy).data,
            status=201,
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
        except LateMarkLOPPolicy.DoesNotExist:
            return None

    def get(self, request: Request, pk) -> Response:
        if not _has_perm(request.user, 'view_latemarkloppolicy'):
            return error('You do not have permission to view late mark/LOP policies.', status=403)

        policy = self._get_object(pk)
        if policy is None:
            return error('Late mark/LOP policy not found.', status=404)

        return success(
            'Late mark/LOP policy retrieved successfully.',
            LateMarkLOPPolicyRetrieveSerializer(policy).data,
        )

    def put(self, request: Request, pk) -> Response:
        return self._update(request, pk, partial=False)

    def patch(self, request: Request, pk) -> Response:
        return self._update(request, pk, partial=True)

    def _update(self, request: Request, pk, *, partial: bool) -> Response:
        if not _has_perm(request.user, 'change_latemarkloppolicy'):
            return error('You do not have permission to update late mark/LOP policies.', status=403)

        policy = self._get_object(pk)
        if policy is None:
            return error('Late mark/LOP policy not found.', status=404)

        serializer = LateMarkLOPPolicyUpdateSerializer(
            policy, data=request.data, partial=partial,
        )
        if not serializer.is_valid():
            return first_error(serializer.errors)

        policy = serializer.save(updated_by=request.user)
        logger.info(
            'LateMarkLOPPolicy updated: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Late mark/LOP policy updated successfully.',
            LateMarkLOPPolicyRetrieveSerializer(policy).data,
        )

    def delete(self, request: Request, pk) -> Response:
        if not _has_perm(request.user, 'delete_latemarkloppolicy'):
            return error('You do not have permission to delete late mark/LOP policies.', status=403)

        policy = self._get_object(pk)
        if policy is None:
            return error('Late mark/LOP policy not found.', status=404)

        if policy.is_default:
            return error(
                'Cannot delete the default late mark/LOP policy. '
                'Assign another policy as default before deleting this one.',
                status=400,
            )

        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        logger.info(
            'LateMarkLOPPolicy soft-deleted: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success('Late mark/LOP policy deleted successfully.')
