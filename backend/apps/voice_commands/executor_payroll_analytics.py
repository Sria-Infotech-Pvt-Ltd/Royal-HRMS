from __future__ import annotations

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.payroll.views.analytics import BranchPayrollBreakdownView, PayrollCostSummaryView
from apps.payroll.views.attendance_approval import AttendancePendingCyclesView

from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import text
from apps.voice_commands.payroll_period_extractor import extract_period_month, extract_period_offset

# Shared factory — same convention executor_payroll.py's own module-level
# _api_request_factory follows (building a request through it touches no
# database/shared state, just Django's request/response plumbing).
_api_request_factory = APIRequestFactory()

_ACCESS_DENIED_MESSAGE = {
    'en': "You don't have permission to view payroll analytics.",
    'hi': 'आपको पेरोल एनालिटिक्स देखने की अनुमति नहीं है।',
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

_COST_SUMMARY_FAILED_MESSAGE = {
    'en': 'Could not retrieve the payroll cost summary.',
    'hi': 'पेरोल लागत सारांश प्राप्त नहीं किया जा सका।',
}
_NO_COST_DATA_MESSAGE = {
    'en': 'No payroll data was found for that period.',
    'hi': 'उस अवधि के लिए कोई पेरोल डेटा नहीं मिला।',
}
# Read aloud in full, unlike executor_payroll.py's payslip messages — this is
# company/branch-wide aggregate data the caller already holds payroll.view
# for, not another employee's private payslip, so no speech_message
# redaction is set here (ExecutionResult.speech_message stays None, meaning
# "speak `message` unchanged" — see that field's own docstring).
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

_BREAKDOWN_FAILED_MESSAGE = {
    'en': 'Could not retrieve the branch payroll breakdown.',
    'hi': 'शाखा पेरोल विवरण प्राप्त नहीं किया जा सका।',
}
_NO_BREAKDOWN_DATA_MESSAGE = {
    'en': 'No branch payroll data was found for that period.',
    'hi': 'उस अवधि के लिए कोई शाखा पेरोल डेटा नहीं मिला।',
}
# Single-branch phrasing for a branch-scoped caller (BranchPayrollBreakdownView
# naturally returns one row for them, not an error — see that view's own
# docstring).
_SINGLE_BRANCH_TEMPLATE = {
    'en': 'For {branch_name}, net pay for the period was ₹{net_pay}, across {employee_count} employees.',
    'hi': '{branch_name} के लिए, अवधि का शुद्ध वेतन ₹{net_pay} था, कुल {employee_count} कर्मचारियों में।',
}
# Full data is always returned for the UI (data=... below) — only the
# SPOKEN summary is capped to the top 3 branches by net pay, since reading
# out every branch aloud for a large company would be unusably long.
_TOP_BRANCHES_TEMPLATE = {
    'en': 'Top branches by net pay: {branches}.',
    'hi': 'शुद्ध वेतन के अनुसार शीर्ष शाखाएं: {branches}।',
}


def _period_query_params(raw_text: str) -> dict:
    """
    Shared period-resolution for the two analytics intents below — explicit
    month wins over offset, mirroring apps.payroll.views.analytics'
    _resolve_period_cycle's own precedence (and its own docstring on why).
    raw_text is the caller's raw utterance, forwarded by
    conversation.py/execute_intent's generic dispatch path via
    slots['raw_text'] — empty string when absent (e.g. typed/no slots).
    """
    month = extract_period_month(raw_text)
    if month:
        return {'month': month}
    offset = extract_period_offset(raw_text)
    return {'offset': str(offset)} if offset else {}


def _dispatch_get(view_cls, path: str, request, params: dict):
    """Small shared dispatch helper — same APIRequestFactory/force_authenticate
    pattern executor_payroll.py's own functions use to call a real view
    rather than duplicating its query/permission logic here."""
    django_request = _api_request_factory.get(path, params)
    force_authenticate(django_request, user=request.user)
    return view_cls.as_view()(django_request)


def _failure_result(response, fallback_message: dict) -> ExecutionResult:
    message = text(fallback_message)
    if response.status_code == 403:
        message = text(_ACCESS_DENIED_MESSAGE)
    elif isinstance(response.data, dict) and response.data.get('message'):
        message = response.data['message']  # external, dynamic — see execute_apply_leave's own note
    return ExecutionResult(success=False, message=message, data=response.data)


def execute_check_pending_payroll_cycles(request) -> ExecutionResult:
    """
    Dispatches through the existing AttendancePendingCyclesView
    (payroll/views/attendance_approval.py) rather than reimplementing its
    manager-vs-HR pending-cycle scoping here — that view already IS "check
    pending payroll cycles" for a real HTTP caller; this just gives it a
    voice front door, same house style as execute_acknowledge_payslip/
    execute_raise_payslip_query in executor_payroll.py.
    """
    response = _dispatch_get(AttendancePendingCyclesView, '/api/payroll/cycles/pending-approval/', request, {})

    if response.status_code >= 400:
        return _failure_result(response, _PENDING_CYCLES_FAILED_MESSAGE)

    cycles = response.data.get('data') if isinstance(response.data, dict) else None
    count = len(cycles) if isinstance(cycles, list) else 0

    if count == 0:
        return ExecutionResult(success=True, message=text(_NO_PENDING_CYCLES_MESSAGE), data=cycles)

    message = text(_PENDING_CYCLES_TEMPLATE).format(count=count)
    return ExecutionResult(success=True, message=message, data=cycles)


def execute_check_payroll_cost_summary(request, raw_text: str = '') -> ExecutionResult:
    """
    Dispatches through PayrollCostSummaryView — see that view's own
    docstring for branch-scoping/period-resolution. raw_text is parsed for
    an explicit month ("payroll cost for March") or a "last cycle/month"
    relative phrase; absent either, the view's own default (offset 0 — the
    latest non-cancelled cycle per branch) applies.
    """
    params = _period_query_params(raw_text or '')
    response = _dispatch_get(PayrollCostSummaryView, '/api/payroll/analytics/cost-summary/', request, params)

    if response.status_code >= 400:
        return _failure_result(response, _COST_SUMMARY_FAILED_MESSAGE)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    employee_count = (data or {}).get('employee_count', 0)

    if not employee_count:
        return ExecutionResult(success=True, message=text(_NO_COST_DATA_MESSAGE), data=data)

    message = text(_COST_SUMMARY_TEMPLATE).format(
        gross_earnings=data['gross_earnings'], net_pay=data['net_pay'], employee_count=employee_count,
    )
    return ExecutionResult(success=True, message=message, data=data)


def execute_check_branch_payroll_breakdown(request, raw_text: str = '') -> ExecutionResult:
    """
    Dispatches through BranchPayrollBreakdownView. The spoken summary reads
    only the top 3 branches by net pay (the view already orders its rows
    net-pay-descending) — the full, un-truncated list is still returned as
    `data` for the UI panel. A branch-scoped caller's own single-row result
    gets a dedicated singular phrasing instead of "top branches: X" for one
    branch.
    """
    params = _period_query_params(raw_text or '')
    response = _dispatch_get(BranchPayrollBreakdownView, '/api/payroll/analytics/branch-breakdown/', request, params)

    if response.status_code >= 400:
        return _failure_result(response, _BREAKDOWN_FAILED_MESSAGE)

    rows = response.data.get('data') if isinstance(response.data, dict) else None
    if not rows:
        return ExecutionResult(success=True, message=text(_NO_BREAKDOWN_DATA_MESSAGE), data=rows)

    if len(rows) == 1:
        row = rows[0]
        message = text(_SINGLE_BRANCH_TEMPLATE).format(
            branch_name=row['branch_name'], net_pay=row['net_pay'], employee_count=row['employee_count'],
        )
        return ExecutionResult(success=True, message=message, data=rows)

    top_three = ', '.join(f"{row['branch_name']}: ₹{row['net_pay']}" for row in rows[:3])
    message = text(_TOP_BRANCHES_TEMPLATE).format(branches=top_three)
    return ExecutionResult(success=True, message=message, data=rows)
