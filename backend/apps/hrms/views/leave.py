import base64
import csv
import io
import logging
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_REJECTED,
    CARRY_FORWARD_UNLIMITED, CARRY_FORWARD_MANUAL,
    DURATION_FULL,
    LEAVE_LWP, LEAVE_TYPE_CHOICES,
    REQ_APPROVED, REQ_CANCELLED, REQ_L2_PENDING, REQ_PENDING, REQ_REJECTED,
    CarryForwardLog, LeaveBalance, LeavePolicy, LeaveRequest,
)
from ..serializers import (
    CarryForwardInputSerializer,
    CarryForwardLogSerializer,
    LeaveBalanceSerializer,
    LeavePolicyCreateSerializer,
    LeavePolicySerializer,
    LeavePolicyUpdateSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
)

logger = logging.getLogger(__name__)


def _current_year() -> int:
    from apps.accounts.utils import get_company_financial_year_config, get_fy_start_year
    config = get_company_financial_year_config()
    return get_fy_start_year(date.today(), config.get('financial_year_start_month', 'April'))


def _resolve_approver(role, employee) -> 'accounts.User | None':
    """Resolve a Role FK to the actual User approver for a given employee."""
    if role is None:
        return None
    if role.can_manage_team:
        return getattr(employee, 'reporting_manager', None)
    return getattr(employee, 'hr', None)


def _resolve_approval_chain(employee):
    """
    Return (l1_approver, l2_approver) for a leave request.
    Checks EmployeeApprovalOverride first, falls back to ApprovalWorkflowRule.
    """
    from apps.accounts.models import EmployeeApprovalOverride
    override = EmployeeApprovalOverride.objects.filter(
        employee=employee, workflow_type='leave'
    ).first()

    if override:
        return override.l1_override, override.l2_override

    from core.cache_service import ApprovalWorkflowCacheService
    rule = ApprovalWorkflowCacheService.get_rule('leave')
    if not rule:
        return None, None

    l1 = _resolve_approver(rule.l1_approver_role, employee) if rule.l1_approver_role else None
    l2 = _resolve_approver(rule.l2_approver_role, employee) if rule.l2_approver_role else None
    return l1, l2


def _user_branch(user) -> str:
    return (getattr(user, 'branch', '') or '').strip()


def _is_branch_admin(user) -> bool:
    return bool(user.role and getattr(user.role, 'can_manage_branch', False))


def _branch_admin_covers(user, employee) -> bool:
    """True when user is a branch_admin whose branch matches the employee's."""
    branch = _user_branch(user)
    if not branch:
        return True
    return (getattr(employee, 'branch', '') or '').strip() == branch


def _can_hr_access_request(hr_user, leave_request) -> bool:
    """
    True when hr_user is the request's specifically assigned HR (l2_approver), or —
    for requests with no HR assigned at all — hr_user shares the employee's branch
    (or has no branch restriction). Keeps view/detail access in sync with
    _approval_scope_filter and _can_approve_at_stage: a branch can have several HR
    users, but each should only reach requests for their own assigned employees.

    branch_admin bypasses the assignment check entirely — unconditional access
    to every request in their own branch, same as they get for employees/
    expenses/documents.
    """
    if _is_branch_admin(hr_user):
        return _branch_admin_covers(hr_user, leave_request.employee)
    if leave_request.l2_approver_id:
        return leave_request.l2_approver_id == hr_user.id
    branch = _user_branch(hr_user)
    if not branch:
        return True
    return (getattr(leave_request.employee, 'branch', '') or '').strip() == branch


def _can_approve_at_stage(user, leave_request, stage: str) -> bool:
    """
    Return True if `user` is authorised to act at the given approval stage.

    - settings.edit (admin): always authorised — override for any stuck request.
    - can_manage_branch (Branch Admin): always authorised for any request whose
      employee is in their own branch — unconditional, unlike HR/manager below.
    - l1 stage: must be the designated l1_approver on the request — L1 is a
                per-manager assignment, not a shared queue.
    - l2 stage: must be the designated l2_approver (the employee's specifically
                assigned HR — see User.hr), or any leave.approve holder in the
                same branch ONLY when the employee has no HR assigned at all.

    Enforcing the designated approver prevents any user with leave.approve or
    can_manage_team from jumping the queue or acting on employees not assigned
    to them — a branch can have several HR users, and each must stay confined
    to their own assigned employees. _approval_scope_filter and
    _can_hr_access_request mirror this same assigned-first, branch-fallback
    logic so the approval queue a user sees always matches what they can act on.
    """
    if _has_perm(user, 'settings.edit'):
        return True
    if _is_branch_admin(user):
        return _branch_admin_covers(user, leave_request.employee)

    if stage == 'l1':
        if leave_request.l1_approver_id:
            return leave_request.l1_approver_id == user.id
        return False

    if stage == 'l2':
        if leave_request.l2_approver_id:
            return leave_request.l2_approver_id == user.id
        # No designated L2 — any leave.approve holder with branch access may step in.
        return _has_perm(user, 'leave.approve') and _can_hr_access_request(user, leave_request)

    return False


def _approval_scope_filter(user) -> 'Q':
    """
    Scope filter for the approval queue — enforces both permission and status visibility.
    can_manage_team  → REQ_PENDING requests where they are the designated L1 approver.
    leave.approve    → REQ_L2_PENDING requests where they are the designated l2_approver
                       (an employee's specifically assigned HR — see User.hr), plus —
                       for non-manager approvers only — orphaned requests (no HR
                       assigned to the employee) in their branch as a fallback so
                       nothing is left unactionable. A branch can have multiple HR
                       users; each must only see the employees actually assigned to
                       them, matching _can_approve_at_stage's action gate.
    settings.edit    → all statuses, all employees except own (admin override).

    can_manage_team and leave.approve are NOT mutually exclusive: every manager
    role also holds leave.approve (required to pass the approve-action's
    permission gate at L1). Checking leave.approve first would always route a
    manager into the L2/HR branch — which only matches REQ_L2_PENDING requests —
    silently hiding their entire L1 queue. Both scopes are combined via OR
    instead of short-circuited, so a manager keeps their L1 queue even though
    they also hold leave.approve; the branch-wide orphan fallback is withheld
    from managers so leave.approve alone doesn't turn them into a shadow
    branch-wide HR queue.

    can_manage_branch (Branch Admin) sees every pending/l2_pending request in
    their own branch unconditionally, regardless of l1/l2 assignment.
    """
    if _has_perm(user, 'settings.edit'):
        return ~Q(employee=user)

    if _is_branch_admin(user):
        branch = _user_branch(user)
        branch_q = Q(employee__branch__iexact=branch) if branch else Q()
        return branch_q & Q(status__in=[REQ_PENDING, REQ_L2_PENDING]) & ~Q(employee=user)

    is_manager = bool(user.role and user.role.can_manage_team)
    scope = Q(l1_approver=user, status=REQ_PENDING) if is_manager else None

    if _has_perm(user, 'leave.approve'):
        l2_scope = Q(l2_approver=user, status=REQ_L2_PENDING)
        if not is_manager:
            branch = _user_branch(user)
            orphaned = Q(l2_approver__isnull=True, status=REQ_L2_PENDING)
            if branch:
                orphaned &= Q(employee__branch__iexact=branch)
            l2_scope |= orphaned
        scope = (scope | l2_scope) if scope is not None else l2_scope

    if scope is not None:
        return scope & ~Q(employee=user)
    return Q(employee=user)


def _calendar_scope_filter(user) -> 'Q':
    """
    Scope filter for the team calendar.
    settings.edit    → all (admin sees everything)
    can_manage_team  → team + own
    leave.approve    → branch-scoped or org-wide if no branch
    employee         → all approved (to see who's out for absence planning)
    """
    if _has_perm(user, 'settings.edit'):
        return Q()
    # Same precedence as _approval_scope_filter above: can_manage_team must be
    # checked before leave.approve, since manager__team_lead holds both.
    if user.role and user.role.can_manage_team:
        return Q(employee__reporting_manager=user) | Q(employee=user)
    if _has_perm(user, 'leave.approve'):
        return Q(employee__branch__iexact=user.branch) if user.branch else Q()
    return Q()  # employee: see all approved leaves to plan around absences


