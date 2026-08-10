import hashlib
import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import ExtractDay, ExtractMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success
from apps.dashboard.views.people import _serialize_birthday

logger = logging.getLogger(__name__)
_DENIED = 'You do not have permission to perform this action.'

_TTL_BIRTHDAYS = 6 * 3600   # 6 h — team birthday data is stable


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    # settings.edit is this codebase's universal "sees/does everything"
    # signal — checking it here (permission-based) instead of a hardcoded
    # role name means any role actually granted settings.edit gets the same
    # bypass, and revoking it from system_admin would actually revoke it.
    return user.role.role_permissions.filter(
        permission__codename__in={codename, 'settings.edit'}
    ).exists()



# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_manager_or_lead(user) -> bool:
    if not user or not user.role:
        return False
    # can_manage_team is the authoritative flag — set per-role, no role-name strings.
    if user.role.can_manage_team:
        return True
    # Admin/HR have employees.view — they also get manager dashboard access.
    if _has_perm(user, 'employees.view'):
        return True
    # Fallback: any user who has direct reports is effectively a manager.
    return user.direct_reports.filter(is_active=True).exists()


def _greeting() -> str:
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good morning'
    if hour < 17:
        return 'Good afternoon'
    return 'Good evening'


def _team_cache_suffix(manager_id) -> str:
    """Stable 12-char suffix scoped to the manager. Team composition changes
    are tolerated within the birthday TTL window (6 h)."""
    return hashlib.md5(str(manager_id).encode()).hexdigest()[:12]


def _activity_label(action: str) -> str:
    _LABELS = {
        'login':                        'Logged in',
        'logout':                       'Logged out',
        'leave_apply':                  'Applied for leave',
        'leave_approved':               'Leave approved',
        'leave_rejected':               'Leave rejected',
        'leave_cancelled':              'Cancelled leave',
        'expense_submitted':            'Submitted an expense',
        'expense_approved':             'Expense approved',
        'attendance_correction_submit': 'Submitted attendance correction',
        'clock_in':                     'Clocked in',
        'clock_out':                    'Clocked out',
    }
    return _LABELS.get(action, action.replace('_', ' ').title())


# ─── Manager Dashboard ────────────────────────────────────────────────────────

