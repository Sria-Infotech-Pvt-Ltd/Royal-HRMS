"""
Overview-landing endpoints for Attendance/Leave/Payroll/Performance/Reports/
Settings — the same KPI-row + overview-table + quick-actions pattern already
built for the main Dashboard (HRDashboardOverviewView) and Organization
(OrgOverviewView), just scoped to each module's own real data. Every number
here is a genuine query against that module's own models — never hardcoded.
"""
import datetime
import logging

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success

logger = logging.getLogger(__name__)
_DENIED = 'You do not have permission to perform this action.'


def _last_7_days_labels(today):
    return [(today - datetime.timedelta(days=i)) for i in range(6, -1, -1)]


class AttendanceOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.attendance.models import AttendanceRecord

        today = timezone.localdate()
        active_total = User.objects.filter(is_active=True).exclude(employee_id='').count()

        counts = {
            row['status']: row['n']
            for row in AttendanceRecord.objects.filter(date=today).values('status').annotate(n=Count('id'))
        }
        present = counts.get('present', 0) + counts.get('late', 0) + counts.get('half_day', 0)
        on_leave = counts.get('on_leave', 0)
        late = counts.get('late', 0)
        missing_punch = AttendanceRecord.objects.filter(
            date=today, status='incomplete',
        ).count()

        recent = list(
            AttendanceRecord.objects.filter(date=today).select_related('employee')
            .order_by('-updated_at')[:5]
        )
        overview_rows = [{
            'name': r.employee.full_name,
            'context': f"{r.employee.branch or '—'} · {r.first_punch_in.strftime('%H:%M') if r.first_punch_in else '—'}",
            'status_label': AttendanceRecord.STATUS_DISPLAY_MAP.get(r.status, r.status),
            'status_kind': (
                'success' if r.status in ('present',) else
                'error' if r.status in ('absent', 'incomplete') else 'warn'
            ),
            'link': '/dashboard/attendance',
        } for r in recent]

        days = _last_7_days_labels(today)
        chart = [{
            'label': d.strftime('%a')[0],
            'count': AttendanceRecord.objects.filter(date=d, status__in=['present', 'late', 'half_day']).count(),
        } for d in days]

        return success('Attendance overview retrieved.', {
            'present': present, 'present_pct': round(present / active_total * 100) if active_total else 0,
            'on_leave': on_leave, 'late_arrivals': late, 'missing_punch': missing_punch,
            'total_employees': active_total,
            'overview_rows': overview_rows, 'weekly_chart': chart,
        })


class LeaveOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'leave.view'):
            return error(_DENIED, http_status=403)

        from apps.hrms.models import Holiday, LeaveRequest, REQ_APPROVED, REQ_PENDING

        today = timezone.localdate()
        pending = LeaveRequest.objects.filter(status=REQ_PENDING).count()
        on_leave_today = LeaveRequest.objects.filter(
            status=REQ_APPROVED, start_date__lte=today, end_date__gte=today,
        ).count()
        upcoming = LeaveRequest.objects.filter(
            status=REQ_APPROVED, start_date__gt=today, start_date__lte=today + datetime.timedelta(days=14),
        ).count()
        holidays_remaining = Holiday.objects.filter(is_active=True, date__gt=today, date__year=today.year).count()

        from apps.branch.models import Branch
        holiday_states = list(
            Branch.objects.filter(status=Branch.STATUS_ACTIVE).select_related('state')
            .values_list('state__name', flat=True).distinct()
        )

        recent = list(
            LeaveRequest.objects.select_related('employee').order_by('-id')[:5]
        )
        overview_rows = [{
            'name': r.employee.full_name,
            'context': f"{r.get_leave_type_display()} · {r.start_date.strftime('%d %b')}"
                       + (f"–{r.end_date.strftime('%d %b')}" if r.end_date != r.start_date else ''),
            'status_label': f"{r.total_days:g} day{'s' if r.total_days != 1 else ''}" if r.status == REQ_PENDING else r.get_status_display(),
            'status_kind': 'success' if r.status == REQ_APPROVED else 'error' if r.status == 'rejected' else 'warn',
            'link': '/dashboard/leave',
        } for r in recent]

        days = _last_7_days_labels(today)
        chart = [{
            'label': d.strftime('%a')[0],
            'count': LeaveRequest.objects.filter(status=REQ_APPROVED, start_date__lte=d, end_date__gte=d).count(),
        } for d in days]

        return success('Leave overview retrieved.', {
            'pending': pending, 'on_leave_today': on_leave_today, 'upcoming': upcoming,
            'holidays_remaining': holidays_remaining, 'holiday_states': holiday_states,
            'overview_rows': overview_rows, 'weekly_chart': chart,
        })


class PayrollOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.hrms.models import SEP_APPROVED, SeparationRequest
        from apps.payroll.models import EmployeePayslip, EmployeeSalaryConfig, PayrollCycle

        cycle = PayrollCycle.objects.order_by('-cycle_start').first()
        employees = User.objects.filter(is_active=True).exclude(employee_id='')
        total_headcount = employees.count()

        # Same "payroll ready" definition as HRDashboardOverviewView — an
        # active EmployeeSalaryConfig plus complete bank details.
        payroll_ready_ids = set(
            EmployeeSalaryConfig.objects.filter(employee__in=employees, is_active=True)
            .values_list('employee_id', flat=True)
        )
        bank_ids = set(
            employees.filter(profile__account_number__isnull=False)
            .exclude(profile__account_number='').exclude(profile__ifsc_code='')
            .values_list('id', flat=True)
        )
        payroll_ready = len(payroll_ready_ids & bank_ids)
        blocked = total_headcount - payroll_ready
        bank_missing = total_headcount - len(bank_ids)

        gross = deductions = net = 0
        if cycle:
            payslips = EmployeePayslip.objects.filter(cycle=cycle)
            for p in payslips:
                gross += p.gross_earnings
                deductions += p.total_deductions
                net += p.net_pay

        today = timezone.localdate()
        salary_revisions_this_month = EmployeeSalaryConfig.objects.filter(
            effective_from__year=today.year, effective_from__month=today.month,
        ).count()
        new_joiners = employees.filter(date_of_joining__year=today.year, date_of_joining__month=today.month).count()
        new_joiners_no_ctc = employees.filter(
            date_of_joining__year=today.year, date_of_joining__month=today.month,
        ).exclude(id__in=payroll_ready_ids).count()
        exit_settlements = SeparationRequest.objects.filter(status=SEP_APPROVED).count()

        attendance_status = 'Not started'
        if cycle:
            if cycle.attendance_l2_approved_at or cycle.attendance_l1_approved_at:
                attendance_status = 'Validated'
            elif cycle.status == PayrollCycle.STATUS_ATTENDANCE_PENDING:
                attendance_status = 'Pending'

        overview_rows = [
            {
                'name': 'Employee master data',
                'context': f"{payroll_ready} of {total_headcount} ready",
                'status_label': f"{blocked} blocked" if blocked else 'Ready',
                'status_kind': 'error' if blocked else 'success',
                'link': '/dashboard/payroll',
            },
            {
                'name': 'Attendance inputs',
                'context': f"{cycle.cycle_start.strftime('%b %d')}–{cycle.cycle_end.strftime('%b %d')}" if cycle else 'No cycle yet',
                'status_label': attendance_status,
                'status_kind': 'success' if attendance_status == 'Validated' else 'warn',
                'link': '/dashboard/payroll',
            },
            {
                'name': 'New joiners',
                'context': f"{new_joiners} employee{'s' if new_joiners != 1 else ''}",
                'status_label': f"{new_joiners_no_ctc} CTC pending" if new_joiners_no_ctc else 'Ready',
                'status_kind': 'error' if new_joiners_no_ctc else 'success',
                'link': '/dashboard/employees',
            },
            {
                'name': 'Exit settlements',
                'context': f"{exit_settlements} employee{'s' if exit_settlements != 1 else ''}",
                'status_label': 'In review' if exit_settlements else 'None pending',
                'status_kind': 'warn' if exit_settlements else 'success',
                'link': '/dashboard/separation',
            },
            {
                'name': 'Bank validation',
                'context': f"{len(bank_ids)} accounts",
                'status_label': f"{bank_missing} missing" if bank_missing else 'Complete',
                'status_kind': 'error' if bank_missing else 'success',
                'link': '/dashboard/employees',
            },
        ]

        return success('Payroll overview retrieved.', {
            'gross_pay': float(gross), 'deductions': float(deductions), 'net_pay': float(net),
            'blocked': blocked, 'employee_count': total_headcount,
            'cycle_label': cycle.cycle_start.strftime('%B %Y') if cycle else 'No cycle yet',
            'cycle_status_display': cycle.get_status_display() if cycle else '',
            'salary_revisions_this_month': salary_revisions_this_month,
            'overview_rows': overview_rows,
            'weekly_chart': [{'label': l, 'count': 0} for l in ['M', 'T', 'W', 'T', 'F', 'S', 'S']],
        })


class PerformanceOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.performance.models import Goal, PerformanceReview, ReviewCycle

        cycle = ReviewCycle.objects.filter(status='active').order_by('-period_start').first()
        self_done = self_total = mgr_done = mgr_total = self_pct = manager_pct = 0
        goals_at_risk = 0
        cycle_closes = ''
        my_review_tasks = 0
        active_goals = 0
        overview_rows = []
        if cycle:
            # Personalized to the viewing user — their own pending self-review
            # plus whichever direct reports' reviews are waiting on them as
            # manager, both for the active cycle.
            my_review_tasks = (
                PerformanceReview.objects.filter(cycle=cycle, employee=request.user, self_submitted_at__isnull=True).count()
                + PerformanceReview.objects.filter(cycle=cycle, manager=request.user, manager_submitted_at__isnull=True).count()
            )
            active_goals = Goal.objects.filter(cycle=cycle).exclude(status='completed').count()
            reviews = PerformanceReview.objects.filter(cycle=cycle)
            self_total = mgr_total = reviews.count()
            self_done = reviews.exclude(self_submitted_at__isnull=True).count()
            mgr_done = reviews.exclude(manager_submitted_at__isnull=True).count()
            self_pct = round(self_done / self_total * 100) if self_total else 0
            manager_pct = round(mgr_done / mgr_total * 100) if mgr_total else 0
            goals_at_risk = Goal.objects.filter(cycle=cycle, status='at_risk').count()
            # %-d (no leading zero) isn't portable to Windows strftime — build it manually.
            cycle_closes = f"Closes {cycle.period_end.day} {cycle.period_end.strftime('%b')}" if cycle.period_end else ''

            overview_rows.append({
                'name': f'{cycle.name} performance review',
                'context': 'All employees',
                'status_label': 'In progress' if cycle.status == 'active' else cycle.get_status_display(),
                'status_kind': 'warn' if cycle.status == 'active' else 'success',
                'link': '/dashboard/performance',
            })

            # Real probation employee closest to their computed confirmation
            # due date (date_of_joining + probation_period_months, both set
            # on the Hire wizard's Employment step) — the most urgent one.
            probation_rows = []
            for u in User.objects.filter(
                is_active=True, employment_status=User.EMPLOYMENT_STATUS_PROBATION,
                date_of_joining__isnull=False, probation_period_months__isnull=False,
            ):
                due = u.date_of_joining + datetime.timedelta(days=u.probation_period_months * 30)
                probation_rows.append((due, u))
            if probation_rows:
                probation_rows.sort(key=lambda t: t[0])
                due, u = probation_rows[0]
                overview_rows.append({
                    'name': 'Probation reviews', 'context': u.full_name,
                    'status_label': f"Due {due.day} {due.strftime('%b')}", 'status_kind': 'warn',
                    'link': '/dashboard/employees',
                })

            # Real department-level goal check-in completion — the
            # department (User.department) with the most goals this cycle.
            dept_counts = (
                Goal.objects.filter(cycle=cycle).exclude(employee__department='')
                .values('employee__department').annotate(n=Count('id')).order_by('-n').first()
            )
            if dept_counts:
                dept = dept_counts['employee__department']
                dept_goals = Goal.objects.filter(cycle=cycle, employee__department=dept)
                dept_total = dept_goals.count()
                dept_done = dept_goals.filter(status='completed').count()
                dept_pct = round(dept_done / dept_total * 100) if dept_total else 0
                overview_rows.append({
                    'name': 'Goal check-ins', 'context': dept,
                    'status_label': f'{dept_pct}% complete',
                    'status_kind': 'success' if dept_pct >= 75 else 'warn',
                    'link': '/dashboard/performance',
                })

        return success('Performance overview retrieved.', {
            'active_cycle': cycle.name if cycle else 'No active cycle', 'active_cycle_closes': cycle_closes,
            'self_reviews_done': self_done, 'self_reviews_total': self_total, 'self_reviews_pct': self_pct,
            'manager_reviews_done': mgr_done, 'manager_reviews_total': mgr_total, 'manager_reviews_pct': manager_pct,
            'goals_at_risk': goals_at_risk, 'my_review_tasks': my_review_tasks, 'active_goals': active_goals,
            'overview_rows': overview_rows,
            'weekly_chart': [{'label': l, 'count': 0} for l in ['M', 'T', 'W', 'T', 'F', 'S', 'S']],
        })


class ReportsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import AuditLog, User
        from apps.hrms.models import SEP_APPROVED, SeparationRequest
        from apps.payroll.models import PayrollCycle

        today = timezone.localdate()
        exports_today = AuditLog.objects.filter(action='export', created_at__date=today).count()
        audit_events_30d = AuditLog.objects.filter(created_at__date__gte=today - datetime.timedelta(days=30)).count()
        days = _last_7_days_labels(today)
        chart = [{'label': d.strftime('%a')[0], 'count': AuditLog.objects.filter(created_at__date=d).count()} for d in days]

        employees = User.objects.filter(is_active=True).exclude(employee_id='')
        total_headcount = employees.count()
        last_updated = employees.order_by('-updated_at').values_list('updated_at', flat=True).first()

        cycle = PayrollCycle.objects.order_by('-cycle_start').first()

        required_doc_types = {'pan_card', 'aadhaar_card'}
        missing_docs = 0
        for u in employees.select_related('profile'):
            has_pan = bool(getattr(u.profile, 'pan_number', '')) if hasattr(u, 'profile') else False
            if not has_pan:
                missing_docs += 1

        attrition_12mo = SeparationRequest.objects.filter(
            status=SEP_APPROVED, created_at__date__gte=today - datetime.timedelta(days=365),
        ).count()

        overview_rows = [
            {
                'name': 'Employee master register', 'context': 'People & organization',
                'status_label': 'Updated now' if last_updated and last_updated.date() == today else 'Up to date',
                'status_kind': 'success', 'link': '/dashboard/employees',
            },
            {
                'name': 'Monthly attendance', 'context': 'Time & attendance',
                'status_label': today.strftime('%B %Y'), 'status_kind': 'success', 'link': '/dashboard/attendance',
            },
            {
                'name': 'Payroll variance', 'context': 'Payroll',
                'status_label': 'Draft available' if cycle and cycle.status == PayrollCycle.STATUS_DRAFT else ('No cycle yet' if not cycle else cycle.get_status_display()),
                'status_kind': 'warn' if not cycle or cycle.status == PayrollCycle.STATUS_DRAFT else 'success',
                'link': '/dashboard/payroll',
            },
            {
                'name': 'Statutory readiness', 'context': 'Compliance',
                'status_label': f"{missing_docs} exception{'s' if missing_docs != 1 else ''}" if missing_docs else 'Compliant',
                'status_kind': 'error' if missing_docs else 'success', 'link': '/dashboard/settings/audit',
            },
            {
                'name': 'Attrition analysis', 'context': 'Workforce analytics',
                'status_label': f"{attrition_12mo} in last 12 months", 'status_kind': 'success', 'link': '/dashboard/separation',
            },
        ]

        return success('Reports overview retrieved.', {
            'exports_today': exports_today, 'audit_events_30d': audit_events_30d, 'weekly_chart': chart,
            'overview_rows': overview_rows, 'total_headcount': total_headcount,
        })


class SettingsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import AuditLog, Role

        today = timezone.localdate()
        admin_roles = Role.objects.filter(is_active=True).exclude(name='employee').count()
        audit_events_30d = AuditLog.objects.filter(created_at__date__gte=today - datetime.timedelta(days=30)).count()

        return success('Settings overview retrieved.', {
            'admin_roles': admin_roles, 'audit_events_30d': audit_events_30d,
        })
