"""
Historical (month-over-month) analytics for the System Admin / HR
dashboards — headcount growth, leave approval/rejection volume, and payroll
cost, each as a trailing-6-month series. Complements overview.py's
point-in-time snapshots (today's attendance, current payroll readiness,
etc.) with "how did we get here" trend lines.

Every number is computed from real data via the same shared services the
rest of the app already uses (services_headcount.get_headcount for
headcount, LeaveRequest for leave volume, EmployeePayslip for payroll
cost) — nothing here is a new source of truth, just a new time-series view
over existing ones.
"""
from __future__ import annotations

import logging
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.dashboard.views.overview import _DENIED, _is_hr_or_admin
from core.responses import error, success

logger = logging.getLogger(__name__)

_TRAILING_MONTHS = 6
_TTL_TREND = 3600  # 1 h — only the current (still-open) month's figures can change meaningfully within a day


def _month_end(d: date) -> date:
    return (d.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)


def _trailing_month_ends(count: int = _TRAILING_MONTHS) -> list[date]:
    """The last `count` month-end dates, oldest first, ending with the current (in-progress) month."""
    today = date.today()
    return [_month_end(today - relativedelta(months=offset)) for offset in range(count - 1, -1, -1)]


class HeadcountTrendView(APIView):
    """GET /dashboard/trends/headcount/ — total active headcount as of the
    end of each of the last 6 months, reusing get_headcount's own
    historical `as_of` reconstruction so this always matches what
    Employees > As Of would show for the same date."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        cache_key = f'dashboard:trends:headcount:{date.today().isoformat()}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success('Headcount trend retrieved.', data=cached)

        from apps.accounts.services_headcount import get_headcount

        series = [
            {'label': month_end.strftime('%b %Y'), 'count': get_headcount(as_of=month_end)['total']}
            for month_end in _trailing_month_ends()
        ]
        data = {'series': series}
        cache.set(cache_key, data, _TTL_TREND)
        return success('Headcount trend retrieved.', data=data)


class LeaveTrendView(APIView):
    """GET /dashboard/trends/leave/ — approved vs. rejected leave requests
    per month for the last 6 months, grouped by when the request was
    raised (created_at), not when it was decided."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        cache_key = f'dashboard:trends:leave:{date.today().isoformat()}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success('Leave trend retrieved.', data=cached)

        from apps.hrms.models import LeaveRequest, REQ_APPROVED, REQ_REJECTED

        month_ends = _trailing_month_ends()
        range_start = month_ends[0].replace(day=1)
        rows = (
            LeaveRequest.objects
            .filter(created_at__date__gte=range_start, status__in=[REQ_APPROVED, REQ_REJECTED])
            .values_list('status', 'created_at')
        )
        counts: dict[tuple[int, int], dict[str, int]] = {}
        for status, created_at in rows:
            key = (created_at.year, created_at.month)
            bucket = counts.setdefault(key, {'approved': 0, 'rejected': 0})
            bucket['approved' if status == REQ_APPROVED else 'rejected'] += 1

        series = [
            {
                'label': month_end.strftime('%b %Y'),
                'approved': counts.get((month_end.year, month_end.month), {}).get('approved', 0),
                'rejected': counts.get((month_end.year, month_end.month), {}).get('rejected', 0),
            }
            for month_end in month_ends
        ]
        data = {'series': series}
        cache.set(cache_key, data, _TTL_TREND)
        return success('Leave trend retrieved.', data=data)


class PayrollCostTrendView(APIView):
    """GET /dashboard/trends/payroll-cost/ — total net pay per payroll
    cycle for the last 6 cycles that actually reached payslip generation
    (drafts/cancelled cycles carry no meaningful cost yet)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_or_admin(request.user):
            return error(_DENIED, http_status=403)

        cache_key = f'dashboard:trends:payroll-cost:{date.today().isoformat()}'
        cached = cache.get(cache_key)
        if cached is not None:
            return success('Payroll cost trend retrieved.', data=cached)

        from apps.payroll.models import PayrollCycle

        excluded_statuses = [PayrollCycle.STATUS_DRAFT, PayrollCycle.STATUS_CANCELLED, PayrollCycle.STATUS_ATTENDANCE_PENDING, PayrollCycle.STATUS_ATTENDANCE_APPROVED, PayrollCycle.STATUS_PROCESSING]
        cycles = (
            PayrollCycle.objects
            .exclude(status__in=excluded_statuses)
            .order_by('-cycle_start')[:_TRAILING_MONTHS]
        )
        series = [
            {
                'label': cycle.cycle_start.strftime('%b %Y'),
                'amount': float(cycle.payslips.aggregate(total=Sum('net_pay'))['total'] or 0),
            }
            for cycle in reversed(list(cycles))
        ]
        data = {'series': series}
        cache.set(cache_key, data, _TTL_TREND)
        return success('Payroll cost trend retrieved.', data=data)
