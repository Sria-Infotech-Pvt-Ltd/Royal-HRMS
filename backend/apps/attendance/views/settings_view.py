"""
Unified Attendance Settings view.

GET /api/attendance/settings/
    Returns the current settings. If none have been saved yet, returns the
    built-in defaults so the frontend can pre-populate the form.

PUT /api/attendance/settings/
    Saves all six sections in a single request. The service layer wraps
    everything in transaction.atomic() — a failure anywhere rolls back all.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.serializers_settings import (
    AttendanceSettingsReadSerializer,
    AttendanceSettingsPatchSerializer,
    AttendanceSettingsWriteSerializer,
)
from apps.attendance.services import DEFAULT_SETTINGS, AttendanceSettingsService

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class AttendanceSettingsAPIView(APIView):
    """
    Single endpoint for the "Attendance Settings" page.

    GET  → load current settings (or defaults if not yet configured).
    PUT  → save / update all sections atomically.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        if not _has_perm(request.user, 'settings.view'):
            return error(
                'You do not have permission to view attendance settings.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        from core.cache_service import AttendanceSettingsCacheService
        instance = AttendanceSettingsCacheService.get()

        if instance is None:
            return success(
                'Attendance settings not configured yet. Showing defaults.',
                DEFAULT_SETTINGS,
            )

        return success(
            'Attendance settings retrieved successfully.',
            AttendanceSettingsReadSerializer(instance).data,
        )

    def put(self, request: Request) -> Response:
        if not _has_perm(request.user, 'settings.view'):
            return error(
                'You do not have permission to update attendance settings.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AttendanceSettingsWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        instance = AttendanceSettingsService.upsert(
            serializer.validated_data,
            request.user,
        )

        return success(
            'Attendance settings saved successfully.',
            AttendanceSettingsReadSerializer(instance).data,
        )

    def patch(self, request: Request) -> Response:
        if not _has_perm(request.user, 'settings.view'):
            return error(
                'You do not have permission to update attendance settings.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AttendanceSettingsPatchSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        instance = AttendanceSettingsService.partial_update(
            serializer.validated_data,
            request.user,
        )

        return success(
            'Attendance settings updated successfully.',
            AttendanceSettingsReadSerializer(instance).data,
        )