def _allocate_leaves_for_employee(employee, joining_date=None) -> int:
    """
    Auto-allocate leave balances for a new employee based on active LeavePolicy records.
    Called on candidate→employee conversion and direct employee creation.

    Pro-rata rule: joining month counts as a full month.
    e.g. joining July → 6 months remaining → 6/12 × annual_days.
    Skips policies with minimum_service_period > 0 (new joiner has 0 months service).
    Idempotent: get_or_create prevents duplicates on re-runs.

    Returns number of LeaveBalance records created.
    """
    from datetime import datetime as _dt
    today = date.today()
    if joining_date is None:
        joining_date = today
    elif isinstance(joining_date, str):
        joining_date = _dt.strptime(joining_date, '%Y-%m-%d').date() if joining_date else today

    year             = joining_date.year
    remaining_months = 13 - joining_date.month  # Jan→12, Jul→6, Dec→1

    try:
        from apps.accounts.models import EmployeeProfile
        profile    = EmployeeProfile.objects.filter(user=employee).first()
        emp_gender = (profile.gender or 'all') if profile else 'all'
    except Exception:
        emp_gender = 'all'

    created_count = 0

    for policy in LeavePolicy.objects.filter(is_active=True):
        if policy.minimum_service_period > 0:
            continue

        if policy.applicable_branches and (
            not employee.branch or employee.branch not in policy.applicable_branches
        ):
            continue

        if policy.applicable_departments and (
            not employee.department or employee.department not in policy.applicable_departments
        ):
            continue

        if policy.applicable_designations and (
            not employee.designation or employee.designation not in policy.applicable_designations
        ):
            continue

        if policy.applicable_gender not in ('', 'all') and emp_gender != policy.applicable_gender:
            continue

        # Round to nearest 0.5 — standard HRMS display precision
        raw     = float(policy.annual_days) * remaining_months / 12
        prorata = Decimal(str(round(raw * 2) / 2))

        _, created = LeaveBalance.objects.get_or_create(
            employee=employee,
            leave_type=policy.leave_type,
            year=year,
            defaults={'total_days': prorata, 'carried_forward': Decimal('0')},
        )
        if created:
            created_count += 1

    if created_count:
        logger.info(
            'Auto-allocated %d leave balance(s) for %s (joining %s, year %d)',
            created_count, employee.email, joining_date, year,
        )
    return created_count


def _get_holiday_dates(start: date, end: date, branch_name: str = '') -> set:
    from core.cache_service import HolidayCacheService
    return HolidayCacheService.get_holiday_dates(start, end, branch_name)


def _get_holidays_with_names(start: date, end: date, branch_name: str = '') -> list:
    from core.cache_service import HolidayCacheService
    return HolidayCacheService.get_holidays_with_names(start, end, branch_name)


def _get_weekoffs_in_range(start: date, end: date, employee=None) -> list:
    """Return [{'date': 'YYYY-MM-DD', 'day': str}] for week-off days in range."""
    from datetime import timedelta
    off_days_by_date = _get_weekly_off_days(employee, start, end)
    result, cur = [], start
    while cur <= end:
        if cur.strftime('%A').lower() in off_days_by_date[cur]:
            result.append({'date': cur.strftime('%Y-%m-%d'), 'day': cur.strftime('%A')})
        cur += timedelta(days=1)
    return result


def _calc_working_days(start: date, end: date, duration: str, policy=None, employee=None) -> float:
    if duration != 'full_day':
        return 0.5
    off_days_by_date = _get_weekly_off_days(employee, start, end)
    count_offs     = getattr(policy, 'count_weekoffs_as_leave', False)
    sandwich       = getattr(policy, 'sandwich_leave_enabled', False)
    count_holidays = getattr(policy, 'count_holidays_as_leave', False)
    branch_name    = (getattr(employee, 'branch', '') or '') if employee else ''
    holiday_dates  = _get_holiday_dates(start, end, branch_name)

    count = 0
    current = start
    from datetime import timedelta
    while current <= end:
        is_off     = current.strftime('%A').lower() in off_days_by_date[current]
        is_holiday = current in holiday_dates

        if is_holiday and not count_holidays:
            pass                              # holiday excluded regardless of sandwich setting
        elif sandwich:
            count += 1                        # sandwich: all remaining days count
        elif is_off and not count_offs:
            pass                              # week-off excluded
        else:
            count += 1
        current += timedelta(days=1)
    return float(count)


def _get_weekly_off_days(employee=None, start: date = None, end: date = None) -> dict:
    """
    Centralized weekly-off resolution for the leave module — per-day, per-
    employee via WeeklyOffCacheService.get_effective_range() (the same
    resolver AttendanceProcessorService/AttendanceDashboardService use), so an
    employee's assigned pattern changing mid-range (e.g. a leave request
    spanning a pattern-change date) resolves correctly for each day rather
    than using one flat org-wide set for the whole range.

    Returns {date: set_of_weekly_off_day_names} for every date in [start, end].
    `start`/`end` default to today when omitted (kept optional so any existing
    caller that only needs "today's" off-days still works unchanged).
    """
    from core.cache_service import WeeklyOffCacheService
    if start is None:
        start = date.today()
    if end is None:
        end = start
    return WeeklyOffCacheService.get_effective_range(employee, start, end)


def _zero_working_days_reason(start: date, end: date, policy=None, employee=None) -> str:
    """Return a user-friendly message explaining why a date range has no working days."""
    from datetime import timedelta
    off_days_by_date = _get_weekly_off_days(employee, start, end)
    count_offs     = getattr(policy, 'count_weekoffs_as_leave', False)
    count_holidays = getattr(policy, 'count_holidays_as_leave', False)
    branch_name    = (getattr(employee, 'branch', '') or '') if employee else ''
    holiday_dates  = _get_holiday_dates(start, end, branch_name)

    holiday_count = weekoff_count = total = 0
    cur = start
    while cur <= end:
        total += 1
        if cur in holiday_dates and not count_holidays:
            holiday_count += 1
        elif cur.strftime('%A').lower() in off_days_by_date[cur] and not count_offs:
            weekoff_count += 1
        cur += timedelta(days=1)

    if start == end:
        if holiday_count:
            return 'The selected date is a public holiday. Please choose a working day.'
        if weekoff_count:
            return f'The selected date falls on a weekly off ({start.strftime("%A")}). Please choose a working day.'

    if holiday_count == total:
        return 'All selected dates are public holidays. Please select at least one working day to apply for leave.'
    if weekoff_count == total:
        return 'All selected dates fall on weekly off days. Please select at least one working day to apply for leave.'
    if holiday_count + weekoff_count == total:
        return (
            'The selected date range contains only holidays and weekly off days. '
            'Please select at least one working day to apply for leave.'
        )
    return 'The selected date range contains no working days. Please select at least one working day to apply for leave.'


def _validate_leave_policy(policy, employee, duration, total_days, start, end, document, today) -> str | None:
    """Validate a leave request against policy rules. Returns error string or None."""
    if duration != 'full_day' and not policy.allow_half_day:
        return 'Half-day leave is not allowed for this leave type.'
    if policy.minimum_leave_duration and total_days < float(policy.minimum_leave_duration):
        return f'Minimum {policy.minimum_leave_duration} day(s) required for this leave type.'
    if policy.maximum_leave_duration and total_days > policy.maximum_leave_duration:
        return f'Maximum {policy.maximum_leave_duration} day(s) allowed for this leave type.'
    if policy.maximum_consecutive_days and total_days > policy.maximum_consecutive_days:
        if not getattr(policy, 'convert_to_lop', False):
            return f'Maximum {policy.maximum_consecutive_days} consecutive day(s) allowed for this leave type.'
        # convert_to_lop is enabled — excess days become LOP; preview shows the warning, POST proceeds
    if policy.minimum_notice_period and (start - today).days < policy.minimum_notice_period:
        return f'This leave type requires {policy.minimum_notice_period} day(s) advance notice.'
    if start < today:
        if not policy.allow_backdated_leave:
            return 'Backdated leave applications are not allowed for this leave type.'
        if policy.maximum_backdated_days and (today - start).days > policy.maximum_backdated_days:
            return f'Backdated leave is limited to {policy.maximum_backdated_days} day(s) in the past.'
    if start > today:
        if not policy.allow_future_leave:
            return 'Future-dated leave applications are not allowed for this leave type.'
        if policy.maximum_future_days and (start - today).days > policy.maximum_future_days:
            return f'Leave can only be applied {policy.maximum_future_days} day(s) in advance.'
    if policy.attachment_required and not document:
        return 'An attachment is required for this leave type.'
    if policy.applicable_branches:
        emp_branch = (getattr(employee, 'branch', '') or '').strip()
        if emp_branch and emp_branch not in policy.applicable_branches:
            return 'You are not eligible for this leave type (branch restriction).'
    if policy.applicable_departments:
        emp_dept = (getattr(employee, 'department', '') or '').strip()
        if emp_dept and emp_dept not in policy.applicable_departments:
            return 'You are not eligible for this leave type (department restriction).'
    if policy.applicable_gender != 'all':
        emp_gender = (getattr(employee, 'gender', '') or '').lower().strip()
        if emp_gender and emp_gender != policy.applicable_gender:
            return 'You are not eligible for this leave type (gender restriction).'
    if policy.minimum_service_period:
        joining = getattr(employee, 'date_of_joining', None) or getattr(employee, 'joining_date', None)
        if joining:
            months = (today.year - joining.year) * 12 + (today.month - joining.month)
            if months < policy.minimum_service_period:
                return f'This leave type requires {policy.minimum_service_period} month(s) of service.'
    return None


def _deduct_balance(employee, leave_type: str, days: float, year: int) -> None:
    if leave_type == LEAVE_LWP:
        return
    LeaveBalance.objects.filter(
        employee=employee, leave_type=leave_type, year=year
    ).update(used_days=F('used_days') + days)


# ─── Leave Policy ──────────────────────────────────────────────────────────────

class LeavePolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def _ensure_policies(self):
        existing = set(LeavePolicy.objects.values_list('leave_type', flat=True))
        defaults = {
            'casual':    {'annual_days': 12, 'can_carry_forward': False, 'max_carry_forward_days': 0, 'policy_note': 'Max 3 consecutive days. Apply 1 day in advance.'},
            'earned':    {'annual_days': 15, 'can_carry_forward': True,  'max_carry_forward_days': 30, 'policy_note': 'Min 3 days notice. Carry-forward up to 30 days.'},
            'sick':      {'annual_days': 12, 'can_carry_forward': False, 'max_carry_forward_days': 0, 'policy_note': 'Medical certificate required for 3+ consecutive days.'},
            'lwp':       {'annual_days': 0,  'can_carry_forward': False, 'max_carry_forward_days': 0, 'policy_note': 'Salary deducted. Requires HR approval. No carry-forward.'},
            'maternity': {'annual_days': 90, 'can_carry_forward': False, 'max_carry_forward_days': 0, 'policy_note': 'Up to 180 days per Maternity Benefit Act. HR approval required.'},
            'paternity': {'annual_days': 5,  'can_carry_forward': False, 'max_carry_forward_days': 0, 'policy_note': 'Within 15 days of child\'s birth. Birth certificate required.'},
        }
        for lt, kwargs in defaults.items():
            if lt not in existing:
                LeavePolicy.objects.create(leave_type=lt, **kwargs)

    def get(self, request):
        self._ensure_policies()
        from core.cache_service import LeavePolicyCacheService
        policies = LeavePolicyCacheService.get_all()
        return success('Leave policies retrieved.', LeavePolicySerializer(policies, many=True).data)

    def put(self, request, leave_type: str):
        if not (_has_perm(request.user, 'settings.edit') or _has_perm(request.user, 'leave.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        policy = LeavePolicy.objects.filter(leave_type=leave_type).first()
        if not policy:
            return error('Leave type not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = LeavePolicyUpdateSerializer(policy, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Policy updated.', LeavePolicySerializer(policy).data)

    def patch(self, request, leave_type: str):
        return self.put(request, leave_type)

    def post(self, request, leave_type: str = None):
        if leave_type:
            return self.put(request, leave_type)
        if not (_has_perm(request.user, 'settings.edit') or _has_perm(request.user, 'leave.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = LeavePolicyCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        data  = serializer.validated_data
        label = data.pop('leave_type_label')
        leave_type_key = label.lower().replace(' ', '_').replace('-', '_')
        policy = LeavePolicy.objects.create(
            leave_type=leave_type_key, leave_type_label=label, **data
        )
        logger.info('Created leave type "%s" by %s', leave_type_key, request.user.email)
        return success('Leave type created.', LeavePolicySerializer(policy).data, http_status=status.HTTP_201_CREATED)

    def delete(self, request, leave_type: str):
        if not (_has_perm(request.user, 'settings.edit') or _has_perm(request.user, 'leave.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        _BUILTIN = {'casual', 'earned', 'sick', 'lwp', 'maternity', 'paternity'}
        if leave_type in _BUILTIN:
            return error('Built-in leave types cannot be deleted.', http_status=status.HTTP_400_BAD_REQUEST)
        policy = LeavePolicy.objects.filter(leave_type=leave_type).first()
        if not policy:
            return error('Leave type not found.', http_status=status.HTTP_404_NOT_FOUND)
        policy.delete()
        logger.info('Deleted leave type "%s" by %s', leave_type, request.user.email)
        return success('Leave type deleted.')


# ─── Leave Balance ─────────────────────────────────────────────────────────────

class LeaveBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get('year', _current_year()))
        except (TypeError, ValueError):
            return error('year must be a valid integer.')
        employee_id = request.query_params.get('employee_id')

        if employee_id and _has_perm(request.user, 'employees.view'):
            from apps.accounts.models import User
            employee = User.objects.filter(employee_id=employee_id).first()
            if not employee:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        else:
            employee = request.user

        balances = LeaveBalance.objects.filter(employee=employee, year=year).order_by('leave_type')
        return success('Balances retrieved.', LeaveBalanceSerializer(balances, many=True).data)

    def post(self, request):
        """Credit annual leave balances for all active employees or a specific employee."""
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        try:
            year = int(request.data.get('year', _current_year()))
        except (TypeError, ValueError):
            return error('year must be a valid integer.')
        from apps.accounts.models import User
        employees = User.objects.filter(is_active=True, onboarding_status='complete').exclude(employee_id='')

        specific_id = request.data.get('employee_id')
        if specific_id:
            employees = employees.filter(employee_id=specific_id)

        policies = {p.leave_type: p for p in LeavePolicy.objects.filter(is_active=True)}
        created_count = 0

        for emp in employees:
            for lt, policy in policies.items():
                if lt == LEAVE_LWP:
                    continue
                balance, created = LeaveBalance.objects.get_or_create(
                    employee=emp, leave_type=lt, year=year,
                    defaults={'total_days': policy.annual_days, 'used_days': 0, 'carried_forward': 0},
                )
                if created:
                    created_count += 1

        logger.info('Credited leave balances for year %d — %d records created.', year, created_count)
        return success(f'Credited {created_count} balance records for {year}.', {'year': year, 'credited': created_count})


def _can_adjust_balance(user, balance) -> bool:
    """
    Block self-adjustment entirely (nobody may inflate their own balance),
    then scope by permission — mirrors _can_approve_at_stage's branch/
    reporting-chain conventions used for leave request approval.
    """
    if balance.employee_id == user.id:
        return False
    if _has_perm(user, 'settings.edit'):
        return True
    # Managers also hold leave.approve (needed for the L1 approve-action gate),
    # so this must be checked before the broader leave.approve branch below —
    # otherwise a manager could adjust any same-branch employee's balance
    # instead of only their own direct reports.
    if user.role and user.role.can_manage_team:
        return balance.employee.reporting_manager_id == user.id
    if _has_perm(user, 'leave.approve'):
        branch = _user_branch(user)
        return not branch or _user_branch(balance.employee) == branch
    return False


class LeaveBalanceAdjustView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_balance(self, balance_id: str):
        try:
            return LeaveBalance.objects.select_related('employee').get(id=balance_id), None
        except LeaveBalance.DoesNotExist:
            return None, error('Balance record not found.', http_status=status.HTTP_404_NOT_FOUND)

    def get(self, request, balance_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        balance, err = self._get_balance(balance_id)
        if err:
            return err
        if not _can_adjust_balance(request.user, balance):
            return error('Balance record not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Balance retrieved.', LeaveBalanceSerializer(balance).data)

    def patch(self, request, balance_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        balance, err = self._get_balance(balance_id)
        if err:
            return err
        if not _can_adjust_balance(request.user, balance):
            return error('Balance record not found.', http_status=status.HTTP_404_NOT_FOUND)

        total = request.data.get('total_days')
        used  = request.data.get('used_days')
        if total is None and used is None:
            return error('Provide at least one of total_days or used_days to adjust.')
        if total is not None:
            try:
                total = Decimal(str(total))
                if total < 0:
                    raise ValueError
            except (TypeError, ValueError, InvalidOperation):
                return error('total_days must be a non-negative number.')
            balance.total_days = total
        if used is not None:
            try:
                used = Decimal(str(used))
                if used < 0:
                    raise ValueError
            except (TypeError, ValueError, InvalidOperation):
                return error('used_days must be a non-negative number.')
            balance.used_days = used
        balance.save(update_fields=['total_days', 'used_days', 'updated_at'])
        logger.info('Leave balance %s adjusted by %s', balance_id, request.user.email)
        return success('Balance adjusted.', LeaveBalanceSerializer(balance).data)

    def put(self, request, balance_id: str):
        return self.patch(request, balance_id)

    def post(self, request, balance_id: str):
        return self.patch(request, balance_id)

    def delete(self, request, balance_id: str):
        return error(
            'Leave balance records cannot be deleted. Adjust total_days or used_days instead.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


def _leave_preview(request):
    """Read-only calculation for GET /api/leave/requests/?action=preview."""
    from datetime import date as date_cls
    params     = request.query_params
    leave_type = params.get('leave_type', '')
    duration   = params.get('duration', 'full_day')
    try:
        start = date_cls.fromisoformat(params['start_date'])
        end   = date_cls.fromisoformat(params['end_date'])
    except (KeyError, ValueError):
        return error('start_date and end_date are required in YYYY-MM-DD format.')
    if end < start:
        return error('end_date must be on or after start_date.')

    from core.cache_service import LeavePolicyCacheService
    policy       = LeavePolicyCacheService.get(leave_type)
    actual_days  = _calc_working_days(start, end, duration, policy, request.user)
    branch_name  = (getattr(request.user, 'branch', '') or '')
    holidays     = _get_holidays_with_names(start, end, branch_name)
    week_offs    = _get_weekoffs_in_range(start, end, request.user)
    calendar_days = (end - start).days + 1

    holidays_out  = [{'date': h['date'].strftime('%d %b'), 'name': h['name']} for h in holidays]
    week_offs_out = [{'date': w['date'], 'day': w['day']} for w in week_offs]

    available      = 0.0
    convert_to_lop = getattr(policy, 'convert_to_lop', False)
    if leave_type and leave_type != LEAVE_LWP:
        bal = LeaveBalance.objects.filter(
            employee=request.user, leave_type=leave_type, year=start.year
        ).first()
        if bal:
            available = float(bal.total_days - bal.used_days)

    lop_days    = round(max(0.0, actual_days - available), 1) if convert_to_lop and leave_type != LEAVE_LWP else 0.0
    earned_used = round(actual_days - lop_days, 1)

    warning = None
    max_consec = getattr(policy, 'maximum_consecutive_days', None)
    if max_consec and actual_days > max_consec:
        if convert_to_lop and lop_days > 0:
            warning = (
                f'The selected leave exceeds the maximum consecutive leave limit of {max_consec} day(s). '
                f'Your available {leave_type} balance will be used first. '
                f'The remaining {lop_days} day(s) will be treated as Leave Without Pay (LOP), subject to approval.'
            )
        else:
            warning = f'The selected leave exceeds the maximum consecutive leave limit of {max_consec} day(s).'

    return success('Leave preview calculated.', {
        'leave_type':             leave_type,
        'start_date':             start.strftime('%Y-%m-%d'),
        'end_date':               end.strftime('%Y-%m-%d'),
        'duration':               duration,
        'calendar_days':          calendar_days,
        'company_holidays':       holidays_out,
        'company_holiday_count':  len(holidays_out),
        'week_offs':              week_offs_out,
        'week_off_count':         len(week_offs_out),
        'sandwich_leave_enabled': getattr(policy, 'sandwich_leave_enabled', False),
        'actual_leave_days':      actual_days,
        'available_balance':      available,
        'earned_leave_used':      earned_used,
        'lop_days':               lop_days,
        'lop_enabled':            convert_to_lop,
        'sufficient_balance':     actual_days <= available,
        'warning':                warning,
    })


# ─── Leave Requests ────────────────────────────────────────────────────────────

class LeaveRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        if request.query_params.get('action') == 'preview':
            return _leave_preview(request)

        has_approve = _has_perm(request.user, 'leave.approve')
        scope       = request.query_params.get('scope', '')

        qs_base = LeaveRequest.objects.select_related('employee', 'l1_approver', 'l2_approver')

        employee_id_param = request.query_params.get('employee_id')
        if employee_id_param:
            if not (_has_perm(request.user, 'employees.view') or has_approve):
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            from apps.accounts.models import User
            target_user = User.objects.filter(employee_id=employee_id_param).first()
            if not target_user:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
            queryset = qs_base.filter(employee=target_user)
        elif scope == 'team' and has_approve:
            # Approval queue — scoped by role, own requests excluded
            queryset = qs_base.filter(_approval_scope_filter(request.user))
        else:
            # Default: return the requesting user's own requests only
            queryset = qs_base.filter(employee=request.user)

        leave_type = request.query_params.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)

        req_status = request.query_params.get('status')
        if req_status:
            statuses = [s.strip() for s in req_status.split(',')]
            queryset = queryset.filter(status__in=statuses)

        year = request.query_params.get('year')
        if year:
            queryset = queryset.filter(start_date__year=year)

        branch = request.query_params.get('branch')
        if branch and _has_perm(request.user, 'settings.edit'):
            queryset = queryset.filter(employee__branch__iexact=branch)

        department = request.query_params.get('department')
        if department and has_approve:
            queryset = queryset.filter(employee__department__iexact=department)

        queryset = queryset.order_by('-created_at')

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = LeaveRequestSerializer(page_obj.object_list, many=True, context={'request': request})
        return success('Leave requests retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        serializer = LeaveRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data       = serializer.validated_data
        start      = data['start_date']
        end        = data['end_date']
        duration   = data.get('duration', 'full_day')
        leave_type = data['leave_type']

        from core.cache_service import LeavePolicyCacheService
        policy     = LeavePolicyCacheService.get(leave_type)
        total_days = _calc_working_days(start, end, duration, policy, request.user)

        if total_days <= 0:
            return error(_zero_working_days_reason(start, end, policy, request.user))

        if policy:
            today   = timezone.localdate()
            err_msg = _validate_leave_policy(
                policy, request.user, duration, total_days,
                start, end, data.get('document'), today,
            )
            if err_msg:
                return error(err_msg)

        _ACTIVE_STATUSES = (REQ_PENDING, REQ_L2_PENDING, REQ_APPROVED)
        overlap = LeaveRequest.objects.filter(
            employee=request.user,
            status__in=_ACTIVE_STATUSES,
            start_date__lte=end,
            end_date__gte=start,
        ).exists()
        if overlap:
            return error(
                'You already have a leave request for the selected date(s). '
                'Please modify or cancel the existing request before applying again.'
            )

        year = start.year

        # Balance check + creation wrapped in a transaction with row-level lock
        # to prevent double-booking when the same employee submits concurrent requests.
        lop_days = 0.0
        with transaction.atomic():
            if leave_type != LEAVE_LWP:
                balance = (
                    LeaveBalance.objects
                    .select_for_update()
                    .filter(employee=request.user, leave_type=leave_type, year=year)
                    .first()
                )
                if not balance:
                    return error(f'No leave balance found for {leave_type} in {year}. Contact HR.')
                available = float(balance.total_days - balance.used_days)
                if total_days > available:
                    if policy and policy.convert_to_lop:
                        # Use available balance; excess days become LOP — leave_type stays unchanged
                        lop_days = round(total_days - available, 1)
                    elif policy and policy.allow_negative_balance:
                        pass  # allow overdraft
                    else:
                        return error(f'Insufficient balance. You have {available} day(s) available.')

            l1, l2 = _resolve_approval_chain(request.user)

            # Managers skip L1 — their leave routes directly to HR (L2).
            # Also escalate to L2 when the employee has no reporting manager set,
            # so the request is never orphaned with no one to act on it.
            if (request.user.role and request.user.role.can_manage_team) or l1 is None:
                initial_status = REQ_L2_PENDING
                l1_approver    = None
                l2_approver    = l2
            else:
                initial_status = REQ_PENDING
                l1_approver    = l1
                l2_approver    = l2

            leave_request = LeaveRequest.objects.create(
                employee=request.user,
                leave_type=leave_type,
                duration=duration,
                start_date=start,
                end_date=end,
                total_days=total_days,
                lop_days=lop_days,
                reason=data.get('reason', ''),
                contact_during_leave=data.get('contact_during_leave', ''),
                handover_to=data.get('handover_to', ''),
                handover_notes=data.get('handover_notes', ''),
                document=data.get('document'),
                is_lwp=(leave_type == LEAVE_LWP),
                l1_approver=l1_approver,
                l2_approver=l2_approver,
                status=initial_status,
            )

        logger.info('Leave request %s created by %s (%s, %s days)', leave_request.id, request.user.email, leave_type, total_days)
        out = LeaveRequestSerializer(leave_request, context={'request': request})
        return success('Leave request submitted.', out.data, http_status=status.HTTP_201_CREATED)


class LeaveRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_request(self, request_id: str, user):
        try:
            leave_request = LeaveRequest.objects.select_related(
                'employee', 'l1_approver', 'l2_approver'
            ).get(id=request_id)
        except LeaveRequest.DoesNotExist:
            return None, error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)

        has_approve = _has_perm(user, 'leave.approve')
        if not has_approve and leave_request.employee_id != user.id:
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        if has_approve and not _can_hr_access_request(user, leave_request):
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        return leave_request, None

    def get(self, request, request_id: str):
        leave_request, err = self._get_request(request_id, request.user)
        if err:
            return err
        return success('Leave request retrieved.', LeaveRequestSerializer(leave_request, context={'request': request}).data)

    def patch(self, request, request_id: str):
        """Employee cancels their own pending request."""
        leave_request, err = self._get_request(request_id, request.user)
        if err:
            return err

        if leave_request.employee_id != request.user.id:
            return error('Only the employee can cancel their own request.', http_status=status.HTTP_403_FORBIDDEN)

        if leave_request.status not in (REQ_PENDING, REQ_L2_PENDING):
            return error('Only pending requests can be cancelled.')

        leave_request.status = REQ_CANCELLED
        leave_request.save(update_fields=['status', 'updated_at'])
        logger.info('Leave request %s cancelled by %s', leave_request.id, request.user.email)
        return success('Leave request cancelled.', LeaveRequestSerializer(leave_request, context={'request': request}).data)

    def put(self, request, request_id: str):
        return self.patch(request, request_id)

    def post(self, request, request_id: str):
        return self.patch(request, request_id)

    def delete(self, request, request_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only HR can delete leave requests.', http_status=status.HTTP_403_FORBIDDEN)
        leave_request, err = self._get_request(request_id, request.user)
        if err:
            return err
        if leave_request.status == REQ_APPROVED:
            return error(
                'Approved leave requests cannot be deleted.',
                http_status=status.HTTP_409_CONFLICT,
            )
        leave_request.delete()
        logger.info('Leave request %s deleted by %s', request_id, request.user.email)
        return success('Leave request deleted.')


class LeaveApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            leave_request = LeaveRequest.objects.select_related(
                'employee', 'l1_approver', 'l2_approver'
            ).get(id=request_id)
        except LeaveRequest.DoesNotExist:
            return error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)
        if _has_perm(request.user, 'leave.approve') and not _can_hr_access_request(request.user, leave_request):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return success(
            'Leave request retrieved.',
            LeaveRequestSerializer(leave_request, context={'request': request}).data,
        )

    def post(self, request, request_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        try:
            leave_request = LeaveRequest.objects.select_related('employee', 'l1_approver', 'l2_approver').get(id=request_id)
        except LeaveRequest.DoesNotExist:
            return error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)

        if leave_request.employee_id == request.user.id:
            return error('You cannot approve or reject your own leave request.', http_status=status.HTTP_403_FORBIDDEN)
        if _has_perm(request.user, 'leave.approve') and not _can_hr_access_request(request.user, leave_request):
            return error('You can only approve leave requests for employees in your branch.', http_status=status.HTTP_403_FORBIDDEN)

        action  = request.data.get('action')
        remarks = (request.data.get('remarks') or request.data.get('reason') or '').strip()

        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')

        now = timezone.now()

        if leave_request.status == REQ_PENDING:
            if not _can_approve_at_stage(request.user, leave_request, 'l1'):
                return error(
                    'You are not authorised to act on this request at the L1 stage. '
                    'Only the designated reporting manager may approve or reject it.',
                    http_status=status.HTTP_403_FORBIDDEN,
                )
            leave_request.l1_approver    = request.user
            leave_request.l1_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
            leave_request.l1_remarks     = remarks
            leave_request.l1_actioned_at = now

            if action == 'reject':
                leave_request.status = REQ_REJECTED
            elif leave_request.l2_approver_id:
                leave_request.status = REQ_L2_PENDING
            else:
                # No L2 configured — L1 approval is final.
                leave_request.status = REQ_APPROVED
                _deduct_balance_safe(leave_request)
                _sync_leave_attendance(leave_request)

        elif leave_request.status == REQ_L2_PENDING:
            if not _can_approve_at_stage(request.user, leave_request, 'l2'):
                return error(
                    'You are not authorised to act on this request at the L2 stage. '
                    'Only the designated HR approver may approve or reject it.',
                    http_status=status.HTTP_403_FORBIDDEN,
                )
            leave_request.l2_approver    = request.user
            leave_request.l2_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
            leave_request.l2_remarks     = remarks
            leave_request.l2_actioned_at = now
            leave_request.status = REQ_APPROVED if action == 'approve' else REQ_REJECTED
            if action == 'approve':
                _deduct_balance_safe(leave_request)
                _sync_leave_attendance(leave_request)

        else:
            return error(f'Cannot act on a request with status "{leave_request.status}".')

        leave_request.save()
        logger.info('Leave request %s %sd by %s', leave_request.id, action, request.user.email)

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action=f'leave_{action}d', module='leave',
            object_id=str(leave_request.id),
            changes={
                'employee':  leave_request.employee.full_name,
                'leave_type': leave_request.leave_type,
                'status':    leave_request.status,
                'remarks':   remarks,
            },
            branch=leave_request.employee.branch,
            ip_address=get_client_ip(request),
        )

        from apps.dashboard.views.overview import push_leave_update
        push_leave_update(request.user.id)

        return success(f'Request {action}d.', LeaveRequestSerializer(leave_request, context={'request': request}).data)


def _deduct_balance_safe(leave_request: LeaveRequest) -> None:
    if leave_request.is_lwp:  # pure LWP request — no leave balance record to deduct
        return
    year = leave_request.start_date.year
    lop = float(getattr(leave_request, 'lop_days', 0) or 0)
    earned_days = float(leave_request.total_days) - lop
    if earned_days > 0:
        LeaveBalance.objects.filter(
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            year=year,
        ).update(used_days=F('used_days') + earned_days)


def _sync_leave_attendance(leave_request: LeaveRequest) -> None:
    """Create or update AttendanceRecord rows to 'on_leave' for every day of an approved leave."""
    import uuid as _uuid_mod
    from apps.attendance.models import AttendanceRecord

    current = leave_request.start_date
    end = leave_request.end_date
    employee = leave_request.employee

    while current <= end:
        AttendanceRecord.objects.update_or_create(
            employee=employee,
            date=current,
            defaults={
                'status': AttendanceRecord.STATUS_ON_LEAVE,
                'first_punch_in': None,
                'last_punch_out': None,
                'total_working_minutes': 0,
            },
        )
        current += timedelta(days=1)
    logger.info(
        'Synced %d on_leave attendance record(s) for employee %s (leave %s)',
        (leave_request.end_date - leave_request.start_date).days + 1,
        employee.email,
        leave_request.id,
    )


# ─── Stats & Calendar ──────────────────────────────────────────────────────────

class LeaveStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        has_approve = _has_perm(request.user, 'leave.approve')
        try:
            year = int(request.query_params.get('year', _current_year()))
        except (TypeError, ValueError):
            return error('year must be a valid integer.')

        scope = request.query_params.get('scope', '')

        # HR/manager viewing another employee's stats
        employee_id_param = request.query_params.get('employee_id')
        stats_user = None
        if employee_id_param:
            if not (_has_perm(request.user, 'employees.view') or has_approve):
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            from apps.accounts.models import User
            stats_user = User.objects.filter(employee_id=employee_id_param).first()
            if not stats_user:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        own_scope = scope == 'own' or not has_approve or stats_user is not None
        target = stats_user or request.user

        if own_scope:
            qs = LeaveRequest.objects.filter(employee=target, start_date__year=year)
        else:
            qs = LeaveRequest.objects.filter(
                _approval_scope_filter(request.user), start_date__year=year
            )

        agg = qs.aggregate(
            total        = Count('id'),
            pending      = Count('id', filter=Q(status__in=[REQ_PENDING, REQ_L2_PENDING])),
            approved     = Count('id', filter=Q(status=REQ_APPROVED)),
            rejected     = Count('id', filter=Q(status=REQ_REJECTED)),
            cancelled    = Count('id', filter=Q(status=REQ_CANCELLED)),
            lop_total    = Sum('lop_days', filter=Q(status=REQ_APPROVED)),
            lop_requests = Count('id', filter=Q(status=REQ_APPROVED, lop_days__gt=0)),
        )

        # Balance breakdown only for own-scope views (employee or ?scope=own or ?employee_id=)
        balance_data = []
        if own_scope:
            balances = LeaveBalance.objects.filter(employee=target, year=year)
            balance_data = [
                {
                    'leave_type':         b.leave_type,
                    'leave_type_display': b.get_leave_type_display(),
                    'total_days':         float(b.total_days),
                    'used_days':          float(b.used_days),
                    'available':          float(b.total_days - b.used_days),
                }
                for b in balances
            ]

        return success('Stats retrieved.', {
            'total':     agg['total']     or 0,
            'pending':   agg['pending']   or 0,
            'approved':  agg['approved']  or 0,
            'rejected':  agg['rejected']  or 0,
            'cancelled': agg['cancelled'] or 0,
            'lop_days':     float(agg['lop_total'] or 0),
            'lop_requests': agg['lop_requests'] or 0,
            'year':         year,
            'balances':  balance_data,
        })


class LeaveCalendarView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get('year', _current_year()))
        except (TypeError, ValueError):
            return error('year must be a valid integer.')
        month = request.query_params.get('month')

        scope_filter = _calendar_scope_filter(request.user)
        qs = LeaveRequest.objects.select_related('employee').filter(
            scope_filter,
            status=REQ_APPROVED,
            start_date__year=year,
        )
        if month:
            try:
                qs = qs.filter(start_date__month=int(month))
            except (TypeError, ValueError):
                return error('month must be a valid integer between 1 and 12.')

        # system_admin can still narrow by branch via the UI branch dropdown
        branch = request.query_params.get('branch')
        if branch and _has_perm(request.user, 'settings.edit'):
            qs = qs.filter(employee__branch__iexact=branch)

        events = [
            {
                'id':            str(lr.id),
                'employee_name': lr.employee.full_name,
                'employee_code': lr.employee.employee_id,
                'leave_type':    lr.leave_type,
                'leave_type_display': lr.get_leave_type_display(),
                'start_date':    str(lr.start_date),
                'end_date':      str(lr.end_date),
                'total_days':    float(lr.total_days),
            }
            for lr in qs.order_by('start_date')
        ]
        return success('Calendar events retrieved.', events)


# ─── Carry Forward ────────────────────────────────────────────────────────────

def _eligible_for_policy(employee, policy, today) -> bool:
    """Return False if the employee doesn't meet the policy's eligibility rules."""
    doj = getattr(employee, 'date_of_joining', None)
    if policy.minimum_service_period > 0 and doj:
        months_served = (today.year - doj.year) * 12 + (today.month - doj.month)
        if months_served < policy.minimum_service_period:
            return False
    if policy.applicable_branches and (
        not employee.branch or employee.branch not in policy.applicable_branches
    ):
        return False
    if policy.applicable_departments and (
        not employee.department or employee.department not in policy.applicable_departments
    ):
        return False
    if policy.applicable_designations and (
        not employee.designation or employee.designation not in policy.applicable_designations
    ):
        return False
    return True


def _build_carry_forward_rows(employees, policies, from_year, to_year, today):
    """
    Return a list of preview dicts and a set of (employee_id, leave_type) keys
    that already have a to_year balance.
    """
    leave_type_label_map = dict(LEAVE_TYPE_CHOICES)

    existing_to_year = set(
        LeaveBalance.objects.filter(year=to_year)
        .values_list('employee_id', 'leave_type')
    )

    rows = []
    for employee in employees:
        for policy in policies:
            if not policy.can_carry_forward:
                continue
            if not _eligible_for_policy(employee, policy, today):
                continue

            prev = LeaveBalance.objects.filter(
                employee=employee, leave_type=policy.leave_type, year=from_year,
            ).first()
            if not prev:
                continue

            unused = prev.total_days - prev.used_days
            if unused <= 0:
                continue

            if policy.carry_forward_type == CARRY_FORWARD_UNLIMITED:
                cf_amount = unused
            else:
                cf_amount = min(unused, Decimal(str(policy.max_carry_forward_days)))

            expiry_date = None
            if policy.carry_forward_expiry_days > 0:
                expiry_date = today + timedelta(days=policy.carry_forward_expiry_days)

            already = (employee.id, policy.leave_type) in existing_to_year

            rows.append({
                'employee_id':          employee.employee_id or '',
                'employee_name':        employee.full_name,
                'leave_type':           policy.leave_type,
                'leave_type_display':   leave_type_label_map.get(policy.leave_type, policy.leave_type),
                'unused_days':          float(unused),
                'carry_forward_amount': float(cf_amount),
                'expiry_date':          expiry_date.isoformat() if expiry_date else None,
                'already_processed':    already,
            })

    return rows


class CarryForwardYearsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        today = date.today()
        years = (
            LeaveBalance.objects
            .values_list('year', flat=True)
            .distinct()
            .order_by('year')
        )

        pairs = [
            {'from_year': y, 'to_year': y + 1}
            for y in years
        ]

        return success('Available carry-forward year pairs.', {
            'years':        pairs,
            'default_from': today.year - 1,
            'default_to':   today.year,
        })


class CarryForwardPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        ser = CarryForwardInputSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), http_status=status.HTTP_400_BAD_REQUEST)

        from_year = ser.validated_data['from_year']
        to_year   = ser.validated_data['to_year']
        today     = date.today()

        from apps.accounts.models import User
        employees = list(
            User.objects.filter(is_active=True, role__isnull=False, employee_id__isnull=False)
        )
        policies = list(LeavePolicy.objects.filter(is_active=True, can_carry_forward=True))

        rows = _build_carry_forward_rows(employees, policies, from_year, to_year, today)

        already_count = sum(1 for r in rows if r['already_processed'])

        return success('Carry-forward preview.', {
            'from_year':               from_year,
            'to_year':                 to_year,
            'preview_rows':            rows,
            'total_rows':              len(rows),
            'already_processed_count': already_count,
            'pending_count':           len(rows) - already_count,
        })


class CarryForwardRunView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        ser = CarryForwardInputSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), http_status=status.HTTP_400_BAD_REQUEST)

        from_year = ser.validated_data['from_year']
        to_year   = ser.validated_data['to_year']
        today     = date.today()

        if CarryForwardLog.objects.filter(
            from_year=from_year, to_year=to_year, is_completed=True,
        ).exists():
            return error(
                f'Carry forward for {from_year}→{to_year} has already been executed. '
                'Check history for details.',
                http_status=status.HTTP_409_CONFLICT,
            )

        from apps.accounts.models import User
        employees = list(
            User.objects.filter(is_active=True, role__isnull=False, employee_id__isnull=False)
        )
        policies = list(
            LeavePolicy.objects.filter(
                is_active=True, can_carry_forward=True, carry_forward_mode=CARRY_FORWARD_MANUAL,
            )
        )

        processed = 0
        skipped   = 0
        failed    = 0

        for employee in employees:
            for policy in policies:
                if not _eligible_for_policy(employee, policy, today):
                    skipped += 1
                    continue

                prev = LeaveBalance.objects.filter(
                    employee=employee, leave_type=policy.leave_type, year=from_year,
                ).first()
                if not prev:
                    skipped += 1
                    continue

                unused = prev.total_days - prev.used_days
                if unused <= 0:
                    skipped += 1
                    continue

                if policy.carry_forward_type == CARRY_FORWARD_UNLIMITED:
                    cf_amount = unused
                else:
                    cf_amount = min(unused, Decimal(str(policy.max_carry_forward_days)))

                expiry_date = None
                if policy.carry_forward_expiry_days > 0:
                    expiry_date = today + timedelta(days=policy.carry_forward_expiry_days)

                try:
                    existing = LeaveBalance.objects.filter(
                        employee=employee, leave_type=policy.leave_type, year=to_year,
                    ).first()
                    if existing:
                        skipped += 1
                        continue

                    LeaveBalance.objects.create(
                        employee=employee,
                        leave_type=policy.leave_type,
                        year=to_year,
                        total_days=policy.annual_days + cf_amount,
                        carried_forward=cf_amount,
                        carry_forward_expiry_date=expiry_date,
                    )
                    processed += 1
                except Exception:
                    logger.exception(
                        'CarryForward failed for employee=%s leave_type=%s',
                        employee.employee_id, policy.leave_type,
                    )
                    failed += 1

        log = CarryForwardLog.objects.create(
            from_year=from_year,
            to_year=to_year,
            executed_by=request.user,
            process_mode='execute',
            total_processed=processed,
            total_skipped=skipped,
            total_failed=failed,
            is_completed=True,
        )

        return success('Carry forward executed.', CarryForwardLogSerializer(log).data)


class CarryForwardHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        qs                  = CarryForwardLog.objects.select_related('executed_by').order_by('-created_at')
        page_obj, paginator = paginate(qs, request)
        results             = CarryForwardLogSerializer(page_obj, many=True).data
        return success('Carry-forward history.', paginated_data(paginator, page_obj, results))


# ─── Leave Opening Balance Import ─────────────────────────────────────────────

_LEAVE_IMPORT_BATCH_SIZE    = 500
_LEAVE_IMPORT_MAX_BYTES     = 5 * 1024 * 1024  # 5 MB

_LEAVE_IMPORT_COL_MAP = {
    'employee id': 'employee_id',         'employee_id': 'employee_id',
    'employee code': 'employee_id',       'employee_code': 'employee_id',
    'emp id': 'employee_id',              'emp_id': 'employee_id',
    'emp code': 'employee_id',            'emp_code': 'employee_id',
    'leave type': 'leave_type',           'leave_type': 'leave_type',
    'financial year': 'financial_year',   'financial_year': 'financial_year',
    'fy': 'financial_year',               'year': 'financial_year',
    'fy year': 'financial_year',
    'opening balance': 'opening_balance', 'opening_balance': 'opening_balance',
    'opening': 'opening_balance',
    'leave allocated': 'allocated',       'leave_allocated': 'allocated',
    'allocated': 'allocated',             'allocation': 'allocated',
    'leave availed': 'availed',           'leave_availed': 'availed',
    'availed': 'availed',                 'used': 'availed',
    'used days': 'availed',               'leaves used': 'availed',
    'carry forward': 'carry_forward',         'carry_forward': 'carry_forward',
    'carry forward days': 'carry_forward',    'carry_forward_days': 'carry_forward',
    'cf days': 'carry_forward',               'cf_days': 'carry_forward',
    'carried forward': 'carry_forward',       'carried_forward': 'carry_forward',
    'leave balance': 'balance',           'leave_balance': 'balance',
    'balance': 'balance',                 'closing balance': 'balance',
    'lop days': 'lop_days',               'lop_days': 'lop_days',
    'lop': 'lop_days',
    # History row date columns
    'from date': 'from_date',             'from_date': 'from_date',
    'start date': 'from_date',            'start_date': 'from_date',
    'leave from': 'from_date',            'leave from date': 'from_date',
    'to date': 'to_date',                 'to_date': 'to_date',
    'end date': 'to_date',                'end_date': 'to_date',
    'leave to': 'to_date',                'leave to date': 'to_date',
    'total days': 'days',                 'total_days': 'days',
    'days': 'days',                       'no of days': 'days',
    'leave days': 'days',                 'no. of days': 'days',
    'duration': 'days',
    'remarks': 'remarks',                 'notes': 'remarks',
    'comments': 'remarks',
}

_LEAVE_IMPORT_SAMPLE_HEADERS = [
    'Employee ID', 'Leave Type', 'Financial Year',
    'Opening Balance', 'Leave Allocated', 'Leave Availed',
    'Leave Balance', 'Carry Forward Days',
    'From Date', 'To Date', 'Total Days',
    'Remarks',
]

_LEAVE_IMPORT_SAMPLE_ROWS = [
    # Balance rows — set annual opening numbers (leave From Date / To Date empty)
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '6',  '6',  '2', '10', '0', '', '', '', 'Opening migration'],
    ['RSS00001', 'Earned Leave', 'FY 2026-27', '15', '15', '5', '30', '5', '', '', '', ''],
    ['RSS00002', 'Casual Leave', 'FY 2026-27', '6',  '6',  '0', '12', '0', '', '', '', ''],
    # History rows — individual leave dates (leave balance columns empty)
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '', '', '', '', '', '05-Apr-2025', '06-Apr-2025', '2', 'Annual leave'],
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '', '', '', '', '', '15-May-2025', '15-May-2025', '1', ''],
]


