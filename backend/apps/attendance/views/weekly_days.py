from __future__ import annotations

import logging

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from apps.attendance.models import WeeklyDayPolicy
from apps.attendance.serializers import (
    WeeklyDayPolicyCreateSerializer,
    WeeklyDayPolicyListSerializer,
    WeeklyDayPolicyRetrieveSerializer,
    WeeklyDayPolicyUpdateSerializer,
)

logger = logging.getLogger(__name__)

_PERM_DENIED = 'You do not have permission to perform this action.'


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class WeeklyDayPolicyListCreateView(APIView):
    """
    GET  /api/attendance/weekly-days/  — paginated list
    POST /api/attendance/weekly-days/  — create new policy
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (
            WeeklyDayPolicy.objects
            .select_related('created_by', 'updated_by')
            .annotate(
                # One aggregation query for the whole page — counts each
                # policy's currently-open assignments, not one query per row.
                assigned_employee_count=Count(
                    'employee_assignments',
                    filter=Q(employee_assignments__effective_to__isnull=True),
                    distinct=True,
                ),
            )
            # Explicit — the Count() annotation's GROUP BY otherwise loses
            # Meta.ordering, tripping Paginator's UnorderedObjectListWarning.
            .order_by('-is_default', 'name')
        )

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
        serializer = WeeklyDayPolicyListSerializer(page_obj, many=True)

        return success(
            'Weekly day policies retrieved successfully.',
            data=paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if not data.get('policy_code'):
            count = WeeklyDayPolicy.objects.count()
            data['policy_code'] = f'WD-{count + 1:03d}'

        serializer = WeeklyDayPolicyCreateSerializer(data=data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        policy = serializer.save(created_by=request.user, updated_by=request.user)
        logger.info('Weekly day policy created — code=%s by user=%s', policy.policy_code, request.user.email)

        return success(
            'Weekly day policy created successfully.',
            data=WeeklyDayPolicyRetrieveSerializer(policy).data,
            http_status=status.HTTP_201_CREATED,
        )


class WeeklyDayPolicyDetailView(APIView):
    """
    GET    /api/attendance/weekly-days/<pk>/ — retrieve
    PUT    /api/attendance/weekly-days/<pk>/ — full update
    PATCH  /api/attendance/weekly-days/<pk>/ — partial update
    DELETE /api/attendance/weekly-days/<pk>/ — soft delete
    """

    permission_classes = [IsAuthenticated]

    def _get_policy(self, pk: str) -> WeeklyDayPolicy | None:
        try:
            return (
                WeeklyDayPolicy.objects
                .select_related('created_by', 'updated_by')
                .get(pk=pk)
            )
        except (WeeklyDayPolicy.DoesNotExist, ValueError):
            return None

    def get(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Weekly day policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success(
            'Weekly day policy retrieved successfully.',
            data=WeeklyDayPolicyRetrieveSerializer(policy).data,
        )

    def put(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Weekly day policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = WeeklyDayPolicyUpdateSerializer(policy, data=request.data, partial=False)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        policy = serializer.save(updated_by=request.user)
        logger.info('Weekly day policy updated (full) — code=%s by user=%s', policy.policy_code, request.user.email)
        return success('Weekly day policy updated successfully.', data=WeeklyDayPolicyRetrieveSerializer(policy).data)

    def patch(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.edit'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Weekly day policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = WeeklyDayPolicyUpdateSerializer(policy, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        policy = serializer.save(updated_by=request.user)
        logger.info('Weekly day policy updated (partial) — code=%s by user=%s', policy.policy_code, request.user.email)
        return success('Weekly day policy updated successfully.', data=WeeklyDayPolicyRetrieveSerializer(policy).data)

    def delete(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.delete'):
            return error(_PERM_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        policy = self._get_policy(pk)
        if not policy:
            return error('Weekly day policy not found.', http_status=status.HTTP_404_NOT_FOUND)
        if policy.is_default:
            return error(
                'Cannot deactivate the default weekly day policy. '
                'Assign another policy as default before removing this one.',
                http_status=status.HTTP_409_CONFLICT,
            )
        assigned_count = policy.employee_assignments.filter(effective_to__isnull=True).count()
        if assigned_count:
            return error(
                f'This weekly-off pattern is currently assigned to {assigned_count} '
                f'employee{"s" if assigned_count != 1 else ""} and cannot be deleted. '
                'Reassign them to a different pattern first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        if not policy.is_active:
            return error('Weekly day policy is already inactive.', http_status=status.HTTP_409_CONFLICT)
        policy.is_active = False
        policy.updated_by = request.user
        policy.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        logger.info('Weekly day policy deactivated — code=%s by user=%s', policy.policy_code, request.user.email)
        return success('Weekly day policy deactivated successfully.')
