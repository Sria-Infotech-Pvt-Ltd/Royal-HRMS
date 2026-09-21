"""
Payroll analytics — company/branch-wide cost figures, as opposed to any
single employee's own payslip (see views/payslips.py) or a single cycle's
processing status (see views/cycles.py).

Both views below share the same three concerns:
  - payroll.view is checked manually, not via DRF permission_classes, the
    same convention BranchPayrollStatusView (views/cycles.py) already uses
    for a read-only, company/branch-wide payroll view.
  - branch scoping reuses _is_admin/_resolve_user_branch from views/cycles.py
    verbatim rather than reimplementing them — admin (settings.edit) sees
    every active branch, everyone else sees only their own.
  - "the period" is resolved PER BRANCH, not once for the whole request —
    branches can run payroll on different cadences (see PayrollSettings'
    per-branch cycle_start_day/cycle_end_day), so there is no single
    company-wide "current cycle" to default to.
"""
from decimal import Decimal
from typing import Optional

from django.db.models import Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success
from apps.branch.models import Branch
from apps.payroll.models import EmployeePayslip, PayrollCycle
from apps.payroll.views.cycles import _is_admin, _resolve_user_branch

_REQUIRED_PERMISSION = 'payroll.view'

_NOT_BRANCH_ASSIGNED_MESSAGE = 'Your account is not assigned to a branch. Contact an administrator.'
_INVALID_PERIOD_MESSAGE = 'Invalid month or offset parameter. Use ?month=YYYY-MM or ?offset=N.'


def _resolve_branches(user) -> list[Branch]:
    """Same admin-vs-branch-scoped-user split BranchPayrollStatusView uses
    (views/cycles.py) — reused here rather than reimplemented."""
    if _is_admin(user):
        return list(Branch.objects.filter(status=Branch.STATUS_ACTIVE).order_by('branch_name'))
    branch_obj = _resolve_user_branch(user)
    return [branch_obj] if branch_obj else []


def _parse_month_param(request) -> tuple[Optional[int], Optional[int]]:
    """(None, None) when ?month= is absent. Raises ValueError for a
    present-but-malformed value — callers turn that into a 400."""
    raw = request.query_params.get('month')
    if not raw:
        return None, None
    year_str, sep, month_str = raw.partition('-')
    if not sep:
        raise ValueError('month must be YYYY-MM')
    year, month = int(year_str), int(month_str)
    if not (1 <= month <= 12):
        raise ValueError('month out of range')
    return year, month


def _parse_offset_param(request) -> int:
    """?offset=N, default 0. Raises ValueError for a negative/non-integer
    value — callers turn that into a 400."""
    offset = int(request.query_params.get('offset', '0'))
    if offset < 0:
        raise ValueError('offset must be >= 0')
    return offset


def _resolve_period_cycle(
    branch: Branch, year: Optional[int], month: Optional[int], offset: int,
) -> Optional[PayrollCycle]:
    """
    Resolves "the period" for ONE branch. An explicit ?month=YYYY-MM (year/
    month both not None) wins over ?offset=N — callers only pass a
    meaningful offset when month wasn't given. offset=0 is that branch's own
    latest non-cancelled cycle (mirrors BranchPayrollStatusView's own
    "latest non-cancelled cycle" convention), offset=1 the one before that,
    etc. Cancelled cycles are excluded either way — a cancelled cycle was
    never actually paid, so it shouldn't count as "the period" for cost
    figures.
    """
    qs = PayrollCycle.objects.filter(branch=branch).exclude(status=PayrollCycle.STATUS_CANCELLED)
    if year is not None and month is not None:
        return qs.filter(cycle_start__year=year, cycle_start__month=month).order_by('-cycle_start').first()
    matches = list(qs.order_by('-cycle_start')[offset:offset + 1])
    return matches[0] if matches else None


def _aggregate_payslips(cycle_ids) -> dict:
    aggregates = EmployeePayslip.objects.filter(cycle_id__in=cycle_ids).aggregate(
        gross_earnings=Sum('gross_earnings'),
        net_pay=Sum('net_pay'),
        employee_count=Count('id'),
    )
    return {
        'gross_earnings': str(aggregates['gross_earnings'] or Decimal('0')),
        'net_pay': str(aggregates['net_pay'] or Decimal('0')),
        'employee_count': aggregates['employee_count'] or 0,
    }


class PayrollCostSummaryView(APIView):
    """
    Company-wide (admin) or own-branch (everyone else) payroll cost totals
    for one resolved period — real ORM Sum()/Count() aggregates across every
    EmployeePayslip row in each included branch's resolved cycle, not a
    per-employee breakdown (see views/payslips.py for that).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, _REQUIRED_PERMISSION):
            return error('Access denied.', http_status=403)

        try:
            year, month = _parse_month_param(request)
            offset = _parse_offset_param(request)
        except ValueError:
            return error(_INVALID_PERIOD_MESSAGE, http_status=400)

        branches = _resolve_branches(request.user)
        if not branches:
            return error(_NOT_BRANCH_ASSIGNED_MESSAGE, http_status=400)

        cycle_ids = []
        branches_included = []
        for branch in branches:
            cycle = _resolve_period_cycle(branch, year, month, offset)
            if cycle is None:
                continue
            cycle_ids.append(cycle.id)
            branches_included.append({
                'branch_id': str(branch.id),
                'branch_name': branch.branch_name,
                'cycle_id': str(cycle.id),
                'cycle_start': str(cycle.cycle_start),
                'cycle_end': str(cycle.cycle_end),
            })

        data = _aggregate_payslips(cycle_ids)
        data['branches_included'] = branches_included
        return success('Payroll cost summary retrieved.', data)


class BranchPayrollBreakdownView(APIView):
    """
    Per-branch payroll cost totals for one resolved period, ordered by net
    pay descending. Admin sees every active branch (one row each, including
    a zeroed row for a branch with no matching cycle); a branch-scoped
    caller's own _resolve_branches() result is a single branch, so this
    naturally returns a single-row list rather than an error.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, _REQUIRED_PERMISSION):
            return error('Access denied.', http_status=403)

        try:
            year, month = _parse_month_param(request)
            offset = _parse_offset_param(request)
        except ValueError:
            return error(_INVALID_PERIOD_MESSAGE, http_status=400)

        branches = _resolve_branches(request.user)
        if not branches:
            return error(_NOT_BRANCH_ASSIGNED_MESSAGE, http_status=400)

        rows = []
        for branch in branches:
            cycle = _resolve_period_cycle(branch, year, month, offset)
            row = {
                'branch_id': str(branch.id),
                'branch_name': branch.branch_name,
                'branch_code': getattr(branch, 'branch_code', ''),
            }
            if cycle is None:
                row.update({
                    'cycle_id': None, 'cycle_start': None, 'cycle_end': None,
                    'gross_earnings': '0', 'net_pay': '0', 'employee_count': 0,
                })
            else:
                row.update({
                    'cycle_id': str(cycle.id), 'cycle_start': str(cycle.cycle_start), 'cycle_end': str(cycle.cycle_end),
                })
                row.update(_aggregate_payslips([cycle.id]))
            rows.append(row)

        rows.sort(key=lambda r: Decimal(r['net_pay']), reverse=True)
        return success('Branch payroll breakdown retrieved.', rows)
