import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

logger = logging.getLogger(__name__)
_DENIED = 'You do not have permission to perform this action.'


def _is_manager(user):
    return bool(user and user.role and user.role.name == 'manager__team_lead')


class ManagerKPIView(APIView):
    """Greeting-banner KPIs: team size, pending approvals, on-leave-today, attendance rate."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_manager(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.attendance.models import AttendanceRecord
        from apps.hrms.models import Expense, LeaveRequest, REQ_APPROVED, REQ_PENDING

        today     = timezone.localdate()
        team_size = User.objects.filter(reporting_manager=request.user, is_active=True).count()

        leave_pending   = LeaveRequest.objects.filter(l1_approver=request.user, status=REQ_PENDING).count()
        expense_pending = Expense.objects.filter(
            employee__reporting_manager=request.user, status='pending',
        ).count()

        on_leave_today = LeaveRequest.objects.filter(
            employee__reporting_manager=request.user,
            status=REQ_APPROVED,
            start_date__lte=today,
            end_date__gte=today,
        ).count()

        present_today = AttendanceRecord.objects.filter(
            employee__reporting_manager=request.user,
            date=today,
            status__in=[
                AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_INCOMPLETE, AttendanceRecord.STATUS_HALF_DAY,
            ],
        ).count()
        attendance_rate = round((present_today / team_size) * 100) if team_size else 0

        return success('Manager dashboard KPIs retrieved.', data={
            'team_size':          team_size,
            'pending_approvals':  leave_pending + expense_pending,
            'on_leave_today':     on_leave_today,
            'attendance_rate':    attendance_rate,
        })


class ManagerPendingApprovalsView(APIView):
    """Preview of the team's pending leave/expense approvals — top 5. Full review is on /dashboard/approvals."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_manager(request.user):
            return error(_DENIED, http_status=403)

        from apps.hrms.models import Expense, LeaveRequest, REQ_PENDING

        items = []
        for lr in LeaveRequest.objects.filter(
            l1_approver=request.user, status=REQ_PENDING,
        ).select_related('employee').order_by('-created_at')[:10]:
            items.append({
                'type':          'leave',
                'id':            str(lr.id),
                'employee_name': lr.employee.full_name,
                'created_at':    lr.created_at.isoformat(),
                'details': {
                    'leave_type': lr.leave_type,
                    'start_date': str(lr.start_date),
                    'end_date':   str(lr.end_date),
                    'total_days': float(lr.total_days),
                },
            })

        for ex in Expense.objects.filter(
            employee__reporting_manager=request.user, status='pending',
        ).select_related('employee').order_by('-created_at')[:10]:
            items.append({
                'type':          'expense',
                'id':            str(ex.id),
                'employee_name': ex.employee.full_name,
                'created_at':    ex.created_at.isoformat(),
                'details': {
                    'title':        ex.title,
                    'category':     ex.category,
                    'amount':       float(ex.amount),
                    'expense_date': str(ex.expense_date),
                },
            })

        items.sort(key=lambda x: x['created_at'], reverse=True)
        return success('Pending approvals retrieved.', data={
            'total_pending': len(items),
            'items':         items[:5],
        })


class ManagerTeamAttendanceTodayView(APIView):
    """Today's attendance status for every direct report."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_manager(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.attendance.models import AttendanceRecord

        today = timezone.localdate()
        team  = list(
            User.objects.filter(reporting_manager=request.user, is_active=True).order_by('full_name')
        )
        records_by_employee = {
            r.employee_id: r
            for r in AttendanceRecord.objects.filter(employee__reporting_manager=request.user, date=today)
        }

        present_statuses = {
            AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE,
            AttendanceRecord.STATUS_INCOMPLETE, AttendanceRecord.STATUS_HALF_DAY,
        }
        present_count = 0
        rows = []
        for emp in team:
            record = records_by_employee.get(emp.id)
            if record:
                status = record.status
                if status in present_statuses:
                    present_count += 1
                status_display = AttendanceRecord.STATUS_DISPLAY_MAP.get(status, status.replace('_', ' ').title())
                first_punch_in = str(record.first_punch_in) if record.first_punch_in else None
            else:
                status, status_display, first_punch_in = 'not_marked', 'Not Marked', None

            rows.append({
                'employee_id':     str(emp.id),
                'employee_name':   emp.full_name,
                'status':          status,
                'status_display':  status_display,
                'first_punch_in':  first_punch_in,
            })

        return success('Team attendance retrieved.', data={
            'team_size':     len(team),
            'present_count': present_count,
            'rows':          rows,
        })


class ManagerUpcomingLeaveView(APIView):
    """Team's upcoming approved leave, soonest first — top 5."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_manager(request.user):
            return error(_DENIED, http_status=403)

        from apps.hrms.models import LeaveRequest, REQ_APPROVED

        today = timezone.localdate()
        qs = LeaveRequest.objects.filter(
            employee__reporting_manager=request.user,
            status=REQ_APPROVED,
            end_date__gte=today,
        ).select_related('employee').order_by('start_date')[:5]

        items = [{
            'id':            str(lr.id),
            'employee_name': lr.employee.full_name,
            'leave_type':    lr.leave_type,
            'start_date':    str(lr.start_date),
            'end_date':      str(lr.end_date),
            'total_days':    float(lr.total_days),
        } for lr in qs]

        return success('Upcoming team leave retrieved.', data={'items': items})


class ManagerRecentActivityView(APIView):
    """Recent team activity feed — clock-ins and leave applications, newest first, top 5."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_manager(request.user):
            return error(_DENIED, http_status=403)

        from apps.attendance.models import AttendanceAuditLog
        from apps.hrms.models import LeaveRequest

        items = []
        for log in AttendanceAuditLog.objects.filter(
            employee__reporting_manager=request.user,
            event=AttendanceAuditLog.EVENT_CLOCK_IN,
        ).select_related('employee').order_by('-created_at')[:5]:
            items.append({
                'type':          'clock_in',
                'employee_name': log.employee.full_name,
                'created_at':    log.created_at.isoformat(),
            })

        for lr in LeaveRequest.objects.filter(
            employee__reporting_manager=request.user,
        ).select_related('employee').order_by('-created_at')[:5]:
            items.append({
                'type':          'leave_applied',
                'employee_name': lr.employee.full_name,
                'created_at':    lr.created_at.isoformat(),
                'details': {
                    'leave_type': lr.leave_type,
                    'start_date': str(lr.start_date),
                    'end_date':   str(lr.end_date),
                },
            })

        items.sort(key=lambda x: x['created_at'], reverse=True)
        return success('Recent team activity retrieved.', data={'items': items[:5]})
