from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from django.utils import timezone

from core.responses import get_client_ip

from apps.attendance.models import AttendancePunch
from apps.attendance.serializers_my_attendance import (
    MonthlySummarySerializer,
    PunchWriteSerializer,
    StatsSerializer,
)
from apps.attendance.services_attendance import AttendanceDashboardService, PunchService
from apps.attendance.views.hr_attendance import HRAttendanceDashboardView
from apps.hrms.models import (
    REQ_APPROVED,
    REQ_CANCELLED,
    REQ_L2_PENDING,
    REQ_PENDING,
    REQ_REJECTED,
    LeaveBalance,
    LeaveRequest,
)
from apps.hrms.serializers import LeaveBalanceSerializer, LeaveRequestSerializer
from apps.hrms.views.leave import LeaveApprovalView, LeaveRequestListCreateView
from apps.voice_commands.approval_extractor import match_employee_name
from apps.voice_commands.matcher import DEFAULT_LANG, get_required_permission
from apps.voice_commands.permissions import has_required_permission

from rest_framework.test import APIRequestFactory, force_authenticate

logger = logging.getLogger(__name__)

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

_LEAVE_APPROVAL_INTENT_ACTIONS = {INTENT_APPROVE_LEAVE: 'approve', INTENT_REJECT_LEAVE: 'reject'}

_CORRECTION_NEEDS_DASHBOARD_MESSAGE = (
    'Attendance corrections need a date, punch type, and reason — please submit this from the dashboard.'
)
_APPLY_LEAVE_SUBMIT_FAILED_MESSAGE = 'Could not submit the leave request.'

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for every intent that dispatches through an existing DRF view
# (apply_leave, check_team_leave_queue, check_team_attendance) rather than
# duplicating that view's query/scoping logic here.
_api_request_factory = APIRequestFactory()

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."

# Presentation-only labels for TTS-friendly phrasing — not business logic,
# just how the raw status codes read out loud. Mirrors frontend/app/dashboard
# /leave/_data.ts's STATUS_LABEL mapping.
_STATUS_LABELS = {
    REQ_PENDING: 'pending manager approval',
    REQ_L2_PENDING: 'pending HR approval',
    REQ_APPROVED: 'approved',
    REQ_REJECTED: 'rejected',
    REQ_CANCELLED: 'cancelled',
}


