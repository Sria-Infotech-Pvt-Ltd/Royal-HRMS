from __future__ import annotations

from datetime import date

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
from apps.hrms.views.leave import LeaveRequestListCreateView

from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import text

from rest_framework.test import APIRequestFactory, force_authenticate

_APPLY_LEAVE_SUBMIT_FAILED_MESSAGE = {
    'en': 'Could not submit the leave request.',
    'hi': 'छुट्टी का अनुरोध सबमिट नहीं हो सका।',
}

# Spoken instead of the full detail (own balance figures / own leave dates)
# in `message` — TTS confidentiality, same reasoning as executor_payroll.py's
# _OWN_PAYSLIP_SPEECH_MESSAGE. See executor_result.ExecutionResult.speech_message.
_LEAVE_BALANCE_SPEECH_MESSAGE = {
    'en': 'Your leave balance is ready to view.',
    'hi': 'आपकी छुट्टी का शेष विवरण देखने के लिए तैयार है।',
}
_LEAVE_STATUS_SPEECH_MESSAGE = {
    'en': 'Your leave status is ready to view.',
    'hi': 'आपकी छुट्टी की स्थिति देखने के लिए तैयार है।',
}
_LEAVE_CANCELLED_SPEECH_MESSAGE = {
    'en': 'Your leave request has been cancelled.',
    'hi': 'आपका छुट्टी का अनुरोध रद्द कर दिया गया है।',
}

_NO_BALANCE_RECORDS_TEMPLATE = {
    'en': 'You have no leave balance records for {year}.',
    'hi': '{year} के लिए आपका कोई छुट्टी शेष रिकॉर्ड नहीं है।',
}
_BALANCE_SUMMARY_TEMPLATE = {
    'en': 'Your leave balance — {summary}.',
    'hi': 'आपकी छुट्टी का शेष — {summary}।',
}
_NO_REQUESTS_ON_RECORD_MESSAGE = {
    'en': 'You have no leave requests on record.',
    'hi': 'आपका कोई छुट्टी अनुरोध रिकॉर्ड में नहीं है।',
}
_LATEST_REQUEST_STATUS_TEMPLATE = {
    'en': (
        'Your most recent leave request — {leave_type_display} '
        'from {start_date} to {end_date} — is {status_label}.'
    ),
    'hi': (
        'आपका सबसे हाल का छुट्टी अनुरोध — {leave_type_display}, '
        '{start_date} से {end_date} तक — {status_label} है।'
    ),
}
_MORE_REQUESTS_ON_FILE_TEMPLATE = {
    'en': ' You have {count} more recent request(s) on file.',
    'hi': ' आपके रिकॉर्ड में {count} और हाल के अनुरोध हैं।',
}
_NO_CANCELLABLE_REQUESTS_MESSAGE = {
    'en': "You don't have any pending leave requests to cancel.",
    'hi': 'रद्द करने के लिए आपका कोई लंबित छुट्टी अनुरोध नहीं है।',
}
_MULTIPLE_CANCELLABLE_REQUESTS_MESSAGE = {
    'en': (
        'You have more than one pending leave request — please specify which one, '
        'or cancel it from the dashboard.'
    ),
    'hi': (
        'आपके एक से अधिक लंबित छुट्टी अनुरोध हैं — कृपया बताएं कि कौन सा, '
        'या इसे डैशबोर्ड से रद्द करें।'
    ),
}
_LEAVE_CANCELLED_TEMPLATE = {
    'en': 'Your {leave_type} request from {start_date} to {end_date} has been cancelled.',
    'hi': 'आपका {leave_type} अनुरोध, {start_date} से {end_date} तक, रद्द कर दिया गया है।',
}
_LEAVE_SUBMITTED_TEMPLATE = {
    'en': 'Your {leave_type} leave request from {start_date} to {end_date} has been submitted.',
    'hi': 'आपका {leave_type} छुट्टी अनुरोध, {start_date} से {end_date} तक, सबमिट कर दिया गया है।',
}

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for apply_leave, the only intent here that dispatches through an
# existing DRF view rather than duplicating its query/scoping logic.
_api_request_factory = APIRequestFactory()

