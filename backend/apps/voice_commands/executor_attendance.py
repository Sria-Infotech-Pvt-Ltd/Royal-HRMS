from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from django.utils import timezone

from rest_framework.test import APIRequestFactory, force_authenticate

from core.responses import get_client_ip

from apps.attendance.models import AttendancePunch
from apps.attendance.serializers_my_attendance import (
    MonthlySummarySerializer,
    PunchWriteSerializer,
    StatsSerializer,
)
from apps.attendance.services_attendance import AttendanceDashboardService, PunchService
from apps.attendance.views.my_attendance import AttendanceCorrectionView

from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import text

logger = logging.getLogger(__name__)

_CORRECTION_SUBMIT_FAILED_MESSAGE = {
    'en': 'Could not submit the attendance correction request.',
    'hi': 'उपस्थिति सुधार अनुरोध सबमिट नहीं हो सका।',
}
_CLOCK_IN_SUCCESS_MESSAGE = {
    'en': 'You have been clocked in successfully.',
    'hi': 'आपकी उपस्थिति सफलतापूर्वक दर्ज कर दी गई है।',
}
_CLOCK_OUT_SUCCESS_MESSAGE = {
    'en': 'You have been clocked out successfully.',
    'hi': 'आपका क्लॉक-आउट सफलतापूर्वक दर्ज कर दिया गया है।',
}
_PUNCH_FAILED_MESSAGE = {
    'en': 'Could not process the request.',
    'hi': 'अनुरोध संसाधित नहीं किया जा सका।',
}
_ATTENDANCE_STATS_TEMPLATE = {
    'en': (
        "This month you've been present {days_present} of {working_days} working days "
        '({attendance_percentage}% attendance), with {late_arrivals} late arrival(s) '
        'and an average of {avg_hours_per_day} hours per day.'
    ),
    'hi': (
        'इस महीने आप {working_days} कार्य दिवसों में से {days_present} दिन उपस्थित रहे हैं '
        '({attendance_percentage}% उपस्थिति), {late_arrivals} बार देर से आए, '
        'और औसतन प्रतिदिन {avg_hours_per_day} घंटे काम किया।'
    ),
}
_ATTENDANCE_SUMMARY_TEMPLATE = {
    'en': (
        'This month — {days_present} days present, {days_absent} absent, '
        '{leave_days} leave day(s), {half_days} half day(s), '
        'out of {working_days} working days.'
    ),
    'hi': (
        'इस महीने — {working_days} कार्य दिवसों में से {days_present} दिन उपस्थित, '
        '{days_absent} अनुपस्थित, {leave_days} छुट्टी के दिन, {half_days} आधे दिन।'
    ),
}

# Building a request through this doesn't touch the database or any shared
# state, just Django's request/response plumbing — same reasoning
# executor_leave.py's own factory instance gives; kept as a separate
# instance here rather than importing that one, matching the existing
# one-factory-per-executor-module convention.
_api_request_factory = APIRequestFactory()


def execute_clock_in(
    request, attendance_mode: Optional[str],
    latitude: Optional[float] = None, longitude: Optional[float] = None,
    face_embedding: Optional[list] = None, liveness_passed: Optional[bool] = None,
    liveness_score: Optional[float] = None, capture_session_id: str = '',
) -> ExecutionResult:
    """No mode said -> office, same default a fresh web punch gets
    (PunchWriteSerializer's own default, services_attendance.py:114).

    face_embedding etc. are only ever non-None once
    conversation_clock_in_face.py has already run its own "taking facial
    proof" turn and matched — see that module. Passed straight through so
    PunchService.record_punch's own FaceVerificationService call (the single
    authoritative check) still runs; this is never a second, separate gate."""
    mode = attendance_mode or AttendancePunch.MODE_OFFICE
    return _execute_punch(
        request, punch_type='IN', attendance_mode=mode,
        success_message=text(_CLOCK_IN_SUCCESS_MESSAGE),
        latitude=latitude, longitude=longitude, face_embedding=face_embedding,
        liveness_passed=liveness_passed, liveness_score=liveness_score,
        capture_session_id=capture_session_id,
    )