@dataclass
class ExecutionResult:
    success: bool
    message: str
    data: Optional[Any] = None


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

    attendance_mode is None when the transcript didn't name one explicitly.
    clock_in and clock_out apply different fallbacks for that case — see
    each branch below.

    latitude/longitude are forwarded straight into _execute_punch for
    clock_in/clock_out only (every other intent ignores them); None on the
    caller's first attempt, populated on VoiceCommandButton's silent retry
    after a geofencing rejection prompts it to fetch the browser's location.
    No validation happens here — PunchWriteSerializer + GeofencingService
    (via PunchService.record_punch, called from _execute_punch below) are
    the same real checks the manual ClockWidget punch already goes through.

    slots is meaningful for apply_leave — voice_commands/conversation.py fills
    it in once all required slots (leave_type, start_date, end_date, reason)
    have been collected, possibly across several turns, and only calls
    execute_intent() at that point — and for approve_leave/reject_leave,
    which use it differently: every turn of those two dispatches through
    execute_intent() (not just the last one), so the leave.approve gate below
    always runs before any team leave data is looked up. slots['stage'] is
    'identify' (look up the team's pending requests and fuzzy-match
    slots['name_query']) or 'confirm' (actually call LeaveApprovalView.post()
    for slots['request_id']) — see conversation.py's _start_leave_approval/
    _continue_leave_approval. Every other intent ignores slots entirely.

    Every intent is gated on its registry-declared required_permission before
    dispatch. Most intents set required_permission: null (they're
    IsAuthenticated-only, matching the equivalent REST view — see
    registry/intents_en.yaml), so this check is a no-op for them.
    check_team_leave_queue (leave.approve) and check_team_attendance
    (attendance.view) are the two that actually rely on this gate: it's what
    lets voice reject with a permission-denied message instead of reaching
    the underlying view at all — notably for check_team_leave_queue, whose
    REST view (LeaveRequestListCreateView.get(), scope=team branch) silently
    falls back to the caller's own requests rather than rejecting when
    leave.approve is absent. Voice never reaches that fallback because this
    gate stops the caller first.
    """
    required_permission = get_required_permission(intent, lang=lang)
    if required_permission and not has_required_permission(request.user, required_permission):
        return ExecutionResult(success=False, message=_PERMISSION_DENIED_MESSAGE)

    if intent == INTENT_CLOCK_IN:
        # No mode said -> office, same default a fresh web punch gets
        # (PunchWriteSerializer's own default, services_attendance.py:114).
        mode = attendance_mode or AttendancePunch.MODE_OFFICE
        return _execute_punch(
            request, punch_type='IN', attendance_mode=mode,
            success_message='You have been clocked in successfully.',
            latitude=latitude, longitude=longitude,
        )
    if intent == INTENT_CLOCK_OUT:
        # No mode said -> inherit today's still-open IN punch's mode, mirroring
        # the web ClockWidget (reuses the same mode-dropdown value for both the
        # IN and OUT clicks — see useClockWidget.ts / ClockWidget.tsx:89).
        # Defaulting to office here instead would force a geofence check
        # against the office on a day that was opened as WFH/field/etc.
        mode = attendance_mode or _resolve_clock_out_mode(request.user)
        return _execute_punch(
            request, punch_type='OUT', attendance_mode=mode,
            success_message='You have been clocked out successfully.',
            latitude=latitude, longitude=longitude,
        )
    if intent == INTENT_CHECK_LEAVE_BALANCE:
        return _execute_check_leave_balance(request)
    if intent == INTENT_CHECK_LEAVE_STATUS:
        return _execute_check_leave_status(request)
    if intent == INTENT_CANCEL_LEAVE:
        return _execute_cancel_leave(request)
    if intent == INTENT_CHECK_ATTENDANCE_STATS:
        return _execute_check_attendance_stats(request)
    if intent == INTENT_CHECK_ATTENDANCE_SUMMARY:
        return _execute_check_attendance_summary(request)
    if intent == INTENT_REQUEST_ATTENDANCE_CORRECTION:
        return _execute_request_attendance_correction()
    if intent == INTENT_CHECK_TEAM_LEAVE_QUEUE:
        return _execute_check_team_leave_queue(request)
    if intent == INTENT_CHECK_TEAM_ATTENDANCE:
        return _execute_check_team_attendance(request)
    if intent == INTENT_APPLY_LEAVE:
        return _execute_apply_leave(request, slots or {})
    if intent in _LEAVE_APPROVAL_INTENT_ACTIONS:
        action = _LEAVE_APPROVAL_INTENT_ACTIONS[intent]
        slots = slots or {}
        if slots.get('stage') == 'confirm':
            return _execute_confirm_leave_approval(request, action, slots.get('request_id'))
        return _execute_identify_leave_approval_target(request, action, slots.get('name_query'))
    return ExecutionResult(success=False, message="I didn't understand that command.")


def _resolve_clock_out_mode(employee) -> str:
    """
    Look up today's most recent punch; if it's a still-open IN, inherit its
    attendance_mode. Falls back to MODE_OFFICE if there's no open IN punch —
    record_punch() will reject with 'not currently clocked in' before
    geofencing even runs in that case, so this fallback is never actually
    reached as a geofence decision.
    """
    today = timezone.localdate()
    last_punch = (
        AttendancePunch.objects
        .filter(employee=employee, punched_at__date=today)
        .order_by('-punched_at')
        .first()
    )
    if last_punch and last_punch.punch_type == AttendancePunch.PUNCH_IN:
        return last_punch.attendance_mode
    return AttendancePunch.MODE_OFFICE


def _execute_punch(
    request, punch_type: str, attendance_mode: str, success_message: str,
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> ExecutionResult:
    """
    Same path as AttendancePunchView.post() — PunchWriteSerializer then
    PunchService.record_punch(). latitude/longitude are passed straight into
    the serializer exactly like the manual ClockWidget's punch payload
    (frontend/hooks/useClockWidget.ts) — PunchWriteSerializer already
    defaults both to None/allows either omitted, so there's nothing extra to
    validate here.
    """
    serializer = PunchWriteSerializer(data={
        'punch_type': punch_type,
        'attendance_mode': attendance_mode,
        'latitude': latitude,
        'longitude': longitude,
    })
    if not serializer.is_valid():
        logger.error('Voice %s payload invalid: %s', punch_type, serializer.errors)
        return ExecutionResult(success=False, message='Could not process the request.')

    punch_data = serializer.validated_data.copy()
    punch_data['ip_address'] = get_client_ip(request)

    try:
        PunchService.record_punch(request.user, punch_data)
    except ValueError as exc:
        return ExecutionResult(success=False, message=str(exc))
    except PermissionError as exc:
        return ExecutionResult(success=False, message=str(exc))

    return ExecutionResult(success=True, message=success_message)


def _execute_check_leave_balance(request) -> ExecutionResult:
    """Same query LeaveBalanceView.get() runs for the caller's own balances, current year."""
    year = date.today().year
    balances = LeaveBalance.objects.filter(employee=request.user, year=year).order_by('leave_type')
    data = LeaveBalanceSerializer(balances, many=True).data

    if not data:
        return ExecutionResult(
            success=True,
            message=f'You have no leave balance records for {year}.',
            data=data,
        )

    summary = ', '.join(f"{row['leave_type_display']}: {row['available_days']}" for row in data)
    return ExecutionResult(success=True, message=f'Your leave balance — {summary}.', data=data)


