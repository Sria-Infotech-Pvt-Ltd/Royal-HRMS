import logging
from datetime import date

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_REJECTED,
    LEAVE_LWP, LEAVE_TYPE_CHOICES,
    REQ_APPROVED, REQ_CANCELLED, REQ_L2_PENDING, REQ_PENDING, REQ_REJECTED,
    LeaveBalance, LeavePolicy, LeaveRequest,
)
from ..serializers import (
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
    return date.today().year


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


def _approval_scope_filter(user) -> 'Q':
    """
    Scope filter for the approval queue — enforces both role and status visibility.
    manager   → pending requests from direct reports only (L1 queue)
    hr_admin  → l2_pending requests from same branch only (L2 queue)
    system_admin → all statuses, all employees except own
    """
    role = _role_name(user)
    if role == 'system_admin':
        return ~Q(employee=user)
    if role == 'hr_admin':
        branch = _user_branch(user)
        if branch:
            return Q(employee__branch=branch, status=REQ_L2_PENDING) & ~Q(employee=user)
        return Q(employee__hr=user, status=REQ_L2_PENDING) & ~Q(employee=user)
    if role == 'manager':
        return Q(employee__reporting_manager=user, status=REQ_PENDING) & ~Q(employee=user)
    return Q(employee=user)


def _calendar_scope_filter(user) -> 'Q':
    """
    Scope filter for the team calendar.
    employee → all approved (to see who's out); manager → team + own; hr_admin → branch; system_admin → all.
    """
    role = _role_name(user)
    if role == 'system_admin':
        return Q()
    if role == 'hr_admin':
        return Q(employee__branch=user.branch) if user.branch else Q()
    if role == 'manager':
        return Q(employee__reporting_manager=user) | Q(employee=user)
    return Q()  # employee: see all approved leaves to plan around absences


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

            # Managers skip L1 — their leave routes directly to HR (L2)
            if _role_name(request.user) == 'manager':
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
        if has_approve and _role_name(user) == 'hr_admin' and not _can_hr_access_request(user, leave_request):
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
        if _role_name(request.user) == 'hr_admin' and not _can_hr_access_request(request.user, leave_request):
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
        if _role_name(request.user) == 'hr_admin' and not _can_hr_access_request(request.user, leave_request):
            return error('You can only approve leave requests for employees in your branch.', http_status=status.HTTP_403_FORBIDDEN)

        action  = request.data.get('action')
        remarks = (request.data.get('remarks') or request.data.get('reason') or '').strip()

        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')

        now = timezone.now()

        if leave_request.status == REQ_PENDING:
            leave_request.l1_approver    = request.user
            leave_request.l1_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
            leave_request.l1_remarks     = remarks
            leave_request.l1_actioned_at = now

            if action == 'reject':
                leave_request.status = REQ_REJECTED
            elif leave_request.l2_approver_id:
                leave_request.status = REQ_L2_PENDING
            else:
                leave_request.status = REQ_APPROVED
                _deduct_balance_safe(leave_request)

        elif leave_request.status == REQ_L2_PENDING:
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
