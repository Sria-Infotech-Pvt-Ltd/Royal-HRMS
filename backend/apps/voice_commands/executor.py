from __future__ import annotations

from typing import Optional

from django.db import connection

from apps.tenants.models import MODULE_ATTENDANCE, MODULE_LABELS, MODULE_LEAVE, MODULE_PAYROLL
from apps.voice_commands.executor_approval import (
    execute_check_team_attendance,
    execute_check_team_leave_queue,
    execute_confirm_leave_approval,
    execute_identify_leave_approval_target,
)
from apps.voice_commands.executor_attendance import (
    execute_check_attendance_stats,
    execute_check_attendance_summary,
    execute_clock_in,
    execute_clock_out,
    execute_request_attendance_correction,
)
from apps.voice_commands.executor_greeting import execute_greeting
from apps.voice_commands.executor_leave import (
    execute_apply_leave,
    execute_cancel_leave,
    execute_check_leave_balance,
    execute_check_leave_status,
)
from apps.voice_commands.executor_payroll import (
    execute_acknowledge_payslip,
    execute_check_my_payslip,
    execute_identify_employee_payslip,
    execute_raise_payslip_query,
)
from apps.voice_commands.audit import log_permission_denied
from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.matcher import DEFAULT_LANG, get_required_permission
from apps.voice_commands.permissions import has_required_permission

INTENT_CLOCK_IN = 'clock_in'
INTENT_CLOCK_OUT = 'clock_out'
INTENT_CHECK_LEAVE_BALANCE = 'check_leave_balance'
INTENT_CHECK_LEAVE_STATUS = 'check_leave_status'
INTENT_CANCEL_LEAVE = 'cancel_leave'
INTENT_CHECK_ATTENDANCE_STATS = 'check_attendance_stats'
INTENT_CHECK_ATTENDANCE_SUMMARY = 'check_attendance_summary'
INTENT_REQUEST_ATTENDANCE_CORRECTION = 'request_attendance_correction'
INTENT_APPLY_LEAVE = 'apply_leave'
INTENT_CHECK_TEAM_LEAVE_QUEUE = 'check_team_leave_queue'
INTENT_CHECK_TEAM_ATTENDANCE = 'check_team_attendance'
INTENT_APPROVE_LEAVE = 'approve_leave'
INTENT_REJECT_LEAVE = 'reject_leave'
INTENT_CHECK_MY_PAYSLIP = 'check_my_payslip'
INTENT_ACKNOWLEDGE_PAYSLIP = 'acknowledge_payslip'
INTENT_RAISE_PAYSLIP_QUERY = 'raise_payslip_query'
INTENT_CHECK_EMPLOYEE_PAYSLIP = 'check_employee_payslip'
INTENT_GREETING = 'greeting'

_LEAVE_APPROVAL_INTENT_ACTIONS = {INTENT_APPROVE_LEAVE: 'approve', INTENT_REJECT_LEAVE: 'reject'}

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."

# Every intent below dispatches straight into another app's view/service code
# via a direct Python call (APIRequestFactory or a raw query), never a real
# HTTP request — so apps.tenants.middleware.TenantSchemaMiddleware's module
# gate, which only inspects the *outer* request path (/api/voice/parse/,
# gated on voice_commands itself), never runs a second time for the module
# the action actually belongs to. Without the check below, a company with
# voice_commands enabled but not leave/attendance/payroll could use voice to
# fully exercise those modules regardless of enabled_modules. Mirrors
# apps.tenants.feature_gate.MODULE_URL_PREFIXES's mapping, keyed by intent
# instead of URL path since there's no request path to inspect here.
_INTENT_MODULES = {
    INTENT_CLOCK_IN: MODULE_ATTENDANCE,
    INTENT_CLOCK_OUT: MODULE_ATTENDANCE,
    INTENT_CHECK_ATTENDANCE_STATS: MODULE_ATTENDANCE,
    INTENT_CHECK_ATTENDANCE_SUMMARY: MODULE_ATTENDANCE,
    INTENT_REQUEST_ATTENDANCE_CORRECTION: MODULE_ATTENDANCE,
    INTENT_CHECK_TEAM_ATTENDANCE: MODULE_ATTENDANCE,
    INTENT_CHECK_LEAVE_BALANCE: MODULE_LEAVE,
    INTENT_CHECK_LEAVE_STATUS: MODULE_LEAVE,
    INTENT_CANCEL_LEAVE: MODULE_LEAVE,
    INTENT_APPLY_LEAVE: MODULE_LEAVE,
    INTENT_CHECK_TEAM_LEAVE_QUEUE: MODULE_LEAVE,
    INTENT_APPROVE_LEAVE: MODULE_LEAVE,
    INTENT_REJECT_LEAVE: MODULE_LEAVE,
    INTENT_CHECK_MY_PAYSLIP: MODULE_PAYROLL,
    INTENT_ACKNOWLEDGE_PAYSLIP: MODULE_PAYROLL,
    INTENT_RAISE_PAYSLIP_QUERY: MODULE_PAYROLL,
    INTENT_CHECK_EMPLOYEE_PAYSLIP: MODULE_PAYROLL,
}


