"""
HR Attendance — Audit History + Invalid Punch Action views.

GET  /api/attendance/records/<pk>/audit/            — Audit history for a record
POST /api/attendance/invalid-punches/<pk>/assign/   — Assign to an HR user
POST /api/attendance/invalid-punches/<pk>/discard/  — Discard (accidental/duplicate)
POST /api/attendance/invalid-punches/<pk>/convert/  — Convert to a valid punch
"""
from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.serializers_hr import (
    AuditLogEntrySerializer,
    InvalidPunchAssignSerializer,
    InvalidPunchConvertSerializer,
    InvalidPunchDiscardSerializer,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    # settings.edit is this codebase's universal "sees/does everything"
    # signal — checking it here (permission-based) instead of a hardcoded
    # role name means any role actually granted settings.edit gets the same
    # bypass, and revoking it from system_admin would actually revoke it.
    return user.role.role_permissions.filter(
        permission__codename__in={codename, 'settings.edit'}
    ).exists()


# ── Audit History ─────────────────────────────────────────────────────────────

class HRAttendanceAuditView(APIView):
    """
    GET /api/attendance/records/<pk>/audit/

    Returns chronological audit history for one AttendanceRecord.
    Each entry shows who performed an action and what changed.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        from apps.attendance.services_audit_log import get_audit_history
        history = get_audit_history(str(pk))

        if history is None:
            return error('Attendance record not found.', http_status=404)

        return success(
            'Attendance audit history fetched successfully.',
            AuditLogEntrySerializer(history, many=True).data,
        )


# ── Invalid Punch Actions ─────────────────────────────────────────────────────

class HRInvalidPunchAssignView(APIView):
    """POST /api/attendance/invalid-punches/<pk>/assign/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = InvalidPunchAssignSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_invalid_punch import assign_invalid_punch
        try:
            result = assign_invalid_punch(
                punch_id=str(pk),
                assigned_to_id=str(ser.validated_data['assigned_to']),
                performed_by=request.user,
            )
        except ValueError as exc:
            return error(str(exc))

        return success('Invalid punch assigned successfully.', result)


class HRInvalidPunchDiscardView(APIView):
    """POST /api/attendance/invalid-punches/<pk>/discard/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = InvalidPunchDiscardSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_invalid_punch import discard_invalid_punch
        try:
            result = discard_invalid_punch(
                punch_id=str(pk),
                remarks=ser.validated_data.get('remarks', ''),
                performed_by=request.user,
            )
        except ValueError as exc:
            return error(str(exc))

        return success('Invalid punch discarded.', result)


class HRInvalidPunchConvertView(APIView):
    """POST /api/attendance/invalid-punches/<pk>/convert/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = InvalidPunchConvertSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_invalid_punch import convert_invalid_punch
        try:
            result = convert_invalid_punch(
                punch_id=str(pk),
                target_punch_type=ser.validated_data['target_punch_type'],
                target_time_str=ser.validated_data['target_time'].strftime('%H:%M'),
                performed_by=request.user,
            )
        except ValueError as exc:
            return error(str(exc))

        return success(
            'Invalid punch converted. Attendance record recalculated.',
            result,
        )
