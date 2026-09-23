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

# ── HR Corrections ────────────────────────────────────────────────────────────

class HRCorrectionListView(APIView):
    """
    GET /api/attendance/corrections/

    List correction requests visible to the caller — managers see requests
    where they're the designated L1 approver; HR/system_admin see the full
    branch-scoped/unrestricted list, same as before.
    Query params: branch, department, status (pending|l2_pending|approved|rejected)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = CorrectionListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_hr_corrections import list_corrections
        rows = list_corrections(
            request.user,
            branch=_branch_scope(request.user, ser.validated_data['branch']),
            department=ser.validated_data['department'],
            status_filter=ser.validated_data['status'],
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} correction request(s) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


class HRCorrectionReviewView(APIView):
    """
    PATCH /api/attendance/corrections/<uuid:pk>/review/
    Body: { "action": "approve" | "reject" }

    Two-stage: L1 (reporting manager) approval routes to L2 (HR) unless no
    L2 is configured for the employee, in which case L1 approval is final.
    Only the designated approver for the request's current stage may act
    (enforced in services_hr_corrections._can_approve_at_stage) —
    system_admin may always unblock a stuck request.

    Approve (final stage only): creates the missing punch(es), reprocesses
             the attendance record. Status changes incomplete → present/late;
             employee drops from Un-Punches.
    Reject:  marks the correction rejected, no punch changes.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = CorrectionReviewSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        remarks = ser.validated_data.get('remarks', '')

        from apps.attendance.services_hr_corrections import approve_correction, reject_correction
        try:
            if ser.validated_data['action'] == 'approve':
                result = approve_correction(str(pk), actioning_user=request.user, remarks=remarks)
                msg = 'Correction approved. Attendance record updated.' if result['status'] == 'approved' else 'Correction approved. Awaiting HR review.'
            else:
                result = reject_correction(str(pk), actioning_user=request.user, remarks=remarks)
                msg = 'Correction rejected.'
        except PermissionError as exc:
            return error(str(exc), http_status=403)
        except ValueError as exc:
            return error(str(exc), http_status=404)

        return success(msg, result)


# ── Export ────────────────────────────────────────────────────────────────────

class HRAttendanceExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = AttendanceListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
        filters['employee_ids'] = _manager_scope_employee_ids(request.user)
        csv_content = export_attendance_csv(filters)
        date_str = ser.validated_data['date'].strftime('%Y-%m-%d')
        filename = f'attendance_{date_str}.csv'

        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


