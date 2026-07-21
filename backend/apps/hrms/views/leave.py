import base64
import csv
import io
import logging
import time
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, get_client_ip, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_REJECTED,
    CARRY_FORWARD_UNLIMITED, CARRY_FORWARD_MANUAL,
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


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _current_year() -> int:
    from apps.accounts.utils import get_company_financial_year_config, get_fy_start_year
    config = get_company_financial_year_config()
    return get_fy_start_year(date.today(), config.get('financial_year_start_month', 'April'))


def _resolve_approver(role_str: str, employee) -> 'accounts.User | None':
    """Map a role string from ApprovalWorkflowRule to an actual User on the employee."""
    if role_str in ('reporting_manager', 'rm', 'manager'):
        return getattr(employee, 'reporting_manager', None)
    if role_str in ('hr', 'hr_manager', 'hr_admin'):
        return getattr(employee, 'hr', None)
    return None


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


def _role_name(user) -> str:
    return user.role.name if user.role else 'employee'


def _user_branch(user) -> str:
    return (getattr(user, 'branch', '') or '').strip()


def _can_hr_access_request(hr_user, leave_request) -> bool:
    """Branch guard for hr_admin: True when no branch set (no restriction) or branches match."""
    branch = _user_branch(hr_user)
    if not branch:
        return True
    return (getattr(leave_request.employee, 'branch', '') or '').strip() == branch


def _can_approve_at_stage(user, leave_request, stage: str) -> bool:
    """
    Return True if `user` is authorised to act at the given approval stage.

    - system_admin: always authorised (admin override for any stuck request).
    - l1 stage: must be the designated l1_approver on the request.
    - l2 stage: must be the designated l2_approver, or an hr_admin / hr in
                the same branch when no l2 was stamped at creation time.

    Enforcing the designated approver prevents any user with leave.approve from
    jumping the queue or acting at the wrong stage.
    """
    role = _role_name(user)
    if role == 'system_admin':
        return True

    if stage == 'l1':
        if leave_request.l1_approver_id:
            return leave_request.l1_approver_id == user.id
        # No designated L1 — only system_admin (handled above) may unblock.
        return False

    if stage == 'l2':
        if leave_request.l2_approver_id:
            return leave_request.l2_approver_id == user.id
        # No designated L2 — HR admin with branch access may step in.
        return role in ('hr_admin', 'hr') and _can_hr_access_request(user, leave_request)

    return False


def _is_hr_role(role: str) -> bool:
    """True for both 'hr' (current DB value) and legacy 'hr_admin' alias."""
    return role in ('hr', 'hr_admin')


def _approval_scope_filter(user) -> 'Q':
    """
    Scope filter for the approval queue — enforces both role and status visibility.
    manager__team_lead → REQ_PENDING requests where they are the designated L1 approver.
    hr / hr_admin      → REQ_L2_PENDING requests in their branch.
    system_admin       → all statuses, all employees except own.
    """
    role = _role_name(user)
    if role == 'system_admin':
        return ~Q(employee=user)
    if _is_hr_role(role):
        branch = _user_branch(user)
        if branch:
            return Q(employee__branch=branch, status=REQ_L2_PENDING) & ~Q(employee=user)
        return Q(employee__hr=user, status=REQ_L2_PENDING) & ~Q(employee=user)
    if role == 'manager__team_lead':
        # Show only requests where this manager is the designated L1 approver.
        # Scoping by l1_approver (not reporting_manager) is precise — it respects
        # per-employee overrides and avoids showing requests already past L1.
        return Q(l1_approver=user, status=REQ_PENDING) & ~Q(employee=user)
    return Q(employee=user)


def _calendar_scope_filter(user) -> 'Q':
    """
    Scope filter for the team calendar.
    employee           → all approved (to see who's out)
    manager__team_lead → team + own
    hr_admin           → branch
    system_admin       → all
    """
    role = _role_name(user)
    if role == 'system_admin':
        return Q()
    if _is_hr_role(role):
        return Q(employee__branch=user.branch) if user.branch else Q()
    if role == 'manager__team_lead':
        return Q(employee__reporting_manager=user) | Q(employee=user)
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


