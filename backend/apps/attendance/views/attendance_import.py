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

from apps.attendance.views.hr_attendance_shared import *  # noqa: F401,F403

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