def _leave_err(row_num, emp_id, lt, fy, reason, *, from_date='', to_date='') -> dict:
    d = {'row': row_num, 'employee_id': emp_id, 'leave_type': lt, 'financial_year': fy, 'reason': reason}
    if from_date or to_date:
        d['from_date'] = from_date
        d['to_date'] = to_date
    return d


def _normalize_leave_row(raw: dict) -> dict:
    return {
        _LEAVE_IMPORT_COL_MAP[(k or '').strip().lower()]: (v or '').strip()
        for k, v in raw.items()
        if _LEAVE_IMPORT_COL_MAP.get((k or '').strip().lower())
    }


def _parse_fy_year(value: str):
    val = str(value or '').strip().upper().replace('FY', '').strip()
    if '-' in val:
        try:
            start = int(val.split('-')[0].strip())
            return (2000 + start) if start < 100 else start
        except (ValueError, IndexError):
            return None
    try:
        year = int(val)
        return year if 2000 <= year <= 2100 else None
    except ValueError:
        return None


def _to_decimal_safe(value, label: str):
    try:
        d = Decimal(str(value or 0).strip())
        if d < 0:
            return None, f'{label} must be ≥ 0.'
        return d, None
    except Exception:
        return None, f'{label} must be a valid number.'


def _parse_leave_row_amounts(row: dict):
    fields = [
        ('opening_balance', 'Opening Balance'), ('allocated', 'Leave Allocated'),
        ('availed', 'Leave Availed'),           ('carry_forward', 'Carry Forward Days'),
    ]
    vals = []
    for key, label in fields:
        val, err = _to_decimal_safe(row.get(key, 0), label)
        if err:
            return None, None, None, None, err
        vals.append(val)
    return vals[0], vals[1], vals[2], vals[3], None


