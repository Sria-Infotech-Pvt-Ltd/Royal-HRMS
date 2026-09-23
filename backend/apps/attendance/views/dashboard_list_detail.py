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











# ── Dashboard ─────────────────────────────────────────────────────────────────

class HRAttendanceDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = DateFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        data = ser.validated_data
        employee_ids = _manager_scope_employee_ids(request.user)
        stats = get_dashboard_stats(
            target_date=data['date'],
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=employee_ids,
        )
        return success('Dashboard stats loaded.', stats)


# ── Attendance List ───────────────────────────────────────────────────────────

class HRAttendanceListView(APIView):
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
        rows = get_attendance_list(filters)
        page_obj, paginator = paginate(rows, request)
        return success(
            'Attendance list loaded.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── Attendance Detail ─────────────────────────────────────────────────────────

class HRAttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        target_date_str = request.query_params.get('date', '')
        employee_id_str = request.query_params.get('employee_id', '')

        target_date = datetime.date.today()
        if target_date_str:
            try:
                target_date = datetime.date.fromisoformat(target_date_str)
            except ValueError:
                return error('Invalid date format. Use YYYY-MM-DD.')

        detail = get_attendance_detail(
            record_id=str(pk),
            target_date=target_date,
            employee_id_str=employee_id_str,
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        if not detail:
            return error('Attendance record not found.', http_status=404)

        return success('Attendance detail loaded.', detail)

    def patch(self, request, pk: str):
        """HR edits an existing attendance record — status, punch times, note."""
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = HRAttendanceEditSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.models import AttendanceRecord, AttendanceAuditLog
        from apps.attendance.services_audit_log import write_audit_log
        from apps.payroll.models import PayrollCycle

        try:
            record = AttendanceRecord.objects.select_related('employee').get(pk=pk)
        except AttendanceRecord.DoesNotExist:
            return error('Attendance record not found.', http_status=404)

        if not _manager_can_access_employee(request.user, record.employee):
            return error('Attendance record not found.', http_status=404)

        locked = PayrollCycle.objects.filter(
            cycle_start__lte=record.date,
            cycle_end__gte=record.date,
            status__in=['paid', 'closed'],
        ).first()
        if locked:
            return error(
                f'This date is locked — payroll cycle is {locked.get_status_display()}.',
                http_status=409,
            )

        data = ser.validated_data
        old_val = (
            f"{record.status} | "
            f"{record.first_punch_in or '—'} → {record.last_punch_out or '—'}"
        )

        if 'status' in data:
            record.status = data['status']
        if 'clock_in' in data:
            record.first_punch_in = data['clock_in']
        if 'clock_out' in data:
            record.last_punch_out = data['clock_out']
        record.note = data.get('note', record.note)

        if record.first_punch_in and record.last_punch_out:
            import datetime as _dt
            _dummy = _dt.date(2000, 1, 1)
            t_in  = _dt.datetime.combine(_dummy, record.first_punch_in)
            t_out = _dt.datetime.combine(_dummy, record.last_punch_out)
            if t_out < t_in:
                t_out = _dt.datetime.combine(_dummy + _dt.timedelta(days=1), record.last_punch_out)
            record.total_working_minutes = max(0, int((t_out - t_in).total_seconds() / 60))
        elif not record.first_punch_in and not record.last_punch_out:
            record.total_working_minutes = 0

        record.save()

        new_val = (
            f"{record.status} | "
            f"{record.first_punch_in or '—'} → {record.last_punch_out or '—'}"
        )
        write_audit_log(
            employee=record.employee,
            date=record.date,
            event=AttendanceAuditLog.EVENT_MANUALLY_EDITED,
            performed_by=request.user,
            record=record,
            old_value=old_val,
            new_value=new_val,
            action='HR manually edited attendance record.',
            remarks=data.get('reason', ''),
        )
        return success('Attendance record updated.', {'record_id': str(record.id)})
