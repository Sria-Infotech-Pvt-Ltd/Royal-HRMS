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

        month_start = datetime.date(year, mon, 1)
        month_end   = datetime.date(year, mon, _calendar.monthrange(year, mon)[1])

        record_map = {
            r.date: r
            for r in AttendanceRecord.objects.filter(
                employee=employee, date__gte=month_start, date__lte=month_end,
            )
        }

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
            if status in LOP_STATUSES:
                stats['lop_days'] += 1
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
                'record_id':      str(rec.id) if rec else None,
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


