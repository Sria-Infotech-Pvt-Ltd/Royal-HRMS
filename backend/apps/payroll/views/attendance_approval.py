import logging

from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error
from apps.payroll.models import PayrollCycle
from apps.payroll.serializers import PayrollCycleSerializer

logger = logging.getLogger(__name__)

APPROVER_ROLES = frozenset(['system_admin', 'hr', 'manager__team_lead'])
HR_ROLES       = frozenset(['system_admin', 'hr'])


def _role(user):
    return user.role.name if user.role else ''


class AttendancePendingCyclesView(APIView):
    """Cycles awaiting attendance approval for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _role(request.user)
        if role not in APPROVER_ROLES:
            return error('Access denied.', http_status=403)

        cycles = PayrollCycle.objects.filter(
            status=PayrollCycle.STATUS_ATTENDANCE_PENDING,
        ).select_related(
            'created_by', 'attendance_approved_by_l1', 'attendance_approved_by_l2',
        ).order_by('-cycle_start')

        # Managers only see cycles where their L1 approval is still pending
        if role == 'manager__team_lead':
            cycles = cycles.filter(attendance_approved_by_l1__isnull=True)

        serializer = PayrollCycleSerializer(cycles, many=True)
        return success('Pending attendance approval cycles.', serializer.data)


class CycleAttendanceSummaryView(APIView):
    """Team attendance breakdown for a payroll cycle period."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = _role(request.user)
        if role not in APPROVER_ROLES:
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        # Late import to avoid circular deps
        from apps.attendance.models import AttendanceRecord

        records = AttendanceRecord.objects.filter(
            date__range=[cycle.cycle_start, cycle.cycle_end],
            employee__is_active=True,
        ).select_related('employee')

        # Managers see only their direct reportees
        if role == 'manager__team_lead':
            records = records.filter(employee__reporting_manager=request.user)

        summary = (
            records
            .values(
                'employee__id',
                'employee__employee_id',
                'employee__full_name',
                'employee__department',
                'employee__designation',
            )
            .annotate(
                present_days    = Count('id', filter=Q(status='present')),
                late_days       = Count('id', filter=Q(status='late')),
                half_days       = Count('id', filter=Q(status='half_day')),
                absent_days     = Count('id', filter=Q(status='absent')),
                incomplete_days = Count('id', filter=Q(status='incomplete')),
                on_leave_days   = Count('id', filter=Q(status='on_leave')),
                weekly_off_days = Count('id', filter=Q(status='weekly_off')),
                holiday_days    = Count('id', filter=Q(status='holiday')),
                total_minutes   = Sum('total_working_minutes'),
            )
            .order_by('employee__full_name')
        )

        cycle_data = {
            'id':                        str(cycle.id),
            'cycle_start':               str(cycle.cycle_start),
            'cycle_end':                 str(cycle.cycle_end),
            'pay_date':                  str(cycle.pay_date),
            'status':                    cycle.status,
            'l1_approver':               cycle.attendance_approved_by_l1.full_name if cycle.attendance_approved_by_l1 else None,
            'l2_approver':               cycle.attendance_approved_by_l2.full_name if cycle.attendance_approved_by_l2 else None,
            'l1_approved_at':            str(cycle.attendance_l1_approved_at) if cycle.attendance_l1_approved_at else None,
            'l2_approved_at':            str(cycle.attendance_l2_approved_at) if cycle.attendance_l2_approved_at else None,
        }

        employees = [
            {
                'employee_id':   row['employee__employee_id'],
                'employee_uuid': str(row['employee__id']),
                'full_name':     row['employee__full_name'],
                'department':    row['employee__department'] or '—',
                'designation':   row['employee__designation'] or '—',
                'present_days':  row['present_days'],
                'late_days':     row['late_days'],
                'half_days':     row['half_days'],
                'absent_days':   row['absent_days'],
                'incomplete_days': row['incomplete_days'],
                'on_leave_days': row['on_leave_days'],
                'lop_days':      (row['absent_days'] or 0) + (row['incomplete_days'] or 0),
                'working_hours': round((row['total_minutes'] or 0) / 60, 1),
            }
            for row in summary
        ]

        return success('Attendance summary retrieved.', {'cycle': cycle_data, 'employees': employees})


class CycleEmployeeDailyView(APIView):
    """Day-by-day attendance for one employee within a payroll cycle period."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, employee_pk):
        role = _role(request.user)
        if role not in APPROVER_ROLES:
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        import uuid as _uuid_mod
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            _uuid_mod.UUID(str(employee_pk))
            employee = User.objects.filter(pk=employee_pk, is_active=True).first()
        except (ValueError, AttributeError):
            employee = User.objects.filter(employee_id=employee_pk, is_active=True).first()

        if not employee:
            return error('Employee not found.', http_status=404)

        if role == 'manager__team_lead' and employee.reporting_manager_id != request.user.pk:
            return error('Access denied.', http_status=403)

        from apps.attendance.models import AttendanceRecord
        from datetime import timedelta

        record_map = {
            r.date: r
            for r in AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=cycle.cycle_start,
                date__lte=cycle.cycle_end,
            )
        }

        STATUS_LABELS = {
            'present':    'Present',
            'late':       'Late Arrival',
            'half_day':   'Half Day',
            'on_leave':   'On Leave',
            'weekly_off': 'Week Off',
            'holiday':    'Holiday',
            'absent':     'Absent',
            'incomplete': 'Incomplete',
        }

        days = []
        current = cycle.cycle_start
        while current <= cycle.cycle_end:
            rec = record_map.get(current)
            status = rec.status if rec else 'no_record'
            minutes = (rec.total_working_minutes or 0) if rec else 0
            days.append({
                'date':          current.isoformat(),
                'day':           current.strftime('%a'),
                'status':        status,
                'status_label':  STATUS_LABELS.get(status, 'No Record'),
                'working_hours': round(minutes / 60, 1),
                'is_flagged':    status in ('absent', 'incomplete'),
            })
            current += timedelta(days=1)

        return success('Daily attendance retrieved.', {
            'employee_id': employee.employee_id,
            'full_name':   employee.full_name,
            'days':        days,
        })
