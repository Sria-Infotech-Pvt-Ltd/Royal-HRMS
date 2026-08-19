import logging
import os

from django.conf import settings as django_settings
from django.core.cache import cache
from django.db import connection as db_connection
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import HasCompletedOnboarding, has_perm as _has_perm
from core.responses import error, success

logger = logging.getLogger(__name__)
_DENIED = 'You do not have permission to perform this action.'

_TTL_HEADCOUNT     = 12 * 3600   # 12 h
_TTL_FUNNEL        = 10 * 60     # 10 min
_TTL_ACTION_QUEUE  = 45          # seconds — action-queue counts, short TTL to stay near-real-time
_TTL_ATTENDANCE    = 3  * 60     # today's attendance breakdown


def _is_system_admin(user):
    return _has_perm(user, 'settings.edit')


def _is_hr_or_admin(user):
    return _has_perm(user, 'employees.view')


def _hr_dashboard_branch(user):
    """
    Branch to scope the HR dashboard's KPI/action-queue counts to, or None for
    company-wide totals. Deliberately checks role name / the raw is_superuser
    flag rather than the 'settings.edit' permission — that permission has
    historically also been granted to the HR role itself (see seed migration
    0002_seed_roles_permissions), which would make company-wide totals leak
    to branch HR users if used here.
    """
    if not user:
        return None
    if user.role and user.role.name == 'system_admin':
        return None
    if getattr(user, 'is_superuser', False):
        return None
    return user.branch or None


def _todays_attendance(employee, today):
    """
    Shared 'today's attendance' lookup — used by HRKPIView, EmployeeKPIView,
    and EmployeeAttendanceStatusView. Returns (today_attendance, is_clocked_in);
    today_attendance is None when there's no record for today yet.
    """
    from apps.attendance.models import AttendanceRecord

    record = AttendanceRecord.objects.filter(employee=employee, date=today).first()
    if not record:
        return None, False
    today_attendance = {
        'status':                record.status,
        'first_punch_in':        str(record.first_punch_in) if record.first_punch_in else None,
        'last_punch_out':        str(record.last_punch_out) if record.last_punch_out else None,
        'total_working_minutes': record.total_working_minutes,
    }
    is_clocked_in = bool(record.first_punch_in and not record.last_punch_out)
    return today_attendance, is_clocked_in


def _headcount_data():
    """Shared department headcount — cached 12 h, used by both dashboards."""
    rows = cache.get('dashboard:hr:headcount')
    if rows is None:
        from apps.accounts.models import User
        rows = list(
            User.objects.filter(is_active=True).exclude(department='')
            .values('department').annotate(count=Count('id')).order_by('-count')
        )
        cache.set('dashboard:hr:headcount', rows, _TTL_HEADCOUNT)
    return rows


# ─── System Admin KPIs ────────────────────────────────────────────────────────

class SystemAdminKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User, SMTPSettings
        from apps.branch.models import Branch
        from apps.hrms.models import LeaveRequest, Expense, REQ_PENDING, REQ_L2_PENDING

        # Slow-changing aggregate — cached like HRKPIView.total_workforce below.
        total_employees = cache.get('dashboard:sysadmin:total_employees')
        if total_employees is None:
            total_employees = User.objects.filter(is_active=True).count()
            cache.set('dashboard:sysadmin:total_employees', total_employees, 5 * 60)

        # Pending-action counts — deliberately NOT cached (matches HRKPIView's
        # "Real-time counts — not cached per spec": an admin acting on one of
        # these expects the number to move immediately, not after a TTL).
        leave_pending        = LeaveRequest.objects.filter(status__in=[REQ_PENDING, REQ_L2_PENDING]).count()
        expense_pending      = Expense.objects.filter(status='pending').count()
        onboarding_submitted = User.objects.filter(
            onboarding_status=User.ONBOARDING_SUBMITTED, is_active=True
        ).count()
        pending_approvals = leave_pending + expense_pending + onboarding_submitted

        # Onboarding funnel — same category as the (already-cached) recruitment
        # funnel, not an action queue, so it's fine to cache.
        employees_onboarding = cache.get('dashboard:sysadmin:employees_onboarding')
        if employees_onboarding is None:
            employees_onboarding = User.objects.filter(
                onboarding_status__in=[
                    User.ONBOARDING_PENDING,
                    User.ONBOARDING_DRAFT,
                    User.ONBOARDING_SUBMITTED,
                ],
                is_active=True,
            ).count()
            cache.set('dashboard:sysadmin:employees_onboarding', employees_onboarding, _TTL_FUNNEL)

        active_branches = cache.get('dashboard:sysadmin:active_branches')
        if active_branches is None:
            active_branches = Branch.objects.filter(status=Branch.STATUS_ACTIVE).count()
            cache.set('dashboard:sysadmin:active_branches', active_branches, _TTL_HEADCOUNT)

        try:
            db_connection.ensure_connection()
            database_status = True
        except Exception:
            database_status = False

        mail_status    = SMTPSettings.get_active() is not None
        storage_status = bool(
            os.environ.get('CLOUDINARY_URL') or
            os.path.isdir(str(getattr(django_settings, 'MEDIA_ROOT', '')))
        )

        return success('KPIs retrieved.', data={
            'total_employees':      total_employees,
            'pending_approvals':    pending_approvals,
            'employees_onboarding': employees_onboarding,
            'active_branches':      active_branches,
            'api_status':           True,
            'database_status':      database_status,
            'mail_status':          mail_status,
            'storage_status':       storage_status,
        })


# ─── System Admin Announcement ────────────────────────────────────────────────

class SystemAdminAnnouncementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)

        from apps.announcements.models import Announcement

        ann = Announcement.objects.select_related('posted_by').first()
        if ann is None:
            return success('No announcements found.', data=None)

        return success('Latest announcement retrieved.', data={
            'id':         ann.id,
            'title':      ann.title,
            'body':       ann.body,
            'category':   ann.category,
            'visibility': ann.visibility,
            'is_pinned':  ann.is_pinned,
            'posted_by':  ann.posted_by.full_name if ann.posted_by else None,
            'created_at': ann.created_at.isoformat(),
        })


# ─── System Admin Pending Approvals ──────────────────────────────────────────

class SystemAdminPendingApprovalsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.hrms.models import LeaveRequest, Expense, REQ_PENDING, REQ_L2_PENDING

        leave_requests     = LeaveRequest.objects.filter(status__in=[REQ_PENDING, REQ_L2_PENDING]).count()
        expense_claims     = Expense.objects.filter(status='pending').count()
        onboarding_reviews = User.objects.filter(
            onboarding_status=User.ONBOARDING_SUBMITTED, is_active=True
        ).count()
        separation_requests = 0  # model not yet implemented

        return success('Pending approvals retrieved.', data={
            'leave_requests':      leave_requests,
            'expense_claims':      expense_claims,
            'onboarding_reviews':  onboarding_reviews,
            'separation_requests': separation_requests,
            'total_pending':       leave_requests + expense_claims + onboarding_reviews,
        })


# ─── Department Headcount (shared) ───────────────────────────────────────────

class SystemAdminDepartmentHeadcountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_system_admin(request.user):
            return error(_DENIED, http_status=403)
        return success('Department headcount retrieved.', data=_headcount_data())


