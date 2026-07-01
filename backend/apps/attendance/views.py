from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from apps.attendance.models import WorkingHoursPolicy
from apps.attendance.serializers import (
    WorkingHoursPolicyCreateSerializer,
    WorkingHoursPolicyListSerializer,
    WorkingHoursPolicyRetrieveSerializer,
    WorkingHoursPolicyUpdateSerializer,
)

logger = logging.getLogger(__name__)

_PERM_DENIED = 'You do not have permission to perform this action.'


def _has_perm(user, codename: str) -> bool:
    """Return True if the user's role carries the given permission codename."""
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


# ─── Working Hours Policy ─────────────────────────────────────────────────────

class WorkingHoursPolicyListCreateView(APIView):
    """
    GET  /api/attendance/working-hours/  — paginated list
    POST /api/attendance/working-hours/  — create new policy
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            WorkingHoursPolicy.objects
            .select_related('created_by', 'updated_by')
            .all()
        )

        # ── Optional filters ─────────────────────────────────────────────────
        is_active_param = request.query_params.get('is_active')
        if is_active_param is not None:
            qs = qs.filter(is_active=is_active_param.lower() == 'true')

        is_default_param = request.query_params.get('is_default')
        if is_default_param is not None:
            qs = qs.filter(is_default=is_default_param.lower() == 'true')

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(policy_code__icontains=search)

        page_obj, paginator = paginate(qs, request)
        serializer = WorkingHoursPolicyListSerializer(page_obj, many=True)

        return success(
            'Working hours policies retrieved successfully.',
            data=paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()

        # Auto-generate policy_code if the caller did not supply one
        if not data.get('policy_code'):
            existing_count = WorkingHoursPolicy.objects.count()
            data['policy_code'] = f'WH-{existing_count + 1:03d}'

        serializer = WorkingHoursPolicyCreateSerializer(data=data)
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
            'Working hours policy created — code=%s name=%s by user=%s',
            policy.policy_code, policy.name, request.user.email,
        )

        return success(
            'Working hours policy created successfully.',
            data=WorkingHoursPolicyRetrieveSerializer(policy).data,
            http_status=status.HTTP_201_CREATED,
        )


class WorkingHoursPolicyDetailView(APIView):
    """
    GET    /api/attendance/working-hours/<pk>/ — retrieve
    PUT    /api/attendance/working-hours/<pk>/ — full update
    PATCH  /api/attendance/working-hours/<pk>/ — partial update
    DELETE /api/attendance/working-hours/<pk>/ — soft delete (is_active=False)
    """

    permission_classes = [IsAuthenticated]

    def _get_policy(self, pk: str) -> WorkingHoursPolicy | None:
        try:
            return (
                WorkingHoursPolicy.objects
                .select_related('created_by', 'updated_by')
                .get(pk=pk)
            )
        except (WorkingHoursPolicy.DoesNotExist, ValueError):
            return None

    def get(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_policy(pk)
        if not policy:
            return error(
                'Working hours policy not found.',
                http_status=status.HTTP_404_NOT_FOUND,
            )

        return success(
            'Working hours policy retrieved successfully.',
            data=WorkingHoursPolicyRetrieveSerializer(policy).data,
        )

    def put(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_policy(pk)
        if not policy:
            return error(
                'Working hours policy not found.',
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = WorkingHoursPolicyUpdateSerializer(
            policy, data=request.data, partial=False,
        )
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        policy = serializer.save(updated_by=request.user)

        logger.info(
            'Working hours policy updated (full) — code=%s by user=%s',
            policy.policy_code, request.user.email,
        )

        return success(
            'Working hours policy updated successfully.',
            data=WorkingHoursPolicyRetrieveSerializer(policy).data,
        )

    def patch(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_policy(pk)
        if not policy:
            return error(
                'Working hours policy not found.',
                http_status=status.HTTP_404_NOT_FOUND,
            )

        serializer = WorkingHoursPolicyUpdateSerializer(
            policy, data=request.data, partial=True,
        )
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        policy = serializer.save(updated_by=request.user)

        logger.info(
            'Working hours policy updated (partial) — code=%s by user=%s',
            policy.policy_code, request.user.email,
        )

        return success(
            'Working hours policy updated successfully.',
            data=WorkingHoursPolicyRetrieveSerializer(policy).data,
        )

    def delete(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.delete'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        policy = self._get_policy(pk)
        if not policy:
            return error(
                'Working hours policy not found.',
                http_status=status.HTTP_404_NOT_FOUND,
            )

        if policy.is_default:
            return error(
                'Cannot deactivate the default working hours policy. '
                'Assign another policy as default before removing this one.',
                http_status=status.HTTP_409_CONFLICT,
            )

        if not policy.is_active:
            return error(
                'Working hours policy is already inactive.',
                http_status=status.HTTP_409_CONFLICT,
            )

        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])

        logger.info(
            'Working hours policy deactivated — code=%s by user=%s',
            policy.policy_code, request.user.email,
        )

        return success('Working hours policy deactivated successfully.')
