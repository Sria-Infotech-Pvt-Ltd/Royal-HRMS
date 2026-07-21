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
    OvertimeWriteSerializer,
)
from apps.attendance.services_hr import (
    get_attendance_detail,
    get_attendance_list,
    get_dashboard_stats,
    reprocess_date,
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

logger = logging.getLogger(__name__)


def _has_hr_permission(user, codename: str) -> bool:
    if user.is_superuser:
        return True
    try:
        # Employee role must never access HR attendance views — they use /my-attendance endpoints.
        # Migration 0029 removed attendance.view from the employee role, but this guard
        # defends against DB state divergence or accidental re-grants.
        if user.role and user.role.name == 'employee':
            return False
        return user.role.role_permissions.filter(
            permission__codename=codename
        ).exists()
    except Exception:
        return False


def _is_unrestricted(user) -> bool:
    """
    Returns True for users who can see all branches.

    system_admin role and Django superusers have no branch restriction.
    hr_admin and all other roles are scoped to their own branch.
    """
    if user.is_superuser:
        return True
    try:
        return user.role.name == 'system_admin'
    except Exception:
        return False


def _branch_scope(user, requested: str) -> str:
    """
    Resolve the effective branch filter for the current user.

    Unrestricted users: honour whatever branch was requested (empty = all).
    Restricted users (hr_admin etc.): always use their own branch, ignoring
    the query parameter — they cannot see outside their branch.
    """
    if _is_unrestricted(user):
        return requested
    return getattr(user, 'branch', '') or ''


# ── Dashboard ─────────────────────────────────────────────────────────────────

class HRAttendanceDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = DateFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        data = ser.validated_data
        stats = get_dashboard_stats(
            target_date=data['date'],
            branch=_branch_scope(request.user, request.query_params.get('branch', '')),
            department=request.query_params.get('department', ''),
        )
        return success('Dashboard stats loaded.', stats)


# ── Attendance List ───────────────────────────────────────────────────────────

class HRAttendanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = AttendanceListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
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
        if not _has_hr_permission(request.user, 'attendance.view'):
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
        )
        if not detail:
            return error('Attendance record not found.', http_status=404)

        return success('Attendance detail loaded.', detail)


# ── OT Entry List ─────────────────────────────────────────────────────────────

class HROvertimeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.view'):
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
        if not _has_hr_permission(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = OvertimeWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        try:
            ot = create_overtime(ser.validated_data, created_by=request.user)
        except ValueError as exc:
            return error(str(exc))

        return success('Overtime entry created.', {'id': str(ot.id)}, http_status=201)


# ── Invalid Punches ───────────────────────────────────────────────────────────

class HRInvalidPunchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.view'):
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
        if not _has_hr_permission(request.user, 'attendance.view'):
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
        if not _has_hr_permission(request.user, 'attendance.create'):
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
        if not _has_hr_permission(request.user, 'attendance.create'):
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

    _HEADERS = ['Employee ID', 'Date', 'Punch In', 'Punch Out']
    _SAMPLE_ROWS = [
        ['RSS00001', '2026-07-01', '09:00', '18:00'],
        ['RSS00002', '2026-07-01', '08:30', '17:30'],
    ]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.create'):
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

    Reruns AttendanceProcessorService for every employee who has punches on
    the given date. Safe to call multiple times. Use this after fixing
    punch data or after a code change to attendance logic.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_hr_permission(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        date_str = request.data.get('date', '')
        try:
            target_date = (
                datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            )
        except ValueError:
            return error('Invalid date format. Use YYYY-MM-DD.')

        result = reprocess_date(
            target_date=target_date,
            branch=_branch_scope(request.user, request.data.get('branch', '')),
            department=request.data.get('department', ''),
            performed_by=request.user,
        )
        return success(
            f'Reprocessed {result["updated"]} record(s) for {result["date"]}.',
            result,
        )


# ── HR Corrections ────────────────────────────────────────────────────────────

class HRCorrectionListView(APIView):
    """
    GET /api/attendance/corrections/

    List all employee correction requests HR needs to action.
    Query params: branch, department, status (pending|approved|rejected)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = CorrectionListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_hr_corrections import list_corrections
        rows = list_corrections(
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

    Approve: creates the missing punch(es), reprocesses the attendance record.
             Status changes incomplete → present/late; employee drops from Un-Punches.
    Reject:  marks the correction rejected, no punch changes.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not _has_hr_permission(request.user, 'attendance.create'):
            return error('Permission denied.', http_status=403)

        ser = CorrectionReviewSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        from apps.attendance.services_hr_corrections import approve_correction, reject_correction
        try:
            if ser.validated_data['action'] == 'approve':
                result = approve_correction(str(pk), reviewed_by=request.user)
                msg = 'Correction approved. Attendance record updated.'
            else:
                result = reject_correction(str(pk), reviewed_by=request.user)
                msg = 'Correction rejected.'
        except ValueError as exc:
            return error(str(exc), http_status=404)

        return success(msg, result)


# ── Export ────────────────────────────────────────────────────────────────────

class HRAttendanceExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_hr_permission(request.user, 'attendance.view'):
            return error('Permission denied.', http_status=403)

        ser = AttendanceListFilterSerializer(data=request.query_params)
        if not ser.is_valid():
            return error(first_error(ser.errors))

        filters = ser.validated_data
        filters['branch'] = _branch_scope(request.user, filters.get('branch', ''))
        csv_content = export_attendance_csv(filters)
        date_str = ser.validated_data['date'].strftime('%Y-%m-%d')
        filename = f'attendance_{date_str}.csv'

        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
