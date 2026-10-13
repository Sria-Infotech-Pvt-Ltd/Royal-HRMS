"""
HR records leave on an employee's behalf (the Leave dialog in the Employee Directory).

  POST /api/leave/requests/record/   body: employee_id, leave_type, start_date, end_date,
                                     duration (full_day / first_half / second_half), reason (optional)

Unlike an employee's own application (LeaveRequestListCreateView.post) this is final the moment it is
recorded: no approval chain, the balance is deducted and attendance is marked on-leave straight away. That
is why it needs its own permission (leave.record), why the target must be within the recorder's scope, and
why nobody can record leave for themselves.
"""
import copy
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from ..models import (
    APPROVAL_APPROVED, DURATION_CHOICES, DURATION_FULL, LEAVE_LWP, LEAVE_TYPE_CHOICES,
    REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING, LeaveBalance, LeaveRequest, WorkFromHomeRequest,
)
from ..serializers import LeaveRequestSerializer
from .leave_shared import (
    _calc_working_days, _deduct_balance_safe, _sync_leave_attendance, _validate_leave_policy,
    _zero_working_days_reason,
)

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (REQ_PENDING, REQ_L2_PENDING, REQ_APPROVED)
_DENIED = 'You do not have permission to record leave.'


class LeaveRecordSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    leave_type  = serializers.ChoiceField(choices=[code for code, _ in LEAVE_TYPE_CHOICES])
    duration    = serializers.ChoiceField(choices=[code for code, _ in DURATION_CHOICES], default=DURATION_FULL)
    start_date  = serializers.DateField()
    end_date    = serializers.DateField()
    reason      = serializers.CharField(required=False, allow_blank=True, max_length=300, default='')

    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError('End date is before the start date.')
        if data['duration'] != DURATION_FULL and data['start_date'] != data['end_date']:
            raise serializers.ValidationError('Half day applies to a single date only.')
        return data


def _find_target(request, employee_code):
    from apps.accounts.models import User
    from apps.accounts.views.shared import _employee_out_of_branch_scope
    target = User.objects.filter(employee_id=employee_code, is_active=True).first()
    if target is None or _employee_out_of_branch_scope(request.user, target):
        return None
    return target


def _clash_message(target, start, end):
    if LeaveRequest.objects.filter(
        employee=target, status__in=_ACTIVE_STATUSES, start_date__lte=end, end_date__gte=start,
    ).exists():
        return 'This employee already has leave on those dates.'
    if WorkFromHomeRequest.objects.filter(
        employee=target, status__in=_ACTIVE_STATUSES, start_date__lte=end, end_date__gte=start,
    ).exists():
        return 'This employee has a work-from-home request on those dates.'
    return None


def _without_application_windows(policy):
    """Recording leave is HR's call, so the windows that govern an employee APPLYING (advance notice,
    back-dating, how far ahead, attachment) are lifted. Eligibility (branch, department, gender, service)
    and duration rules still apply. A copy is adjusted; the stored policy is never touched."""
    relaxed = copy.copy(policy)
    relaxed.minimum_notice_period = 0
    relaxed.allow_backdated_leave = True
    relaxed.maximum_backdated_days = 0
    relaxed.allow_future_leave = True
    relaxed.maximum_future_days = 0
    relaxed.attachment_required = False
    return relaxed


def _lop_for_shortfall(policy, balance, total_days):
    """(lop_days, error). Mirrors the employee's own application: excess days become LOP only when the
    policy converts them; an overdraft is allowed only when the policy allows it."""
    available = float(balance.total_days - balance.used_days)
    if total_days <= available:
        return 0.0, None
    if policy and policy.convert_to_lop:
        return round(total_days - available, 1), None
    if policy and policy.allow_negative_balance:
        return 0.0, None
    return 0.0, f'Only {available:g} day(s) available. Record the excess as Loss of Pay.'


class LeaveRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'leave.record'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        serializer = LeaveRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        data = serializer.validated_data

        target = _find_target(request, data['employee_id'])
        if target is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        if target.pk == request.user.pk:
            return error('You cannot record leave for yourself.', http_status=status.HTTP_403_FORBIDDEN)

        from core.cache_service import LeavePolicyCacheService
        policy = LeavePolicyCacheService.get(data['leave_type'])
        total_days = _calc_working_days(data['start_date'], data['end_date'], data['duration'], policy, target)
        if total_days <= 0:
            return error(_zero_working_days_reason(data['start_date'], data['end_date'], policy, target))
        if policy:
            message = _validate_leave_policy(
                _without_application_windows(policy), target, data['duration'], total_days,
                data['start_date'], data['end_date'], True, data['start_date'],
            )
            if message:
                return error(message)

        with transaction.atomic():
            from apps.accounts.models import User
            User.objects.select_for_update().get(pk=target.pk)
            clash = _clash_message(target, data['start_date'], data['end_date'])
            if clash:
                return error(clash)
            lop_days = 0.0
            if data['leave_type'] != LEAVE_LWP:
                balance = LeaveBalance.objects.select_for_update().filter(
                    employee=target, leave_type=data['leave_type'], year=data['start_date'].year,
                ).first()
                if balance is None:
                    return error(f'No {data["leave_type"]} balance for {data["start_date"].year}.')
                lop_days, shortfall = _lop_for_shortfall(policy, balance, total_days)
                if shortfall:
                    return error(shortfall)

            now = timezone.now()
            leave = LeaveRequest.objects.create(
                employee=target, leave_type=data['leave_type'], duration=data['duration'],
                start_date=data['start_date'], end_date=data['end_date'], total_days=total_days,
                lop_days=lop_days, reason=data['reason'], is_lwp=(data['leave_type'] == LEAVE_LWP),
                status=REQ_APPROVED, l2_approver=request.user, l2_status=APPROVAL_APPROVED,
                l2_remarks='Recorded by HR', l2_actioned_at=now,
            )
            problem = _deduct_balance_safe(leave)
            if problem:
                transaction.set_rollback(True)
                return error(problem)
            leave.save()
            _sync_leave_attendance(leave)

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='leave_recorded', module='leave', object_id=str(leave.id),
            changes={'employee': target.full_name, 'leave_type': leave.leave_type, 'days': float(total_days)},
            branch=target.branch, ip_address=get_client_ip(request),
        )
        logger.info('Leave %s recorded for %s by %s (%s days)', leave.id, target.email, request.user.email, total_days)
        return success('Leave recorded.', LeaveRequestSerializer(leave, context={'request': request}).data,
                       http_status=status.HTTP_201_CREATED)
