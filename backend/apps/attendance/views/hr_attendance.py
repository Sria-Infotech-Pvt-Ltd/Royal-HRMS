"""
HR Attendance Management views.

All business logic lives in services_hr, services_hr_audit, services_hr_ops.
Views: validate input → call service → return response.
"""
from __future__ import annotations

import datetime
import logging

from django.http import HttpResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.serializers_hr import (
    AttendanceListFilterSerializer,
    CorrectionListFilterSerializer,
    CorrectionReviewSerializer,
    DateFilterSerializer,
    HRAttendanceEditSerializer,
    HRAttendanceManualCreateSerializer,
    OvertimeWriteSerializer,
    WeeklyOffAssignmentFilterSerializer,
    WeeklyOffAssignmentWriteSerializer,
    WeeklyOffBulkAssignmentWriteSerializer,
)
from apps.attendance.services_hr import (
    assign_weekly_off,
    build_weekly_off_assignment_queryset,
    bulk_assign_weekly_off,
    get_attendance_detail,
    get_attendance_list,
    get_dashboard_stats,
    get_weekly_off_assignment_history,
    serialize_weekly_off_assignment_row,
)
from apps.attendance.services_hr_audit import (
    get_invalid_punches,
    get_unpunches,
)
from apps.attendance.services_hr_ops import (
    create_overtime,
    export_attendance_csv,
    import_attendance_csv,
    list_overtime,
)
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm

logger = logging.getLogger(__name__)


def _is_unrestricted(user) -> bool:
    return _has_perm(user, 'settings.edit')


def _branch_scope(user, requested: str) -> str:
    """
    Resolve the effective branch filter for the current user.

    Unrestricted users: honour whatever branch was requested (empty = all).
    Restricted users (hr_admin etc.): always use their own branch, ignoring
    the query parameter — they cannot see outside their branch.

    Managers should be scoped by _manager_scope_employee_ids instead (their
    own direct reports, not their whole branch) — callers must check that
    first and only fall back to this branch value when it returns None.
    """
    if _is_unrestricted(user):
        return requested
    return getattr(user, 'branch', '') or ''


def _manager_scope_employee_ids(user) -> list[str] | None:
    """
    Returns the employee IDs a manager is restricted to (their own direct
    reports) — or None if this user isn't manager-scoped, meaning the caller
    should fall back to _branch_scope instead (hr_admin/hr/system_admin).

    A branch commonly has multiple managers, each responsible for a
    different team — scoping a manager by branch (like HR is) would show
    them every other manager's team too, not just their own.
    """
    try:
        if user.role and getattr(user.role, 'can_manage_team', False):
            return list(
                user.direct_reports.filter(is_active=True).values_list('id', flat=True)
            )
    except Exception:
        pass
    return None


def _manager_can_access_employee(user, employee) -> bool:
    """
    Single-record gate for manager-scoped users: True when this user is not
    manager-scoped (HR/system_admin, no restriction) or when `employee` is
    one of their own direct reports. Used by views that act on one specific
    employee/record rather than a filtered list, where a queryset filter
    can't apply.
    """
    employee_ids = _manager_scope_employee_ids(user)
    if employee_ids is None:
        return True
    return str(employee.pk) in {str(i) for i in employee_ids}


# ── Dashboard ─────────────────────────────────────────────────────────────────

class HRAttendanceDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = DateFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        data = ser.validated_data
        employee_ids = _manager_scope_employee_ids(request.user)
        stats = get_dashboard_stats(
            target_date=data['date'],
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=employee_ids,
        )
        return success('Dashboard stats loaded.', stats)


# ── Attendance List ───────────────────────────────────────────────────────────

class HRAttendanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = AttendanceListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
        filters['employee_ids'] = _manager_scope_employee_ids(request.user)
        rows = get_attendance_list(filters)
        page_obj, paginator = paginate(rows, request)
        return success(
            'Attendance list loaded.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── Attendance Detail ─────────────────────────────────────────────────────────

class HRAttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        target_date_str = request.query_params.get('date', '')
        employee_id_str = request.query_params.get('employee_id', '')

        target_date = datetime.date.today()
        if target_date_str:
            try:
                target_date = datetime.date.fromisoformat(target_date_str)
            except ValueError:
                return error('Invalid date format. Use YYYY-MM-DD.')

        detail = get_attendance_detail(
            record_id=str(pk),
            target_date=target_date,
            employee_id_str=employee_id_str,
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        if not detail:
            return error('Attendance record not found.', http_status=404)

        return success('Attendance detail loaded.', detail)

    def patch(self, request, pk: str):
        """HR edits an existing attendance record — status, punch times, note."""
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = HRAttendanceEditSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.models import AttendanceRecord, AttendanceAuditLog
        from apps.attendance.services_audit_log import write_audit_log
        from apps.payroll.models import PayrollCycle

        try:
            record = AttendanceRecord.objects.select_related('employee').get(pk=pk)
        except AttendanceRecord.DoesNotExist:
            return error('Attendance record not found.', http_status=404)

        if not _manager_can_access_employee(request.user, record.employee):
            return error('Attendance record not found.', http_status=404)

        locked = PayrollCycle.objects.filter(
            cycle_start__lte=record.date,
            cycle_end__gte=record.date,
            status__in=['paid', 'closed'],
        ).first()
        if locked:
            return error(
                f'This date is locked — payroll cycle is {locked.get_status_display()}.',
                http_status=409,
            )

        data = ser.validated_data
        old_val = (
            f"{record.status} | "
            f"{record.first_punch_in or '—'} → {record.last_punch_out or '—'}"
        )

        if 'status' in data:
            record.status = data['status']
        if 'clock_in' in data:
            record.first_punch_in = data['clock_in']
        if 'clock_out' in data:
            record.last_punch_out = data['clock_out']
        record.note = data.get('note', record.note)

        if record.first_punch_in and record.last_punch_out:
            import datetime as _dt
            _dummy = _dt.date(2000, 1, 1)
            t_in  = _dt.datetime.combine(_dummy, record.first_punch_in)
            t_out = _dt.datetime.combine(_dummy, record.last_punch_out)
            if t_out < t_in:
                t_out = _dt.datetime.combine(_dummy + _dt.timedelta(days=1), record.last_punch_out)
            record.total_working_minutes = max(0, int((t_out - t_in).total_seconds() / 60))
        elif not record.first_punch_in and not record.last_punch_out:
            record.total_working_minutes = 0

        record.save()

        new_val = (
            f"{record.status} | "
            f"{record.first_punch_in or '—'} → {record.last_punch_out or '—'}"
        )
        write_audit_log(
            employee=record.employee,
            date=record.date,
            event=AttendanceAuditLog.EVENT_MANUALLY_EDITED,
            performed_by=request.user,
            record=record,
            old_value=old_val,
            new_value=new_val,
            action='HR manually edited attendance record.',
            remarks=data.get('reason', ''),
        )
        return success('Attendance record updated.', {'record_id': str(record.id)})


# ── HR Attendance Manual Create ───────────────────────────────────────────────

class HRAttendanceCreateView(APIView):
    """HR creates an attendance record for a day with no existing record."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = HRAttendanceManualCreateSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        data = ser.validated_data

        import uuid as _uuid_mod
        from django.contrib.auth import get_user_model
        from apps.attendance.models import AttendanceRecord, AttendanceAuditLog
        from apps.attendance.services_audit_log import write_audit_log
        from apps.payroll.models import PayrollCycle

        User = get_user_model()
        employee_pk = str(data['employee_id'])
        try:
            _uuid_mod.UUID(employee_pk)
            employee = User.objects.filter(pk=employee_pk, is_active=True).first()
        except (ValueError, AttributeError):
            employee = User.objects.filter(employee_id=employee_pk, is_active=True).first()

        if not employee:
            return error('Employee not found.', http_status=404)

        if not _manager_can_access_employee(request.user, employee):
            return error('Employee not found.', http_status=404)

        target_date = data['date']

        locked = PayrollCycle.objects.filter(
            cycle_start__lte=target_date,
            cycle_end__gte=target_date,
            status__in=['paid', 'closed'],
        ).first()
        if locked:
            return error(
                f'This date is locked — payroll cycle is {locked.get_status_display()}.',
                http_status=409,
            )

        if AttendanceRecord.objects.filter(employee=employee, date=target_date).exists():
            return error(
                'An attendance record already exists for this date. Use edit instead.',
                http_status=409,
            )

        clock_in  = data.get('clock_in')
        clock_out = data.get('clock_out')
        total_minutes = 0
        if clock_in and clock_out:
            import datetime as _dt
            _dummy = _dt.date(2000, 1, 1)
            t_in  = _dt.datetime.combine(_dummy, clock_in)
            t_out = _dt.datetime.combine(_dummy, clock_out)
            if t_out < t_in:
                t_out = _dt.datetime.combine(_dummy + _dt.timedelta(days=1), clock_out)
            total_minutes = max(0, int((t_out - t_in).total_seconds() / 60))

        record = AttendanceRecord.objects.create(
            employee=employee,
            date=target_date,
            status=data['status'],
            first_punch_in=clock_in,
            last_punch_out=clock_out,
            total_working_minutes=total_minutes,
            note=data.get('note', ''),
        )

        write_audit_log(
            employee=employee,
            date=target_date,
            event=AttendanceAuditLog.EVENT_MANUALLY_EDITED,
            performed_by=request.user,
            record=record,
            old_value='No Record',
            new_value=(
                f"{record.status} | "
                f"{record.first_punch_in or '—'} → {record.last_punch_out or '—'}"
            ),
            action='HR manually created attendance record.',
            remarks=data.get('reason', ''),
        )

        return success('Attendance record created.', {'record_id': str(record.id)}, http_status=201)


# ── OT Entry List ─────────────────────────────────────────────────────────────

class HROvertimeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        date_str = request.query_params.get('date', '')
        date = None
        if date_str:
            try:
                date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return error('Invalid date format. Use YYYY-MM-DD.')

        rows = list_overtime(
            date=date,
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            'Overtime entries loaded.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── OT Entry Create ───────────────────────────────────────────────────────────

class HROvertimeCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = OvertimeWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        try:
            ot = create_overtime(
                ser.validated_data,
                created_by=request.user,
                employee_ids=_manager_scope_employee_ids(request.user),
            )
        except ValueError as exc:
            return error(str(exc))

        return success('Overtime entry created.', {'id': str(ot.id)}, http_status=201)


# ── Invalid Punches ───────────────────────────────────────────────────────────

class HRInvalidPunchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        date_str = request.query_params.get('date', '')
        try:
            target_date = (
                datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            )
        except ValueError:
            return error('Invalid date format. Use YYYY-MM-DD.')

        rows = get_invalid_punches(
            target_date=target_date,
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} invalid punch(es) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── Un-punches ────────────────────────────────────────────────────────────────

class HRUnpunchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        date_str = request.query_params.get('date', '')
        try:
            target_date = (
                datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            )
        except ValueError:
            return error('Invalid date format. Use YYYY-MM-DD.')

        rows = get_unpunches(
            target_date=target_date,
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
            employee_ids=_manager_scope_employee_ids(request.user),
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} un-punch(es) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


# ── Import ────────────────────────────────────────────────────────────────────

class HRAttendanceImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        file = request.FILES.get('file')
        if not file:
            return error('No file uploaded. Send the CSV as form-data field "file".')

        if not file.name.lower().endswith('.csv'):
            return error('Only CSV files are accepted.')

        if file.size > 5 * 1024 * 1024:
            return error('File size must not exceed 5 MB.')

        result = import_attendance_csv(file, imported_by=request.user)
        status_val = result.get('status')
        if status_val == 'queued':
            http_status = 202
        elif result.get('failed', 0) == 0:
            http_status = 200
        elif result.get('successful', 0) == 0:
            http_status = 400
        else:
            http_status = 207
        return success(result['message'], result, http_status=http_status)


# ── Import status (progress polling for async imports) ───────────────────────

class HRAttendanceImportStatusView(APIView):
    """
    GET /api/attendance/import/<uuid:import_id>/status/

    Returns the current processing state of a bulk import job.
    Used by the frontend to poll progress for large files that were queued
    asynchronously (status='queued' on the initial POST response).

    Response data:
        import_id       — UUID of the import log
        status          — processing | queued | success | partial_success | failed
        total_records   — total rows in the uploaded file
        successful      — rows saved or updated so far
        failed          — rows that could not be saved
        skipped         — intra-file duplicate rows (last occurrence wins)
        errors          — first 50 row-level error entries
        task_id         — Celery task ID (present when import was async)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, import_id):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        from apps.attendance.models import AttendanceImportLog

        try:
            log = AttendanceImportLog.objects.get(id=import_id)
        except AttendanceImportLog.DoesNotExist:
            return error('Import log not found.', http_status=404)

        raw_status = log.status
        if raw_status == AttendanceImportLog.STATUS_PROCESSING:
            display_status = 'processing'
        elif raw_status == AttendanceImportLog.STATUS_COMPLETED:
            display_status = 'success' if log.failed_rows == 0 else 'partial_success'
        else:
            display_status = 'failed' if log.success_rows == 0 else 'partial_success'

        skipped = max(log.total_rows - log.success_rows - log.failed_rows, log.skipped_rows)

        data = {
            'import_id':     str(log.id),
            'status':        display_status,
            'total_records': log.total_rows,
            'successful':    log.success_rows,
            'failed':        log.failed_rows,
            'skipped':       skipped,
            'errors':        (log.errors or [])[:50],
        }
        if log.task_id:
            data['task_id'] = log.task_id

        return success('Import status retrieved.', data)


# ── Import Sample Template ────────────────────────────────────────────────────

class HRAttendanceImportSampleView(APIView):
    """
    GET /api/attendance/import/sample/?format=csv
    GET /api/attendance/import/sample/?format=xlsx

    Download a sample import template for Attendance Bulk Import.
    Headers match the columns accepted by HRAttendanceImportView exactly.
    Permission mirrors the upload endpoint (attendance.create required).
    """
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    _HEADERS = ['Employee ID', 'Date', 'Punch In', 'Punch Out']
    _SAMPLE_ROWS = [
        ['RSS00001', '2026-07-01', '09:00', '18:00'],
        ['RSS00002', '2026-07-01', '08:30', '17:30'],
    ]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        from core.file_utils import build_sample_csv, build_sample_xlsx, _CSV_MIME, _XLSX_MIME

        fmt = request.query_params.get('format', 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(self._HEADERS, self._SAMPLE_ROWS, 'Attendance Import')
            filename = 'attendance_import_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(self._HEADERS, self._SAMPLE_ROWS)
            filename = 'attendance_import_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ── Reprocess ────────────────────────────────────────────────────────────────

class HRAttendanceReprocessView(APIView):
    """
    POST /api/attendance/reprocess/
    Body: { "date": "2026-07-02" }   (optional — defaults to today)

    Queues AttendanceProcessorService reprocessing (via Celery) for every
    employee who has punches or an existing record on the given date, then
    returns immediately — the request no longer waits for every employee to
    be recalculated. Safe to queue multiple times: reprocessing a given
    employee/date never creates a duplicate AttendanceRecord (it's an
    upsert keyed on the employee+date unique constraint).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        date_str = request.data.get('date', '')
        try:
            target_date = (
                datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            )
        except ValueError:
            return error('Invalid date format. Use YYYY-MM-DD.')

        branch = _branch_scope(request.user, request.data.get('branch', ''))
        department = request.data.get('department', '')
        scoped_ids = _manager_scope_employee_ids(request.user)
        employee_ids = [str(i) for i in scoped_ids] if scoped_ids is not None else None

        from apps.attendance.tasks import reprocess_attendance_task
        try:
            # retry=False + ignore_result=True — bounds broker/backend
            # retries so a down Redis can't block this request; see the
            # referral-submission dispatch in recruitment/views.py. Nothing
            # reads this task's result via Celery — .id is still available
            # on the returned AsyncResult immediately, independent of
            # whether the broker publish itself succeeds.
            async_result = reprocess_attendance_task.apply_async(
                args=[target_date.isoformat(), branch, department, str(request.user.pk), employee_ids],
                retry=False, ignore_result=True,
            )
        except Exception as exc:
            logger.error('Failed to queue attendance reprocess task: %s', exc, exc_info=True)
            return error(
                'Failed to queue attendance reprocessing. Please try again.',
                http_status=503,
            )

        return success(
            f'Attendance reprocessing queued for {target_date.isoformat()}.',
            {'date': target_date.isoformat(), 'status': 'queued', 'task_id': async_result.id},
        )


# ── HR Corrections ────────────────────────────────────────────────────────────

class HRCorrectionListView(APIView):
    """
    GET /api/attendance/corrections/

    List correction requests visible to the caller — managers see requests
    where they're the designated L1 approver; HR/system_admin see the full
    branch-scoped/unrestricted list, same as before.
    Query params: branch, department, status (pending|l2_pending|approved|rejected)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = CorrectionListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_hr_corrections import list_corrections
        rows = list_corrections(
            request.user,
            branch=_branch_scope(request.user, ser.validated_data['branch']),
            department=ser.validated_data['department'],
            status_filter=ser.validated_data['status'],
        )
        page_obj, paginator = paginate(rows, request)
        return success(
            f'{paginator.count} correction request(s) found.',
            paginated_data(paginator, page_obj, list(page_obj)),
        )


class HRCorrectionReviewView(APIView):
    """
    PATCH /api/attendance/corrections/<uuid:pk>/review/
    Body: { "action": "approve" | "reject" }

    Two-stage: L1 (reporting manager) approval routes to L2 (HR) unless no
    L2 is configured for the employee, in which case L1 approval is final.
    Only the designated approver for the request's current stage may act
    (enforced in services_hr_corrections._can_approve_at_stage) —
    system_admin may always unblock a stuck request.

    Approve (final stage only): creates the missing punch(es), reprocesses
             the attendance record. Status changes incomplete → present/late;
             employee drops from Un-Punches.
    Reject:  marks the correction rejected, no punch changes.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = CorrectionReviewSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        remarks = ser.validated_data.get('remarks', '')

        from apps.attendance.services_hr_corrections import approve_correction, reject_correction
        try:
            if ser.validated_data['action'] == 'approve':
                result = approve_correction(str(pk), actioning_user=request.user, remarks=remarks)
                msg = 'Correction approved. Attendance record updated.' if result['status'] == 'approved' else 'Correction approved. Awaiting HR review.'
            else:
                result = reject_correction(str(pk), actioning_user=request.user, remarks=remarks)
                msg = 'Correction rejected.'
        except PermissionError as exc:
            return error(str(exc), http_status=403)
        except ValueError as exc:
            return error(str(exc), http_status=404)

        return success(msg, result)


# ── Export ────────────────────────────────────────────────────────────────────

class HRAttendanceExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = AttendanceListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
        filters['employee_ids'] = _manager_scope_employee_ids(request.user)
        csv_content = export_attendance_csv(filters)
        date_str = ser.validated_data['date'].strftime('%Y-%m-%d')
        filename = f'attendance_{date_str}.csv'

        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ── Employee Monthly Calendar (HR) ────────────────────────────────────────────

class HREmployeeMonthView(APIView):
    """Monthly attendance calendar for a single employee — HR use."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        employee_pk = request.query_params.get('employee_id')
        month_str   = request.query_params.get('month')

        if not employee_pk:
            return error('employee_id is required.', http_status=400)
        if not month_str:
            return error('month is required (YYYY-MM).', http_status=400)

        try:
            year, mon = (int(x) for x in month_str.split('-'))
            if not (1 <= mon <= 12):
                raise ValueError('month out of range')
        except (ValueError, AttributeError):
            return error('month must be in YYYY-MM format.', http_status=400)

        import uuid as _uuid_mod
        import datetime
        import calendar as _calendar
        from django.contrib.auth import get_user_model
        from apps.attendance.models import AttendanceRecord

        User = get_user_model()
        try:
            _uuid_mod.UUID(str(employee_pk))
            employee = User.objects.filter(pk=employee_pk, is_active=True).first()
        except (ValueError, AttributeError):
            employee = User.objects.filter(employee_id=employee_pk, is_active=True).first()

        if not employee:
            return error('Employee not found.', http_status=404)

        month_start = datetime.date(year, mon, 1)
        month_end   = datetime.date(year, mon, _calendar.monthrange(year, mon)[1])

        record_map = {
            r.date: r
            for r in AttendanceRecord.objects.filter(
                employee=employee, date__gte=month_start, date__lte=month_end,
            )
        }

        STATUS_LABELS = {
            'present': 'Present', 'late': 'Late Arrival', 'half_day': 'Half Day',
            'on_leave': 'On Leave', 'weekly_off': 'Week Off', 'holiday': 'Holiday',
            'absent': 'Absent', 'incomplete': 'Incomplete',
        }
        LOP_STATUSES = frozenset(['absent', 'incomplete'])
        stat_keys    = ('present', 'late', 'half_day', 'absent', 'on_leave',
                        'weekly_off', 'holiday', 'incomplete')
        stats = {k: 0 for k in stat_keys}
        stats['lop_days'] = 0
        total_minutes = 0

        days = []
        current = month_start
        while current <= month_end:
            rec      = record_map.get(current)
            status   = rec.status if rec else 'no_record'
            minutes  = (rec.total_working_minutes or 0) if rec else 0
            ot_mins  = (rec.overtime_minutes or 0) if rec else 0
            clock_in  = rec.first_punch_in.strftime('%H:%M') if rec and rec.first_punch_in else None
            clock_out = rec.last_punch_out.strftime('%H:%M') if rec and rec.last_punch_out else None

            if status in stats:
                stats[status] += 1
            if status in LOP_STATUSES:
                stats['lop_days'] += 1
            total_minutes += minutes

            days.append({
                'date':           current.isoformat(),
                'day_name':       current.strftime('%A'),
                'day_short':      current.strftime('%a'),
                'day_num':        current.day,
                'status':         status,
                'status_label':   STATUS_LABELS.get(status, 'No Record'),
                'clock_in':       clock_in,
                'clock_out':      clock_out,
                'total_hours':    round(minutes / 60, 1),
                'overtime_hours': round(ot_mins / 60, 1),
                'is_flagged':     status in LOP_STATUSES,
                'record_id':      str(rec.id) if rec else None,
            })
            current += datetime.timedelta(days=1)

        return success('Employee monthly attendance retrieved.', {
            'employee': {
                'id':          str(employee.pk),
                'employee_id': employee.employee_id,
                'full_name':   employee.full_name,
                'department':  employee.department or '',
                'designation': employee.designation or '',
            },
            'month': month_str,
            'stats': {**stats, 'total_hours': round(total_minutes / 60, 1)},
            'days':  days,
        })


# ── Weekly Off Assignment ──────────────────────────────────────────────────────
#
# Assigns a WeeklyDayPolicy (configured under Settings -> Attendance Rules ->
# Weekly Off Patterns — the existing WeeklyDayPolicy CRUD at
# /api/attendance/weekly-days/, unchanged) to a specific employee. History is
# preserved via services_hr.bulk_assign_weekly_off()/assign_weekly_off() — see
# their docstrings. All actual attendance/leave calculations resolve the
# effective pattern through the centralized
# core.cache_service.WeeklyOffCacheService, not through these views.

def _get_policy_or_error(policy_id):
    from apps.attendance.models import WeeklyDayPolicy
    try:
        return WeeklyDayPolicy.objects.get(pk=policy_id, is_active=True), None
    except (WeeklyDayPolicy.DoesNotExist, ValueError):
        return None, error('Weekly off pattern not found.', http_status=404)


class WeeklyOffAssignmentListView(APIView):
    """
    GET  /api/attendance/weekly-off-assignments/  — paginated list, one row
         per active employee with their current assignment (if any)
    POST /api/attendance/weekly-off-assignments/  — assign a pattern to a
         single employee
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = WeeklyOffAssignmentFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
        filters['employee_ids'] = _manager_scope_employee_ids(request.user)

        qs = build_weekly_off_assignment_queryset(filters)
        page_obj, paginator = paginate(qs, request)
        rows = [serialize_weekly_off_assignment_row(u) for u in page_obj]
        return success(
            'Weekly off assignments retrieved.',
            paginated_data(paginator, page_obj, rows),
        )

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = WeeklyOffAssignmentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors, http_status=422)

        data = ser.validated_data
        policy, err = _get_policy_or_error(data['pattern'])
        if err:
            return err

        assignment = assign_weekly_off(data['employee_id'], policy, data['effective_from'], request.user)
        if assignment is None:
            return error('Employee not found.', http_status=404)

        logger.info(
            'Weekly-off pattern "%s" assigned to %s effective %s by %s',
            policy.policy_code, data['employee_id'], data['effective_from'], request.user.email,
        )
        return success('Weekly off pattern assigned.', {
            'employee_id':    data['employee_id'],
            'pattern_id':     str(policy.pk),
            'pattern_name':   policy.name,
            'effective_from': assignment.effective_from.strftime('%Y-%m-%d'),
        }, http_status=201)


class WeeklyOffAssignmentBulkView(APIView):
    """
    POST /api/attendance/weekly-off-assignments/bulk/ — assign a pattern to
    many employees at once (explicit id list, or branch/department filter
    resolved server-side). O(1) queries regardless of how many are selected.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = WeeklyOffBulkAssignmentWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors, http_status=422)

        data = ser.validated_data
        policy, err = _get_policy_or_error(data['pattern'])
        if err:
            return err

        employee_ids = data.get('employee_ids') or []
        if not employee_ids:
            # Resolve branch/department filter server-side — the frontend
            # never has to load all matching employees just to select them.
            filters = {
                'branch':     _branch_scope(request.user, data.get('branch', '')),
                'department': data.get('department', ''),
                'employee_ids': _manager_scope_employee_ids(request.user),
            }
            employee_ids = list(
                build_weekly_off_assignment_queryset(filters).values_list('employee_id', flat=True)
            )

        count = bulk_assign_weekly_off(employee_ids, policy, data['effective_from'], request.user)
        return success(f'Weekly off pattern assigned to {count} employee(s).', {'count': count})


class WeeklyOffAssignmentHistoryView(APIView):
    """GET /api/attendance/weekly-off-assignments/<employee_id>/history/ — full timeline for one employee."""
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)
        history = get_weekly_off_assignment_history(employee_id)
        return success('Weekly off assignment history retrieved.', {'employee_id': employee_id, 'history': history})