# Presentation-only labels for TTS-friendly phrasing — not business logic,
# just how the raw status codes read out loud. Mirrors frontend/app/dashboard
# /leave/_data.ts's STATUS_LABEL mapping (English side only; the Hindi side
# is this app's own addition, Phase 3).
_STATUS_LABELS = {
    REQ_PENDING: {'en': 'pending manager approval', 'hi': 'मैनेजर की स्वीकृति लंबित'},
    REQ_L2_PENDING: {'en': 'pending HR approval', 'hi': 'एचआर की स्वीकृति लंबित'},
    REQ_APPROVED: {'en': 'approved', 'hi': 'स्वीकृत'},
    REQ_REJECTED: {'en': 'rejected', 'hi': 'अस्वीकृत'},
    REQ_CANCELLED: {'en': 'cancelled', 'hi': 'रद्द'},
}


def execute_check_leave_balance(request) -> ExecutionResult:
    """Same query LeaveBalanceView.get() runs for the caller's own balances, current year."""
    year = date.today().year
    balances = LeaveBalance.objects.filter(employee=request.user, year=year).order_by('leave_type')
    data = LeaveBalanceSerializer(balances, many=True).data

    if not data:
        return ExecutionResult(
            success=True,
            message=text(_NO_BALANCE_RECORDS_TEMPLATE).format(year=year),
            data=data,
        )

    summary = ', '.join(f"{row['leave_type_display']}: {row['available_days']}" for row in data)
    return ExecutionResult(
        success=True, message=text(_BALANCE_SUMMARY_TEMPLATE).format(summary=summary), data=data,
        speech_message=text(_LEAVE_BALANCE_SPEECH_MESSAGE),
    )


def execute_check_leave_status(request) -> ExecutionResult:
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
        return ExecutionResult(success=True, message=text(_NO_REQUESTS_ON_RECORD_MESSAGE), data=data)

    latest = data[0]
    status_label = text(_STATUS_LABELS.get(latest['status'], {'en': latest['status'], 'hi': latest['status']}))
    message = text(_LATEST_REQUEST_STATUS_TEMPLATE).format(
        leave_type_display=latest['leave_type_display'],
        start_date=latest['start_date'], end_date=latest['end_date'], status_label=status_label,
    )
    if len(data) > 1:
        message += text(_MORE_REQUESTS_ON_FILE_TEMPLATE).format(count=len(data) - 1)

    return ExecutionResult(
        success=True, message=message, data=data, speech_message=text(_LEAVE_STATUS_SPEECH_MESSAGE),
    )


def execute_cancel_leave(request) -> ExecutionResult:
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
        return ExecutionResult(success=False, message=text(_NO_CANCELLABLE_REQUESTS_MESSAGE))

    if len(cancellable) > 1:
        return ExecutionResult(success=False, message=text(_MULTIPLE_CANCELLABLE_REQUESTS_MESSAGE))

    leave_request = cancellable[0]
    leave_request.status = REQ_CANCELLED
    leave_request.save(update_fields=['status', 'updated_at'])

    return ExecutionResult(
        success=True,
        message=text(_LEAVE_CANCELLED_TEMPLATE).format(
            leave_type=leave_request.get_leave_type_display(),
            start_date=leave_request.start_date, end_date=leave_request.end_date,
        ),
        speech_message=text(_LEAVE_CANCELLED_SPEECH_MESSAGE),
    )


def execute_apply_leave(request, slots: dict) -> ExecutionResult:
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
        message = text(_APPLY_LEAVE_SUBMIT_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            # External, dynamic message straight from LeaveRequestListCreateView's
            # own validation (e.g. an overlapping-request rejection) — English
            # only, regardless of detected language. Translating it would mean
            # localizing hrms's own serializers, outside voice_commands and
            # outside this phase's scope; flagged in the Phase 3 report.
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    message = text(_LEAVE_SUBMITTED_TEMPLATE).format(
        leave_type=slots['leave_type'], start_date=slots['start_date'], end_date=slots['end_date'],
    )
    return ExecutionResult(success=True, message=message, data=data)
