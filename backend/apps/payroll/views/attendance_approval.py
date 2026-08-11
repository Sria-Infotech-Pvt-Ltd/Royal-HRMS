import logging

from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error
from core.permissions import has_perm as _has_perm
from apps.payroll.models import PayrollCycle, ManagerAttendanceApproval
from apps.payroll.serializers import PayrollCycleSerializer, ManagerAttendanceApprovalSerializer

logger = logging.getLogger(__name__)

HR_PERMISSION = 'payroll.edit'


def _is_manager(user):
    """True for users whose role has can_manage_team=True."""
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return bool(user.role.can_manage_team)


def _is_hr(user):
    return _has_perm(user, HR_PERMISSION)


def _can_view_approvals(user):
    return _is_manager(user) or _is_hr(user)


class AttendancePendingCyclesView(APIView):
    """Cycles awaiting attendance approval for the current user.

    Managers see cycles where their own ManagerAttendanceApproval row is still
    pending (approved_at=null). HR sees all attendance_pending cycles.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_view_approvals(request.user):
            return error('Access denied.', http_status=403)

        if _is_hr(request.user) and not _is_manager(request.user):
            # Pure HR: show all pending cycles (they may need to do L2)
            cycles = PayrollCycle.objects.filter(
                status=PayrollCycle.STATUS_ATTENDANCE_PENDING,
            ).select_related(
                'created_by', 'attendance_approved_by_l1', 'attendance_approved_by_l2',
            ).order_by('-cycle_start')
        else:
            # Manager: show cycles where this user's row is still pending
            pending_cycle_ids = ManagerAttendanceApproval.objects.filter(
                manager=request.user,
                approved_at__isnull=True,
            ).values_list('cycle_id', flat=True)

            cycles = PayrollCycle.objects.filter(
                id__in=pending_cycle_ids,
                status=PayrollCycle.STATUS_ATTENDANCE_PENDING,
            ).select_related(
                'created_by', 'attendance_approved_by_l1', 'attendance_approved_by_l2',
            ).order_by('-cycle_start')

        serializer = PayrollCycleSerializer(cycles, many=True)
        return success('Pending attendance approval cycles.', serializer.data)


class CycleAttendanceSummaryView(APIView):
    """Team attendance breakdown for a payroll cycle period.

    Managers see only their direct reportees.
    HR sees everyone.
    Also returns per-manager approval status for the cycle.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _can_view_approvals(request.user):
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        from apps.attendance.models import AttendanceRecord

        records = AttendanceRecord.objects.filter(
            date__range=[cycle.cycle_start, cycle.cycle_end],
            employee__is_active=True,
        ).select_related('employee')

        if _is_manager(request.user) and not _is_hr(request.user):
            # Always scope to direct reportees — a manager with no reportees
            # configured must see an empty table, never every employee.
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

        # Per-manager approval rows for this cycle
        mgr_rows = ManagerAttendanceApproval.objects.filter(
            cycle=cycle,
        ).select_related('manager')
        mgr_serializer = ManagerAttendanceApprovalSerializer(mgr_rows, many=True)
        total_mgrs    = mgr_rows.count()
        approved_mgrs = mgr_rows.filter(approved_at__isnull=False).count()
        current_user_pending = mgr_rows.filter(
            manager=request.user, approved_at__isnull=True,
        ).exists()

        cycle_data = {
            'id':                  str(cycle.id),
            'cycle_start':         str(cycle.cycle_start),
            'cycle_end':           str(cycle.cycle_end),
            'pay_date':            str(cycle.pay_date),
            'status':              cycle.status,
            # Legacy single-approver fields (set only when L1 is fully complete)
            'l1_approver':         cycle.attendance_approved_by_l1.full_name if cycle.attendance_approved_by_l1 else None,
            'l2_approver':         cycle.attendance_approved_by_l2.full_name if cycle.attendance_approved_by_l2 else None,
            'l1_approved_at':      str(cycle.attendance_l1_approved_at) if cycle.attendance_l1_approved_at else None,
            'l2_approved_at':      str(cycle.attendance_l2_approved_at) if cycle.attendance_l2_approved_at else None,
            'hr_self_approved_at': str(cycle.hr_self_approved_at) if cycle.hr_self_approved_at else None,
            # Per-manager breakdown
            'manager_approvals':       mgr_serializer.data,
            'mgr_approved_count':      approved_mgrs,
            'mgr_total_count':         total_mgrs,
            'mgr_all_approved':        total_mgrs > 0 and approved_mgrs == total_mgrs,
            'current_user_pending':    current_user_pending,
        }

        employees = [
            {
                'employee_id':     row['employee__employee_id'],
                'employee_uuid':   str(row['employee__id']),
                'full_name':       row['employee__full_name'],
                'department':      row['employee__department'] or '—',
                'designation':     row['employee__designation'] or '—',
                'present_days':    row['present_days'],
                'late_days':       row['late_days'],
                'half_days':       row['half_days'],
                'absent_days':     row['absent_days'],
                'incomplete_days': row['incomplete_days'],
                'on_leave_days':   row['on_leave_days'],
                'lop_days':        (row['absent_days'] or 0) + (row['incomplete_days'] or 0),
                'working_hours':   round((row['total_minutes'] or 0) / 60, 1),
            }
            for row in summary
        ]

        return success('Attendance summary retrieved.', {'cycle': cycle_data, 'employees': employees})


class CycleEmployeeDailyView(APIView):
    """Day-by-day attendance for one employee within a payroll cycle period."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, employee_pk):
        if not _can_view_approvals(request.user):
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        import uuid as _uuid_mod
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        try:
            _uuid_mod.UUID(str(employee_pk))
            employee = UserModel.objects.filter(pk=employee_pk, is_active=True).first()
        except (ValueError, AttributeError):
            employee = UserModel.objects.filter(employee_id=employee_pk, is_active=True).first()

        if not employee:
            return error('Employee not found.', http_status=404)

        # Managers can only drill into their own direct reportees
        if _is_manager(request.user) and not _is_hr(request.user):
            if employee.reporting_manager_id != request.user.pk:
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