def _execute_check_leave_status(request) -> ExecutionResult:
    """
    Same default (own-requests, no employee_id/scope) branch
    LeaveRequestListCreateView.get() runs (hrms/views/leave.py:538-561),
    most recent first. Summarizes the latest request in one sentence rather
    than dumping the full list — that's what the raw REST list response is for.
    """
    requests = list(
        LeaveRequest.objects.filter(employee=request.user).order_by('-created_at')[:3]
    )
    data = LeaveRequestSerializer(requests, many=True, context={'request': request}).data

    if not data:
        return ExecutionResult(success=True, message='You have no leave requests on record.', data=data)

    latest = data[0]
    status_label = _STATUS_LABELS.get(latest['status'], latest['status'])
    message = (
        f"Your most recent leave request — {latest['leave_type_display']} "
        f"from {latest['start_date']} to {latest['end_date']} — is {status_label}."
    )
    if len(data) > 1:
        message += f' You have {len(data) - 1} more recent request(s) on file.'

    return ExecutionResult(success=True, message=message, data=data)


def _execute_cancel_leave(request) -> ExecutionResult:
    """
    Same mutation LeaveRequestDetailView.patch() performs for the cancel path
    (hrms/views/leave.py:716-731) — same status check, same field update.

    Voice can't reference a request by ID, so instead of requiring one: if
    exactly one of the caller's requests is cancellable (pending or
    l2_pending), cancel that one. If there's more than one, or none, don't
    guess — ask the user to be specific / use the dashboard instead.
    """
    cancellable = list(
        LeaveRequest.objects.filter(
            employee=request.user,
            status__in=(REQ_PENDING, REQ_L2_PENDING),
        ).order_by('-created_at')
    )

    if not cancellable:
        return ExecutionResult(success=False, message="You don't have any pending leave requests to cancel.")

    if len(cancellable) > 1:
        return ExecutionResult(
            success=False,
            message=(
                'You have more than one pending leave request — please specify which one, '
                'or cancel it from the dashboard.'
            ),
        )

    leave_request = cancellable[0]
    leave_request.status = REQ_CANCELLED
    leave_request.save(update_fields=['status', 'updated_at'])

    return ExecutionResult(
        success=True,
        message=(
            f'Your {leave_request.get_leave_type_display()} request from '
            f'{leave_request.start_date} to {leave_request.end_date} has been cancelled.'
        ),
    )


def _execute_check_attendance_stats(request) -> ExecutionResult:
    """Same query AttendanceStatsView.get() runs for the caller's own stats, current month/year, no employee_id."""
    today = date.today()
    stats = AttendanceDashboardService.get_stats(request.user, today.year, today.month)
    data = StatsSerializer(stats).data

    message = (
        f"This month you've been present {data['days_present']} of {data['working_days']} working days "
        f"({data['attendance_percentage']}% attendance), with {data['late_arrivals']} late arrival(s) "
        f"and an average of {data['avg_hours_per_day']} hours per day."
    )
    return ExecutionResult(success=True, message=message, data=data)


def _execute_check_attendance_summary(request) -> ExecutionResult:
    """Same query AttendanceSummaryView.get() runs for the caller's own summary, current month/year, no employee_id."""
    today = date.today()
    summary = AttendanceDashboardService.get_monthly_summary(request.user, today.year, today.month)
    data = MonthlySummarySerializer(summary).data

    message = (
        f"This month — {data['days_present']} days present, {data['days_absent']} absent, "
        f"{data['leave_days']} leave day(s), {data['half_days']} half day(s), "
        f"out of {data['working_days']} working days."
    )
    return ExecutionResult(success=True, message=message, data=data)


