from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model

from apps.payroll.models import EmployeePayslip
from apps.payroll.serializers import EmployeePayslipSerializer
from apps.payroll.views.payslips import AcknowledgePayslipView, PayslipDetailView, PayslipQueryListView

from apps.voice_commands.approval_extractor import match_employee_name
from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import LANG_HI, get_current_language, text

from rest_framework.test import APIRequestFactory, force_authenticate

User = get_user_model()  # matches apps/payroll/views/employee_salary.py's own convention

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for acknowledge_payslip/raise_payslip_query/check_employee_payslip,
# which dispatch through AcknowledgePayslipView/PayslipQueryListView/
# PayslipDetailView rather than duplicating their business rules here — same
# reasoning as executor_leave.py/executor_approval.py's own factory.
_api_request_factory = APIRequestFactory()

_NO_PAYSLIP_MESSAGE = {
    'en': "You don't have any payslips on record yet.",
    'hi': 'अभी तक आपका कोई पेस्लिप रिकॉर्ड में नहीं है।',
}

# Spoken instead of the figures-bearing `message` — TTS confidentiality:
# gross/net pay figures shouldn't be read aloud by default (shoulder-surfing
# risk in a shared space), even though the full breakdown stays visible in
# the panel/toast. check_employee_payslip's version doesn't even say the
# employee's name aloud — it's someone else's financial data, not the
# caller's own. See executor_result.ExecutionResult.speech_message.
_OWN_PAYSLIP_SPEECH_MESSAGE = {
    'en': 'Your payslip is ready — check your screen for the details.',
    'hi': 'आपकी पेस्लिप तैयार है — विवरण के लिए अपनी स्क्रीन देखें।',
}
_EMPLOYEE_PAYSLIP_SPEECH_MESSAGE = {
    'en': 'The payslip is ready — check your screen for the details.',
    'hi': 'पेस्लिप तैयार है — विवरण के लिए अपनी स्क्रीन देखें।',
}

# Built straight from the model's own choices for the English side (so a
# future status added to EmployeePayslip.STATUS_CHOICES is picked up there
# too, same intent as executor_leave.py's _STATUS_LABELS) with a parallel
# Hindi label added per code — this app's own addition (Phase 3), kept
# local to voice_commands rather than touching the payroll app's model.
_STATUS_LABELS_HI = {
    EmployeePayslip.STATUS_DRAFT: 'ड्राफ्ट',
    EmployeePayslip.STATUS_SENT: 'कर्मचारी को भेजी गई',
    EmployeePayslip.STATUS_ACKNOWLEDGED: 'स्वीकार की गई',
    EmployeePayslip.STATUS_QUERIED: 'प्रश्न दर्ज किया गया',
    EmployeePayslip.STATUS_RESOLVED: 'प्रश्न सुलझाया गया',
    EmployeePayslip.STATUS_PAID: 'भुगतान हो चुका',
}
_STATUS_LABELS = {
    code: {'en': label, 'hi': _STATUS_LABELS_HI.get(code, label)}
    for code, label in EmployeePayslip.STATUS_CHOICES
}

_ACKNOWLEDGE_FAILED_MESSAGE = {
    'en': 'Could not acknowledge your payslip.',
    'hi': 'आपकी पेस्लिप को स्वीकार नहीं किया जा सका।',
}
_ACKNOWLEDGED_MESSAGE = {
    'en': 'Your payslip has been acknowledged.',
    'hi': 'आपकी पेस्लिप स्वीकार कर ली गई है।',
}
_QUERY_FAILED_MESSAGE = {
    'en': 'Could not raise a query on your payslip.',
    'hi': 'आपकी पेस्लिप पर प्रश्न दर्ज नहीं किया जा सका।',
}
_QUERY_RAISED_MESSAGE = {
    'en': "Your query has been raised with HR — they'll follow up on your payslip.",
    'hi': 'आपका प्रश्न एचआर के पास दर्ज कर दिया गया है — वे आपकी पेस्लिप के बारे में आपसे संपर्क करेंगे।',
}
_NEED_EMPLOYEE_NAME_MESSAGE = {
    'en': "Which employee's payslip would you like to check?",
    'hi': 'आप किस कर्मचारी की पेस्लिप देखना चाहेंगे?',
}
_NO_EMPLOYEE_FOUND_TEMPLATE = {
    'en': 'No employee found named {name_query}.',
    'hi': '{name_query} नाम का कोई कर्मचारी नहीं मिला।',
}
_MULTIPLE_EMPLOYEES_TEMPLATE = {
    'en': (
        'More than one employee matches "{name_query}" — '
        'could you be more specific, for example with a last name?'
    ),
    'hi': (
        '"{name_query}" से एक से अधिक कर्मचारी मेल खाते हैं — '
        'क्या आप अधिक स्पष्ट बता सकते हैं, जैसे उपनाम के साथ?'
    ),
}
_EMPLOYEE_NO_PAYSLIP_TEMPLATE = {
    'en': "{employee_name} doesn't have any payslips on record yet.",
    'hi': '{employee_name} की अभी तक कोई पेस्लिप रिकॉर्ड में नहीं है।',
}
_EMPLOYEE_PAYSLIP_RETRIEVE_FAILED_TEMPLATE = {
    'en': "Could not retrieve {employee_name}'s payslip.",
    'hi': '{employee_name} की पेस्लिप प्राप्त नहीं की जा सकी।',
}


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


