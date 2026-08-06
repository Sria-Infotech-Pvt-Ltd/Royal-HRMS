"""
My Attendance views.

All views use APIView. Each view has one responsibility.
Business logic lives in the service layer — views only coordinate
request parsing, permission checks, and response shaping.

Endpoints:
  POST   /api/attendance/punch/          — Clock In / Clock Out
  GET    /api/attendance/today/          — ClockWidget data
  GET    /api/attendance/stats/          — Stat cards (?month=&year=)
  GET    /api/attendance/summary/        — Monthly Summary grid (?month=&year=)
  GET    /api/attendance/calendar/       — Calendar + detail table (?month=&year=)
  POST   /api/attendance/correction/     — Submit Attendance Correction Request
  GET    /api/attendance/corrections/my/ — Own correction requests + status (?status=&date_from=&date_to=)
"""
from __future__ import annotations

import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, get_client_ip, success

from apps.attendance.models import AttendanceCorrection
from apps.attendance.serializers_my_attendance import (
    CalendarSerializer,
    CorrectionReadSerializer,
    CorrectionWriteSerializer,
    HistoryRowSerializer,
    MonthYearQuerySerializer,
    MonthlySummarySerializer,
    MyCorrectionsFilterSerializer,
    PunchWriteSerializer,
    StatsSerializer,
    TodayAttendanceSerializer,
)
from apps.attendance.services_attendance import (
    AttendanceDashboardService,
    PunchService,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if user.role.name == 'system_admin' or getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _resolve_target_user(request):
    """Return (target_user, err). If no employee_id param, returns (request.user, None)."""
    employee_id = request.query_params.get('employee_id')
    if not employee_id:
        return request.user, None
    # Employees can only view their own attendance — looking up others is HR/manager only
    if not (_has_perm(request.user, 'attendance.view') or _has_perm(request.user, 'employees.view')):
        return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
    from apps.accounts.models import User
    user = User.objects.filter(employee_id=employee_id).first()
    if not user:
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

    # Scope who a non-system_admin can look up — managers get their direct
    # reports only, everyone else (e.g. hr_admin) is scoped to their own
    # branch, mirroring the reporting-chain/branch scoping used in leave.py.
    if not _has_perm(request.user, 'settings.edit'):
        if request.user.role and getattr(request.user.role, 'can_manage_team', False):
            if user.reporting_manager_id != request.user.id:
                return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        elif request.user.branch and user.branch != request.user.branch:
            return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

    return user, None


def _write_correction_submitted_audit(employee, data: dict) -> None:
    """Write CORRECTION_SUBMITTED audit entry — must never raise."""
    from apps.attendance.models import AttendanceAuditLog, AttendanceRecord
    from apps.attendance.services_audit_log import write_audit_log
    try:
        record = AttendanceRecord.objects.filter(
            employee=employee, date=data['date'],
        ).first()
        write_audit_log(
            employee=employee,
            date=data['date'],
            event=AttendanceAuditLog.EVENT_CORRECTION_SUBMITTED,
            performed_by=employee,
            record=record,
            new_value=data['punch_type'],
            action='Employee submitted attendance correction request',
        )
    except Exception as exc:
        logger.error('Correction submitted audit failed: %s', exc)


# ── Punch (Clock In / Clock Out) ──────────────────────────────────────────────

class AttendancePunchView(APIView):
    """
    POST /api/attendance/punch/

    Body: { "punch_type": "IN" | "OUT" }

    Stores the punch, processes the day's attendance record, and returns
    the updated today-session so ClockWidget can refresh in one round-trip.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = PunchWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        punch_data = serializer.validated_data.copy()
        punch_data['ip_address'] = get_client_ip(request)
        # Confirms TLS on this leg before FaceVerificationService ever touches
        # a submitted embedding — see that service's own precondition check.
        punch_data['is_secure']  = request.is_secure()

        try:
            PunchService.record_punch(request.user, punch_data)
        except ValueError as exc:
            return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return error(str(exc), http_status=status.HTTP_403_FORBIDDEN)

        punch_type = punch_data['punch_type']
        session    = PunchService.get_today_session(request.user)

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

        return success(
            f'Clocked {"in" if punch_type == "IN" else "out"} successfully.',
            TodayAttendanceSerializer(session).data,
        )


# ── Today's Session ───────────────────────────────────────────────────────────

class TodayAttendanceView(APIView):
    """
    GET /api/attendance/today/

    Returns everything ClockWidget needs:
      is_clocked_in, punches[], total_seconds, session_seconds, date_display
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        session = PunchService.get_today_session(request.user)
        return success(
            "Today's attendance retrieved successfully.",
            TodayAttendanceSerializer(session).data,
        )


# ── Stat Cards ────────────────────────────────────────────────────────────────

class AttendanceStatsView(APIView):
    """
    GET /api/attendance/stats/?month=6&year=2025

    Powers the four stat cards: Days Present, Late Arrivals, Avg Hours/Day,
    Attendance %.  Defaults to the current month if params omitted.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qp = MonthYearQuerySerializer(data=request.query_params)
        if not qp.is_valid():
            return error(first_error(qp.errors), data=qp.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        target, err = _resolve_target_user(request)
        if err:
            return err

        params = qp.validated_data
        stats  = AttendanceDashboardService.get_stats(
            target, params['year'], params['month'],
        )
        return success('Stats retrieved successfully.', StatsSerializer(stats).data)


# ── Monthly Summary ───────────────────────────────────────────────────────────

class AttendanceSummaryView(APIView):
    """
    GET /api/attendance/summary/?month=6&year=2025

    Powers the Monthly Summary 6-cell grid:
      Working Days, Days Present, Days Absent, Leave Days, Half Days, OT Hours.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qp = MonthYearQuerySerializer(data=request.query_params)
        if not qp.is_valid():
            return error(first_error(qp.errors), data=qp.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        target, err = _resolve_target_user(request)
        if err:
            return err

        params  = qp.validated_data
        summary = AttendanceDashboardService.get_monthly_summary(
            target, params['year'], params['month'],
        )
        return success(
            'Monthly summary retrieved successfully.',
            MonthlySummarySerializer(summary).data,
        )


# ── Calendar ──────────────────────────────────────────────────────────────────

class AttendanceCalendarView(APIView):
    """
    GET /api/attendance/calendar/?month=6&year=2025

    Returns per-day data keyed by day number.
    Shape matches CalendarGrid's Record<number, DayRecord> exactly.
    Also returns the detail-table rows (used by MonthDetail component).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qp = MonthYearQuerySerializer(data=request.query_params)
        if not qp.is_valid():
            return error(first_error(qp.errors), data=qp.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        target, err = _resolve_target_user(request)
        if err:
            return err

        params   = qp.validated_data
        calendar = AttendanceDashboardService.get_calendar(
            target, params['year'], params['month'],
        )
        history = AttendanceDashboardService.get_history(
            target, params['year'], params['month'],
        )
        return success('Calendar retrieved successfully.', {
            'calendar': CalendarSerializer(calendar).data,
            'history':  HistoryRowSerializer(history, many=True).data,
            'month':    params['month'],
            'year':     params['year'],
        })


# ── Attendance Correction Request ─────────────────────────────────────────────

class AttendanceCorrectionView(APIView):
    """
    POST /api/attendance/correction/

    Submits a regularization request for a missed or incorrect punch.

    Business rules enforced:
    - Date cannot be in the future.
    - Correct In Time required if punch_type is IN or BOTH.
    - Correct Out Time required if punch_type is OUT or BOTH.
    - Cannot submit if a pending correction already exists for the same date.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = CorrectionWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data     = serializer.validated_data
        employee = request.user

        with transaction.atomic():
            # select_for_update prevents a race where two concurrent submissions
            # both pass the exists() check before either creates the record.
            if AttendanceCorrection.objects.select_for_update().filter(
                employee=employee,
                date=data['date'],
                status__in=[AttendanceCorrection.STATUS_PENDING, AttendanceCorrection.STATUS_L2_PENDING],
            ).exists():
                return error(
                    'A correction request is already pending for this date. '
                    'Please wait for it to be reviewed before submitting another.',
                    http_status=status.HTTP_409_CONFLICT,
                )

            from apps.attendance.services_hr_corrections import submit_correction
            correction = submit_correction(
                employee=employee,
                date=data['date'],
                punch_type=data['punch_type'],
                requested_in_time=data.get('correct_in_time'),
                requested_out_time=data.get('correct_out_time'),
                reason=data['reason'],
                notes=data.get('notes', ''),
            )
        _write_correction_submitted_audit(employee, data)

        logger.info(
            'Correction submitted: employee=%s date=%s type=%s',
            employee.pk, data['date'], data['punch_type'],
        )

        return success(
            'Attendance correction request submitted successfully. '
            'Your manager will review it within the regularization window.',
            CorrectionReadSerializer({
                'id':         correction.pk,
                'date':       correction.date,
                'punch_type': correction.punch_type,
                'reason':     correction.reason,
                'status':     correction.status,
                'created_at': correction.created_at,
            }).data,
            http_status=status.HTTP_201_CREATED,
        )


class MyCorrectionsListView(APIView):
    """
    GET /api/attendance/corrections/my/

    An employee's own attendance correction / un-punch requests, newest
    first, with approval status and reviewer info — read-only.
    Query params: status, date_from, date_to; ?page=&page_size= for pagination.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        ser = MyCorrectionsFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_hr_corrections import list_my_corrections
        rows = list_my_corrections(
            request.user,
            status_filter=ser.validated_data['status'],
            date_from=ser.validated_data['date_from'],
            date_to=ser.validated_data['date_to'],
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} correction request(s) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )
