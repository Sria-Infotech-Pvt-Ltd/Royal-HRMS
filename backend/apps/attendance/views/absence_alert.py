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

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
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

_PERM_DENIED = 'You do not have permission to perform this action.'


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class AbsenceAlertPolicyListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            AbsenceAlertPolicy.objects
            .filter(is_active=True)
            .select_related('created_by', 'updated_by')
            .order_by('-is_default', 'name')
        )

        is_enabled = request.query_params.get('is_enabled')
        if is_enabled is not None:
            qs = qs.filter(is_enabled=(is_enabled.lower() == 'true'))

        page_obj, paginator = paginate(qs, request)
        serializer = AbsenceAlertPolicyListSerializer(page_obj, many=True)
        return success(
            'Absence alert policies retrieved successfully.',
            data=paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if not data.get('policy_code'):
            existing_count = AbsenceAlertPolicy.objects.count()
            data['policy_code'] = f'AA-{existing_count + 1:03d}'

        serializer = AbsenceAlertPolicyCreateSerializer(data=data)
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
            'AbsenceAlertPolicy created: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Absence alert policy created successfully.',
            data=AbsenceAlertPolicyRetrieveSerializer(policy).data,
            http_status=status.HTTP_201_CREATED,
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
        except (AbsenceAlertPolicy.DoesNotExist, ValueError):
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_object(pk)
        if policy is None:
            return error('Absence alert policy not found.', http_status=status.HTTP_404_NOT_FOUND)

        return success(
            'Absence alert policy retrieved successfully.',
            data=AbsenceAlertPolicyRetrieveSerializer(policy).data,
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
            return error('Absence alert policy not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = AbsenceAlertPolicyUpdateSerializer(
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
            'AbsenceAlertPolicy updated: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success(
            'Absence alert policy updated successfully.',
            data=AbsenceAlertPolicyRetrieveSerializer(policy).data,
        )

    def delete(self, request, pk):
        if not _has_perm(request.user, 'attendance.delete'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_object(pk)
        if policy is None:
            return error('Absence alert policy not found.', http_status=status.HTTP_404_NOT_FOUND)

        if policy.is_default:
            return error(
                'Cannot delete the default absence alert policy. '
                'Assign another policy as default before deleting this one.',
                http_status=status.HTTP_409_CONFLICT,
            )
        if not policy.is_active:
            return error('Absence alert policy is already inactive.', http_status=status.HTTP_409_CONFLICT)

        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        logger.info(
            'AbsenceAlertPolicy soft-deleted: %s (%s) by user %s',
            policy.name, policy.policy_code, request.user.pk,
        )
        return success('Absence alert policy deleted successfully.')
