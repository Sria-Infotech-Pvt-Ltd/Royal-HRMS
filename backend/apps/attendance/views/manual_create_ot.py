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



# ── HR Attendance Manual Create ───────────────────────────────────────────────

class HRAttendanceCreateView(APIView):
    """HR creates an attendance record for a day with no existing record."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = HRAttendanceManualCreateSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        data = ser.validated_data

        import uuid as _uuid_mod
        from django.contrib.auth import get_user_model
        from apps.attendance.models import AttendanceRecord, AttendanceAuditLog
        from apps.attendance.services_audit_log import write_audit_log
        from apps.payroll.models import PayrollCycle

        User = get_user_model()
        employee_pk = str(data['employee_id'])
        try:
            _uuid_mod.UUID(employee_pk)
            employee = User.objects.filter(pk=employee_pk, is_active=True).first()
        except (ValueError, AttributeError):
            employee = User.objects.filter(employee_id=employee_pk, is_active=True).first()

        if not employee:
            return error('Employee not found.', http_status=404)

        if not _manager_can_access_employee(request.user, employee):
            return error('Employee not found.', http_status=404)

        target_date = data['date']

        locked = PayrollCycle.objects.filter(
            cycle_start__lte=target_date,
            cycle_end__gte=target_date,
            status__in=['paid', 'closed'],
        ).first()
        if locked:
            return error(
                f'This date is locked — payroll cycle is {locked.get_status_display()}.',
                http_status=409,
            )

        if AttendanceRecord.objects.filter(employee=employee, date=target_date).exists():
            return error(
                'An attendance record already exists for this date. Use edit instead.',
                http_status=409,
            )

        clock_in  = data.get('clock_in')
        clock_out = data.get('clock_out')
        total_minutes = 0
        if clock_in and clock_out:
            import datetime as _dt
            _dummy = _dt.date(2000, 1, 1)
            t_in  = _dt.datetime.combine(_dummy, clock_in)
            t_out = _dt.datetime.combine(_dummy, clock_out)
            if t_out < t_in:
                t_out = _dt.datetime.combine(_dummy + _dt.timedelta(days=1), clock_out)
            total_minutes = max(0, int((t_out - t_in).total_seconds() / 60))

        record = AttendanceRecord.objects.create(
            employee=employee,
            date=target_date,
            status=data['status'],
            first_punch_in=clock_in,
            last_punch_out=clock_out,
            total_working_minutes=total_minutes,
            note=data.get('note', ''),
        )

        write_audit_log(
            employee=employee,
            date=target_date,
            event=AttendanceAuditLog.EVENT_MANUALLY_EDITED,
            performed_by=request.user,
            record=record,
            old_value='No Record',
            new_value=(
                f"{record.status} | "
                f"{record.first_punch_in or '—'} → {record.last_punch_out or '—'}"
            ),
            action='HR manually created attendance record.',
            remarks=data.get('reason', ''),
        )

        return success('Attendance record created.', {'record_id': str(record.id)}, http_status=201)


# ── OT Entry List ─────────────────────────────────────────────────────────────

class HROvertimeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        date_str = request.query_params.get('date', '')
        date = None
        if date_str:
            try:
                date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return error('Invalid date format. Use YYYY-MM-DD.')

        rows = list_overtime(
            date=date,
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            'Overtime entries loaded.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── OT Entry Create ───────────────────────────────────────────────────────────

class HROvertimeCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = OvertimeWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        try:
            ot = create_overtime(
                ser.validated_data,
                created_by=request.user,
                employee_ids=_manager_scope_employee_ids(request.user),
            )
        except ValueError as exc:
            return error(str(exc))

        return success('Overtime entry created.', {'id': str(ot.id)}, http_status=201)


