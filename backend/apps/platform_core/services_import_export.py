"""
Phase 2 Task I — import/export framework. Execution is SYNCHRONOUS in
this phase (the model's own status machine — uploaded -> validating ->
validated -> committing -> completed/failed/rolled_back — is built to
the full spec; see ImportJob/ExportJob docstrings and PHASE2_REPORT.md
"Deferred" for why async Celery execution is not wired up here). Scoped
to custom entities and custom attributes on core entities only, per the
prompt's own scope note — existing module imports (attendance, leave,
payroll, candidates) are not converted.
"""
from __future__ import annotations

import csv
import io

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from django.db import transaction
from django.utils import timezone

from apps.platform_core import services_attributes as attrs
from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core import services_lookups
from apps.platform_core.models import FieldDefinition, ImportJob

MAX_IMPORT_ROWS = 10_000  # system-setting-worthy limit (Task I.6) — hardcoded here pending a real Settings row; see PHASE2_REPORT.md.
FORMULA_PREFIXES = ('=', '+', '-', '@')


class ImportExportError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def escape_formula(value):
    """Task I.5 — spreadsheet formula-injection protection: a cell whose
    value starts with =, +, - or @ opens as a formula in Excel/Sheets,
    which can execute arbitrary lookups (including remote ones) against
    the opener's machine. Prefixing with a single quote forces it to
    render as literal text instead."""
    if isinstance(value, str) and value and value[0] in FORMULA_PREFIXES:
        return "'" + value
    return value


def _importable_fields(entity):
    return list(FieldDefinition.objects.filter(
        entity=entity, status=FieldDefinition.STATUS_PUBLISHED, is_importable=True,
    ).order_by('order'))


def generate_import_template(entity) -> openpyxl.Workbook:
    """Task I.1 — one column per importable field, header row of field
    CODES (row 1, what parse_uploaded_rows actually maps on) plus a
    second row of human labels, dropdown validation for lookup fields,
    and an Instructions sheet."""
    fields = _importable_fields(entity)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Data'
    ws.append([f.code for f in fields])
    ws.append([f.label for f in fields])

    for idx, field in enumerate(fields, start=1):
        if field.data_type == 'lookup' and field.lookup_type_id:
            values = [v.code for v in services_lookups.get_values(field.lookup_type.code)]
            if values:
                dv = DataValidation(type='list', formula1='"%s"' % ','.join(values), allow_blank=True)
                col_letter = get_column_letter(idx)
                ws.add_data_validation(dv)
                dv.add(f'{col_letter}3:{col_letter}{MAX_IMPORT_ROWS + 2}')

    instructions = wb.create_sheet('Instructions')
    instructions.append(['Field code', 'Label', 'Required', 'Data type', 'Notes'])
    for field in fields:
        instructions.append([
            field.code, field.label, 'Yes' if field.required else 'No', field.data_type,
            'Values: ' + ', '.join(v.code for v in services_lookups.get_values(field.lookup_type.code)) if field.data_type == 'lookup' and field.lookup_type_id else '',
        ])
    return wb


def parse_uploaded_rows(job: ImportJob) -> list[dict]:
    """Returns a list of {field_code: raw_value} dicts, applying
    job.mapping (uploaded column header -> field code) — an unmapped
    column passes through under its own header name unchanged (so a
    file whose headers already match field codes needs no mapping)."""
    job.file.open('rb')
    try:
        content = job.file.read()
    finally:
        job.file.close()

    name = job.file.name.lower()
    rows = []
    if name.endswith('.csv'):
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        raw_rows = list(reader)
    else:
        # read_only=True — Task I.6: never execute macros/external links,
        # just read cell values.
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header = next(rows_iter)
        raw_rows = [dict(zip(header, row)) for row in rows_iter if any(c is not None for c in row)]

    if len(raw_rows) > MAX_IMPORT_ROWS:
        raise ImportExportError(f'This file has {len(raw_rows)} rows, exceeding the {MAX_IMPORT_ROWS}-row import limit.')

    for raw_row in raw_rows:
        mapped = {job.mapping.get(k, k): v for k, v in raw_row.items() if k is not None}
        rows.append({k: v for k, v in mapped.items() if v not in (None, '')})
    return rows


