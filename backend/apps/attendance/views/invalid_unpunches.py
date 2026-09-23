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

# ── Invalid Punches ───────────────────────────────────────────────────────────

class HRInvalidPunchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        date_str = request.query_params.get('date', '')
        try:
            target_date = (
                datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            )
        except ValueError:
            return error('Invalid date format. Use YYYY-MM-DD.')

        rows = get_invalid_punches(
            target_date=target_date,
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} invalid punch(es) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── Un-punches ────────────────────────────────────────────────────────────────

class HRUnpunchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        date_str = request.query_params.get('date', '')
        try:
            target_date = (
                datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            )
        except ValueError:
            return error('Invalid date format. Use YYYY-MM-DD.')

        rows = get_unpunches(
            target_date=target_date,
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} un-punch(es) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


