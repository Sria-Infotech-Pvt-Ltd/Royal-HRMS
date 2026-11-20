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

# ── Employee Monthly Calendar (HR) ────────────────────────────────────────────

class HREmployeeMonthView(APIView):
    """Monthly attendance calendar for a single employee — HR use."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        employee_pk = request.query_params.get('employee_id')
        month_str   = request.query_params.get('month')

        if not employee_pk:
            return error('employee_id is required.', http_status=400)
        if not month_str:
            return error('month is required (YYYY-MM).', http_status=400)

        try:
            year, mon = (int(x) for x in month_str.split('-'))
            if not (1 <= mon <= 12):
                raise ValueError('month out of range')
        except (ValueError, AttributeError):
            return error('month must be in YYYY-MM format.', http_status=400)

        import uuid as _uuid_mod
        import datetime
        import calendar as _calendar
        from django.contrib.auth import get_user_model
        from apps.attendance.models import AttendanceRecord

        User = get_user_model()
        try:
            _uuid_mod.UUID(str(employee_pk))
            employee = User.objects.filter(pk=employee_pk, is_active=True).first()
        except (ValueError, AttributeError):
            employee = User.objects.filter(employee_id=employee_pk, is_active=True).first()

        if not employee:
            return error('Employee not found.', http_status=404)
        if not _manager_can_access_employee(request.user, employee):
            return error('Permission denied.', http_status=403)

        month_start = datetime.date(year, mon, 1)
        month_end   = datetime.date(year, mon, _calendar.monthrange(year, mon)[1])

        record_map = {
            r.date: r
            for r in AttendanceRecord.objects.filter(
                employee=employee, date__gte=month_start, date__lte=month_end,
            )
        }

        # Work from home is a tag next to the status, not a status of its own (a day can be Late and WFH). A day is WFH when its
        # saved record says so, or when an approved work-from-home request covers it (so an approved day shows even before, or
        # without, a punch). One query for the month.
        from apps.hrms.models import REQ_APPROVED, WorkFromHomeRequest
        wfh_ranges = list(WorkFromHomeRequest.objects.filter(
            employee=employee, status=REQ_APPROVED, start_date__lte=month_end, end_date__gte=month_start,
        ).values_list('start_date', 'end_date'))

        def is_wfh_day(day, record) -> bool:
            if record is not None and record.work_mode == AttendanceRecord.WORK_MODE_WFH:
                return True
            return any(start <= day <= end for start, end in wfh_ranges)

        STATUS_LABELS = {
            'present': 'Present', 'late': 'Late Arrival', 'half_day': 'Half Day',
            'on_leave': 'On Leave', 'weekly_off': 'Week Off', 'holiday': 'Holiday',
            'absent': 'Absent', 'incomplete': 'Incomplete',
        }
        LOP_STATUSES = frozenset(['absent', 'incomplete'])
        stat_keys    = ('present', 'late', 'half_day', 'absent', 'on_leave',
                        'weekly_off', 'holiday', 'incomplete')
        stats = {k: 0 for k in stat_keys}
        stats['lop_days'] = 0
        stats['wfh'] = 0
        total_minutes = 0

        days = []
        current = month_start
        while current <= month_end:
            rec      = record_map.get(current)
            status   = rec.status if rec else 'no_record'
            minutes  = (rec.total_working_minutes or 0) if rec else 0
            ot_mins  = (rec.overtime_minutes or 0) if rec else 0
            clock_in  = rec.first_punch_in.strftime('%H:%M') if rec and rec.first_punch_in else None
            clock_out = rec.last_punch_out.strftime('%H:%M') if rec and rec.last_punch_out else None

            if status in stats:
                stats[status] += 1
            # A late arrival was still present, so a Late day counts as Present too; a late login (full hours, stored as Present) counts as
            # Late too. Present days and Late days therefore overlap on purpose.
            if status == 'late':
                stats['present'] += 1
            elif status == 'present' and rec is not None and rec.is_late:
                stats['late'] += 1
            if status in LOP_STATUSES:
                stats['lop_days'] += 1
            day_is_wfh = is_wfh_day(current, rec)
            if day_is_wfh:
                stats['wfh'] += 1
            total_minutes += minutes

            days.append({
                'date':           current.isoformat(),
                'day_name':       current.strftime('%A'),
                'day_short':      current.strftime('%a'),
                'day_num':        current.day,
                'status':         status,
                'status_label':   STATUS_LABELS.get(status, 'No Record'),
                'clock_in':       clock_in,
                'clock_out':      clock_out,
                'total_hours':    round(minutes / 60, 1),
                'overtime_hours': round(ot_mins / 60, 1),
                'is_flagged':     status in LOP_STATUSES,
                # Arrived late but worked the full hours: stored as Present, shown with a "Late login" tag.
                'is_late':        bool(rec and rec.is_late),
                'late_forgiven':  bool(rec and rec.is_late and status == 'present'),
                'record_id':      str(rec.id) if rec else None,
                'is_wfh':         day_is_wfh,
            })
            current += datetime.timedelta(days=1)

        return success('Employee monthly attendance retrieved.', {
            'employee': {
                'id':          str(employee.pk),
                'employee_id': employee.employee_id,
                'full_name':   employee.full_name,
                'department':  employee.department or '',
                'designation': employee.designation or '',
            },
            'month': month_str,
            'stats': {**stats, 'total_hours': round(total_minutes / 60, 1)},
            'days':  days,
        })