def _parse_leave_import_xlsx(file_obj):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = iter(ws.iter_rows(values_only=True))
        header_row = next(rows_iter, None)
        if not header_row:
            return [], 'The XLSX file has no header row.'
        headers = [str(h).strip() if h is not None else '' for h in header_row]
        rows = []
        for raw in rows_iter:
            if all(v is None or str(v).strip() == '' for v in raw):
                continue
            rows.append({headers[i]: (str(raw[i]).strip() if raw[i] is not None else '') for i in range(len(headers))})
        wb.close()
        return rows, None
    except Exception as exc:
        return [], f'Could not parse XLSX: {exc}'


def _parse_leave_import_csv(file_obj):
    try:
        text = file_obj.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        return [
            {k: (v or '').strip() for k, v in row.items()}
            for row in reader
            if any((v or '').strip() for v in row.values())
        ], None
    except Exception as exc:
        return [], f'Could not parse CSV: {exc}'


def _build_leave_error_csv(errors: list) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    has_dates = any('from_date' in e for e in errors)
    headers = ['Row', 'Employee ID', 'Leave Type', 'Financial Year']
    if has_dates:
        headers += ['From Date', 'To Date']
    headers.append('Reason')
    writer.writerow(headers)
    for e in errors:
        row = [e.get('row'), e.get('employee_id'), e.get('leave_type'), e.get('financial_year')]
        if has_dates:
            row += [e.get('from_date', ''), e.get('to_date', '')]
        row.append(e.get('reason'))
        writer.writerow(row)
    return base64.b64encode(buf.getvalue().encode('utf-8-sig')).decode('ascii')