def execute_clock_out(
    request, attendance_mode: Optional[str],
    latitude: Optional[float] = None, longitude: Optional[float] = None,
    face_embedding: Optional[list] = None, liveness_passed: Optional[bool] = None,
    liveness_score: Optional[float] = None, capture_session_id: str = '',
) -> ExecutionResult:
    """No mode said -> inherit today's still-open IN punch's mode, mirroring
    the web ClockWidget (reuses the same mode-dropdown value for both the
    IN and OUT clicks — see useClockWidget.ts / ClockWidget.tsx:89).
    Defaulting to office here instead would force a geofence check
    against the office on a day that was opened as WFH/field/etc.

    face_embedding etc. — see execute_clock_in's docstring above."""
    mode = attendance_mode or _resolve_clock_out_mode(request.user)
    return _execute_punch(
        request, punch_type='OUT', attendance_mode=mode,
        success_message=text(_CLOCK_OUT_SUCCESS_MESSAGE),
        latitude=latitude, longitude=longitude, face_embedding=face_embedding,
        liveness_passed=liveness_passed, liveness_score=liveness_score,
        capture_session_id=capture_session_id,
    )


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
    face_embedding: Optional[list] = None, liveness_passed: Optional[bool] = None,
    liveness_score: Optional[float] = None, capture_session_id: str = '',
) -> ExecutionResult:
    """
    Same path as AttendancePunchView.post() — PunchWriteSerializer then
    PunchService.record_punch(). latitude/longitude/face_embedding/etc. are
    passed straight into the serializer exactly like the manual ClockWidget's
    punch payload (frontend/hooks/useClockWidget.ts) — PunchWriteSerializer
    already defaults all of them to None/allows omission, so there's nothing
    extra to validate here.
    """
    serializer = PunchWriteSerializer(data={
        'punch_type': punch_type,
        'attendance_mode': attendance_mode,
        'latitude': latitude,
        'longitude': longitude,
        'face_embedding': face_embedding,
        'liveness_passed': liveness_passed,
        'liveness_score': liveness_score,
        'capture_session_id': capture_session_id,
        # Tags this punch distinctly from a browser punch — kept even though
        # voice DOES have camera access now (see AttendancePunch's own
        # docstring), so audit trails still show which channel initiated it.
        'source': 'voice',
    })
    if not serializer.is_valid():
        logger.error('Voice %s payload invalid: %s', punch_type, serializer.errors)
        return ExecutionResult(success=False, message=text(_PUNCH_FAILED_MESSAGE))

    punch_data = serializer.validated_data.copy()
    punch_data['ip_address'] = get_client_ip(request)
    # Voice runs through the same browser tab as the web dashboard — same TLS
    # guarantee applies, checked the same way the web punch view checks it.
    # NOTE: request.is_secure() only reflects the real scheme when Django
    # itself terminates TLS; if this is ever deployed behind a reverse proxy
    # that terminates TLS instead, config/settings.py needs
    # SECURE_PROXY_SSL_HEADER set too, or this (and the web view's identical
    # check) will misread every request as insecure.
    punch_data['is_secure'] = request.is_secure()

    try:
        PunchService.record_punch(request.user, punch_data)
    except ValueError as exc:
        return ExecutionResult(success=False, message=str(exc))
    except PermissionError as exc:
        return ExecutionResult(success=False, message=str(exc))

    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        from core.notification_groups import notification_group_name
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                notification_group_name(request.user.id),
                {'type': 'attendance.update'},
            )
    except Exception:
        pass

    return ExecutionResult(success=True, message=success_message)


def execute_check_attendance_stats(request) -> ExecutionResult:
    """Same query AttendanceStatsView.get() runs for the caller's own stats, current month/year, no employee_id."""
    today = date.today()
    stats = AttendanceDashboardService.get_stats(request.user, today.year, today.month)
    data = StatsSerializer(stats).data

    message = text(_ATTENDANCE_STATS_TEMPLATE).format(
        days_present=data['days_present'], working_days=data['working_days'],
        attendance_percentage=data['attendance_percentage'], late_arrivals=data['late_arrivals'],
        avg_hours_per_day=data['avg_hours_per_day'],
    )
    return ExecutionResult(success=True, message=message, data=data)


def execute_check_attendance_summary(request) -> ExecutionResult:
    """Same query AttendanceSummaryView.get() runs for the caller's own summary, current month/year, no employee_id."""
    today = date.today()
    summary = AttendanceDashboardService.get_monthly_summary(request.user, today.year, today.month)
    data = MonthlySummarySerializer(summary).data

    message = text(_ATTENDANCE_SUMMARY_TEMPLATE).format(
        days_present=data['days_present'], days_absent=data['days_absent'],
        leave_days=data['leave_days'], half_days=data['half_days'], working_days=data['working_days'],
    )
    return ExecutionResult(success=True, message=message, data=data)


def execute_request_attendance_correction(request, slots: dict) -> ExecutionResult:
    """
    Submits the fully-collected slots (date, punch_type, correct_in_time
    and/or correct_out_time, reason — see voice_commands/
    conversation_attendance_correction.py for how they're gathered across
    turns) to AttendanceCorrectionView.post() directly, rather than
    duplicating its conflict-check (one pending correction per date) and
    audit-logging here — same APIRequestFactory + force_authenticate
    approach executor_leave.execute_apply_leave uses for
    LeaveRequestListCreateView.
    """
    payload = {
        'date': slots['date'].isoformat(),
        'punch_type': slots['punch_type'],
        'reason': slots['reason'],
    }
    if slots.get('correct_in_time'):
        payload['correct_in_time'] = slots['correct_in_time'].strftime('%H:%M')
    if slots.get('correct_out_time'):
        payload['correct_out_time'] = slots['correct_out_time'].strftime('%H:%M')

    django_request = _api_request_factory.post('/api/attendance/correction/', payload, format='json')
    force_authenticate(django_request, user=request.user)
    response = AttendanceCorrectionView.as_view()(django_request)

    if response.status_code >= 400:
        message = text(_CORRECTION_SUBMIT_FAILED_MESSAGE)
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic — see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    # response.data['message'] here is AttendanceCorrectionView's own success
    # message — external and dynamic, same as the failure path's passthrough
    # above (see executor_leave's own note) — not one of this app's own
    # strings, so there's no Hindi counterpart to select for it.
    message = response.data.get('message') if isinstance(response.data, dict) else text(_CORRECTION_SUBMIT_FAILED_MESSAGE)
    return ExecutionResult(success=True, message=message, data=data)
