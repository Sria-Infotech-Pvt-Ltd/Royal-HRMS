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

# ─── Carry Forward ────────────────────────────────────────────────────────────





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