def _load_leave_ref_data(emp_ids: set):
    from apps.accounts.models import User
    emp_map = {
        u.employee_id: u
        for u in User.objects.filter(employee_id__in=emp_ids, is_active=True).only('id', 'employee_id', 'full_name')
    }
    valid_lt = {}
    for code, label in LEAVE_TYPE_CHOICES:
        valid_lt[code.lower()] = code
        valid_lt[label.lower()] = code
    for p in LeavePolicy.objects.filter(is_active=True).values('leave_type', 'leave_type_label'):
        valid_lt[p['leave_type'].lower()] = p['leave_type']
        if p.get('leave_type_label') and p['leave_type_label'].lower() not in valid_lt:
            valid_lt[p['leave_type_label'].lower()] = p['leave_type']
    existing = {
        (b['employee_id'], b['leave_type'], b['year'])
        for b in LeaveBalance.objects.filter(
            employee_id__in=[u.pk for u in emp_map.values()]
        ).values('employee_id', 'leave_type', 'year')
    }
    return emp_map, valid_lt, existing


def _validate_leave_rows(normalized: list, emp_map: dict, valid_lt: dict, existing: set):
    to_create, errors = [], []
    fail_count, skip_count = 0, 0
    seen: set = set()

    for i, row in enumerate(normalized, 1):
        row_num = row.get('__row__', i)
        emp_id = row.get('employee_id', '')
        raw_lt = row.get('leave_type', '')
        raw_fy = row.get('financial_year', '')

        user = emp_map.get(emp_id)
        if not user:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'Employee "{emp_id}" not found or inactive.'))
            fail_count += 1; continue

        lt_code = valid_lt.get(raw_lt.lower())
        if not lt_code:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'Leave type "{raw_lt}" is not recognised.'))
            fail_count += 1; continue

        year = _parse_fy_year(raw_fy)
        if year is None:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'Financial year "{raw_fy}" is invalid. Use YYYY or "FY 2026-27".'))
            fail_count += 1; continue

        row_key = (user.pk, lt_code, year)
        if row_key in seen:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, 'Duplicate row in file — first occurrence wins.'))
            skip_count += 1; continue
        seen.add(row_key)

        if row_key in existing:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, 'Opening balance already exists for this employee, leave type, and year.'))
            fail_count += 1; continue

        opening, allocated, availed, carry_fwd, err = _parse_leave_row_amounts(row)
        if err:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, err))
            fail_count += 1; continue

        to_create.append(LeaveBalance(
            employee=user, leave_type=lt_code, year=year,
            total_days=opening + carry_fwd + allocated,
            used_days=availed, carried_forward=carry_fwd,
        ))

    return to_create, errors, fail_count, skip_count


