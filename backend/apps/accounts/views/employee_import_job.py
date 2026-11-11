"""Bulk employee import as a background job: confirm (returns a job id at once), list, progress, error report, cancel."""
from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.services_employee_import import ImportFileError
from apps.accounts.services_employee_import_commit import ImportRejected
from apps.accounts.services_employee_import_job import (
    cancel_job, create_job, dispatch_job, get_job_for, job_error_report, job_progress, list_jobs, run_job,
)
from apps.accounts.services_employee_import_template import XLSX_CONTENT_TYPE
from apps.accounts.views.employee_import import _read_upload, _refuse_without_permission, _row_payload
from core.responses import error, success

logger = logging.getLogger(__name__)


def _job_or_404(request, job_id):
    job = get_job_for(request.user, job_id)
    return job, (None if job else error('No import job with that id was found.', http_status=status.HTTP_404_NOT_FOUND))


class EmployeeImportJobListCreateView(APIView):
    """POST confirms an import: the file is validated, a durable job is stored and its id is returned immediately (HTTP 202)."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get(self, request):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        return success('Recent imports.', data={'jobs': list_jobs(request.user)})

    def post(self, request):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        try:
            batch_id = str(uuid.UUID(str(request.data.get('batch_id', ''))))
        except ValueError:
            return error('A valid batch_id from the preview is required.', http_status=status.HTTP_400_BAD_REQUEST)
        content, problem = _read_upload(request)
        if problem:
            return problem
        try:
            job, created = create_job(request.user, content, batch_id=batch_id, expected_hash=str(request.data.get('file_hash', '')),
                                      file_name=getattr(request.FILES.get('file'), 'name', ''))
        except ImportFileError as exc:
            return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
        except ImportRejected as exc:
            return error(exc.message, data={'created': 0, 'rows': [_row_payload(r) for r in exc.results if not r.is_valid]},
                         http_status=status.HTTP_400_BAD_REQUEST)
        if created:
            if getattr(settings, 'RUNNING_TESTS', False):          # deterministic under the test runner; production queues a Celery task
                while run_job(job.pk) == 'running':
                    pass
            else:
                dispatch_job(job.pk)
            job.refresh_from_db()
        message = 'Import started. You can close this page; progress is saved.' if created else 'This import already exists. Showing its progress.'
        return success(message, data=job_progress(job), http_status=status.HTTP_202_ACCEPTED)


class EmployeeImportJobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        job, missing = _job_or_404(request, job_id)
        return missing or success('Import progress.', data=job_progress(job))


class EmployeeImportJobErrorsView(APIView):
    """The rows that could not be imported, as an Excel file (non-sensitive columns only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        job, missing = _job_or_404(request, job_id)
        if missing:
            return missing
        response = HttpResponse(job_error_report(job), content_type=XLSX_CONTENT_TYPE)
        response['Content-Disposition'] = 'attachment; filename="employee_import_errors.xlsx"'
        return response


class EmployeeImportJobCancelView(APIView):
    """Stop a job after its current batch. Employees already created stay; the rest are not created."""
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        job, missing = _job_or_404(request, job_id)
        if missing:
            return missing
        return success('Cancellation requested.', data=job_progress(cancel_job(job)))
