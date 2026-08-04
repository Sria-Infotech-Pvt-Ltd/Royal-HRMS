from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model

from apps.payroll.models import EmployeePayslip
from apps.payroll.serializers import EmployeePayslipSerializer
from apps.payroll.views.payslips import AcknowledgePayslipView, PayslipDetailView, PayslipQueryListView

from apps.voice_commands.approval_extractor import match_employee_name
from apps.voice_commands.executor_result import ExecutionResult

from rest_framework.test import APIRequestFactory, force_authenticate

User = get_user_model()  # matches apps/payroll/views/employee_salary.py's own convention

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for acknowledge_payslip/raise_payslip_query/check_employee_payslip,
# which dispatch through AcknowledgePayslipView/PayslipQueryListView/
# PayslipDetailView rather than duplicating their business rules here — same
# reasoning as executor_leave.py/executor_approval.py's own factory.
_api_request_factory = APIRequestFactory()

_NO_PAYSLIP_MESSAGE = "You don't have any payslips on record yet."

# Spoken instead of the figures-bearing `message` — TTS confidentiality:
# gross/net pay figures shouldn't be read aloud by default (shoulder-surfing
# risk in a shared space), even though the full breakdown stays visible in
# the panel/toast. check_employee_payslip's version doesn't even say the
# employee's name aloud — it's someone else's financial data, not the
# caller's own. See executor_result.ExecutionResult.speech_message.
_OWN_PAYSLIP_SPEECH_MESSAGE = 'Your payslip is ready — check your screen for the details.'
_EMPLOYEE_PAYSLIP_SPEECH_MESSAGE = 'The payslip is ready — check your screen for the details.'

# Built straight from the model's own choices rather than hand-copied, so a
# future status added to EmployeePayslip.STATUS_CHOICES is picked up here
# too — same intent as executor_leave.py's _STATUS_LABELS, but there's
# nothing to rephrase for TTS here: "Sent to Employee" / "Query Raised" /
# etc. already read naturally out loud as-is.
_STATUS_LABELS = dict(EmployeePayslip.STATUS_CHOICES)


def _most_recent_payslip(employee_id):
    """
    Same ordering MyPayslipsView.get() uses (payroll/views/payslips.py:328)
    for 'the caller's own payslips, most recent cycle first' — queried
    directly rather than through that view since this is a simple filter+
    order+first(), the same shape as executor_leave.py's
    execute_check_leave_balance/execute_check_leave_status for "my own
    data". There is no REST endpoint that does this same lookup for an
    arbitrary OTHER employee (MyPayslipsView hardcodes employee=request.user),
    so this same helper is reused for both the caller's own payslip and,
    once an HR caller has identified a specific employee, that employee's.
    """
    return (
        EmployeePayslip.objects
        .filter(employee_id=employee_id)
        .select_related('cycle')
        .order_by('-cycle__cycle_start')
        .first()
    )


def _payslip_summary_message(data: dict, *, subject: str) -> str:
    status_label = _STATUS_LABELS.get(data['status'], data['status'])
    return (
        f"{subject} most recent payslip, for the period ending {data['cycle_end']}, "
        f"shows gross earnings of ₹{data['gross_earnings']}, total deductions of "
        f"₹{data['total_deductions']}, and a net pay of ₹{data['net_pay']}. "
        f"Status: {status_label}."
    )


def execute_check_my_payslip(request) -> ExecutionResult:
    """
    Own most-recent payslip — gated on payroll.view_own, the same codename
    MyPayslipsView.get() itself checks (payroll/views/payslips.py:323-324).
    No 'current month' filter exists on the real endpoint either; this takes
    the first result the same way MyPayslipsView's own ordering already
    would (results[0] on the client).
    """
    payslip = _most_recent_payslip(request.user.id)
    if payslip is None:
        return ExecutionResult(success=True, message=_NO_PAYSLIP_MESSAGE, data=None)

    data = EmployeePayslipSerializer(payslip).data
    message = _payslip_summary_message(data, subject='Your')
    return ExecutionResult(
        success=True, message=message, data=data, speech_message=_OWN_PAYSLIP_SPEECH_MESSAGE,
    )