_PAYSLIP_SUMMARY_TEMPLATE = {
    'en': (
        '{subject} most recent payslip, for the period ending {cycle_end}, '
        'shows gross earnings of ₹{gross_earnings}, total deductions of '
        '₹{total_deductions}, and a net pay of ₹{net_pay}. '
        'Status: {status_label}.'
    ),
    # subject_hi already carries the correct possessive marker ("आपकी" /
    # "{name} की") — see _payslip_summary_message's own subject_hi param.
    'hi': (
        '{subject} सबसे हाल की पेस्लिप, अवधि {cycle_end} तक, में '
        '₹{gross_earnings} की सकल आय, ₹{total_deductions} की कुल कटौती, '
        'और ₹{net_pay} का शुद्ध वेतन दिखाया गया है। स्थिति: {status_label}।'
    ),
}


def _payslip_summary_message(data: dict, *, subject_en: str, subject_hi: str) -> str:
    """
    subject_en/subject_hi are the SAME possessive phrase in each language
    ("Your"/"आपकी" for the caller's own payslip, "{name}'s"/"{name} की" for
    someone else's) — kept as two separate params rather than one `subject`
    reused across languages because Hindi possessive agreement ("की", since
    पेस्लिप is grammatically feminine) doesn't share English's "'s" form, so
    the caller must supply both, not just translate one at the call site.
    """
    status_label = text(_STATUS_LABELS.get(data['status'], {'en': data['status'], 'hi': data['status']}))
    subject = subject_hi if get_current_language() == LANG_HI else subject_en
    return text(_PAYSLIP_SUMMARY_TEMPLATE).format(
        subject=subject, cycle_end=data['cycle_end'], gross_earnings=data['gross_earnings'],
        total_deductions=data['total_deductions'], net_pay=data['net_pay'], status_label=status_label,
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
        return ExecutionResult(success=True, message=text(_NO_PAYSLIP_MESSAGE), data=None)

    data = EmployeePayslipSerializer(payslip).data
    message = _payslip_summary_message(data, subject_en='Your', subject_hi='आपकी')
    return ExecutionResult(
        success=True, message=message, data=data, speech_message=text(_OWN_PAYSLIP_SPEECH_MESSAGE),
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
        return ExecutionResult(success=False, message=text(_NO_PAYSLIP_MESSAGE))

    django_request = _api_request_factory.post(
        f'/api/payroll/my-payslips/{payslip.pk}/acknowledge/', {}, format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = AcknowledgePayslipView.as_view()(django_request, pk=payslip.pk)

    if response.status_code >= 400:
        message = text(_ACKNOWLEDGE_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see execute_apply_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    return ExecutionResult(success=True, message=text(_ACKNOWLEDGED_MESSAGE), data=data)


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
        return ExecutionResult(success=False, message=text(_NO_PAYSLIP_MESSAGE))

    django_request = _api_request_factory.post(
        '/api/payroll/queries/',
        {'payslip': str(payslip.pk), 'description': description},
        format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = PayslipQueryListView.as_view()(django_request)

    if response.status_code >= 400:
        message = text(_QUERY_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see execute_apply_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    return ExecutionResult(success=True, message=text(_QUERY_RAISED_MESSAGE), data=data)


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
            message=text(_NEED_EMPLOYEE_NAME_MESSAGE),
            data={'outcome': 'need_name'},
        )

    matches = _find_employees_by_name(request, name_query)

    if not matches:
        return ExecutionResult(
            success=False,
            message=text(_NO_EMPLOYEE_FOUND_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'zero_match'},
        )

    if len(matches) > 1:
        return ExecutionResult(
            success=True,
            message=text(_MULTIPLE_EMPLOYEES_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'multiple_match'},
        )

    matched = matches[0]
    payslip = _most_recent_payslip(matched['user_id'])
    if payslip is None:
        return ExecutionResult(
            success=True,
            message=text(_EMPLOYEE_NO_PAYSLIP_TEMPLATE).format(employee_name=matched['employee_name']),
            data={'outcome': 'single_match', 'matched': matched},
        )

    django_request = _api_request_factory.get(f'/api/payroll/payslips/{payslip.pk}/')
    force_authenticate(django_request, user=request.user)
    response = PayslipDetailView.as_view()(django_request, pk=payslip.pk)

    if response.status_code >= 400:
        message = text(_EMPLOYEE_PAYSLIP_RETRIEVE_FAILED_TEMPLATE).format(employee_name=matched['employee_name'])
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see execute_apply_leave's own note
        return ExecutionResult(success=False, message=message, data={'outcome': 'zero_match'})

    data = response.data.get('data') if isinstance(response.data, dict) else None
    message = _payslip_summary_message(
        data, subject_en=f"{matched['employee_name']}'s", subject_hi=f"{matched['employee_name']} की",
    )
    return ExecutionResult(
        success=True, message=message,
        data={'outcome': 'single_match', 'matched': matched, 'payslip': data},
        speech_message=text(_EMPLOYEE_PAYSLIP_SPEECH_MESSAGE),
    )
