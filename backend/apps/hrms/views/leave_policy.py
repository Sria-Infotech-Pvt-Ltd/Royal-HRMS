import base64
import csv
import io
import logging
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

from apps.hrms.views.leave_shared import *  # noqa: F401,F403







































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
            'bereavement': {'annual_days': 5, 'can_carry_forward': False, 'max_carry_forward_days': 0, 'policy_note': 'For the loss of an immediate family member.'},
            # Not a fixed annual allotment (earned per instance of extra worked
            # time, credited separately) — annual_days=0 here is informational
            # only; neither accrual task touches this policy's balance.
            'comp_off':    {'annual_days': 0,  'can_carry_forward': True,  'max_carry_forward_days': 5, 'carry_forward_type': 'limited', 'policy_note': 'Earned for approved extra worked time (e.g. weekend/holiday work).'},
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