def validate_job(job: ImportJob) -> tuple[list[tuple[int, dict]], dict[int, dict]]:
    """Task I.3 — a dry run: no writes. Returns (valid_rows, errors_by_row)
    where valid_rows is [(row_number, cleaned_values), ...] and row_number
    is 1-based with the header counted as row 1 (so the first data row is
    row 2, matching what a spreadsheet user sees)."""
    job.status = ImportJob.STATUS_VALIDATING
    job.save(update_fields=['status'])

    entity = job.entity
    rows = parse_uploaded_rows(job)
    errors_by_row = {}
    valid_rows = []
    partial = job.mode != ImportJob.MODE_CREATE

    for i, row in enumerate(rows, start=2):
        try:
            cleaned = attrs.validate(entity, None, row, partial=partial)
            valid_rows.append((i, cleaned))
        except attrs.AttributeValidationError as exc:
            errors_by_row[i] = exc.errors

    job.total_rows = len(rows)
    job.valid_rows = len(valid_rows)
    job.invalid_rows = len(errors_by_row)
    job.status = ImportJob.STATUS_VALIDATED
    job.save(update_fields=['total_rows', 'valid_rows', 'invalid_rows', 'status'])
    return valid_rows, errors_by_row


def _find_existing_by_key(entity, key_field: str, value):
    if not key_field or value in (None, ''):
        return None
    return custom_objects.list_records(entity).filter(**{f'data__{key_field}': value}).first()


@transaction.atomic
def commit_job(job: ImportJob, *, actor=None, skip_invalid: bool = True) -> dict:
    """Task I.3's commit step. Runs inside one transaction (small/medium
    batches in this synchronous phase — batching into chunks is an async-
    execution concern deferred alongside Celery wiring, see module
    docstring). `skip_invalid=False` makes the whole job fail atomically
    on the first invalid row rather than partially committing."""
    if job.status not in (ImportJob.STATUS_VALIDATED, ImportJob.STATUS_UPLOADED):
        raise ImportExportError(f'Cannot commit a job in status "{job.status}".')

    job.status = ImportJob.STATUS_COMMITTING
    job.save(update_fields=['status'])

    entity = job.entity
    rows = parse_uploaded_rows(job)
    partial = job.mode != ImportJob.MODE_CREATE
    created_ids, created, updated, skipped = [], 0, 0, 0

    for row in rows:
        try:
            if job.mode == ImportJob.MODE_CREATE:
                record = custom_objects.create_record(entity, row, actor=actor)
                created_ids.append(str(record.pk))
                created += 1
                continue

            existing = _find_existing_by_key(entity, job.key_field, row.get(job.key_field))
            if existing is not None:
                custom_objects.update_record(existing, row, actor=actor, partial=partial)
                updated += 1
            elif job.mode == ImportJob.MODE_UPSERT:
                record = custom_objects.create_record(entity, row, actor=actor)
                created_ids.append(str(record.pk))
                created += 1
            else:
                skipped += 1
        except attrs.AttributeValidationError:
            if not skip_invalid:
                job.status = ImportJob.STATUS_FAILED
                job.save(update_fields=['status'])
                raise
            skipped += 1

    job.created_count = created
    job.updated_count = updated
    job.skipped_count = skipped
    job.created_record_ids = created_ids
    job.status = ImportJob.STATUS_COMPLETED
    job.completed_at = timezone.now()
    job.save(update_fields=['created_count', 'updated_count', 'skipped_count', 'created_record_ids', 'status', 'completed_at'])
    return {'created': created, 'updated': updated, 'skipped': skipped}


def rollback_job(job: ImportJob) -> int:
    """Task I.4 — soft-deletes every record THIS job created. Documented
    limitation (see module docstring and PHASE2_REPORT.md): only undoes
    creates. Rolling back an UPDATE/UPSERT's modified values would need
    the pre-import value, which services_attributes' ChangeHistory
    logging does not currently retain (it logs 'old': None) — rolling
    back an update in this phase would silently do nothing, which is
    worse than refusing, so update/upsert jobs cannot be rolled back at
    all yet."""
    if job.status != ImportJob.STATUS_COMPLETED:
        raise ImportExportError(f'Cannot roll back a job in status "{job.status}".')
    if job.mode != ImportJob.MODE_CREATE:
        raise ImportExportError('Rollback is only supported for create-mode imports in this phase.')

    records = custom_objects.list_records(job.entity, include_deleted=True).filter(pk__in=job.created_record_ids)
    count = 0
    for record in records:
        custom_objects.soft_delete_record(record)
        count += 1

    job.status = ImportJob.STATUS_ROLLED_BACK
    job.save(update_fields=['status'])
    return count


def export_rows_to_xlsx(entity, rows: list[dict], *, columns: list[str]) -> bytes:
    """Task I.5 — every cell value passes through escape_formula() before
    being written, regardless of source, so a malicious value stored in
    any field can't execute as a formula for whoever opens the export."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = entity.code
    ws.append(columns)
    for row in rows:
        ws.append([escape_formula(row.get(col)) for col in columns])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
