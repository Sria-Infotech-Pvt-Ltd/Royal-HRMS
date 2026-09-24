from __future__ import annotations

from typing import Optional

from apps.attendance.models import AttendanceCorrection
from apps.attendance.views.hr_attendance import HRAttendanceDashboardView, HRCorrectionListView, HRCorrectionReviewView
from apps.hrms.models import REQ_L2_PENDING, REQ_PENDING
from apps.hrms.views.leave import LeaveApprovalView, LeaveRequestListCreateView
from apps.voice_commands.approval_extractor import match_employee_name
from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import LANG_HI, get_current_language, text

from rest_framework.test import APIRequestFactory, force_authenticate

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for every intent here, all of which dispatch through an existing
# DRF view (LeaveRequestListCreateView/LeaveApprovalView/
# HRAttendanceDashboardView) rather than duplicating that view's
# query/scoping logic.
_api_request_factory = APIRequestFactory()

_TEAM_QUEUE_RETRIEVE_FAILED_MESSAGE = {
    'en': 'Could not retrieve the team leave queue.',
    'hi': 'टीम की छुट्टी सूची प्राप्त नहीं की जा सकी।',
}
_NO_PENDING_APPROVALS_MESSAGE = {
    'en': 'You have no leave requests pending your approval.',
    'hi': 'आपकी स्वीकृति के लिए कोई छुट्टी अनुरोध लंबित नहीं है।',
}
_ONE_PENDING_APPROVAL_MESSAGE = {
    'en': 'You have 1 leave request pending your approval.',
    'hi': 'आपकी स्वीकृति के लिए 1 छुट्टी अनुरोध लंबित है।',
}
_MANY_PENDING_APPROVALS_TEMPLATE = {
    'en': 'You have {count} leave requests pending your approval.',
    'hi': 'आपकी स्वीकृति के लिए {count} छुट्टी अनुरोध लंबित हैं।',
}
# action is always 'approve'/'reject' (see _LEAVE_APPROVAL_INTENT_ACTIONS in
# executor.py) — this local dict is the Hindi verb-form lookup for it, used
# everywhere `action` is spoken/shown below.
_ACTION_LABELS_HI = {'approve': 'स्वीकृत', 'reject': 'अस्वीकृत'}
# `action` is a single, already-localized word (see _ACTION_LABELS_HI and
# each call site below, which pre-selects the English or Hindi verb before
# .format() ever runs) — one shared placeholder name in both languages
# rather than an `{action}`/`{action_hi}` pair, so the two templates stay
# structurally comparable (see test_executor_hindi_strings.py's placeholder-
# parity check, which caught the original two-name version).
_WHO_TO_ACTION_TEMPLATE = {
    'en': 'Who would you like to {action} leave for?',
    'hi': 'आप किसकी छुट्टी {action} करना चाहेंगे?',
}
_NO_PENDING_REQUEST_FOR_NAME_TEMPLATE = {
    'en': 'No pending leave request found for {name_query}.',
    'hi': '{name_query} के लिए कोई लंबित छुट्टी अनुरोध नहीं मिला।',
}
_MULTIPLE_PENDING_REQUESTS_TEMPLATE = {
    'en': (
        'More than one pending leave request matches "{name_query}" — '
        'could you be more specific, for example with a last name?'
    ),
    'hi': (
        '"{name_query}" से एक से अधिक लंबित छुट्टी अनुरोध मेल खाते हैं — '
        'क्या आप अधिक स्पष्ट बता सकते हैं, जैसे उपनाम के साथ?'
    ),
}
_CONFIRM_APPROVAL_TEMPLATE = {
    'en': (
        "{employee_name}'s {leave_type_display} leave request from {start_date} to {end_date} "
        '— {action} this request? Please say yes or no.'
    ),
    'hi': (
        '{employee_name} का {leave_type_display} छुट्टी अनुरोध, {start_date} से {end_date} तक '
        '— क्या इसे {action} करें? कृपया हां या नहीं कहें।'
    ),
}
# TTS confidentiality variant — leave TYPE dropped from speech (see call
# site's own comment); everything else identical to the template above.
_CONFIRM_APPROVAL_SPEECH_TEMPLATE = {
    'en': (
        "{employee_name}'s leave request from {start_date} to {end_date} "
        '— {action} this? Please say yes or no.'
    ),
    'hi': (
        '{employee_name} का छुट्टी अनुरोध, {start_date} से {end_date} तक '
        '— क्या इसे {action} करें? कृपया हां या नहीं कहें।'
    ),
}
_LOST_TRACK_MESSAGE = {
    'en': 'I lost track of which leave request that was — please start over.',
    'hi': 'मैं भूल गया कि वह कौन सा छुट्टी अनुरोध था — कृपया फिर से शुरू करें।',
}
_ACTION_FAILED_TEMPLATE = {
    'en': 'Could not {action} the leave request.',
    'hi': 'छुट्टी अनुरोध को {action} नहीं किया जा सका।',
}
# subject/verb are already-localized (see call site: subject picks between
# subject_en/subject_hi, verb between the English word and verb_hi) — same
# single-shared-placeholder reasoning as _WHO_TO_ACTION_TEMPLATE above.
_ACTION_DONE_TEMPLATE = {
    'en': '{subject} leave request has been {verb}.',
    'hi': '{subject} छुट्टी अनुरोध {verb} कर दिया गया है।',
}
_CORRECTION_QUEUE_RETRIEVE_FAILED_MESSAGE = {
    'en': 'Could not retrieve the attendance correction review queue.',
    'hi': 'उपस्थिति सुधार समीक्षा सूची प्राप्त नहीं की जा सकी।',
}
_WHO_TO_ACTION_CORRECTION_TEMPLATE = {
    'en': 'Whose attendance correction would you like to {action}?',
    'hi': 'आप किसका उपस्थिति सुधार {action} करना चाहेंगे?',
}
_NO_ACTIONABLE_CORRECTION_FOR_NAME_TEMPLATE = {
    'en': 'No attendance correction awaiting your review was found for {name_query}.',
    'hi': '{name_query} के लिए आपकी समीक्षा हेतु कोई लंबित उपस्थिति सुधार नहीं मिला।',
}
_MULTIPLE_ACTIONABLE_CORRECTIONS_TEMPLATE = {
    'en': (
        'More than one attendance correction awaiting your review matches "{name_query}" — '
        'could you be more specific, for example with a last name?'
    ),
    'hi': (
        '"{name_query}" से एक से अधिक लंबित उपस्थिति सुधार मेल खाते हैं — '
        'क्या आप अधिक स्पष्ट बता सकते हैं, जैसे उपनाम के साथ?'
    ),
}
# punch_type is always IN/OUT/BOTH (AttendanceCorrection.PUNCH_* — see
# correction_slot_extractor.py's own _PUNCH_TYPE_SYNONYMS for the same three
# values on the filing side) — pre-localized before .format() the same way
# `action` already is throughout this module, not a second placeholder.
_PUNCH_TYPE_LABELS = {'IN': 'clock-in', 'OUT': 'clock-out', 'BOTH': 'clock-in and clock-out'}
_PUNCH_TYPE_LABELS_HI = {'IN': 'क्लॉक-इन', 'OUT': 'क्लॉक-आउट', 'BOTH': 'क्लॉक-इन और क्लॉक-आउट'}
_CONFIRM_CORRECTION_APPROVAL_TEMPLATE = {
    'en': (
        "{employee_name}'s {punch_type_display} correction for {date} "
        '— {action} this request? Please say yes or no.'
    ),
    'hi': (
        '{employee_name} का {date} के लिए {punch_type_display} सुधार '
        '— क्या इसे {action} करें? कृपया हां या नहीं कहें।'
    ),
}
_LOST_TRACK_CORRECTION_MESSAGE = {
    'en': 'I lost track of which attendance correction that was — please start over.',
    'hi': 'मैं भूल गया कि वह कौन सा उपस्थिति सुधार था — कृपया फिर से शुरू करें।',
}
_CORRECTION_ACTION_FAILED_TEMPLATE = {
    'en': 'Could not {action} the attendance correction.',
    'hi': 'उपस्थिति सुधार को {action} नहीं किया जा सका।',
}
# Distinguishes a FINAL approval from one that only cleared the L1 (manager)
# stage and escalated to L2 (HR) — services_hr_corrections._act_on_correction
# only creates the missing punch(es)/reprocesses the day once the request
# reaches its final stage, so a manager whose approval merely escalated it
# must not be told their employee's attendance was already fixed.
_CORRECTION_APPROVED_FINAL_TEMPLATE = {
    'en': "{employee_name}'s attendance correction has been approved.",
    'hi': '{employee_name} का उपस्थिति सुधार स्वीकृत कर दिया गया है।',
}
_CORRECTION_APPROVED_ESCALATED_TEMPLATE = {
    'en': "{employee_name}'s attendance correction has been approved and sent to HR for final review.",
    'hi': '{employee_name} का उपस्थिति सुधार स्वीकृत कर दिया गया है और अंतिम समीक्षा के लिए HR को भेजा गया है।',
}
_CORRECTION_REJECTED_TEMPLATE = {
    'en': "{employee_name}'s attendance correction has been rejected.",
    'hi': '{employee_name} का उपस्थिति सुधार अस्वीकृत कर दिया गया है।',
}
_TEAM_ATTENDANCE_RETRIEVE_FAILED_MESSAGE = {
    'en': 'Could not retrieve the team attendance dashboard.',
    'hi': 'टीम उपस्थिति डैशबोर्ड प्राप्त नहीं किया जा सका।',
}
_TEAM_ATTENDANCE_SUMMARY_TEMPLATE = {
    'en': (
        'Today, {present_today} of {total_employees} team members are present, '
        '{absent} absent, {leave_days} on leave, {half_day} on half-day, '
        'and {late_arrivals} arrived late.'
    ),
    'hi': (
        'आज, {total_employees} में से {present_today} टीम सदस्य उपस्थित हैं, '
        '{absent} अनुपस्थित, {leave_days} छुट्टी पर, {half_day} आधे दिन पर, '
        'और {late_arrivals} देर से आए।'
    ),
}


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
        message = text(_TEAM_QUEUE_RETRIEVE_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    count = data.get('count', 0) if isinstance(data, dict) else 0

    if count == 0:
        message = text(_NO_PENDING_APPROVALS_MESSAGE)
    elif count == 1:
        message = text(_ONE_PENDING_APPROVAL_MESSAGE)
    else:
        message = text(_MANY_PENDING_APPROVALS_TEMPLATE).format(count=count)

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
        message = text(_TEAM_QUEUE_RETRIEVE_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
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

    localized_action = text({'en': action, 'hi': _ACTION_LABELS_HI[action]})

    if not name_query:
        return ExecutionResult(
            success=True,
            message=text(_WHO_TO_ACTION_TEMPLATE).format(action=localized_action),
            data={'outcome': 'need_name'},
        )

    matches = match_employee_name(name_query, candidates)

    if not matches:
        return ExecutionResult(
            success=False,
            message=text(_NO_PENDING_REQUEST_FOR_NAME_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'zero_match'},
        )

    if len(matches) > 1:
        return ExecutionResult(
            success=True,
            message=text(_MULTIPLE_PENDING_REQUESTS_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'multiple_match'},
        )

    matched = matches[0]
    message = text(_CONFIRM_APPROVAL_TEMPLATE).format(
        employee_name=matched['employee_name'], leave_type_display=matched['leave_type_display'],
        start_date=matched['start_date'], end_date=matched['end_date'], action=localized_action,
    )
    # TTS confidentiality: name + dates stay in speech (needed for the
    # caller to confirm by voice which request this is — the entire point
    # of this turn), but the leave TYPE is dropped from speech only — it can
    # reveal a health/personal category (e.g. "sick", "maternity") about a
    # THIRD PARTY to whoever's in earshot of the approving manager. The full
    # sentence, leave type included, still shows in the panel/toast. See
    # executor_result.ExecutionResult.speech_message.
    speech_message = text(_CONFIRM_APPROVAL_SPEECH_TEMPLATE).format(
        employee_name=matched['employee_name'],
        start_date=matched['start_date'], end_date=matched['end_date'], action=localized_action,
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
        return ExecutionResult(success=False, message=text(_LOST_TRACK_MESSAGE))

    django_request = _api_request_factory.post(
        f'/api/leave/requests/{request_id}/approve/', {'action': action}, format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = LeaveApprovalView.as_view()(django_request, request_id=request_id)

    if response.status_code >= 400:
        message = text(_ACTION_FAILED_TEMPLATE).format(
            action=text({'en': action, 'hi': _ACTION_LABELS_HI[action]}),
        )
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    employee_name = data.get('employee_name') if isinstance(data, dict) else None
    verb_en = 'approved' if action == 'approve' else 'rejected'
    verb_hi = 'स्वीकृत' if action == 'approve' else 'अस्वीकृत'
    verb = text({'en': verb_en, 'hi': verb_hi})
    subject_en = f"{employee_name}'s" if employee_name else 'The'
    subject_hi = f'{employee_name} का' if employee_name else 'यह'
    subject = subject_hi if get_current_language() == LANG_HI else subject_en
    message = text(_ACTION_DONE_TEMPLATE).format(subject=subject, verb=verb)

    from apps.dashboard.views.overview import push_leave_update
    push_leave_update(request.user.id)

    return ExecutionResult(success=True, message=message, data=data)


def execute_identify_attendance_correction_approval_target(
    request, action: str, name_query: Optional[str],
) -> ExecutionResult:
    """
    Turn 1 (or a "be more specific" retry) of approve_attendance_correction/
    reject_attendance_correction. Looks up the caller's own correction review
    queue through HRCorrectionListView.get() (the same view/scoping the web
    Team Approvals page uses), then fuzzy-matches name_query against the
    employee names on requests THIS caller can actually act on RIGHT NOW —
    services_hr_corrections._build_row's own can_action flag, not merely
    "visible to this caller". A manager who is only the L1 approver on a
    request that has since escalated to L2/HR must not be offered it here,
    even though HRCorrectionListView's own _approval_scope_filter still
    returns the row (it stays in their view for visibility/history).

    data['outcome'] mirrors execute_identify_leave_approval_target's four
    values exactly — see that function's own docstring:
      'need_name' / 'zero_match' / 'multiple_match' / 'single_match'
      (data['matched'] on the last one).
    """
    django_request = _api_request_factory.get('/api/attendance/corrections/')
    force_authenticate(django_request, user=request.user)
    response = HRCorrectionListView.as_view()(django_request)

    if response.status_code >= 400:
        message = text(_CORRECTION_QUEUE_RETRIEVE_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
        return ExecutionResult(success=False, message=message)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    results = data.get('results', []) if isinstance(data, dict) else []
    candidates = [
        {
            'correction_id': row['id'], 'employee_name': row['name'],
            'date': row['date'], 'punch_type': row['punch_type'],
        }
        for row in results
        if row.get('can_action')
    ]

    localized_action = text({'en': action, 'hi': _ACTION_LABELS_HI[action]})

    if not name_query:
        return ExecutionResult(
            success=True,
            message=text(_WHO_TO_ACTION_CORRECTION_TEMPLATE).format(action=localized_action),
            data={'outcome': 'need_name'},
        )

    matches = match_employee_name(name_query, candidates)

    if not matches:
        return ExecutionResult(
            success=False,
            message=text(_NO_ACTIONABLE_CORRECTION_FOR_NAME_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'zero_match'},
        )

    if len(matches) > 1:
        return ExecutionResult(
            success=True,
            message=text(_MULTIPLE_ACTIONABLE_CORRECTIONS_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'multiple_match'},
        )

    matched = matches[0]
    punch_type_display = text({
        'en': _PUNCH_TYPE_LABELS[matched['punch_type']], 'hi': _PUNCH_TYPE_LABELS_HI[matched['punch_type']],
    })
    # No TTS confidentiality redaction here (unlike approve_leave's own
    # speech_message, which drops leave TYPE — a potential health/personal
    # category about a third party): punch type and date carry no comparable
    # sensitive category, and the caller needs both to confirm by voice which
    # request this is at all — same reasoning execute_confirm_leave_approval
    # keeps the employee name/dates in speech for.
    message = text(_CONFIRM_CORRECTION_APPROVAL_TEMPLATE).format(
        employee_name=matched['employee_name'], punch_type_display=punch_type_display,
        date=matched['date'], action=localized_action,
    )
    return ExecutionResult(success=True, message=message, data={'outcome': 'single_match', 'matched': matched})


def execute_confirm_attendance_correction_approval(
    request, action: str, correction_id: Optional[str],
) -> ExecutionResult:
    """
    Confirmation turn ("yes"): submits the real action through
    HRCorrectionReviewView.patch() directly, exactly like
    execute_confirm_leave_approval dispatches to LeaveApprovalView.post() —
    the per-stage _can_approve_at_stage check (services_hr_corrections.py)
    runs unchanged; voice never re-implements or bypasses it. A caller whose
    eligibility changed between the identify and confirm turns (e.g. someone
    else already actioned it, or it moved past the stage this caller could
    act on) gets that view's own real rejection surfaced here, not a stale
    success.
    """
    if not correction_id:
        return ExecutionResult(success=False, message=text(_LOST_TRACK_CORRECTION_MESSAGE))

    django_request = _api_request_factory.patch(
        f'/api/attendance/corrections/{correction_id}/review/', {'action': action}, format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = HRCorrectionReviewView.as_view()(django_request, pk=correction_id)

    if response.status_code >= 400:
        message = text(_CORRECTION_ACTION_FAILED_TEMPLATE).format(
            action=text({'en': action, 'hi': _ACTION_LABELS_HI[action]}),
        )
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    employee_name = data.get('name') if isinstance(data, dict) else None
    new_status = data.get('status') if isinstance(data, dict) else None

    if action == 'approve':
        template = (
            _CORRECTION_APPROVED_ESCALATED_TEMPLATE
            if new_status == AttendanceCorrection.STATUS_L2_PENDING
            else _CORRECTION_APPROVED_FINAL_TEMPLATE
        )
    else:
        template = _CORRECTION_REJECTED_TEMPLATE

    subject_en = employee_name or 'The employee'
    subject_hi = employee_name or 'कर्मचारी'
    employee_name_localized = subject_hi if get_current_language() == LANG_HI else subject_en
    message = text(template).format(employee_name=employee_name_localized)

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
        message = text(_TEAM_ATTENDANCE_RETRIEVE_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    stat_cards = data.get('stat_cards', {}) if isinstance(data, dict) else {}
    summary_chips = data.get('summary_chips', {}) if isinstance(data, dict) else {}

    half_day = summary_chips.get('half_day', 0)
    leave_days = stat_cards.get('on_leave', summary_chips.get('on_leave', 0))

    message = text(_TEAM_ATTENDANCE_SUMMARY_TEMPLATE).format(
        present_today=stat_cards.get('present_today', 0), total_employees=stat_cards.get('total_employees', 0),
        absent=stat_cards.get('absent', 0), leave_days=leave_days, half_day=half_day,
        late_arrivals=stat_cards.get('late_arrivals', 0),
    )
    return ExecutionResult(success=True, message=message, data=data)