class ManagerDashboardView(APIView):
    """
    GET /api/dashboard/manager/

    Single endpoint — returns all manager dashboard widgets in one response.
    Scoped strictly to the requesting user's active direct reports.

    Performance notes:
    - direct_report IDs fetched once with VALUES_LIST, reused across every widget
    - all list queries use .only() / .values() — no full ORM object hydration
    - birthday data cached per-manager for 6 h
    - attendance counts use a single GROUP-BY aggregation, not per-employee queries
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        manager = request.user

        if not _is_manager_or_lead(manager):
            return error(_DENIED, http_status=403)

        from apps.accounts.models import AuditLog, EmployeeProfile, User
        from apps.attendance.models import AttendanceCorrection, AttendanceRecord
        from apps.hrms.models import (
            Expense, LeaveRequest,
            REQ_APPROVED, REQ_PENDING, REQ_L2_PENDING,
        )

        today = timezone.localdate()

        # ── 0. Team IDs — fetched once, passed to every widget ─────────────────
        team_ids = list(
            manager.direct_reports
            .filter(is_active=True)
            .values_list('id', flat=True)
        )
        team_size = len(team_ids)

        # ── 1. Team Overview ──────────────────────────────────────────────────
        team_overview = _build_team_overview(
            manager, team_ids, team_size, today,
            AttendanceRecord, LeaveRequest,
            REQ_PENDING, REQ_L2_PENDING,
        )

        # ── 2. Quick Actions ──────────────────────────────────────────────────
        quick_actions = _build_quick_actions(
            manager, team_overview['pending_approvals']
        )

        # ── 3. Pending Approvals ──────────────────────────────────────────────
        pending_approvals = _build_pending_approvals(
            manager, team_ids,
            LeaveRequest, Expense, AttendanceCorrection,
            REQ_PENDING, REQ_L2_PENDING,
        )

        # ── 4 & 5. Birthdays ─────────────────────────────────────────────────
        todays_birthdays, upcoming_birthdays = _build_birthdays(
            manager.id, team_ids, today, EmployeeProfile
        )

        # ── 6. Recent Team Activity ───────────────────────────────────────────
        recent_team_activity = _build_recent_activity(team_ids, AuditLog)

        # ── 7. Team Attendance Today ──────────────────────────────────────────
        team_attendance = _build_team_attendance(
            team_ids, team_size, today, AttendanceRecord, User
        )

        # ── 8. Upcoming Leaves ────────────────────────────────────────────────
        upcoming_leaves = _build_upcoming_leaves(
            team_ids, today, LeaveRequest,
            REQ_APPROVED, REQ_PENDING, REQ_L2_PENDING,
        )

        return success('Manager dashboard retrieved.', data={
            'team_overview':        team_overview,
            'quick_actions':        quick_actions,
            'pending_approvals':    pending_approvals,
            'todays_birthdays':     todays_birthdays,
            'upcoming_birthdays':   upcoming_birthdays,
            'recent_team_activity': recent_team_activity,
            'team_attendance':      team_attendance,
            'upcoming_leaves':      upcoming_leaves,
        })


# ─── Widget builders (module-level functions for testability) ─────────────────

def _build_team_overview(manager, team_ids, team_size, today,
                         AttendanceRecord, LeaveRequest,
                         REQ_PENDING, REQ_L2_PENDING):
    on_leave_today = 0
    present_count  = 0
    attendance_pct = 0.0

    if team_ids:
        status_counts = dict(
            AttendanceRecord.objects
            .filter(employee_id__in=team_ids, date=today)
            .values('status')
            .annotate(n=Count('id'))
            .values_list('status', 'n')
        )
        on_leave_today = status_counts.get(AttendanceRecord.STATUS_ON_LEAVE, 0)
        present_count  = (
            status_counts.get(AttendanceRecord.STATUS_PRESENT,    0) +
            status_counts.get(AttendanceRecord.STATUS_LATE,       0) +
            status_counts.get(AttendanceRecord.STATUS_HALF_DAY,   0) +
            status_counts.get(AttendanceRecord.STATUS_INCOMPLETE, 0)
        )
        if team_size > 0:
            attendance_pct = round(present_count / team_size * 100, 1)

    # Pending approvals where this manager is L1 or L2 approver
    pending_approvals = LeaveRequest.objects.filter(
        Q(l1_approver=manager, status=REQ_PENDING) |
        Q(l2_approver=manager, status=REQ_L2_PENDING)
    ).count()

    return {
        'greeting':                   _greeting(),
        'manager_name':               manager.full_name or manager.email,
        'current_date':               today.isoformat(),
        'team_size':                  team_size,
        'pending_approvals':          pending_approvals,
        'employees_on_leave_today':   on_leave_today,
        'team_attendance_percentage': attendance_pct,
    }


def _build_quick_actions(manager, pending_count):
    role = manager.role.name if manager.role else ''
    actions = [
        {
            'id':    'apply_leave',
            'label': 'Apply Leave',
            'url':   '/dashboard/leave/apply',
            'count': None,
        },
        {
            'id':    'my_requests',
            'label': 'My Requests',
            'url':   '/dashboard/requests',
            'count': None,
        },
        {
            'id':    'team_members',
            'label': 'Team Members',
            'url':   '/dashboard/team',
            'count': None,
        },
        {
            'id':    'review_approvals',
            'label': 'Review Approvals',
            'url':   '/dashboard/approvals',
            'count': pending_count if pending_count > 0 else None,
        },
        {
            'id':    'my_payslip',
            'label': 'My Payslip',
            'url':   '/dashboard/payroll/payslips',
            'count': None,
        },
    ]
    if _has_perm(manager, 'recruitment.view'):
        actions.append({
            'id':    'interviews',
            'label': 'Interviews',
            'url':   '/dashboard/interviews',
            'count': None,
        })
    return actions


def _build_pending_approvals(manager, team_ids,
                              LeaveRequest, Expense, AttendanceCorrection,
                              REQ_PENDING, REQ_L2_PENDING):
    results = []

    # Leave: manager is explicit L1 or L2 approver
    leave_qs = (
        LeaveRequest.objects
        .filter(
            Q(l1_approver=manager, status=REQ_PENDING) |
            Q(l2_approver=manager, status=REQ_L2_PENDING)
        )
        .select_related('employee')
        .only(
            'id', 'status', 'leave_type', 'start_date', 'end_date',
            'total_days', 'created_at',
            'employee__full_name', 'employee__employee_id',
        )
        .order_by('created_at')[:20]
    )
    for lr in leave_qs:
        results.append({
            'id':            str(lr.id),
            'approval_type': 'leave',
            'employee_name': lr.employee.full_name,
            'employee_id':   lr.employee.employee_id or '',
            'summary':       f'{lr.leave_type.replace("_", " ").title()} — {lr.total_days} day(s)',
            'date_from':     str(lr.start_date),
            'date_to':       str(lr.end_date),
            'applied_on':    str(lr.created_at.date()),
            'status':        lr.status,
        })

    if team_ids:
        # Expenses submitted by direct reports
        expense_qs = (
            Expense.objects
            .filter(employee_id__in=team_ids, status='pending')
            .select_related('employee')
            .only(
                'id', 'title', 'amount', 'category', 'expense_date', 'created_at',
                'employee__full_name', 'employee__employee_id',
            )
            .order_by('created_at')[:20]
        )
        for ex in expense_qs:
            results.append({
                'id':            str(ex.id),
                'approval_type': 'expense',
                'employee_name': ex.employee.full_name,
                'employee_id':   ex.employee.employee_id or '',
                'summary':       f'{ex.title} — ₹{ex.amount}',
                'date_from':     str(ex.expense_date),
                'date_to':       str(ex.expense_date),
                'applied_on':    str(ex.created_at.date()),
                'status':        ex.status,
            })

        # Attendance corrections from direct reports
        correction_qs = (
            AttendanceCorrection.objects
            .filter(
                employee_id__in=team_ids,
                status=AttendanceCorrection.STATUS_PENDING,
            )
            .select_related('employee')
            .only(
                'id', 'date', 'punch_type', 'created_at',
                'employee__full_name', 'employee__employee_id',
            )
            .order_by('created_at')[:20]
        )
        for ac in correction_qs:
            results.append({
                'id':            str(ac.id),
                'approval_type': 'attendance_correction',
                'employee_name': ac.employee.full_name,
                'employee_id':   ac.employee.employee_id or '',
                'summary':       f'Attendance Correction — {ac.punch_type.upper()}',
                'date_from':     str(ac.date),
                'date_to':       str(ac.date),
                'applied_on':    str(ac.created_at.date()),
                'status':        ac.status,
            })

    results.sort(key=lambda x: x['applied_on'])
    return results


def _build_birthdays(manager_id, team_ids, today, EmployeeProfile):
    if not team_ids:
        return [], []

    suffix             = _team_cache_suffix(manager_id)
    cache_key_today    = f'dashboard:manager:birthdays:today:{suffix}'
    cache_key_upcoming = f'dashboard:manager:birthdays:upcoming:{suffix}'

    today_data    = cache.get(cache_key_today)
    upcoming_data = cache.get(cache_key_upcoming)

    if today_data is not None and upcoming_data is not None:
        return today_data, upcoming_data

    base_qs = (
        EmployeeProfile.objects
        .select_related('user')
        .filter(
            user_id__in=team_ids,
            date_of_birth__isnull=False,
            user__is_active=True,
        )
        .annotate(
            birth_month=ExtractMonth('date_of_birth'),
            birth_day=ExtractDay('date_of_birth'),
        )
    )

    if today_data is None:
        today_profiles = base_qs.filter(
            birth_month=today.month, birth_day=today.day
        )
        today_data = [_serialize_birthday(p, 0) for p in today_profiles]
        cache.set(cache_key_today, today_data, _TTL_BIRTHDAYS)

    if upcoming_data is None:
        offset_map, upcoming_q = {}, Q()
        for offset in range(1, 31):
            future = today + timedelta(days=offset)
            upcoming_q |= Q(birth_month=future.month, birth_day=future.day)
            offset_map[(future.month, future.day)] = offset
        upcoming_profiles = base_qs.filter(upcoming_q)
        upcoming_data = sorted(
            [
                _serialize_birthday(p, offset_map[(p.birth_month, p.birth_day)])
                for p in upcoming_profiles
            ],
            key=lambda x: x['days_until'],
        )
        cache.set(cache_key_upcoming, upcoming_data, _TTL_BIRTHDAYS)

    return today_data, upcoming_data


def _build_recent_activity(team_ids, AuditLog):
    if not team_ids:
        return []

    logs = (
        AuditLog.objects
        .filter(user_id__in=team_ids)
        .select_related('user')
        .only(
            'id', 'action', 'module', 'created_at',
            'user__full_name', 'user__employee_id',
        )
        .order_by('-created_at')[:10]
    )
    return [
        {
            'employee_name': log.user.full_name if log.user else '',
            'employee_id':   log.user.employee_id if log.user else '',
            'action':        log.action,
            'module':        log.module,
            'description':   _activity_label(log.action),
            'created_at':    log.created_at.isoformat(),
        }
        for log in logs
    ]


def _build_team_attendance(team_ids, team_size, today, AttendanceRecord, User):
    if not team_ids:
        return []

    records = (
        AttendanceRecord.objects
        .filter(employee_id__in=team_ids, date=today)
        .select_related('employee')
        .only(
            'status', 'first_punch_in', 'last_punch_out',
            'employee__id', 'employee__full_name',
            'employee__employee_id', 'employee__designation',
        )
    )

    result       = []
    recorded_ids = set()

    for rec in records:
        recorded_ids.add(rec.employee_id)
        result.append({
            'employee_id':   rec.employee.employee_id or '',
            'employee_name': rec.employee.full_name,
            'designation':   rec.employee.designation or '',
            'clock_in':      str(rec.first_punch_in)[:5]  if rec.first_punch_in  else None,
            'clock_out':     str(rec.last_punch_out)[:5]  if rec.last_punch_out  else None,
            'status':        rec.status,
        })

    # Team members without a record today — mark absent
    no_record_ids = [tid for tid in team_ids if tid not in recorded_ids]
    if no_record_ids:
        for u in (
            User.objects
            .filter(id__in=no_record_ids, is_active=True)
            .only('id', 'full_name', 'employee_id', 'designation')
        ):
            result.append({
                'employee_id':   u.employee_id or '',
                'employee_name': u.full_name,
                'designation':   u.designation or '',
                'clock_in':      None,
                'clock_out':     None,
                'status':        AttendanceRecord.STATUS_ABSENT,
            })

    # Present first, then alphabetical
    result.sort(key=lambda x: (
        x['status'] not in (
            AttendanceRecord.STATUS_PRESENT,
            AttendanceRecord.STATUS_LATE,
            AttendanceRecord.STATUS_INCOMPLETE,
        ),
        x['employee_name'],
    ))
    return result


def _build_upcoming_leaves(team_ids, today, LeaveRequest,
                            REQ_APPROVED, REQ_PENDING, REQ_L2_PENDING):
    if not team_ids:
        return []

    qs = (
        LeaveRequest.objects
        .filter(
            employee_id__in=team_ids,
            start_date__gte=today,
            status__in=[REQ_APPROVED, REQ_PENDING, REQ_L2_PENDING],
        )
        .select_related('employee')
        .only(
            'id', 'leave_type', 'start_date', 'end_date',
            'total_days', 'status',
            'employee__full_name', 'employee__employee_id',
        )
        .order_by('start_date')[:20]
    )
    return [
        {
            'id':            str(lr.id),
            'employee_id':   lr.employee.employee_id or '',
            'employee_name': lr.employee.full_name,
            'leave_type':    lr.leave_type.replace('_', ' ').title(),
            'date_from':     str(lr.start_date),
            'date_to':       str(lr.end_date),
            'total_days':    float(lr.total_days),
            'status':        lr.status,
        }
        for lr in qs
    ]
