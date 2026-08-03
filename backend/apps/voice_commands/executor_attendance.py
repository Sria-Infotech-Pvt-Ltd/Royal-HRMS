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

logger = logging.getLogger(__name__)

_CORRECTION_SUBMIT_FAILED_MESSAGE = 'Could not submit the attendance correction request.'

# Building a request through this doesn't touch the database or any shared
# state, just Django's request/response plumbing — same reasoning
# executor_leave.py's own factory instance gives; kept as a separate
# instance here rather than importing that one, matching the existing
# one-factory-per-executor-module convention.
_api_request_factory = APIRequestFactory()


def execute_clock_in(
    request, attendance_mode: Optional[str],
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> ExecutionResult:
    """No mode said -> office, same default a fresh web punch gets
    (PunchWriteSerializer's own default, services_attendance.py:114)."""
    mode = attendance_mode or AttendancePunch.MODE_OFFICE
    return _execute_punch(
        request, punch_type='IN', attendance_mode=mode,
        success_message='You have been clocked in successfully.',
        latitude=latitude, longitude=longitude,
    )


def execute_clock_out(
    request, attendance_mode: Optional[str],
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> ExecutionResult:
    """No mode said -> inherit today's still-open IN punch's mode, mirroring
    the web ClockWidget (reuses the same mode-dropdown value for both the
    IN and OUT clicks — see useClockWidget.ts / ClockWidget.tsx:89).
    Defaulting to office here instead would force a geofence check
    against the office on a day that was opened as WFH/field/etc."""
    mode = attendance_mode or _resolve_clock_out_mode(request.user)
    return _execute_punch(
        request, punch_type='OUT', attendance_mode=mode,
        success_message='You have been clocked out successfully.',
        latitude=latitude, longitude=longitude,
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

    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f'notifications_{request.user.id}',
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

    message = (
        f"This month you've been present {data['days_present']} of {data['working_days']} working days "
        f"({data['attendance_percentage']}% attendance), with {data['late_arrivals']} late arrival(s) "
        f"and an average of {data['avg_hours_per_day']} hours per day."
    )
    return ExecutionResult(success=True, message=message, data=data)


def execute_check_attendance_summary(request) -> ExecutionResult:
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
        message = _CORRECTION_SUBMIT_FAILED_MESSAGE
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    message = response.data.get('message') if isinstance(response.data, dict) else _CORRECTION_SUBMIT_FAILED_MESSAGE
    return ExecutionResult(success=True, message=message, data=data)