class HRDepartmentHeadcountView(APIView):
    """Shared headcount endpoint — HR and System Admin."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)
        return success('Department headcount retrieved.', data=_headcount_data())


# ─── HR KPIs ──────────────────────────────────────────────────────────────────

class HRKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import User
        from apps.attendance.models import AttendanceCorrection
        from apps.hrms.models import LeaveRequest, Expense, REQ_PENDING, REQ_L2_PENDING
        from apps.recruitment.models import Candidate

        today = timezone.localdate()
        branch = _hr_dashboard_branch(request.user)
        cache_scope = branch or 'all'

        total_workforce = cache.get(f'dashboard:hr:kpis:workforce:{cache_scope}')
        if total_workforce is None:
            workforce_qs = User.objects.filter(is_active=True)
            if branch:
                workforce_qs = workforce_qs.filter(branch=branch)
            total_workforce = workforce_qs.count()
            cache.set(f'dashboard:hr:kpis:workforce:{cache_scope}', total_workforce, 5 * 60)

        active_interviews = cache.get(f'dashboard:hr:kpis:interviews:{cache_scope}')
        if active_interviews is None:
            interviews_qs = Candidate.objects.filter(
                status__in=[Candidate.STATUS_INTERVIEW_SCHEDULED, Candidate.STATUS_INTERVIEW_DONE]
            )
            if branch:
                interviews_qs = interviews_qs.filter(branch__branch_name=branch)
            active_interviews = interviews_qs.count()
            cache.set(f'dashboard:hr:kpis:interviews:{cache_scope}', active_interviews, _TTL_FUNNEL)

        # Real-time counts — not cached per spec
        leave_qs      = LeaveRequest.objects.filter(status__in=[REQ_PENDING, REQ_L2_PENDING])
        expense_qs    = Expense.objects.filter(status='pending')
        onboarding_qs = User.objects.filter(onboarding_status=User.ONBOARDING_SUBMITTED, is_active=True)
        correction_qs = AttendanceCorrection.objects.filter(status=AttendanceCorrection.STATUS_PENDING)
        if branch:
            leave_qs      = leave_qs.filter(employee__branch=branch)
            expense_qs    = expense_qs.filter(employee__branch=branch)
            onboarding_qs = onboarding_qs.filter(branch=branch)
            correction_qs = correction_qs.filter(employee__branch=branch)
        leave_pending      = leave_qs.count()
        expense_pending    = expense_qs.count()
        onboarding_pending = onboarding_qs.count()
        correction_pending = correction_qs.count()
        pending_actions = leave_pending + expense_pending + onboarding_pending

        # Requesting user's own attendance today
        today_attendance, clocked_in = _todays_attendance(request.user, today)

        return success('HR dashboard KPIs fetched successfully.', data={
            'total_workforce':               total_workforce,
            'pending_actions':               pending_actions,
            'active_interviews':             active_interviews,
            'employees_on_probation':        0,
            'clocked_in':                    clocked_in,
            'today_attendance':              today_attendance,
            'attendance_correction_pending': correction_pending,
        })


# ─── HR Action Queue ──────────────────────────────────────────────────────────

class HRActionQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        branch = _hr_dashboard_branch(request.user)

        # Short TTL rather than a full skip: this endpoint is hit on every
        # dashboard load, and a 45s-stale badge count is an acceptable
        # trade-off for the load reduction — long enough to matter under
        # concurrent traffic, short enough that no admin will notice.
        cache_key = f'dashboard:hr:action_queue:{branch or "all"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success('Action queue retrieved.', data=cached)

        from apps.accounts.models import User
        from apps.attendance.models import AttendanceCorrection
        from apps.hrms.models import LeaveRequest, Expense, REQ_PENDING, REQ_L2_PENDING
        from apps.recruitment.models import Candidate

        candidate_qs  = Candidate.objects.filter(
            status=Candidate.STATUS_SELECTED, details_filled=True, hr_approved=False,
        )
        leave_qs      = LeaveRequest.objects.filter(status__in=[REQ_PENDING, REQ_L2_PENDING])
        correction_qs = AttendanceCorrection.objects.filter(status=AttendanceCorrection.STATUS_PENDING)
        expense_qs    = Expense.objects.filter(status='pending')
        onboarding_qs = User.objects.filter(onboarding_status=User.ONBOARDING_SUBMITTED, is_active=True)
        if branch:
            candidate_qs  = candidate_qs.filter(branch__branch_name=branch)
            leave_qs      = leave_qs.filter(employee__branch=branch)
            correction_qs = correction_qs.filter(employee__branch=branch)
            expense_qs    = expense_qs.filter(employee__branch=branch)
            onboarding_qs = onboarding_qs.filter(branch=branch)

        candidate_reviews      = candidate_qs.count()
        leave_approvals        = leave_qs.count()
        attendance_corrections = correction_qs.count()
        expense_claims         = expense_qs.count()
        onboarding_reviews     = onboarding_qs.count()

        total = candidate_reviews + leave_approvals + attendance_corrections + expense_claims + onboarding_reviews

        data = {
            'total_pending':           total,
            'candidate_reviews':       candidate_reviews,
            'leave_approvals':         leave_approvals,
            'attendance_corrections':  attendance_corrections,
            'expense_claims':          expense_claims,
            'onboarding_reviews':      onboarding_reviews,
            'separation_requests':     0,
        }
        cache.set(cache_key, data, _TTL_ACTION_QUEUE)
        return success('Action queue retrieved.', data=data)


def push_leave_update(approving_user_id) -> None:
    """
    Recompute action-queue counts, refresh the cache, then push the full
    data payload through the WebSocket so dashboard components update their
    state directly — no HTTP refetch needed on the client.

    Called from LeaveApprovalView.post() and execute_confirm_leave_approval()
    immediately after a leave is approved or rejected.
    """
    from apps.accounts.models import User
    from apps.attendance.models import AttendanceCorrection
    from apps.hrms.models import LeaveRequest, Expense, REQ_PENDING, REQ_L2_PENDING
    from apps.recruitment.models import Candidate

    approving_user = User.objects.filter(pk=approving_user_id).select_related('role').first()
    branch = _hr_dashboard_branch(approving_user)

    leave_qs      = LeaveRequest.objects.filter(status__in=[REQ_PENDING, REQ_L2_PENDING])
    expense_qs    = Expense.objects.filter(status='pending')
    onboarding_qs = User.objects.filter(onboarding_status=User.ONBOARDING_SUBMITTED, is_active=True)
    candidate_qs  = Candidate.objects.filter(
        status=Candidate.STATUS_SELECTED, details_filled=True, hr_approved=False,
    )
    correction_qs = AttendanceCorrection.objects.filter(status=AttendanceCorrection.STATUS_PENDING)
    if branch:
        leave_qs      = leave_qs.filter(employee__branch=branch)
        expense_qs    = expense_qs.filter(employee__branch=branch)
        onboarding_qs = onboarding_qs.filter(branch=branch)
        candidate_qs  = candidate_qs.filter(branch__branch_name=branch)
        correction_qs = correction_qs.filter(employee__branch=branch)

    leave_approvals        = leave_qs.count()
    expense_claims         = expense_qs.count()
    onboarding_reviews     = onboarding_qs.count()
    candidate_reviews      = candidate_qs.count()
    attendance_corrections = correction_qs.count()

    action_queue = {
        'total_pending':           candidate_reviews + leave_approvals + attendance_corrections + expense_claims + onboarding_reviews,
        'candidate_reviews':       candidate_reviews,
        'leave_approvals':         leave_approvals,
        'attendance_corrections':  attendance_corrections,
        'expense_claims':          expense_claims,
        'onboarding_reviews':      onboarding_reviews,
        'separation_requests':     0,
    }
    pending_actions = leave_approvals + expense_claims + onboarding_reviews

    # Refresh the cache with the freshly computed data so the next HTTP GET
    # also returns accurate counts (for users whose WS connection is down).
    cache.set(f'dashboard:hr:action_queue:{branch or "all"}', action_queue, _TTL_ACTION_QUEUE)

    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        from core.notification_groups import notification_group_name
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                notification_group_name(approving_user_id),
                {
                    'type':            'leave.update',
                    'action_queue':    action_queue,
                    'pending_actions': pending_actions,
                },
            )
    except Exception:
        logger.exception('WebSocket push failed for leave_update (user %s)', approving_user_id)


# ─── HR Recruitment Funnel ────────────────────────────────────────────────────

class HRRecruitmentFunnelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        cached = cache.get('dashboard:hr:recruitment:funnel')
        if cached is not None:
            return success('Recruitment funnel retrieved.', data=cached)

        from apps.recruitment.models import Candidate

        data = {
            'interviews_scheduled': Candidate.objects.filter(status=Candidate.STATUS_INTERVIEW_SCHEDULED).count(),
            'interviewed':          Candidate.objects.filter(status=Candidate.STATUS_INTERVIEW_DONE).count(),
            'selected':             Candidate.objects.filter(status=Candidate.STATUS_SELECTED).count(),
            'details_submitted':    Candidate.objects.filter(details_filled=True).count(),
            'onboarded':            Candidate.objects.filter(status=Candidate.STATUS_CONVERTED).count(),
        }
        cache.set('dashboard:hr:recruitment:funnel', data, _TTL_FUNNEL)
        return success('Recruitment funnel retrieved.', data=data)


# ─── HR Attendance Summary ────────────────────────────────────────────────────

class HRAttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        today = timezone.localdate()
        cache_key = f'dashboard:hr:attendance_summary:{today.isoformat()}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success('Attendance summary retrieved.', data=cached)

        from apps.attendance.models import AttendanceRecord

        counts = dict(
            AttendanceRecord.objects
            .filter(date=today)
            .values('status')
            .annotate(n=Count('id'))
            .values_list('status', 'n')
        )

        data = {
            'present':    counts.get(AttendanceRecord.STATUS_PRESENT, 0) +
                          counts.get(AttendanceRecord.STATUS_INCOMPLETE, 0),
            'absent':     counts.get(AttendanceRecord.STATUS_ABSENT, 0),
            'late':       counts.get(AttendanceRecord.STATUS_LATE, 0),
            'leave':      counts.get(AttendanceRecord.STATUS_ON_LEAVE, 0),
            'weekly_off': counts.get(AttendanceRecord.STATUS_WEEKLY_OFF, 0),
            'holiday':    counts.get(AttendanceRecord.STATUS_HOLIDAY, 0),
        }
        cache.set(cache_key, data, _TTL_ATTENDANCE)
        return success('Attendance summary retrieved.', data=data)


# ─── Shared Announcement (all authenticated users) ───────────────────────────

class SharedAnnouncementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.announcements.models import Announcement

        ann = Announcement.objects.select_related('posted_by').first()
        if ann is None:
            return success('No announcements found.', data=None)

        return success('Latest announcement retrieved.', data={
            'id':         ann.id,
            'title':      ann.title,
            'body':       ann.body,
            'category':   ann.category,
            'visibility': ann.visibility,
            'is_pinned':  ann.is_pinned,
            'posted_by':  ann.posted_by.full_name if ann.posted_by else None,
            'created_at': ann.created_at.isoformat(),
        })


# ─── Employee KPIs ────────────────────────────────────────────────────────────

class EmployeeKPIView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        from apps.accounts.models import EmployeeProfile, EmployeeDocument
        from apps.attendance.models import AttendanceCorrection
        from apps.attendance.services_attendance import AttendanceDashboardService
        from apps.hrms.models import Expense

        employee = request.user
        today    = timezone.localdate()

        # Monthly summary — cached per employee (5 min)
        cache_key = f'dashboard:employee:kpis:{employee.id}'
        summary   = cache.get(cache_key)
        if summary is None:
            summary = AttendanceDashboardService.get_monthly_summary(employee, today.year, today.month)
            cache.set(cache_key, summary, 5 * 60)

        # Real-time counts — never cached
        pending_corrections    = AttendanceCorrection.objects.filter(
            employee=employee, status=AttendanceCorrection.STATUS_PENDING
        ).count()
        pending_expense_claims = Expense.objects.filter(employee=employee, status='pending').count()

        # Profile completeness
        profile = EmployeeProfile.objects.filter(user=employee).first()
        if profile is None or not all([
            profile.date_of_birth, profile.gender, profile.current_address,
            profile.account_number, profile.ifsc_code,
            profile.emergency_name, profile.emergency_phone,
        ]):
            profile_incomplete = 1
        else:
            profile_incomplete = 0

        # Missing required documents
        required_docs = {'pan_card', 'aadhaar_card'}
        uploaded_docs = set(
            EmployeeDocument.objects.filter(user=employee).values_list('document_type', flat=True)
        )
        pending_documents    = len(required_docs - uploaded_docs)
        pending_action_items = profile_incomplete + pending_corrections

        # Today's attendance
        today_attendance, is_clocked_in = _todays_attendance(employee, today)

        return success('Employee dashboard KPIs fetched successfully.', data={
            'days_present':           summary.get('days_present', 0),
            'working_days':           summary.get('working_days', 0),
            'absent_days':            summary.get('days_absent', 0),
            'pending_action_items':   pending_action_items,
            'pending_expense_claims': pending_expense_claims,
            'pending_documents':      pending_documents,
            'clocked_in':             is_clocked_in,
            'today_attendance':       today_attendance,
        })


# ─── Employee Leave Balances ──────────────────────────────────────────────────

class EmployeeLeaveBalanceView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        from apps.hrms.models import LeaveBalance, LeaveRequest, REQ_APPROVED

        employee = request.user
        try:
            year = int(request.query_params.get('year', timezone.localdate().year))
        except (ValueError, TypeError):
            year = timezone.localdate().year

        cache_key = f'dashboard:employee:leave_balance:{employee.id}:{year}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return success('Leave balances retrieved.', data=cached)

        balances  = LeaveBalance.objects.filter(employee=employee, year=year).order_by('leave_type')
        lop_total = (
            LeaveRequest.objects
            .filter(employee=employee, status=REQ_APPROVED, start_date__year=year, lop_days__gt=0)
            .aggregate(total=Sum('lop_days'))['total'] or 0
        )

        result = {
            'year': year,
            'balances': [
                {
                    'leave_type':      b.leave_type,
                    'total_days':      float(b.total_days),
                    'used_days':       float(b.used_days),
                    'remaining':       float(b.available_days),
                    'carried_forward': float(b.carried_forward),
                }
                for b in balances
            ],
            'lop_days': float(lop_total),
        }
        cache.set(cache_key, result, 10 * 60)
        return success('Leave balances retrieved.', data=result)


# ─── Employee Attendance Summary ──────────────────────────────────────────────

class EmployeeAttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        from apps.attendance.services_attendance import AttendanceDashboardService

        today    = timezone.localdate()
        employee = request.user
        try:
            year  = int(request.query_params.get('year',  today.year))
            month = int(request.query_params.get('month', today.month))
        except (ValueError, TypeError):
            year, month = today.year, today.month

        stats   = AttendanceDashboardService.get_stats(employee, year, month)
        summary = AttendanceDashboardService.get_monthly_summary(employee, year, month)

        return success('Attendance summary retrieved.', data={
            'year':                  year,
            'month':                 month,
            'present_days':          stats.get('days_present', 0),
            'absent_days':           summary.get('days_absent', 0),
            'late_marks':            stats.get('late_arrivals', 0),
            'lop_pending':           stats.get('lop_pending', 0),
            'half_days':             summary.get('half_days', 0),
            'leave_days':            summary.get('leave_days', 0),
            'working_days':          summary.get('working_days', 0),
            'avg_hours_per_day':     stats.get('avg_hours_per_day', 0),
            'attendance_percentage': stats.get('attendance_percentage', 0),
            'ot_hours':              summary.get('ot_hours', '0h'),
        })


# ─── Employee Attendance Status (today) ──────────────────────────────────────

class EmployeeAttendanceStatusView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        today    = timezone.localdate()
        employee = request.user
        today_attendance, is_clocked_in = _todays_attendance(employee, today)

        if today_attendance:
            clock_in_time   = today_attendance['first_punch_in'][:5] if today_attendance['first_punch_in'] else None
            clock_out_time  = today_attendance['last_punch_out'][:5] if today_attendance['last_punch_out'] else None
            working_minutes = today_attendance['total_working_minutes'] or 0
        else:
            clock_in_time, clock_out_time, working_minutes = None, None, 0

        hours, minutes = divmod(working_minutes, 60)

        return success('Attendance status retrieved.', data={
            'clocked_in':     is_clocked_in,
            'clock_in_time':  clock_in_time,
            'clock_out_time': clock_out_time,
            'working_hours':  f'{hours:02d}:{minutes:02d}',
            'can_clock_in':   not is_clocked_in,
            'can_clock_out':  is_clocked_in,
        })
