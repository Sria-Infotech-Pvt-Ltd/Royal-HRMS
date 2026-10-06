from __future__ import annotations

from django.http import HttpResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, success

from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core import services_import_export as import_export
from apps.platform_core.models import EntityDefinition, ImportJob


def _get_custom_entity(entity_code, user, *, action):
    entity = EntityDefinition.objects.filter(code=entity_code, kind=EntityDefinition.KIND_CUSTOM).first()
    if entity is None:
        return None, error('Unknown custom entity.', http_status=404)
    if not has_perm(user, custom_objects.permission_codename(entity.code, action)):
        return None, error('You do not have permission for this action.', http_status=403)
    return entity, None


class ImportTemplateDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_code):
        entity, err = _get_custom_entity(entity_code, request.user, action='add')
        if err:
            return err
        wb = import_export.generate_import_template(entity)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{entity.code}_import_template.xlsx"'
        wb.save(response)
        return response


class ImportJobListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, entity_code):
        entity, err = _get_custom_entity(entity_code, request.user, action='add')
        if err:
            return err
        uploaded = request.FILES.get('file')
        if uploaded is None:
            return error('No file provided.', http_status=400)

        job = ImportJob.objects.create(
            entity=entity, mode=request.data.get('mode', ImportJob.MODE_CREATE),
            key_field=request.data.get('key_field', ''), file=uploaded,
            mapping=request.data.get('mapping') or {}, created_by=request.user,
            idempotency_key=request.data.get('idempotency_key', ''),
        )
        return success('Import job created.', {'id': str(job.pk), 'status': job.status}, http_status=201)


class ImportJobValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = ImportJob.objects.filter(pk=job_id).first()
        if job is None:
            return error('Not found.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(job.entity.code, 'add')):
            return error('You do not have permission for this action.', http_status=403)

        try:
            valid_rows, errors_by_row = import_export.validate_job(job)
        except import_export.ImportExportError as exc:
            return error(exc.message, http_status=400)

        preview = [{'row': i, 'values': cleaned} for i, cleaned in valid_rows[:20]]
        return success('Validation complete.', {
            'status': job.status, 'total_rows': job.total_rows, 'valid_rows': job.valid_rows,
            'invalid_rows': job.invalid_rows, 'errors': errors_by_row, 'preview': preview,
        })


class ImportJobCommitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = ImportJob.objects.filter(pk=job_id).first()
        if job is None:
            return error('Not found.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(job.entity.code, 'add')):
            return error('You do not have permission for this action.', http_status=403)

        try:
            counts = import_export.commit_job(job, actor=request.user, skip_invalid=bool(request.data.get('skip_invalid', True)))
        except import_export.ImportExportError as exc:
            return error(exc.message, http_status=400)
        return success('Import committed.', {'status': job.status, **counts})


class ImportJobRollbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        job = ImportJob.objects.filter(pk=job_id).first()
        if job is None:
            return error('Not found.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(job.entity.code, 'delete')):
            return error('You do not have permission for this action.', http_status=403)

        try:
            count = import_export.rollback_job(job)
        except import_export.ImportExportError as exc:
            return error(exc.message, http_status=400)
        return success('Import rolled back.', {'status': job.status, 'records_removed': count})


class ImportJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = ImportJob.objects.filter(pk=job_id).first()
        if job is None:
            return error('Not found.', http_status=404)
        return success('Status retrieved.', {
            'status': job.status, 'progress': job.progress, 'total_rows': job.total_rows,
            'valid_rows': job.valid_rows, 'invalid_rows': job.invalid_rows,
            'created_count': job.created_count, 'updated_count': job.updated_count, 'skipped_count': job.skipped_count,
        })


class ExportView(APIView):
    """Task I.5 — synchronous export (same deferred-async reasoning as
    imports) of any custom entity's records as XLSX, formula-injection
    escaped, masked through the same services_custom_objects.read_record
    every other read goes through."""
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_code):
        entity, err = _get_custom_entity(entity_code, request.user, action='view')
        if err:
            return err
        columns = (request.query_params.get('columns') or '').split(',') if request.query_params.get('columns') else None
        records = custom_objects.list_records(entity)
        rows = [custom_objects.read_record(r, for_user=request.user) | {'title': r.title} for r in records]
        if columns is None:
            columns = sorted({key for row in rows for key in row})

        content = import_export.export_rows_to_xlsx(entity, rows, columns=columns)
        response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{entity.code}_export.xlsx"'
        return response
