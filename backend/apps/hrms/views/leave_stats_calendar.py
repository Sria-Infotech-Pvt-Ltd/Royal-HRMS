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


