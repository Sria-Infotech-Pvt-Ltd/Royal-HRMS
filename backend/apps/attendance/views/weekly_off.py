"""
HR Attendance Management views.

All business logic lives in services_hr, services_hr_audit, services_hr_ops.
Views: validate input → call service → return response.
"""
from __future__ import annotations

import datetime
import logging

from django.http import HttpResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.serializers_hr import (
    AttendanceListFilterSerializer,
    CorrectionListFilterSerializer,
    CorrectionReviewSerializer,
    DateFilterSerializer,
    HRAttendanceEditSerializer,
    HRAttendanceManualCreateSerializer,
    OvertimeWriteSerializer,
    WeeklyOffAssignmentFilterSerializer,
    WeeklyOffAssignmentWriteSerializer,
    WeeklyOffBulkAssignmentWriteSerializer,
)
from apps.attendance.services_hr import (
    assign_weekly_off,
    build_weekly_off_assignment_queryset,
    bulk_assign_weekly_off,
    get_attendance_detail,
    get_attendance_list,
    get_dashboard_stats,
    get_weekly_off_assignment_history,
    serialize_weekly_off_assignment_row,
)
from apps.attendance.services_hr_audit import (
    get_invalid_punches,
    get_unpunches,
)
from apps.attendance.services_hr_ops import (
    create_overtime,
    export_attendance_csv,
    import_attendance_csv,
    list_overtime,
)
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm

logger = logging.getLogger(__name__)

from apps.attendance.views.hr_attendance_shared import *  # noqa: F401,F403

# ── Weekly Off Assignment ──────────────────────────────────────────────────────
#
# Assigns a WeeklyDayPolicy (configured under Settings -> Attendance Rules ->
# Weekly Off Patterns — the existing WeeklyDayPolicy CRUD at
# /api/attendance/weekly-days/, unchanged) to a specific employee. History is
# preserved via services_hr.bulk_assign_weekly_off()/assign_weekly_off() — see
# their docstrings. All actual attendance/leave calculations resolve the
# effective pattern through the centralized
# core.cache_service.WeeklyOffCacheService, not through these views.



class WeeklyOffAssignmentListView(APIView):
    """
    GET  /api/attendance/weekly-off-assignments/  — paginated list, one row
         per active employee with their current assignment (if any)
    POST /api/attendance/weekly-off-assignments/  — assign a pattern to a
         single employee
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = WeeklyOffAssignmentFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
        filters['employee_ids'] = _manager_scope_employee_ids(request.user)

        qs = build_weekly_off_assignment_queryset(filters)
        page_obj, paginator = paginate(qs, request)
        rows = [serialize_weekly_off_assignment_row(u) for u in page_obj]
        return success(
            'Weekly off assignments retrieved.',
            paginated_data(paginator, page_obj, rows),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = WeeklyOffAssignmentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors, http_status=422)

        data = ser.validated_data
        policy, err = _get_policy_or_error(data['pattern'])
        if err:
            return err

        assignment = assign_weekly_off(data['employee_id'], policy, data['effective_from'], request.user)
        if assignment is None:
            return error('Employee not found.', http_status=404)

        logger.info(
            'Weekly-off pattern "%s" assigned to %s effective %s by %s',
            policy.policy_code, data['employee_id'], data['effective_from'], request.user.email,
        )
        return success('Weekly off pattern assigned.', {
            'employee_id':    data['employee_id'],
            'pattern_id':     str(policy.pk),
            'pattern_name':   policy.name,
            'effective_from': assignment.effective_from.strftime('%Y-%m-%d'),
        }, http_status=201)


class WeeklyOffAssignmentBulkView(APIView):
    """
    POST /api/attendance/weekly-off-assignments/bulk/ — assign a pattern to
    many employees at once (explicit id list, or branch/department filter
    resolved server-side). O(1) queries regardless of how many are selected.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = WeeklyOffBulkAssignmentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors, http_status=422)

        data = ser.validated_data
        policy, err = _get_policy_or_error(data['pattern'])
        if err:
            return err

        employee_ids = data.get('employee_ids') or []
        if not employee_ids:
            # Resolve branch/department filter server-side — the frontend
            # never has to load all matching employees just to select them.
            filters = {
                'branch':     _branch_scope(request.user, data.get('branch', '')),
                'department': data.get('department', ''),
                'employee_ids': _manager_scope_employee_ids(request.user),
            }
            employee_ids = list(
                build_weekly_off_assignment_queryset(filters).values_list('employee_id', flat=True)
            )

        count = bulk_assign_weekly_off(employee_ids, policy, data['effective_from'], request.user)
        return success(f'Weekly off pattern assigned to {count} employee(s).', {'count': count})


class WeeklyOffAssignmentHistoryView(APIView):
    """GET /api/attendance/weekly-off-assignments/<employee_id>/history/ — full timeline for one employee."""
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)
        history = get_weekly_off_assignment_history(employee_id)
        return success('Weekly off assignment history retrieved.', {'employee_id': employee_id, 'history': history})
