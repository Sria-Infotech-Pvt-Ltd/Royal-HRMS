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
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasSettingsPermission
from core.responses import error, first_error, success

from apps.attendance.serializers_settings import (
    AttendanceSettingsReadSerializer,
    AttendanceSettingsPatchSerializer,
    AttendanceSettingsWriteSerializer,
)
from apps.attendance.services import DEFAULT_SETTINGS, AttendanceSettingsService

logger = logging.getLogger(__name__)


class AttendanceSettingsAPIView(APIView):
    """
    Single endpoint for the "Attendance Settings" page.

    GET  → load current settings (or defaults if not yet configured).
    PUT  → save / update all sections atomically.

    Permission is enforced by HasSettingsPermission (core/permissions.py):
    settings.view for GET, settings.edit for PUT/PATCH. Previously this view
    checked settings.view on every method including the mutating ones, which
    let any role with view-only access (e.g. branch_admin, granted
    settings.view but deliberately NOT settings.edit — see
    accounts/migrations/0052_seed_branch_admin_role.py) actually save changes
    to this org-wide settings record, including the Face ID Verification
    mandatory toggle. Fixed to match the view/edit split already used
    consistently elsewhere (apps/hrms/views/leave.py, holidays.py, etc.).
    """

    permission_classes = [HasSettingsPermission]

    def get(self, request: Request) -> Response:
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
