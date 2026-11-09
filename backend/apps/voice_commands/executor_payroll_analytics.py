"""
Voice payroll analytics: pending payroll cycles, company/branch payroll cost summary, per-branch breakdown.

Approach (approved for Aira): no new payroll HTTP views. The pending-cycles intent dispatches through the existing
AttendancePendingCyclesView, like the other voice intents. The two cost intents read the existing payroll models
directly and reuse the existing payroll permission/branch helpers:
  - permission: core.permissions.has_perm(user, 'payroll.view')  (seat-aware; the check BranchPayrollStatusView uses)
  - scoping:    payroll.views.shared._is_admin (superuser or settings.edit => every active branch) and
                _resolve_user_branch (everyone else => only their own assigned branch)
Only aggregate figures are read (Sum/Count); no per-employee payslip data is fetched.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db.models import Count, Sum
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.branch.models import Branch
from apps.payroll.models import EmployeePayslip, PayrollCycle
from apps.payroll.views.attendance_approval import AttendancePendingCyclesView
from apps.payroll.views.shared import _is_admin, _resolve_user_branch
from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import text
from apps.voice_commands.payroll_period_extractor import extract_period_month, extract_period_offset
from core.permissions import has_perm

_REQUIRED_PERMISSION = 'payroll.view'
_api_request_factory = APIRequestFactory()

_ACCESS_DENIED_MESSAGE = {
    'en': "You don't have permission to view payroll analytics.",
    'hi': 'आपको पेरोल एनालिटिक्स देखने की अनुमति नहीं है।',
}
_NO_BRANCH_MESSAGE = {
    'en': 'Your account is not assigned to a branch. Contact an administrator.',
    'hi': 'आपका खाता किसी शाखा से जुड़ा नहीं है। कृपया व्यवस्थापक से संपर्क करें।',
}
_PENDING_CYCLES_FAILED_MESSAGE = {
    'en': 'Could not retrieve pending payroll cycles.',
    'hi': 'लंबित पेरोल साइकिल प्राप्त नहीं की जा सकीं।',
}
_NO_PENDING_CYCLES_MESSAGE = {
    'en': 'No payroll cycles are currently awaiting your approval.',
    'hi': 'फिलहाल आपकी स्वीकृति के लिए कोई पेरोल साइकिल लंबित नहीं है।',
}
_PENDING_CYCLES_TEMPLATE = {
    'en': 'You have {count} payroll cycle(s) awaiting your approval.',
    'hi': 'आपकी स्वीकृति के लिए {count} पेरोल साइकिल लंबित हैं।',
}
_NO_COST_DATA_MESSAGE = {
    'en': 'No payroll data was found for that period.',
    'hi': 'उस अवधि के लिए कोई पेरोल डेटा नहीं मिला।',
}
# Company/branch-wide aggregates the caller already holds payroll.view for - never another employee's private payslip.
# The panel/toast (`message`) keeps the full figures, but they are NOT read aloud (see the *_SPEECH_* templates below):
# rupee totals and per-branch pay are exactly what a bystander within earshot of the speaker should not hear.
_COST_SUMMARY_TEMPLATE = {
    'en': (
        'For the selected period, gross earnings were ₹{gross_earnings}, '
        'net pay was ₹{net_pay}, across {employee_count} employees.'
    ),
    'hi': (
        'चयनित अवधि के लिए, सकल आय ₹{gross_earnings} थी, '
        'शुद्ध वेतन ₹{net_pay} था, कुल {employee_count} कर्मचारियों में।'
    ),
}
_NO_BREAKDOWN_DATA_MESSAGE = {
    'en': 'No branch payroll data was found for that period.',
    'hi': 'उस अवधि के लिए कोई शाखा पेरोल डेटा नहीं मिला।',
}
_SINGLE_BRANCH_TEMPLATE = {
    'en': 'For {branch_name}, net pay for the period was ₹{net_pay}, across {employee_count} employees.',
    'hi': '{branch_name} के लिए, अवधि का शुद्ध वेतन ₹{net_pay} था, कुल {employee_count} कर्मचारियों में।',
}
# Only the SPOKEN summary is capped to the top 3 branches; the full list is always returned as `data` for the panel.
_TOP_BRANCHES_TEMPLATE = {
    'en': 'Top branches by net pay: {branches}.',
    'hi': 'शुद्ध वेतन के अनुसार शीर्ष शाखाएं: {branches}।',
}

# Speech-safe stand-ins (ExecutionResult.speech_message, spoken instead of `message`, muted or not). They carry only a
# count of people/branches inside the caller's own scope - no gross/net amounts, no branch names, no per-branch pay, no
# employee-level detail - and point at the screen for the figures. Same convention executor_payroll.py's payslip
# intents use ("ready to view"). The "no data"/error messages hold no figures and are spoken unchanged.
_COST_SUMMARY_SPEECH_MESSAGE = {
    'en': 'Your payroll cost summary for {employee_count} employees across {branch_count} branch(es) is ready to view on screen.',
    'hi': 'आपका पेरोल लागत सारांश, {branch_count} शाखा में {employee_count} कर्मचारियों के लिए, स्क्रीन पर देखने के लिए तैयार है।',
}
_BREAKDOWN_SPEECH_MESSAGE = {
    'en': 'Your branch payroll breakdown for {branch_count} branch(es) is ready to view on screen.',
    'hi': 'आपका शाखा पेरोल विवरण, {branch_count} शाखा के लिए, स्क्रीन पर देखने के लिए तैयार है।',
}
_SINGLE_BRANCH_SPEECH_MESSAGE = {
    'en': 'Your branch payroll summary for {employee_count} employees is ready to view on screen.',
    'hi': 'आपका शाखा पेरोल सारांश, {employee_count} कर्मचारियों के लिए, स्क्रीन पर देखने के लिए तैयार है।',
}


def execute_check_pending_payroll_cycles(request) -> ExecutionResult:
    """Dispatches through the existing AttendancePendingCyclesView, whose own manager-vs-HR scoping and permission
    check (_can_view_approvals) stay authoritative - voice neither reimplements nor bypasses them."""
    django_request = _api_request_factory.get('/api/payroll/cycles/pending-approval/')
    force_authenticate(django_request, user=request.user)
    response = AttendancePendingCyclesView.as_view()(django_request)

    if response.status_code == 403:
        return ExecutionResult(success=False, message=text(_ACCESS_DENIED_MESSAGE), data=response.data)
    if response.status_code >= 400:
        message = text(_PENDING_CYCLES_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic - see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    cycles = response.data.get('data') if isinstance(response.data, dict) else None
    count = len(cycles) if isinstance(cycles, list) else 0
    if count == 0:
        return ExecutionResult(success=True, message=text(_NO_PENDING_CYCLES_MESSAGE), data=cycles)
    return ExecutionResult(success=True, message=text(_PENDING_CYCLES_TEMPLATE).format(count=count), data=cycles)


def _visible_branches(user) -> list[Branch]:
    """Admin (superuser or settings.edit) sees every active branch; everyone else only their own assigned branch."""
    if _is_admin(user):
        return list(Branch.objects.filter(status=Branch.STATUS_ACTIVE).order_by('branch_name'))
    own = _resolve_user_branch(user)
    return [own] if own else []


def _resolve_period_cycle(branch: Branch, month: Optional[str], offset: int) -> Optional[PayrollCycle]:
    """One branch's cycle for the period. An explicit month ('YYYY-MM') wins over offset; offset 0 is the branch's
    latest non-cancelled cycle, 1 the one before it. Cancelled cycles never count (they were never paid)."""
    cycles = PayrollCycle.objects.filter(branch=branch).exclude(status=PayrollCycle.STATUS_CANCELLED)
    if month:
        year_str, _, month_str = month.partition('-')
        return cycles.filter(
            cycle_start__year=int(year_str), cycle_start__month=int(month_str),
        ).order_by('-cycle_start').first()
    return cycles.order_by('-cycle_start')[offset:offset + 1].first()


def _period_args(raw_text: str) -> tuple[Optional[str], int]:
    month = extract_period_month(raw_text or '')
    return month, (0 if month else extract_period_offset(raw_text or ''))


def _totals(cycle_ids) -> dict:
    agg = EmployeePayslip.objects.filter(cycle_id__in=cycle_ids).aggregate(
        gross_earnings=Sum('gross_earnings'), net_pay=Sum('net_pay'), employee_count=Count('id'),
    )
    return {
        'gross_earnings': str(agg['gross_earnings'] or Decimal('0')),
        'net_pay': str(agg['net_pay'] or Decimal('0')),
        'employee_count': agg['employee_count'] or 0,
    }


def _cycle_info(branch: Branch, cycle: PayrollCycle) -> dict:
    return {
        'branch_id': str(branch.id), 'branch_name': branch.branch_name, 'cycle_id': str(cycle.id),
        'cycle_start': str(cycle.cycle_start), 'cycle_end': str(cycle.cycle_end), 'cycle_status': cycle.status,
    }


def _scope_or_failure(request):
    """(branches, None) when the caller may see payroll analytics, else ([], ExecutionResult explaining why)."""
    if not has_perm(request.user, _REQUIRED_PERMISSION):
        return [], ExecutionResult(success=False, message=text(_ACCESS_DENIED_MESSAGE))
    branches = _visible_branches(request.user)
    if not branches:
        return [], ExecutionResult(success=False, message=text(_NO_BRANCH_MESSAGE))
    return branches, None


def execute_check_payroll_cost_summary(request, raw_text: str = '') -> ExecutionResult:
    """Company-wide (admin) or own-branch totals for the resolved period of each visible branch."""
    branches, failure = _scope_or_failure(request)
    if failure:
        return failure
    month, offset = _period_args(raw_text)
    included, cycle_ids = [], []
    for branch in branches:
        cycle = _resolve_period_cycle(branch, month, offset)
        if cycle is not None:
            cycle_ids.append(cycle.id)
            included.append(_cycle_info(branch, cycle))
    data = _totals(cycle_ids)
    data['branches_included'] = included
    if not data['employee_count']:
        return ExecutionResult(success=True, message=text(_NO_COST_DATA_MESSAGE), data=data)
    message = text(_COST_SUMMARY_TEMPLATE).format(
        gross_earnings=data['gross_earnings'], net_pay=data['net_pay'], employee_count=data['employee_count'],
    )
    speech_message = text(_COST_SUMMARY_SPEECH_MESSAGE).format(
        employee_count=data['employee_count'], branch_count=len(included),
    )
    return ExecutionResult(success=True, message=message, data=data, speech_message=speech_message)


def execute_check_branch_payroll_breakdown(request, raw_text: str = '') -> ExecutionResult:
    """Per-branch totals for the resolved period, highest net pay first. A branch-scoped caller gets only their branch."""
    branches, failure = _scope_or_failure(request)
    if failure:
        return failure
    month, offset = _period_args(raw_text)
    rows = []
    for branch in branches:
        cycle = _resolve_period_cycle(branch, month, offset)
        if cycle is None:
            continue
        row = _totals([cycle.id])
        if row['employee_count']:
            row.update(_cycle_info(branch, cycle))
            rows.append(row)
    rows.sort(key=lambda row: Decimal(row['net_pay']), reverse=True)
    if not rows:
        return ExecutionResult(success=True, message=text(_NO_BREAKDOWN_DATA_MESSAGE), data=rows)
    if len(rows) == 1:
        message = text(_SINGLE_BRANCH_TEMPLATE).format(
            branch_name=rows[0]['branch_name'], net_pay=rows[0]['net_pay'], employee_count=rows[0]['employee_count'],
        )
        speech_message = text(_SINGLE_BRANCH_SPEECH_MESSAGE).format(employee_count=rows[0]['employee_count'])
        return ExecutionResult(success=True, message=message, data=rows, speech_message=speech_message)
    top = ', '.join(f"{row['branch_name']}: ₹{row['net_pay']}" for row in rows[:3])
    speech_message = text(_BREAKDOWN_SPEECH_MESSAGE).format(branch_count=len(rows))
    return ExecutionResult(
        success=True, message=text(_TOP_BRANCHES_TEMPLATE).format(branches=top), data=rows,
        speech_message=speech_message,
    )