def execute_acknowledge_payslip(request) -> ExecutionResult:
    """
    Acknowledges the caller's own most-recent payslip through
    AcknowledgePayslipView.post() directly — gated on payroll.view_own,
    verified against the real view (payroll/views/payslips.py:344-345),
    NOT a mutation-flavored codename like payroll.edit. That view's own
    status-must-be-SENT business rule (payslips.py:348-349) runs unchanged;
    voice never re-implements or bypasses it, same as execute_apply_leave
    dispatching to LeaveRequestListCreateView.post().
    """
    payslip = _most_recent_payslip(request.user.id)
    if payslip is None:
        return ExecutionResult(success=False, message=_NO_PAYSLIP_MESSAGE)

    django_request = _api_request_factory.post(
        f'/api/payroll/my-payslips/{payslip.pk}/acknowledge/', {}, format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = AcknowledgePayslipView.as_view()(django_request, pk=payslip.pk)

    if response.status_code >= 400:
        message = 'Could not acknowledge your payslip.'
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    return ExecutionResult(success=True, message='Your payslip has been acknowledged.', data=data)


def execute_raise_payslip_query(request, description: str) -> ExecutionResult:
    """
    Raises a query on the caller's own most-recent payslip through
    PayslipQueryListView.post() directly — gated on payroll.view_own,
    verified against the real view (payroll/views/payslips.py:375-376), the
    SAME codename as check_my_payslip/acknowledge_payslip, not a separate
    one. That view's own business rules (payslip status must be sent/
    acknowledged, query window not yet closed — payslips.py:386-390) run
    unchanged and their rejection message is surfaced verbatim on failure,
    same as every other view-backed executor function here.

    description is collected by conversation_payroll.py, across turns if
    needed — see that module for the download-phrase redirect and the
    voice-only minimum-length floor (the real serializer has none).
    """
    payslip = _most_recent_payslip(request.user.id)
    if payslip is None:
        return ExecutionResult(success=False, message=_NO_PAYSLIP_MESSAGE)

    django_request = _api_request_factory.post(
        '/api/payroll/queries/',
        {'payslip': str(payslip.pk), 'description': description},
        format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = PayslipQueryListView.as_view()(django_request)

    if response.status_code >= 400:
        message = 'Could not raise a query on your payslip.'
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    return ExecutionResult(
        success=True,
        message="Your query has been raised with HR — they'll follow up on your payslip.",
        data=data,
    )


def _find_employees_by_name(request, name_query: str) -> list:
    """
    Search active employees by name for check_employee_payslip. Mirrors the
    same active-employee, branch-scoped-unless-system-admin query
    EmployeeListCreateView.get() runs (accounts/views.py:2403-2415),
    replicated directly here rather than dispatched through that view:
    EmployeeListCreateView is gated on 'employees.view', a DIFFERENT
    codename from this intent's own 'payroll.view' gate (already checked by
    execute_intent() before this runs) — calling through that view via
    force_authenticate would incorrectly require the caller to ALSO hold
    employees.view just to look someone's name up.
    """
    qs = User.objects.filter(is_active=True).exclude(employee_id='')

    # Same "settings.edit = org-wide access" convention used everywhere else
    # (e.g. accounts/views.py's _employee_out_of_branch_scope) rather than a
    # role-name string — keeps Branch Admin (can_manage_branch) correctly
    # branch-scoped here too, same as HR/employee.
    is_org_admin = bool(
        request.user.role
        and request.user.role.role_permissions.filter(permission__codename='settings.edit').exists()
    ) or getattr(request.user, 'is_superuser', False)
    if not is_org_admin and request.user.branch:
        qs = qs.filter(branch=request.user.branch)

    candidates = [{'user_id': u.id, 'employee_name': u.full_name} for u in qs]
    return match_employee_name(name_query, candidates)


def execute_identify_employee_payslip(request, name_query: Optional[str]) -> ExecutionResult:
    """
    check_employee_payslip's only turn: HR/admin-only (payroll.view, checked
    by execute_intent() before this runs). Unlike approve_leave/reject_leave,
    viewing isn't a mutating action, so a single match responds immediately
    with that employee's payslip summary instead of pausing for a yes/no
    confirmation — see conversation_payroll.py, which only ever loops back
    here for a "be more specific" retry, never for a confirm stage.

    data['outcome'] tells conversation_payroll.py what to do next:
      'need_name'      — no name was given at all; ask for one.
      'zero_match'      — a name was given but no employee matches it.
      'multiple_match'  — more than one employee matches; ask to be more
                          specific rather than guessing which one.
      'single_match'    — exactly one match; already the terminal response.
    """
    if not name_query:
        return ExecutionResult(
            success=True,
            message="Which employee's payslip would you like to check?",
            data={'outcome': 'need_name'},
        )

    matches = _find_employees_by_name(request, name_query)

    if not matches:
        return ExecutionResult(
            success=False,
            message=f'No employee found named {name_query}.',
            data={'outcome': 'zero_match'},
        )

    if len(matches) > 1:
        return ExecutionResult(
            success=True,
            message=(
                f'More than one employee matches "{name_query}" — '
                'could you be more specific, for example with a last name?'
            ),
            data={'outcome': 'multiple_match'},
        )

    matched = matches[0]
    payslip = _most_recent_payslip(matched['user_id'])
    if payslip is None:
        return ExecutionResult(
            success=True,
            message=f"{matched['employee_name']} doesn't have any payslips on record yet.",
            data={'outcome': 'single_match', 'matched': matched},
        )

    django_request = _api_request_factory.get(f'/api/payroll/payslips/{payslip.pk}/')
    force_authenticate(django_request, user=request.user)
    response = PayslipDetailView.as_view()(django_request, pk=payslip.pk)

    if response.status_code >= 400:
        message = f"Could not retrieve {matched['employee_name']}'s payslip."
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data={'outcome': 'zero_match'})

    data = response.data.get('data') if isinstance(response.data, dict) else None
    message = _payslip_summary_message(data, subject=f"{matched['employee_name']}'s")
    return ExecutionResult(
        success=True, message=message,
        data={'outcome': 'single_match', 'matched': matched, 'payslip': data},
        speech_message=_EMPLOYEE_PAYSLIP_SPEECH_MESSAGE,
    )
