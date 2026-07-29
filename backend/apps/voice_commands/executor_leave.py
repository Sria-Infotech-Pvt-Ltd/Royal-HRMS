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

from rest_framework.test import APIRequestFactory, force_authenticate

_APPLY_LEAVE_SUBMIT_FAILED_MESSAGE = 'Could not submit the leave request.'

# One shared factory — building a request through it doesn't touch the
# database or any shared state, just Django's request/response plumbing.
# Reused for apply_leave, the only intent here that dispatches through an
# existing DRF view rather than duplicating its query/scoping logic.
_api_request_factory = APIRequestFactory()

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


def execute_check_leave_balance(request) -> ExecutionResult:
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