def _execute_request_attendance_correction() -> ExecutionResult:
    """
    AttendanceCorrectionView.post() (attendance/views/my_attendance.py:252-265)
    needs date, punch_type, and the correct in/out time(s) plus a reason —
    none of which voice can reliably capture without slot-filling
    infrastructure that doesn't exist yet. Rather than guess or half-fill the
    payload, always defer to the dashboard until that infrastructure is built.
    """
    return ExecutionResult(success=False, message=_CORRECTION_NEEDS_DASHBOARD_MESSAGE)


def _execute_apply_leave(request, slots: dict) -> ExecutionResult:
    """
    Submits the fully-collected slots (leave_type, start_date, end_date,
    reason — see voice_commands/conversation.py for how they're gathered
    across turns) to LeaveRequestListCreateView.post() directly, rather than
    duplicating its balance/overlap/approval-chain business rules here.
    APIRequestFactory + force_authenticate builds a real request against
    that view without re-running JWT authentication — request.user is
    already authenticated by the time voice/parse/ reaches this point.
    """
    payload = {
        'leave_type': slots['leave_type'],
        'start_date': slots['start_date'],
        'end_date': slots['end_date'],
        'reason': slots['reason'],
    }
    django_request = _api_request_factory.post('/api/leave/requests/', payload, format='json')
    force_authenticate(django_request, user=request.user)
    response = LeaveRequestListCreateView.as_view()(django_request)

    if response.status_code >= 400:
        message = _APPLY_LEAVE_SUBMIT_FAILED_MESSAGE
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    message = (
        f"Your {slots['leave_type']} leave request from {slots['start_date']} "
        f"to {slots['end_date']} has been submitted."
    )
    return ExecutionResult(success=True, message=message, data=data)


def _execute_check_team_leave_queue(request) -> ExecutionResult:
    """
    HR/manager-only: GET LeaveRequestListCreateView.get() with scope=team —
    the approval-queue branch (hrms/views/leave.py:556-558), role-scoped by
    _approval_scope_filter (manager: direct reports' pending requests;
    hr_admin: branch's l2_pending requests; system_admin: everyone else).

    By the time this runs, execute_intent()'s permission gate has already
    confirmed request.user has leave.approve — this intent's
    required_permission in the registry. That matters because the view
    itself does NOT reject a scope=team request without leave.approve; it
    silently falls back to `else: queryset = qs_base.filter(employee=request.user)`
    (hrms/views/leave.py:559-561) — i.e. the caller's OWN requests. That
    fallback exists for the REST API (a plain list call with no scope is a
    normal "my requests" request), but would be a confusing, silent wrong
    answer over voice: a caller who asked "how many leave requests are
    pending" and lacks leave.approve should hear that they don't have
    permission, not get an answer to a different question. Voice never
    reaches that branch because the gate stops an unauthorized caller first.

    Summarizes as a count only — this queue can span multiple employees, and
    reading out names/details over voice isn't appropriate; that's what the
    dashboard's list view is for.
    """
    django_request = _api_request_factory.get('/api/leave/requests/', {'scope': 'team'})
    force_authenticate(django_request, user=request.user)
    response = LeaveRequestListCreateView.as_view()(django_request)

    if response.status_code >= 400:
        message = 'Could not retrieve the team leave queue.'
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    count = data.get('count', 0) if isinstance(data, dict) else 0

    if count == 0:
        message = 'You have no leave requests pending your approval.'
    elif count == 1:
        message = 'You have 1 leave request pending your approval.'
    else:
        message = f'You have {count} leave requests pending your approval.'

    return ExecutionResult(success=True, message=message, data=data)


