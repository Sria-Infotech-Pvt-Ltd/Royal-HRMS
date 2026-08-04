from __future__ import annotations

from typing import Optional

from apps.attendance.views.hr_attendance import HRAttendanceDashboardView
from apps.hrms.models import REQ_L2_PENDING, REQ_PENDING
from apps.hrms.views.leave import LeaveApprovalView, LeaveRequestListCreateView
from apps.voice_commands.approval_extractor import match_employee_name
from apps.voice_commands.executor_result import ExecutionResult

from rest_framework.test import APIRequestFactory, force_authenticate

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for every intent here, all of which dispatch through an existing
# DRF view (LeaveRequestListCreateView/LeaveApprovalView/
# HRAttendanceDashboardView) rather than duplicating that view's
# query/scoping logic.
_api_request_factory = APIRequestFactory()


def execute_check_team_leave_queue(request) -> ExecutionResult:
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


def execute_identify_leave_approval_target(request, action: str, name_query: Optional[str]) -> ExecutionResult:
    """
    Turn 1 (or a "be more specific" retry) of approve_leave/reject_leave.
    Looks up the caller's team's pending leave requests through the exact
    same scope=team query execute_check_team_leave_queue uses
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
    # TTS confidentiality: name + dates stay in speech (needed for the
    # caller to confirm by voice which request this is — the entire point
    # of this turn), but the leave TYPE is dropped from speech only — it can
    # reveal a health/personal category (e.g. "sick", "maternity") about a
    # THIRD PARTY to whoever's in earshot of the approving manager. The full
    # sentence, leave type included, still shows in the panel/toast. See
    # executor_result.ExecutionResult.speech_message.
    speech_message = (
        f"{matched['employee_name']}'s leave request "
        f"from {matched['start_date']} to {matched['end_date']} — {action} this? "
        'Please say yes or no.'
    )
    return ExecutionResult(
        success=True, message=message, data={'outcome': 'single_match', 'matched': matched},
        speech_message=speech_message,
    )


def execute_confirm_leave_approval(request, action: str, request_id: Optional[str]) -> ExecutionResult:
    """
    Confirmation turn ("yes"): submits the real action through
    LeaveApprovalView.post() directly, exactly like execute_apply_leave
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

    from apps.dashboard.views.overview import push_leave_update
    push_leave_update(request.user.id)

    return ExecutionResult(success=True, message=message, data=data)


def execute_check_team_attendance(request) -> ExecutionResult:
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

    stat_cards alone only carries present/absent/late/on_leave/total — it has
    no half-day tile (get_dashboard_stats, services_hr.py:118-125), so a
    half-day employee is correctly excluded from `absent` but never shows up
    in `present_today` either. The dashboard UI covers that gap with a
    separate summary_chips row (AttendanceTab.tsx CHIP_CONFIG) that includes
    half_day — mirror that here so the spoken summary doesn't silently drop
    people the same way the My Attendance page never collapses Days Present/
    Days Absent/Leave Days/Half Days into just two numbers.
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
    summary_chips = data.get('summary_chips', {}) if isinstance(data, dict) else {}

    half_day = summary_chips.get('half_day', 0)
    leave_days = stat_cards.get('on_leave', summary_chips.get('on_leave', 0))

    message = (
        f"Today, {stat_cards.get('present_today', 0)} of {stat_cards.get('total_employees', 0)} "
        f"team members are present, {stat_cards.get('absent', 0)} absent, "
        f"{leave_days} on leave, {half_day} on half-day, "
        f"and {stat_cards.get('late_arrivals', 0)} arrived late."
    )
    return ExecutionResult(success=True, message=message, data=data)
