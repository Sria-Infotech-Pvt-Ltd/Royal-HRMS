"""Bulk employee import from Excel: template download, read-only preview, error report, and confirmed commit."""
from __future__ import annotations

import logging
import uuid

from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.services_employee_import import (
    MAX_FILE_BYTES, COLUMNS, ImportFileError, RowResult, allowed_branches, file_sha256, parse_workbook, summarise, validate_rows,
)
from apps.accounts.services_employee_import_commit import ImportRejected, commit_import
from apps.accounts.services_employee_import_invites import invite_progress, retry_batch
from apps.accounts.services_employee_import_template import XLSX_CONTENT_TYPE, build_error_report, build_template
from core.permissions import has_perm
from core.responses import error, get_client_ip, success

logger = logging.getLogger(__name__)

PERMISSION = 'employees.create'
# Shown in the preview. Personal details (address, emergency contact, birth date, ...) are imported but not echoed back.
PREVIEW_KEYS = tuple(column.key for column in COLUMNS if column.is_core)


def _refuse_without_permission(request):
    if not has_perm(request.user, PERMISSION):
        return error('You do not have permission to import employees.', http_status=status.HTTP_403_FORBIDDEN)
    return None


def _read_upload(request) -> tuple[bytes | None, object | None]:
    uploaded = request.FILES.get('file')
    if uploaded is None:
        return None, error('No file uploaded. Attach the filled .xlsx template.', http_status=status.HTTP_400_BAD_REQUEST)
    if uploaded.size > MAX_FILE_BYTES:
        return None, error('The file is too large. The maximum size is 5 MB.', http_status=status.HTTP_400_BAD_REQUEST)
    return uploaded.read(), None


def _row_payload(result: RowResult) -> dict:
    return {
        'row': result.row, 'status': result.status, 'is_valid': result.is_valid, 'errors': result.errors,
        'values': {key: result.values.get(key, '') for key in PREVIEW_KEYS},
    }


class EmployeeImportTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        response = HttpResponse(build_template(request.user), content_type=XLSX_CONTENT_TYPE)
        response['Content-Disposition'] = 'attachment; filename="employee_import_template.xlsx"'
        return response


class EmployeeImportPreviewView(APIView):
    """Reads and checks the file. Creates nothing and writes nothing."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        content, problem = _read_upload(request)
        if problem:
            return problem
        try:
            results = validate_rows(request.user, parse_workbook(content))
        except ImportFileError as exc:
            return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
        summary = summarise(results)
        return success('Preview ready. No employees have been created.', data={
            'batch_id': str(uuid.uuid4()), 'file_hash': file_sha256(content),
            'summary': {'total': summary.total, 'valid': summary.valid, 'invalid': summary.invalid, 'duplicate': summary.duplicate},
            'can_import': summary.can_import,
            'allowed_branches': [branch.branch_name for branch in allowed_branches(request.user)],
            'rows': [_row_payload(result) for result in results],
        })


class EmployeeImportErrorsView(APIView):
    """The uploaded file's problem rows as an Excel file (non-sensitive columns only) with an "Import Errors" column."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        content, problem = _read_upload(request)
        if problem:
            return problem
        try:
            results = validate_rows(request.user, parse_workbook(content))
        except ImportFileError as exc:
            return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(build_error_report(results), content_type=XLSX_CONTENT_TYPE)
        response['Content-Disposition'] = 'attachment; filename="employee_import_errors.xlsx"'
        return response


class EmployeeImportCommitView(APIView):
    """Re-validates the file against the hash the user previewed, then creates everyone or no one."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

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
            outcome = commit_import(
                request.user, content, batch_id=batch_id,
                expected_hash=str(request.data.get('file_hash', '')), ip_address=get_client_ip(request),
            )
        except ImportFileError as exc:
            return error(str(exc), http_status=status.HTTP_400_BAD_REQUEST)
        except ImportRejected as exc:
            return error(exc.message, data={
                'created': 0, 'rows': [_row_payload(result) for result in exc.results if not result.is_valid],
            }, http_status=status.HTTP_400_BAD_REQUEST)
        if outcome.already_committed:
            return success(f'This import was already completed: {outcome.created} employees were created.', data={
                'batch_id': outcome.batch_id, 'created': outcome.created, 'already_committed': True,
                'invites_sent': None, 'invite_failures': [],
            })
        message = f'{outcome.created} employees created. Activation emails are being sent.'
        return success(message, data={
            'batch_id': outcome.batch_id, 'created': outcome.created, 'already_committed': False,
            'employees': outcome.created_employees, 'invites_total': outcome.invites_total, 'invites_sent': outcome.invites_sent,
            'invite_failures': outcome.invite_failures,
        }, http_status=status.HTTP_201_CREATED)


class EmployeeImportInvitesView(APIView):
    """How far the activation emails of one import have got (sent so far, failed rows). Only the importer may read it."""
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        progress = invite_progress(request.user, str(batch_id))
        if progress is None:
            return error('No invitations were found for this import.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Invitation progress.', data=progress)


class EmployeeImportInvitesRetryView(APIView):
    """Queue the FAILED activation emails of one import again. Idempotent; never touches the employees themselves."""
    permission_classes = [IsAuthenticated]

    def post(self, request, batch_id):
        refusal = _refuse_without_permission(request)
        if refusal:
            return refusal
        if invite_progress(request.user, str(batch_id)) is None:
            return error('No invitations were found for this import.', http_status=status.HTTP_404_NOT_FOUND)
        result = retry_batch(request.user, str(batch_id))
        return success(f'{result["requeued"]} failed invitations were queued again.', data={**result, 'progress': invite_progress(request.user, str(batch_id))})