def _bulk_insert_leave_balances(to_create: list):
    created, batch_errors = 0, 0
    for i in range(0, len(to_create), _LEAVE_IMPORT_BATCH_SIZE):
        batch = to_create[i:i + _LEAVE_IMPORT_BATCH_SIZE]
        try:
            with transaction.atomic():
                LeaveBalance.objects.bulk_create(batch)
            created += len(batch)
        except Exception as exc:
            logger.error('Leave balance import batch %d error: %s', i // _LEAVE_IMPORT_BATCH_SIZE + 1, exc, exc_info=True)
            batch_errors += len(batch)
    return created, batch_errors


# ── Leave history import helpers ───────────────────────────────────────────────

def _parse_date_value(value: str):
    """Parse a date string in common formats. Returns a date object or None."""
    from datetime import datetime
    val = str(value or '').strip()
    if not val or val.lower() in ('-', 'n/a', 'na', 'none', 'null'):
        return None
    for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%b-%Y',
                '%d %b %Y', '%d-%B-%Y', '%d/%m/%y', '%m/%d/%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _is_history_row(row: dict) -> bool:
    return bool(row.get('from_date') or row.get('to_date'))


def _check_overlap(emp_pk, from_d, to_d, by_emp: dict) -> bool:
    for s, e in by_emp.get(emp_pk, []):
        if s <= to_d and e >= from_d:
            return True
    return False


def _build_leave_request(user, lt_code: str, from_d, to_d, days_val, remarks: str):
    reason = (remarks or '').strip() or 'Imported historical leave record.'
    return LeaveRequest(
        employee=user,
        leave_type=lt_code,
        start_date=from_d,
        end_date=to_d,
        total_days=days_val,
        reason=reason,
        status=REQ_APPROVED,
        duration=DURATION_FULL,
        l1_status=APPROVAL_APPROVED,
        l1_actioned_at=timezone.now(),
        is_lwp=(lt_code == LEAVE_LWP),
    )


def _load_existing_requests(emp_map: dict) -> dict:
    """Return {employee_pk: [(start_date, end_date), ...]} for non-cancelled requests."""
    if not emp_map:
        return {}
    emp_pks = [u.pk for u in emp_map.values()]
    result: dict = {}
    for lr in LeaveRequest.objects.filter(
        employee_id__in=emp_pks,
        status__in=[REQ_APPROVED, REQ_PENDING, REQ_L2_PENDING],
    ).values('employee_id', 'start_date', 'end_date'):
        result.setdefault(lr['employee_id'], []).append((lr['start_date'], lr['end_date']))
    return result


def _validate_leave_history_rows(normalized: list, emp_map: dict, valid_lt: dict, existing_by_emp: dict):
    to_create, errors = [], []
    fail_count, skip_count = 0, 0
    seen_by_emp: dict = {}

    for i, row in enumerate(normalized, 1):
        row_num = row.get('__row__', i)
        emp_id  = row.get('employee_id', '')
        raw_lt  = row.get('leave_type', '')
        raw_fy  = row.get('financial_year', '')
        raw_from = row.get('from_date', '')
        raw_to   = row.get('to_date', '')

        user = emp_map.get(emp_id)
        if not user:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'Employee "{emp_id}" not found or inactive.', from_date=raw_from, to_date=raw_to))
            fail_count += 1; continue

        lt_code = valid_lt.get(raw_lt.lower())
        if not lt_code:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'Leave type "{raw_lt}" is not recognised.', from_date=raw_from, to_date=raw_to))
            fail_count += 1; continue

        from_d = _parse_date_value(raw_from)
        to_d   = _parse_date_value(raw_to)
        if not from_d:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'From Date "{raw_from}" is invalid.', from_date=raw_from, to_date=raw_to))
            fail_count += 1; continue
        if not to_d:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, f'To Date "{raw_to}" is invalid.', from_date=raw_from, to_date=raw_to))
            fail_count += 1; continue
        if from_d > to_d:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, 'From Date must be on or before To Date.', from_date=raw_from, to_date=raw_to))
            fail_count += 1; continue

        raw_days = row.get('days', '')
        days_val, days_err = _to_decimal_safe(raw_days, 'Total Days') if raw_days else (None, None)
        if days_err:
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, days_err, from_date=raw_from, to_date=raw_to))
            fail_count += 1; continue
        if not days_val:
            days_val = Decimal((to_d - from_d).days + 1)

        if _check_overlap(user.pk, from_d, to_d, existing_by_emp):
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, 'Overlaps with an existing leave record — skipped.', from_date=raw_from, to_date=raw_to))
            skip_count += 1; continue

        if _check_overlap(user.pk, from_d, to_d, seen_by_emp):
            errors.append(_leave_err(row_num, emp_id, raw_lt, raw_fy, 'Duplicate date range in file — first occurrence wins.', from_date=raw_from, to_date=raw_to))
            skip_count += 1; continue

        seen_by_emp.setdefault(user.pk, []).append((from_d, to_d))
        to_create.append(_build_leave_request(user, lt_code, from_d, to_d, days_val, row.get('remarks', '')))

    return to_create, errors, fail_count, skip_count