def execute_intent(
    intent: str,
    request,
    attendance_mode: Optional[str] = None,
    lang: str = DEFAULT_LANG,
    slots: Optional[dict] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> ExecutionResult:
    """
    Dispatch a matched intent to the same service/query the equivalent REST endpoint uses.

    This module is deliberately thin — every intent's actual work lives in
    one of four domain modules, split out because a single flat executor.py
    grew past this project's 300-line-file convention:
      - executor_attendance.py — clock_in, clock_out, check_attendance_stats,
        check_attendance_summary, request_attendance_correction
      - executor_leave.py       — apply_leave, check_leave_balance,
        check_leave_status, cancel_leave
      - executor_approval.py    — check_team_leave_queue, check_team_attendance,
        approve_leave, reject_leave
      - executor_payroll.py     — check_my_payslip, acknowledge_payslip,
        raise_payslip_query, check_employee_payslip
      - executor_greeting.py    — greeting
    This function's only job is the permission gate (below) and routing to
    the right one — no domain-specific imports live here.

    attendance_mode is None when the transcript didn't name one explicitly.
    clock_in and clock_out apply different fallbacks for that case — see
    executor_attendance.py's execute_clock_in/execute_clock_out.

    latitude/longitude are forwarded straight into clock_in/clock_out only
    (every other intent ignores them); None on the caller's first attempt,
    populated on VoiceCommandButton's silent retry after a geofencing
    rejection prompts it to fetch the browser's location. No validation
    happens here — PunchWriteSerializer + GeofencingService (via
    PunchService.record_punch, called from executor_attendance.py's
    _execute_punch) are the same real checks the manual ClockWidget punch
    already goes through.

    slots is meaningful for apply_leave — voice_commands/conversation.py fills
    it in once all required slots (leave_type, start_date, end_date, reason)
    have been collected, possibly across several turns, and only calls
    execute_intent() at that point. request_attendance_correction works the
    same way (date, punch_type, reason, plus correct_in_time and/or
    correct_out_time depending on punch_type — see correction_slot_extractor.py
    /conversation_attendance_correction.py), the one difference being that
    which slots are required isn't a flat list, since the time slots are
    only needed for some punch_type values. And for approve_leave/reject_leave,
    which use it differently: every turn of those two dispatches through
    execute_intent() (not just the last one), so the leave.approve gate below
    always runs before any team leave data is looked up. slots['stage'] is
    'identify' (look up the team's pending requests and fuzzy-match
    slots['name_query']) or 'confirm' (actually call LeaveApprovalView.post()
    for slots['request_id']) — see conversation.py's _start_leave_approval/
    _continue_leave_approval. raise_payslip_query uses slots['description'],
    filled in by conversation_payroll.py once a query message has been
    collected (single turn if the caller states it upfront, one follow-up
    question otherwise). check_employee_payslip uses slots['name_query'] on
    every turn (every turn dispatches through execute_intent(), same reason
    as approve_leave/reject_leave above) — unlike those two, there's no
    'confirm' stage: a single employee match is already the terminal
    response (see executor_payroll.execute_identify_employee_payslip).
    Every other intent ignores slots entirely.

    Every intent is gated on its registry-declared required_permission before
    dispatch. Most intents set required_permission: null (they're
    IsAuthenticated-only, matching the equivalent REST view — see
    registry/intents_en.yaml), so this check is a no-op for them.
    check_team_leave_queue (leave.approve) and check_team_attendance
    (attendance.view) rely on this gate to reject with a permission-denied
    message instead of reaching the underlying view at all — notably for
    check_team_leave_queue, whose REST view (LeaveRequestListCreateView.get(),
    scope=team branch) silently falls back to the caller's own requests
    rather than rejecting when leave.approve is absent. Voice never reaches
    that fallback because this gate stops the caller first.

    check_my_payslip, acknowledge_payslip, and raise_payslip_query all
    require payroll.view_own — verified directly against MyPayslipsView.get(),
    AcknowledgePayslipView.post(), and PayslipQueryListView.post() (payroll/
    views/payslips.py:323-324, 344-345, 375-376): all three check that SAME
    codename, not payroll.edit or a per-action codename, despite two of them
    being mutations. check_employee_payslip requires payroll.view instead —
    the codename PayslipDetailView.get() checks for viewing anyone OTHER than
    yourself (payslips.py:61); a caller who only has payroll.view_own is
    correctly blocked from this intent by the gate below, the same way they
    would be from PayslipDetailView itself for someone else's payslip.

    Every leave/attendance/payroll intent is also gated on _INTENT_MODULES
    below. This exists because every one of those intents dispatches into
    its module's view/service code via a direct Python call rather than a
    real HTTP request, so apps.tenants.middleware.TenantSchemaMiddleware's
    module check — which only ever inspects the outer /api/voice/parse/
    request path — never runs for the inner module. Without this, a company
    with voice_commands enabled but not leave/attendance/payroll could use
    voice to fully exercise those modules regardless of enabled_modules.
    """
    required_permission = get_required_permission(intent, lang=lang)
    if required_permission and not has_required_permission(request.user, required_permission):
        log_permission_denied(request, intent, required_permission)
        return ExecutionResult(success=False, message=_PERMISSION_DENIED_MESSAGE)

    required_module = _INTENT_MODULES.get(intent)
    if required_module:
        # connection.tenant is a real Client (has_module available) only once
        # TenantSchemaMiddleware has activated a schema from a genuine HTTP
        # request — exactly the case this whole check exists for. Anything
        # that reaches execute_intent() without that (django-tenants' own
        # FakeTenant placeholder when no schema is active — e.g. every
        # existing voice_commands test, which calls this directly with no
        # request cycle) has no module information to gate on at all, so
        # this is skipped rather than crashed on, matching the "not
        # applicable" behaviour of the `required_module` falsy case above.
        has_module = getattr(connection.tenant, 'has_module', None)
        if callable(has_module) and not has_module(required_module):
            label = MODULE_LABELS.get(required_module, required_module)
            return ExecutionResult(success=False, message=f'{label} is not enabled for your company.')

    if intent == INTENT_CLOCK_IN:
        return execute_clock_in(request, attendance_mode, latitude, longitude)
    if intent == INTENT_CLOCK_OUT:
        return execute_clock_out(request, attendance_mode, latitude, longitude)
    if intent == INTENT_CHECK_LEAVE_BALANCE:
        return execute_check_leave_balance(request)
    if intent == INTENT_CHECK_LEAVE_STATUS:
        return execute_check_leave_status(request)
    if intent == INTENT_CANCEL_LEAVE:
        return execute_cancel_leave(request)
    if intent == INTENT_CHECK_ATTENDANCE_STATS:
        return execute_check_attendance_stats(request)
    if intent == INTENT_CHECK_ATTENDANCE_SUMMARY:
        return execute_check_attendance_summary(request)
    if intent == INTENT_REQUEST_ATTENDANCE_CORRECTION:
        return execute_request_attendance_correction(request, slots or {})
    if intent == INTENT_CHECK_TEAM_LEAVE_QUEUE:
        return execute_check_team_leave_queue(request)
    if intent == INTENT_CHECK_TEAM_ATTENDANCE:
        return execute_check_team_attendance(request)
    if intent == INTENT_APPLY_LEAVE:
        return execute_apply_leave(request, slots or {})
    if intent in _LEAVE_APPROVAL_INTENT_ACTIONS:
        action = _LEAVE_APPROVAL_INTENT_ACTIONS[intent]
        slots = slots or {}
        if slots.get('stage') == 'confirm':
            return execute_confirm_leave_approval(request, action, slots.get('request_id'))
        return execute_identify_leave_approval_target(request, action, slots.get('name_query'))
    if intent == INTENT_CHECK_MY_PAYSLIP:
        return execute_check_my_payslip(request)
    if intent == INTENT_ACKNOWLEDGE_PAYSLIP:
        return execute_acknowledge_payslip(request)
    if intent == INTENT_RAISE_PAYSLIP_QUERY:
        return execute_raise_payslip_query(request, (slots or {}).get('description', ''))
    if intent == INTENT_CHECK_EMPLOYEE_PAYSLIP:
        return execute_identify_employee_payslip(request, (slots or {}).get('name_query'))
    if intent == INTENT_GREETING:
        return execute_greeting(request)
    return ExecutionResult(success=False, message="I didn't understand that command.")