def _get_weekoffs_in_range(start: date, end: date) -> list:
    """Return [{'date': 'YYYY-MM-DD', 'day': str}] for week-off days in range."""
    from datetime import timedelta
    off_days = _get_weekly_off_days()
    result, cur = [], start
    while cur <= end:
        if cur.strftime('%A').lower() in off_days:
            result.append({'date': cur.strftime('%Y-%m-%d'), 'day': cur.strftime('%A')})
        cur += timedelta(days=1)
    return result


def _calc_working_days(start: date, end: date, duration: str, policy=None, employee=None) -> float:
    if duration != 'full_day':
        return 0.5
    off_days       = _get_weekly_off_days()
    count_offs     = getattr(policy, 'count_weekoffs_as_leave', False)
    sandwich       = getattr(policy, 'sandwich_leave_enabled', False)
    count_holidays = getattr(policy, 'count_holidays_as_leave', False)
    branch_name    = (getattr(employee, 'branch', '') or '') if employee else ''
    holiday_dates  = _get_holiday_dates(start, end, branch_name)

    count = 0
    current = start
    from datetime import timedelta
    while current <= end:
        is_off     = current.strftime('%A').lower() in off_days
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


def _get_weekly_off_days() -> set:
    from core.cache_service import WeeklyOffCacheService
    return WeeklyOffCacheService.get()


def _zero_working_days_reason(start: date, end: date, policy=None, employee=None) -> str:
    """Return a user-friendly message explaining why a date range has no working days."""
    from datetime import timedelta
    off_days       = _get_weekly_off_days()
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
        elif cur.strftime('%A').lower() in off_days and not count_offs:
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
        policies = LeavePolicy.objects.all().order_by('leave_type')
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
        return success('Balance retrieved.', LeaveBalanceSerializer(balance).data)

    def patch(self, request, balance_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        balance, err = self._get_balance(balance_id)
        if err:
            return err

        total = request.data.get('total_days')
        used  = request.data.get('used_days')
        if total is None and used is None:
            return error('Provide at least one of total_days or used_days to adjust.')
        if total is not None:
            try:
                total = float(total)
                if total < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return error('total_days must be a non-negative number.')
            balance.total_days = total
        if used is not None:
            try:
                used = float(used)
                if used < 0:
                    raise ValueError
            except (TypeError, ValueError):
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
    week_offs    = _get_weekoffs_in_range(start, end)
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
        if branch and _role_name(request.user) == 'system_admin':
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
            role = _role_name(request.user)
            if role == 'manager__team_lead' or l1 is None:
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
        if has_approve and _is_hr_role(_role_name(user)) and not _can_hr_access_request(user, leave_request):
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
        if _is_hr_role(_role_name(request.user)) and not _can_hr_access_request(request.user, leave_request):
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
        if _is_hr_role(_role_name(request.user)) and not _can_hr_access_request(request.user, leave_request):
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

        else:
            return error(f'Cannot act on a request with status "{leave_request.status}".')

        leave_request.save()
        logger.info('Leave request %s %sd by %s', leave_request.id, action, request.user.email)
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
        if branch and _role_name(request.user) == 'system_admin':
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
        role = _role_name(request.user)
        if role not in ('system_admin', 'hr_admin', 'hr'):
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
        role = _role_name(request.user)
        if role not in ('system_admin', 'hr_admin', 'hr'):
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
        role = _role_name(request.user)
        if role not in ('system_admin', 'hr_admin', 'hr'):
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
        role = _role_name(request.user)
        if role not in ('system_admin', 'hr_admin', 'hr'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        qs                  = CarryForwardLog.objects.select_related('executed_by').order_by('-created_at')
        page_obj, paginator = paginate(qs, request)
        results             = CarryForwardLogSerializer(page_obj, many=True).data
        return success('Carry-forward history.', paginated_data(paginator, page_obj, results))


# ─── Leave Opening Balance Import ─────────────────────────────────────────────

_LEAVE_IMPORT_ALLOWED_ROLES = frozenset({'system_admin', 'hr_admin', 'hr'})
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
    'remarks': 'remarks',                 'notes': 'remarks',
    'comments': 'remarks',
}

_LEAVE_IMPORT_SAMPLE_HEADERS = [
    'Employee ID', 'Leave Type', 'Financial Year',
    'Opening Balance', 'Leave Allocated', 'Leave Availed',
    'Leave Balance', 'Carry Forward Days', 'Remarks',
]

_LEAVE_IMPORT_SAMPLE_ROWS = [
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '6',  '6',  '2', '10', '0', 'Opening migration'],
    ['RSS00001', 'Earned Leave', 'FY 2026-27', '15', '15', '5', '30', '5', ''],
    ['RSS00002', 'Casual Leave', 'FY 2026-27', '6',  '6',  '0', '12', '0', ''],
    ['RSS00002', 'Sick Leave',   'FY 2026-27', '7',  '7',  '3', '11', '0', ''],
]