def _bulk_insert_leave_requests(to_create: list):
    created, batch_errors = 0, 0
    for i in range(0, len(to_create), _LEAVE_IMPORT_BATCH_SIZE):
        batch = to_create[i:i + _LEAVE_IMPORT_BATCH_SIZE]
        try:
            with transaction.atomic():
                LeaveRequest.objects.bulk_create(batch)
            created += len(batch)
        except Exception as exc:
            logger.error('Leave history import batch %d error: %s', i // _LEAVE_IMPORT_BATCH_SIZE + 1, exc, exc_info=True)
            batch_errors += len(batch)
    return created, batch_errors


def _normalize_and_index_rows(rows: list) -> list:
    """Normalize all rows and stamp each with its 1-based file row number."""
    result = []
    for i, row in enumerate(rows, 1):
        n = _normalize_leave_row(row)
        n['__row__'] = i
        result.append(n)
    return result


def _parse_and_validate_file(uploaded):
    """Parse uploaded file. Returns (rows, error_message)."""
    fname = uploaded.name.lower()
    if fname.endswith('.xlsx'):
        return _parse_leave_import_xlsx(uploaded)
    if fname.endswith('.csv'):
        return _parse_leave_import_csv(uploaded)
    return [], 'Unsupported file type. Upload a .csv or .xlsx file.'


class LeaveOpeningBalanceImportView(APIView):
    """POST /api/leave/balance/import/ — bulk import opening leave balances (migration tool)."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only System Admin, HR Admin, and HR can import leave balances.', http_status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or XLSX file as "file".')
        if uploaded.size > _LEAVE_IMPORT_MAX_BYTES:
            return error('File must not exceed 5 MB.')

        fname = uploaded.name.lower()
        if fname.endswith('.xlsx'):
            rows, parse_err = _parse_leave_import_xlsx(uploaded)
        elif fname.endswith('.csv'):
            rows, parse_err = _parse_leave_import_csv(uploaded)
        else:
            return error('Unsupported file type. Upload a .csv or .xlsx file.')
        if parse_err:
            return error(parse_err)
        if not rows:
            return error('The file contains no data rows.')

        normalized = _normalize_and_index_rows(rows)
        emp_ids = {r.get('employee_id', '') for r in normalized} - {''}
        emp_map, valid_lt, existing_balances = _load_leave_ref_data(emp_ids)
        existing_requests = _load_existing_requests(emp_map)

        balance_rows = [r for r in normalized if not _is_history_row(r)]
        history_rows  = [r for r in normalized if _is_history_row(r)]

        start_ts = time.monotonic()
        bal_to_create, bal_errors, bal_fail, bal_skip = _validate_leave_rows(balance_rows, emp_map, valid_lt, existing_balances)
        req_to_create, req_errors, req_fail, req_skip = _validate_leave_history_rows(history_rows, emp_map, valid_lt, existing_requests)

        all_errors = bal_errors + req_errors
        fail_count = bal_fail + req_fail
        skip_count = bal_skip + req_skip

        bal_created, bal_batch_err = _bulk_insert_leave_balances(bal_to_create)
        req_created, req_batch_err = _bulk_insert_leave_requests(req_to_create)
        fail_count += bal_batch_err + req_batch_err

        if bal_created > 0:
            from django.core.cache import cache as _cache
            _cache.delete_many(list({
                f'dashboard:employee:leave_balance:{lb.employee_id}:{lb.year}'
                for lb in bal_to_create
            }))

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='leave_opening_balance_import', module='leave',
            changes={
                'file': uploaded.name, 'total': len(rows),
                'balances_created': bal_created, 'history_imported': req_created,
                'failed': fail_count, 'skipped': skip_count,
            },
            ip_address=get_client_ip(request),
        )
        logger.info(
            'Leave import by %s: %d balances / %d history / %d failed / %d skipped (%.1fs)',
            request.user.email, bal_created, req_created, fail_count, skip_count,
            time.monotonic() - start_ts,
        )

        result = {
            'total_records':    len(rows),
            'balances_created': bal_created,
            'history_imported': req_created,
            'successful':       bal_created + req_created,
            'failed':           fail_count,
            'skipped':          skip_count,
            'errors':           all_errors[:100],
            'error_report_csv': _build_leave_error_csv(all_errors) if all_errors else None,
        }
        return success('Leave import completed.', result)


class LeaveOpeningBalanceSampleView(APIView):
    """GET /api/leave/balance/import/sample/?format=csv|xlsx — download import template."""
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only System Admin, HR Admin, and HR can download the leave balance import template.', http_status=status.HTTP_403_FORBIDDEN)

        from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv, build_sample_xlsx
        fmt = (request.query_params.get('format') or 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(_LEAVE_IMPORT_SAMPLE_HEADERS, _LEAVE_IMPORT_SAMPLE_ROWS, 'Leave Opening Balance')
            filename = 'leave_opening_balance_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(_LEAVE_IMPORT_SAMPLE_HEADERS, _LEAVE_IMPORT_SAMPLE_ROWS)
            filename = 'leave_opening_balance_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class LeaveOpeningBalanceValidateView(APIView):
    """POST /api/leave/balance/import/validate/ — validate file and return row-by-row preview without saving."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only System Admin, HR Admin, and HR can validate import files.', http_status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or XLSX file as "file".')
        if uploaded.size > _LEAVE_IMPORT_MAX_BYTES:
            return error('File must not exceed 5 MB.')

        rows, parse_err = _parse_and_validate_file(uploaded)
        if parse_err:
            return error(parse_err)
        if not rows:
            return error('The file contains no data rows.')

        normalized = _normalize_and_index_rows(rows)
        emp_ids = {r.get('employee_id', '') for r in normalized} - {''}
        emp_map, valid_lt, existing_balances = _load_leave_ref_data(emp_ids)
        existing_requests = _load_existing_requests(emp_map)

        balance_rows = [r for r in normalized if not _is_history_row(r)]
        history_rows  = [r for r in normalized if _is_history_row(r)]

        _, bal_errors, _, _ = _validate_leave_rows(balance_rows, emp_map, valid_lt, existing_balances)
        _, req_errors, _, _ = _validate_leave_history_rows(history_rows, emp_map, valid_lt, existing_requests)

        error_by_row = {e['row']: e for e in (bal_errors + req_errors)}

        preview = []
        for row in normalized:
            row_num = row['__row__']
            is_hist = _is_history_row(row)
            err     = error_by_row.get(row_num)
            preview.append({
                'row':            row_num,
                'row_type':       'history' if is_hist else 'balance',
                'employee_id':    row.get('employee_id', ''),
                'leave_type':     row.get('leave_type', ''),
                'financial_year': row.get('financial_year', ''),
                'from_date':      row.get('from_date') or None,
                'to_date':        row.get('to_date') or None,
                'days':           row.get('days') or None,
                'valid':          err is None,
                'error':          err['reason'] if err else None,
            })

        valid_count = sum(1 for p in preview if p['valid'])
        return success('File validated.', {
            'total_rows':   len(rows),
            'valid_rows':   valid_count,
            'error_rows':   len(rows) - valid_count,
            'balance_rows': len(balance_rows),
            'history_rows': len(history_rows),
            'preview':      preview,
        })