def _execute_identify_leave_approval_target(request, action: str, name_query: Optional[str]) -> ExecutionResult:
    """
    Turn 1 (or a "be more specific" retry) of approve_leave/reject_leave.
    Looks up the caller's team's pending leave requests through the exact
    same scope=team query _execute_check_team_leave_queue uses
    (LeaveRequestListCreateView.get()), then fuzzy-matches name_query against
    the employee names on THOSE requests only — never all employees, since
    only someone with something currently pending can be acted on here.

    data['outcome'] tells conversation.py what to do next:
      'need_name'       — no name was given at all; ask for one.
      'zero_match'      — a name was given but nothing pending matches it.
      'multiple_match'  — more than one pending request matches; ask to be
                          more specific rather than guessing which one.
      'single_match'    — exactly one match; data['matched'] is read back to
                          the caller for an explicit yes/no confirmation.
    """
    django_request = _api_request_factory.get('/api/leave/requests/', {'scope': 'team'})
    force_authenticate(django_request, user=request.user)
    response = LeaveRequestListCreateView.as_view()(django_request)

    if response.status_code >= 400:
        message = 'Could not retrieve the team leave queue.'
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    results = data.get('results', []) if isinstance(data, dict) else []
    candidates = [
        {
            'request_id': row['id'],
            'employee_name': row['employee_name'],
            'leave_type_display': row['leave_type_display'],
            'start_date': row['start_date'],
            'end_date': row['end_date'],
        }
        for row in results
        if row.get('status') in (REQ_PENDING, REQ_L2_PENDING)
    ]

    if not name_query:
        return ExecutionResult(
            success=True,
            message=f'Who would you like to {action} leave for?',
            data={'outcome': 'need_name'},
        )

    matches = match_employee_name(name_query, candidates)

    if not matches:
        return ExecutionResult(
            success=False,
            message=f'No pending leave request found for {name_query}.',
            data={'outcome': 'zero_match'},
        )

    if len(matches) > 1:
        return ExecutionResult(
            success=True,
            message=(
                f'More than one pending leave request matches "{name_query}" — '
                'could you be more specific, for example with a last name?'
            ),
            data={'outcome': 'multiple_match'},
        )

    matched = matches[0]
    message = (
        f"{matched['employee_name']}'s {matched['leave_type_display']} leave request "
        f"from {matched['start_date']} to {matched['end_date']} — {action} this request? "
        'Please say yes or no.'
    )
    return ExecutionResult(success=True, message=message, data={'outcome': 'single_match', 'matched': matched})


def _execute_confirm_leave_approval(request, action: str, request_id: Optional[str]) -> ExecutionResult:
    """
    Confirmation turn ("yes"): submits the real action through
    LeaveApprovalView.post() directly, exactly like _execute_apply_leave
    dispatches to LeaveRequestListCreateView.post() — the self-approval block
    and HR branch-scoping checks (hrms/views/leave.py:783-786) run unchanged,
    voice never re-implements or bypasses them.
    """
    if not request_id:
        return ExecutionResult(
            success=False, message='I lost track of which leave request that was — please start over.',
        )

    django_request = _api_request_factory.post(
        f'/api/leave/requests/{request_id}/approve/', {'action': action}, format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = LeaveApprovalView.as_view()(django_request, request_id=request_id)

    if response.status_code >= 400:
        message = f'Could not {action} the leave request.'
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    employee_name = data.get('employee_name') if isinstance(data, dict) else None
    verb = 'approved' if action == 'approve' else 'rejected'
    subject = f"{employee_name}'s" if employee_name else 'The'
    message = f'{subject} leave request has been {verb}.'
    return ExecutionResult(success=True, message=message, data=data)


def _execute_check_team_attendance(request) -> ExecutionResult:
    """
    HR-only: GET HRAttendanceDashboardView.get() (attendance/views/hr_attendance.py:88-105),
    today's date, no branch/department filter beyond what _branch_scope()
    already forces for a branch-restricted hr_admin. Unlike the leave queue
    above, this view already rejects outright (403) when attendance.view is
    absent (hr_attendance.py:92-93) rather than silently falling back to
    anything — so execute_intent()'s permission gate and this view's own
    check are redundant when request.user has attendance.view, and agree
    when it doesn't: both reject, the gate simply reaches that verdict first.

    Summarizes the stat-card counts in one sentence, same style as
    check_attendance_stats — not the full per-employee list.
    """
    django_request = _api_request_factory.get('/api/attendance/dashboard/')
    force_authenticate(django_request, user=request.user)
    response = HRAttendanceDashboardView.as_view()(django_request)

    if response.status_code >= 400:
        message = 'Could not retrieve the team attendance dashboard.'
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    stat_cards = data.get('stat_cards', {}) if isinstance(data, dict) else {}

    message = (
        f"Today, {stat_cards.get('present_today', 0)} of {stat_cards.get('total_employees', 0)} "
        f"team members are present, {stat_cards.get('absent', 0)} absent, "
        f"{stat_cards.get('on_leave', 0)} on leave, and {stat_cards.get('late_arrivals', 0)} arrived late."
    )
    return ExecutionResult(success=True, message=message, data=data)
