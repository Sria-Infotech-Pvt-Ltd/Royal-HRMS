"""
Absence Alert Policy views.

Endpoints
---------
GET  /api/attendance/absence-alert/          List all active policies (paginated).
POST /api/attendance/absence-alert/          Create a new policy.
GET  /api/attendance/absence-alert/<pk>/     Retrieve a single policy.
PUT  /api/attendance/absence-alert/<pk>/     Full update.
PATCH /api/attendance/absence-alert/<pk>/    Partial update.
DELETE /api/attendance/absence-alert/<pk>/   Soft-delete (is_active=False).
"""

from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from apps.attendance.models import AbsenceAlertPolicy
from apps.attendance.serializers import (
    AbsenceAlertPolicyCreateSerializer,
    AbsenceAlertPolicyListSerializer,
    AbsenceAlertPolicyRetrieveSerializer,
    AbsenceAlertPolicyUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    return user.is_superuser or user.has_perm(f'attendance.{codename}')


class AbsenceAlertPolicyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        if not _has_perm(request.user, 'view_absencealertpolicy'):
            return error('You do not have permission to view absence alert policies.', status=403)

        qs = (
            AbsenceAlertPolicy.objects
            .filter(is_active=True)
            .select_related('created_by', 'updated_by')
            .order_by('-is_default', 'name')
        )

        is_enabled = request.query_params.get('is_enabled')
        if is_enabled is not None:
            qs = qs.filter(is_enabled=(is_enabled.lower() == 'true'))

        page = paginate(request, qs)
        serializer = AbsenceAlertPolicyListSerializer(page, many=True)
        return success(
            'Absence alert policies retrieved successfully.',
            paginated_data(request, qs, serializer.data),
        )

    def post(self, request: Request) -> Response:
        if not _has_perm(request.user, 'add_absencealertpolicy'):
            return error('You do not have permission to create absence alert policies.', status=403)

        serializer = AbsenceAlertPolicyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return first_error(serializer.errors)

        # Auto-generate policy_code when omitted
        if not serializer.validated_data.get('policy_code'):
            existing_count = AbsenceAlertPolicy.objects.count()
            serializer.validated_data['policy_code'] = f'AA-{existing_count + 1:03d}'

        policy = serializer.save(
            created_by=request.user,
            updated_by=request.user,
        )
        logger.info(
            'AbsenceAlertPolicy created: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Absence alert policy created successfully.',
            AbsenceAlertPolicyRetrieveSerializer(policy).data,
            status=201,
        )


class AbsenceAlertPolicyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk) -> AbsenceAlertPolicy | None:
        try:
            return (
                AbsenceAlertPolicy.objects
                .select_related('created_by', 'updated_by')
                .get(pk=pk)
            )
        except AbsenceAlertPolicy.DoesNotExist:
            return None

    def get(self, request: Request, pk) -> Response:
        if not _has_perm(request.user, 'view_absencealertpolicy'):
            return error('You do not have permission to view absence alert policies.', status=403)

        policy = self._get_object(pk)
        if policy is None:
            return error('Absence alert policy not found.', status=404)

        return success(
            'Absence alert policy retrieved successfully.',
            AbsenceAlertPolicyRetrieveSerializer(policy).data,
        )

    def put(self, request: Request, pk) -> Response:
        return self._update(request, pk, partial=False)

    def patch(self, request: Request, pk) -> Response:
        return self._update(request, pk, partial=True)

    def _update(self, request: Request, pk, *, partial: bool) -> Response:
        if not _has_perm(request.user, 'change_absencealertpolicy'):
            return error('You do not have permission to update absence alert policies.', status=403)

        policy = self._get_object(pk)
        if policy is None:
            return error('Absence alert policy not found.', status=404)

        serializer = AbsenceAlertPolicyUpdateSerializer(
            policy, data=request.data, partial=partial,
        )
        if not serializer.is_valid():
            return first_error(serializer.errors)

        policy = serializer.save(updated_by=request.user)
        logger.info(
            'AbsenceAlertPolicy updated: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Absence alert policy updated successfully.',
            AbsenceAlertPolicyRetrieveSerializer(policy).data,
        )

    def delete(self, request: Request, pk) -> Response:
        if not _has_perm(request.user, 'delete_absencealertpolicy'):
            return error('You do not have permission to delete absence alert policies.', status=403)

        policy = self._get_object(pk)
        if policy is None:
            return error('Absence alert policy not found.', status=404)

        if policy.is_default:
            return error(
                'Cannot delete the default absence alert policy. '
                'Assign another policy as default before deleting this one.',
                status=400,
            )

        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        logger.info(
            'AbsenceAlertPolicy soft-deleted: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success('Absence alert policy deleted successfully.')