def _leave_err(row_num, emp_id, lt, fy, reason) -> dict:
    return {'row': row_num, 'employee_id': emp_id, 'leave_type': lt, 'financial_year': fy, 'reason': reason}


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
    writer.writerow(['Row', 'Employee ID', 'Leave Type', 'Financial Year', 'Reason'])
    for e in errors:
        writer.writerow([e.get('row'), e.get('employee_id'), e.get('leave_type'), e.get('financial_year'), e.get('reason')])
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
        if p.get('leave_type_label'):
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
        emp_id = row.get('employee_id', '')
        raw_lt = row.get('leave_type', '')
        raw_fy = row.get('financial_year', '')

        user = emp_map.get(emp_id)
        if not user:
            errors.append(_leave_err(i, emp_id, raw_lt, raw_fy, f'Employee "{emp_id}" not found or inactive.'))
            fail_count += 1; continue

        lt_code = valid_lt.get(raw_lt.lower())
        if not lt_code:
            errors.append(_leave_err(i, emp_id, raw_lt, raw_fy, f'Leave type "{raw_lt}" is not recognised.'))
            fail_count += 1; continue

        year = _parse_fy_year(raw_fy)
        if year is None:
            errors.append(_leave_err(i, emp_id, raw_lt, raw_fy, f'Financial year "{raw_fy}" is invalid. Use YYYY or "FY 2026-27".'))
            fail_count += 1; continue

        row_key = (user.pk, lt_code, year)
        if row_key in seen:
            errors.append(_leave_err(i, emp_id, raw_lt, raw_fy, 'Duplicate row in file — first occurrence wins.'))
            skip_count += 1; continue
        seen.add(row_key)

        if row_key in existing:
            errors.append(_leave_err(i, emp_id, raw_lt, raw_fy, 'Opening balance already exists for this employee, leave type, and year.'))
            fail_count += 1; continue

        opening, allocated, availed, carry_fwd, err = _parse_leave_row_amounts(row)
        if err:
            errors.append(_leave_err(i, emp_id, raw_lt, raw_fy, err))
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


class LeaveOpeningBalanceImportView(APIView):
    """POST /api/leave/balance/import/ — bulk import opening leave balances (migration tool)."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        role = _role_name(request.user)
        if role not in _LEAVE_IMPORT_ALLOWED_ROLES:
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

        normalized = [_normalize_leave_row(r) for r in rows]
        emp_ids = {r.get('employee_id', '') for r in normalized} - {''}
        emp_map, valid_lt, existing = _load_leave_ref_data(emp_ids)

        start_ts = time.monotonic()
        to_create, errors, fail_count, skip_count = _validate_leave_rows(normalized, emp_map, valid_lt, existing)
        created, batch_errors = _bulk_insert_leave_balances(to_create)
        fail_count += batch_errors

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='leave_opening_balance_import', module='leave',
            changes={'file': uploaded.name, 'total': len(rows), 'created': created, 'failed': fail_count, 'skipped': skip_count},
            ip_address=get_client_ip(request),
        )
        logger.info('Leave balance import by %s: %d created / %d failed / %d skipped (%.1fs)',
                    request.user.email, created, fail_count, skip_count, time.monotonic() - start_ts)

        result = {
            'total_records': len(rows),
            'successful':    created,
            'failed':        fail_count,
            'skipped':       skip_count,
            'errors':        errors[:100],
            'error_report_csv': _build_leave_error_csv(errors) if errors else None,
        }
        return success('Leave opening balance import completed.', result)


class LeaveOpeningBalanceSampleView(APIView):
    """GET /api/leave/balance/import/sample/?format=csv|xlsx — download import template."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _role_name(request.user)
        if role not in _LEAVE_IMPORT_ALLOWED_ROLES:
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
