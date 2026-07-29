"""
HR Attendance Operations — OT Entry, CSV Import, CSV Export.
"""
from __future__ import annotations

import base64
import csv
import datetime
import io
import logging
import re
import time as _time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from apps.attendance.models import (
    AttendanceImportLog,
    AttendanceOvertime,
    AttendanceRecord,
)
from apps.attendance.serializers_hr import ImportRowSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

# Maps common/exported column names → what ImportRowSerializer expects.
# Keys must already be lowercase with spaces replaced by underscores.
_HEADER_ALIASES: dict[str, str] = {
    'clock_in':  'punch_in',
    'clock_out': 'punch_out',
    'in_time':   'punch_in',
    'out_time':  'punch_out',
    'checkin':   'punch_in',
    'checkout':  'punch_out',
    'punch_in_time':  'punch_in',
    'punch_out_time': 'punch_out',
    'employee_code':  'employee_id',
    'emp_id':         'employee_id',
}

_OT_MULTIPLIERS = {
    AttendanceOvertime.OT_TYPE_REGULAR:    Decimal('1.5'),
    AttendanceOvertime.OT_TYPE_HOLIDAY:    Decimal('2.0'),
    AttendanceOvertime.OT_TYPE_WEEKLY_OFF: Decimal('1.5'),
}


# ── OT Entry ──────────────────────────────────────────────────────────────────

def list_overtime(
    date: datetime.date | None, branch: str, department: str,
    employee_ids: list[str] | None = None,
) -> list[dict]:
    """
    Return OT rows filtered by optional date/branch/department.

    employee_ids: when provided (a manager's direct reports), restricts the
    scope to exactly those employees instead of branch.
    """
    qs = (
        AttendanceOvertime.objects
        .select_related('employee', 'approved_by')
        .order_by('-date', '-created_at')
    )
    if date:
        qs = qs.filter(date=date)
    if employee_ids is not None:
        qs = qs.filter(employee_id__in=employee_ids)
    elif branch:
        qs = qs.filter(employee__branch=branch)
    if department:
        qs = qs.filter(employee__department=department)

    rows = []
    for ot in qs:
        approver = ot.approved_by.full_name if ot.approved_by else '—'
        rows.append({
            'id':          str(ot.id),
            'employee_id': ot.employee.employee_id or '',
            'name':        ot.employee.full_name or '',
            'initials':    _initials(ot.employee.full_name or ''),
            'date':        ot.date.strftime('%Y-%m-%d'),
            'ot_hours':    ot.ot_hours_display,
            'ot_type':     dict(AttendanceOvertime.OT_TYPE_CHOICES).get(ot.ot_type, ot.ot_type),
            'ot_amount':   str(ot.ot_amount),
            'approved_by': approver,
            'status':      ot.status,
        })
    return rows


def create_overtime(data: dict, created_by, employee_ids: list[str] | None = None) -> AttendanceOvertime:
    """
    Create an OT entry from validated OvertimeWriteSerializer data.

    employee_ids: when provided (a manager's direct reports), the target
    employee must be in this set — reported as "not found" rather than
    "forbidden" so a manager can't probe for employees outside their team.
    """
    try:
        employee = User.objects.get(employee_id=data['employee_id'])
    except User.DoesNotExist:
        raise ValueError(f"Employee '{data['employee_id']}' not found.")

    if employee_ids is not None and str(employee.pk) not in {str(i) for i in employee_ids}:
        raise ValueError(f"Employee '{data['employee_id']}' not found.")

    approved_by = None
    if data.get('approved_by'):
        try:
            approved_by = User.objects.get(
                Q(employee_id=data['approved_by']) | Q(full_name__iexact=data['approved_by'])
            )
        except User.DoesNotExist:
            pass

    start: datetime.time = data['ot_start']
    end:   datetime.time = data['ot_end']
    ot_minutes = int(
        (datetime.datetime.combine(datetime.date.today(), end) -
         datetime.datetime.combine(datetime.date.today(), start)).total_seconds() / 60
    )

    multiplier = _OT_MULTIPLIERS.get(data['ot_type'], Decimal('1.5'))
    hourly_rate = Decimal('0')
    ot_amount   = (Decimal(ot_minutes) / 60 * hourly_rate * multiplier).quantize(Decimal('0.01'))

    with transaction.atomic():
        ot_entry = AttendanceOvertime.objects.create(
            employee=employee,
            date=data['date'],
            ot_start=start,
            ot_end=end,
            ot_minutes=ot_minutes,
            ot_type=data['ot_type'],
            ot_amount=ot_amount,
            reason=data.get('reason', ''),
            approved_by=approved_by,
            status=AttendanceOvertime.STATUS_APPROVED if approved_by else AttendanceOvertime.STATUS_PENDING,
            created_by=created_by,
        )
    return ot_entry


# ── CSV Import ────────────────────────────────────────────────────────────────

# Files with more rows than this are processed asynchronously via Celery.
_SYNC_THRESHOLD = 500
# Rows committed per atomic transaction in the bulk engine.
_BATCH_SIZE = 500


def import_attendance_csv(file, imported_by) -> dict:
    """
    Dispatcher for bulk CSV import.

    ≤ _SYNC_THRESHOLD rows  → processed inline, response returned immediately.
    > _SYNC_THRESHOLD rows  → Celery task queued; response contains import_id
                               for progress polling via GET /import/<id>/status/.

    Performance vs. the old row-by-row path (1 000-row file):
        Employee lookups  :  N queries  →  1 query  (bulk filter by employee_id set)
        Duplicate check   :  N implicit SELECT  →  1 bulk SELECT
        Record writes     :  N update_or_create  →  bulk_create + bulk_update per batch
        Audit log writes  :  N individual INSERTs  →  bulk_create per batch
        Transactions      :  1 per row  →  1 per batch of _BATCH_SIZE rows
    """
    start_ts       = _time.monotonic()
    file_name      = getattr(file, 'name', 'upload.csv')
    importer_email = getattr(imported_by, 'email', str(imported_by))

    logger.info('Attendance import started | file=%s | by=%s', file_name, importer_email)

    content = file.read().decode('utf-8-sig')
    rows    = list(csv.DictReader(io.StringIO(content)))
    total   = len(rows)

    import_log = AttendanceImportLog.objects.create(
        imported_by=imported_by,
        file_name=file_name,
        total_rows=total,
        status=AttendanceImportLog.STATUS_PROCESSING,
    )

    if total > _SYNC_THRESHOLD:
        from apps.attendance.tasks import process_attendance_import
        task = process_attendance_import.delay(
            str(import_log.id), str(imported_by.pk), content,
        )
        import_log.task_id = task.id
        import_log.save(update_fields=['task_id', 'updated_at'])
        logger.info(
            'Attendance import queued | import_id=%s | task_id=%s | total=%d',
            import_log.id, task.id, total,
        )
        return {
            'import_id':     str(import_log.id),
            'status':        'queued',
            'message':       (
                f'Your file has {total} records and is being processed in the background. '
                'Poll GET /api/attendance/import/{import_id}/status/ for progress.'
            ),
            'total_records': total,
            'successful':    0,
            'failed':        0,
            'skipped':       0,
            'errors':        [],
            'task_id':       task.id,
        }

    return _run_import_bulk(import_log, rows, imported_by, start_ts)


def _run_import_bulk(import_log, rows: list, imported_by, start_ts=None) -> dict:
    """
    Bulk import engine — used by both the sync path and the Celery worker.

    Phases:
      1  Normalize every raw CSV row.
      2  Bulk-load all referenced employees — ONE query.
      3  Validate each row with ImportRowSerializer (in-memory, no DB).
      4  Deduplicate within the CSV (last occurrence wins per employee+date).
      5  Bulk-detect existing AttendanceRecords — ONE query.
      6  Build create / update lists in memory.
      7  bulk_create new records in _BATCH_SIZE atomic batches.
      8  bulk_update existing records in _BATCH_SIZE atomic batches.
      9  bulk_create AttendanceAuditLog entries in _BATCH_SIZE batches.
     10  Persist final counts and status to AttendanceImportLog.
    """
    from apps.attendance.models import AttendanceAuditLog
    import uuid as _uuid_mod
    from django.utils import timezone

    if start_ts is None:
        start_ts = _time.monotonic()

    total          = len(rows)
    file_name      = import_log.file_name
    importer_email = getattr(imported_by, 'email', str(imported_by))

    # ── Phase 1: Normalize ─────────────────────────────────────────────────────
    normalized_rows = [_normalize_row(r) for r in rows]

    # ── Phase 2: Bulk employee lookup — ONE query ──────────────────────────────
    emp_ids_in_file: set[str] = {r.get('employee_id', '') for r in normalized_rows}
    emp_ids_in_file.discard('')
    emp_map: dict[str, object] = {}
    if emp_ids_in_file:
        for emp in User.objects.filter(
            employee_id__in=emp_ids_in_file,
        ).only('id', 'employee_id', 'full_name'):
            emp_map[emp.employee_id] = emp

    # ── Phase 3: Row-level validation (ImportRowSerializer, no DB hits) ────────
    errors: list[dict] = []
    failed_count = 0
    valid_rows: list[tuple] = []  # (row_num, validated_data, user_obj)

    for i, normalized in enumerate(normalized_rows, 1):
        raw_emp_id = normalized.get('employee_id', '')
        raw_date   = normalized.get('date', '')
        emp_obj    = emp_map.get(raw_emp_id)
        emp_name   = (getattr(emp_obj, 'full_name', '') or '') if emp_obj else ''

        ser = ImportRowSerializer(data=normalized)
        if not ser.is_valid():
            failed_count += 1
            reason, resolution = _friendly_serializer_error(ser.errors, normalized)
            errors.append(_make_error_entry(i, raw_emp_id, emp_name, raw_date, reason, resolution))
            continue

        v = ser.validated_data

        if emp_obj is None:
            failed_count += 1
            errors.append(_make_error_entry(
                i, raw_emp_id, '',
                str(v.get('date', raw_date)),
                f"Employee ID '{raw_emp_id}' was not found.",
                'Verify the Employee ID or create the employee before importing attendance.',
            ))
            continue

        valid_rows.append((i, v, emp_obj))

    # ── Phase 4: Intra-CSV deduplication (last row wins) ──────────────────────
    # A CSV from a biometric device sometimes exports the same employee+date
    # twice.  We keep the last occurrence and count the earlier ones as skipped.
    skipped_count = 0
    deduped: dict[tuple, tuple] = {}   # (emp_pk, date) → (row_num, v, emp_obj)
    for row_num, v, emp_obj in valid_rows:
        key = (emp_obj.pk, v['date'])
        if key in deduped:
            skipped_count += 1
        deduped[key] = (row_num, v, emp_obj)

    # ── Phase 5: Bulk existing-record detection — ONE query ────────────────────
    existing_records: dict[tuple, AttendanceRecord] = {}
    if deduped:
        emp_pks = {k[0] for k in deduped}
        dates   = {k[1] for k in deduped}
        for rec in AttendanceRecord.objects.filter(
            employee_id__in=emp_pks,
            date__in=dates,
        ):
            existing_records[(rec.employee_id, rec.date)] = rec

    # ── Phase 5b: Approved leave dates — skip creating absent records for these ──
    approved_leave_dates: set[tuple] = set()
    if deduped:
        from apps.hrms.models import LeaveRequest, REQ_APPROVED as _REQ_APPROVED
        min_date = min(k[1] for k in deduped)
        max_date = max(k[1] for k in deduped)
        for lr in LeaveRequest.objects.filter(
            employee_id__in=emp_pks,
            status=_REQ_APPROVED,
            start_date__lte=max_date,
            end_date__gte=min_date,
        ):
            cur = lr.start_date
            while cur <= lr.end_date:
                approved_leave_dates.add((lr.employee_id, cur))
                cur += datetime.timedelta(days=1)

    # ── Phase 6: Build create / update lists in memory ─────────────────────────
    now_ts = timezone.now()
    records_to_create: list[tuple] = []   # (AttendanceRecord, emp_obj, pi, po, date)
    records_to_update: list[tuple] = []

    for (emp_pk, date), (row_num, v, emp_obj) in deduped.items():
        punch_in  = v.get('punch_in')
        punch_out = v.get('punch_out')

        minutes = 0
        if punch_in and punch_out:
            sd = datetime.datetime.combine(date, punch_in)
            ed = datetime.datetime.combine(date, punch_out)
            if ed > sd:
                minutes = int((ed - sd).total_seconds() / 60)

        rec_status = AttendanceRecord.STATUS_PRESENT if minutes >= 240 else AttendanceRecord.STATUS_ABSENT
        key = (emp_pk, date)

        if key in existing_records:
            rec = existing_records[key]
            # Never overwrite a manually-set or leave-synced on_leave status with punch data.
            if rec.status == AttendanceRecord.STATUS_ON_LEAVE:
                skipped_count += 1
                continue
            rec.status                = rec_status
            rec.first_punch_in        = punch_in
            rec.last_punch_out        = punch_out
            rec.total_working_minutes = minutes
            rec.updated_at            = now_ts
            records_to_update.append((rec, emp_obj, punch_in, punch_out, date))
        elif key in approved_leave_dates:
            # Employee was on approved leave this day — create on_leave record instead.
            rec_status = AttendanceRecord.STATUS_ON_LEAVE
            rec = AttendanceRecord(
                id=_uuid_mod.uuid4(),
                employee_id=emp_pk,
                date=date,
                status=rec_status,
                first_punch_in=None,
                last_punch_out=None,
                total_working_minutes=0,
            )
            records_to_create.append((rec, emp_obj, None, None, date))
        else:
            rec = AttendanceRecord(
                id=_uuid_mod.uuid4(),
                employee_id=emp_pk,
                date=date,
                status=rec_status,
                first_punch_in=punch_in,
                last_punch_out=punch_out,
                total_working_minutes=minutes,
            )
            records_to_create.append((rec, emp_obj, punch_in, punch_out, date))

    # ── Phase 7: Batch bulk_create — one transaction per _BATCH_SIZE rows ──────
    created_count = 0
    for batch in _iter_batches(records_to_create, _BATCH_SIZE):
        try:
            with transaction.atomic():
                AttendanceRecord.objects.bulk_create(
                    [t[0] for t in batch],
                    batch_size=_BATCH_SIZE,
                )
            created_count += len(batch)
        except Exception as exc:
            logger.error('bulk_create batch failed (%d rows): %s', len(batch), exc)
            failed_count += len(batch)
            for rec, emp_obj, punch_in, punch_out, date in batch:
                errors.append(_make_error_entry(
                    0,
                    getattr(emp_obj, 'employee_id', '') or '',
                    getattr(emp_obj, 'full_name', '') or '',
                    str(date),
                    'Record could not be saved due to a database error.',
                    'Contact support if this error persists.',
                ))

    # ── Phase 8: Batch bulk_update — one transaction per _BATCH_SIZE rows ──────
    updated_count = 0
    for batch in _iter_batches(records_to_update, _BATCH_SIZE):
        try:
            with transaction.atomic():
                AttendanceRecord.objects.bulk_update(
                    [t[0] for t in batch],
                    fields=[
                        'status', 'first_punch_in', 'last_punch_out',
                        'total_working_minutes', 'updated_at',
                    ],
                    batch_size=_BATCH_SIZE,
                )
            updated_count += len(batch)
        except Exception as exc:
            logger.error('bulk_update batch failed (%d rows): %s', len(batch), exc)
            failed_count += len(batch)
            for rec, emp_obj, punch_in, punch_out, date in batch:
                errors.append(_make_error_entry(
                    0,
                    getattr(emp_obj, 'employee_id', '') or '',
                    getattr(emp_obj, 'full_name', '') or '',
                    str(date),
                    'Record could not be updated due to a database error.',
                    'Contact support if this error persists.',
                ))

    success_count = created_count + updated_count

    # ── Phase 9: Bulk audit logs — failures must never block the import ────────
    importer_pk   = imported_by.pk
    audit_entries = []
    for rec, emp_obj, punch_in, punch_out, date in (records_to_create + records_to_update):
        in_str  = punch_in.strftime('%H:%M')  if punch_in  else '—'
        out_str = punch_out.strftime('%H:%M') if punch_out else '—'
        audit_entries.append(AttendanceAuditLog(
            record_id=rec.id,
            employee_id=emp_obj.pk,
            date=date,
            event=AttendanceAuditLog.EVENT_IMPORTED,
            new_value=f'IN {in_str} OUT {out_str}',
            action='Attendance record imported via CSV',
            performed_by_id=importer_pk,
        ))

    for batch in _iter_batches(audit_entries, _BATCH_SIZE):
        try:
            AttendanceAuditLog.objects.bulk_create(batch, batch_size=_BATCH_SIZE)
        except Exception as exc:
            logger.warning('Audit log bulk_create failed: %s', exc)

    # ── Phase 10: Final status and import log update ───────────────────────────
    if failed_count == 0:
        status_label = 'success'
        status_msg   = 'Attendance imported successfully.'
        log_status   = AttendanceImportLog.STATUS_COMPLETED
    elif success_count == 0:
        status_label = 'failed'
        status_msg   = 'Attendance import failed. No records were imported.'
        log_status   = AttendanceImportLog.STATUS_FAILED
    else:
        status_label = 'partial_success'
        status_msg   = 'Attendance import completed with some errors.'
        log_status   = AttendanceImportLog.STATUS_FAILED

    import_log.success_rows = success_count
    import_log.failed_rows  = failed_count
    import_log.skipped_rows = skipped_count
    import_log.status       = log_status
    import_log.errors       = errors[:100]
    import_log.save(update_fields=[
        'success_rows', 'failed_rows', 'skipped_rows', 'status', 'errors', 'updated_at',
    ])

    duration = _time.monotonic() - start_ts
    logger.info(
        'Attendance import completed | file=%s | by=%s | total=%d | created=%d'
        ' | updated=%d | failed=%d | skipped=%d | duration=%.2fs',
        file_name, importer_email, total,
        created_count, updated_count, failed_count, skipped_count, duration,
    )

    all_imported_dates = sorted({str(v['date']) for _, v, _ in deduped.values()})
    result: dict = {
        'import_id':          str(import_log.id),
        'status':             status_label,
        'message':            status_msg,
        'total_records':      total,
        'successful':         success_count,
        'failed':             failed_count,
        'skipped':            skipped_count,
        'errors':             errors[:50],
        'first_imported_date': all_imported_dates[0] if all_imported_dates else None,
    }
    if errors:
        result['error_report_csv'] = _build_error_report_csv(errors)
    return result


def _iter_batches(lst: list, size: int):
    """Yield successive slices of `lst` each of length at most `size`."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def _make_error_entry(
    row: int,
    employee_id: str,
    employee_name: str,
    attendance_date: str,
    reason: str,
    resolution: str,
) -> dict:
    return {
        'row':             row,
        'employee_id':     employee_id,
        'employee_name':   employee_name,
        'attendance_date': attendance_date,
        'reason':          reason,
        'resolution':      resolution,
    }


def _friendly_serializer_error(errors: dict, normalized: dict) -> tuple[str, str]:
    """Convert ImportRowSerializer validation errors to a user-friendly (reason, resolution) pair."""
    if 'employee_id' in errors:
        val = normalized.get('employee_id', '')
        msg = str(errors['employee_id'][0]) if errors['employee_id'] else 'Invalid value.'
        if 'required' in msg.lower() or 'blank' in msg.lower() or 'null' in msg.lower():
            return (
                'Employee ID is missing.',
                'Add an Employee ID column with a valid value for each row.',
            )
        return (
            f"Employee ID '{val}': {msg}",
            'Check the Employee ID value and correct any typos.',
        )
    if 'date' in errors:
        val = normalized.get('date', '')
        msg = str(errors['date'][0]) if errors['date'] else 'Invalid value.'
        if 'required' in msg.lower() or 'blank' in msg.lower() or 'null' in msg.lower():
            return (
                'Attendance date is missing.',
                'Add a Date column with a value in YYYY-MM-DD or DD-MM-YYYY format.',
            )
        return (
            f"Date '{val}' is not a valid date.",
            'Use the format YYYY-MM-DD or DD-MM-YYYY (e.g. 2026-07-21 or 21-07-2026).',
        )
    if 'punch_in' in errors:
        val = normalized.get('punch_in', '')
        return (
            f"Punch-in time '{val}' is invalid.",
            'Use HH:MM in 24-hour format (e.g. 09:00) or 12-hour format with AM/PM (e.g. 9:00 AM).',
        )
    if 'punch_out' in errors:
        val = normalized.get('punch_out', '')
        msgs = errors['punch_out']
        msg  = str(msgs[0]) if msgs else 'Invalid value.'
        if 'before' in msg.lower() or 'earlier' in msg.lower() or 'less' in msg.lower():
            return (
                'Punch-out time is earlier than or equal to punch-in time.',
                'Make sure punch-out is after punch-in.',
            )
        return (
            f"Punch-out time '{val}' is invalid.",
            'Use HH:MM in 24-hour format (e.g. 18:00) or 12-hour format with AM/PM (e.g. 6:00 PM).',
        )
    # Fallback — first error field
    for field, msgs in errors.items():
        msg = str(msgs[0]) if msgs else 'Invalid value.'
        return (
            f"Field '{field}': {msg}",
            'Check the value and correct it before re-importing.',
        )
    return ('One or more fields are invalid.', 'Check the row values and correct them.')


def _classify_exception(exc: Exception, employee_id: str) -> tuple[str, str]:
    """Convert a runtime exception during upsert to a (reason, resolution) pair."""
    msg = str(exc).lower()
    if 'does not exist' in msg or 'matching query' in msg:
        return (
            f"Employee ID '{employee_id}' was not found.",
            'Verify the Employee ID or create the employee before importing attendance.',
        )
    if 'unique' in msg or 'duplicate' in msg:
        return (
            'A duplicate record exists for this employee and date.',
            'This row was skipped. Remove duplicates from the CSV before re-importing.',
        )
    if 'null' in msg or 'not null' in msg or 'notnull' in msg:
        return (
            'A required field is missing.',
            'Ensure Employee ID and Date are filled in for every row.',
        )
    if 'invalid' in msg or 'value' in msg:
        return (
            'One or more field values are invalid.',
            'Check the Employee ID and Date values for this row.',
        )
    return (
        'An unexpected error occurred while saving this record.',
        'Check the row data and contact support if the problem persists.',
    )


def _build_error_report_csv(errors: list[dict]) -> str:
    """Return a base64-encoded CSV string containing all error rows."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'row', 'employee_id', 'employee_name', 'attendance_date', 'reason', 'resolution',
    ])
    writer.writeheader()
    for entry in errors:
        writer.writerow({
            'row':             entry.get('row', ''),
            'employee_id':     entry.get('employee_id', ''),
            'employee_name':   entry.get('employee_name', ''),
            'attendance_date': entry.get('attendance_date', ''),
            'reason':          entry.get('reason', ''),
            'resolution':      entry.get('resolution', ''),
        })
    csv_bytes = output.getvalue().encode('utf-8-sig')
    return base64.b64encode(csv_bytes).decode('ascii')


@transaction.atomic
def _upsert_attendance_record(data: dict, imported_by) -> None:
    from apps.attendance.models import AttendanceAuditLog
    from apps.attendance.services_audit_log import write_audit_log

    employee  = User.objects.get(employee_id=data['employee_id'])
    punch_in  = data['punch_in']
    punch_out = data.get('punch_out')

    minutes = 0
    if punch_in and punch_out:
        start_dt = datetime.datetime.combine(data['date'], punch_in)
        end_dt   = datetime.datetime.combine(data['date'], punch_out)
        if end_dt > start_dt:
            minutes = int((end_dt - start_dt).total_seconds() / 60)

    rec_status = AttendanceRecord.STATUS_PRESENT if minutes >= 240 else AttendanceRecord.STATUS_ABSENT

    record, _ = AttendanceRecord.objects.update_or_create(
        employee=employee,
        date=data['date'],
        defaults={
            'status':                rec_status,
            'first_punch_in':        punch_in,
            'last_punch_out':        punch_out,
            'total_working_minutes': minutes,
        },
    )

    in_str  = punch_in.strftime('%H:%M') if punch_in else '—'
    out_str = punch_out.strftime('%H:%M') if punch_out else '—'
    write_audit_log(
        employee=employee,
        date=data['date'],
        event=AttendanceAuditLog.EVENT_IMPORTED,
        performed_by=imported_by,
        record=record,
        new_value=f'IN {in_str} OUT {out_str}',
        action='Attendance record imported via CSV',
    )


_DATE_INPUT_FORMATS = ('%d-%m-%Y', '%d/%m/%Y', '%m-%d-%Y', '%m/%d/%Y', '%Y/%m/%d')
_TIME_FIELDS       = frozenset({'punch_in', 'punch_out'})


def _normalize_row(row: dict) -> dict:
    """
    Normalize a raw csv.DictReader row for ImportRowSerializer.

    Per key:
      1. Strip UTF-8 BOM — survives utf-8-sig decode on the first header key.
      2. Strip surrounding whitespace, lowercase, spaces→underscores.
      3. Apply _HEADER_ALIASES (clock_in → punch_in, etc.).
      4. Normalize date to YYYY-MM-DD (handles DD-MM-YYYY written by Excel/WPS).
      5. Convert empty-string time values to None so TimeField(allow_null) accepts them.
    """
    normalized: dict = {}
    for raw_key, raw_val in row.items():
        key = raw_key.lstrip('﻿').strip().lower().replace(' ', '_')
        key = _HEADER_ALIASES.get(key, key)
        val = raw_val.strip() if isinstance(raw_val, str) else (raw_val or '')
        normalized[key] = val

    if 'date' in normalized:
        normalized['date'] = _normalize_date(normalized['date'])

    for field in _TIME_FIELDS:
        val = normalized.get(field, '')
        if not val:
            normalized[field] = None
        else:
            normalized[field] = _normalize_time(val)

    return normalized


def _normalize_date(value: str) -> str:
    """Convert common date formats to YYYY-MM-DD; return value unchanged if unrecognized."""
    if not value:
        return value
    for fmt in _DATE_INPUT_FORMATS:
        try:
            return datetime.datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return value


_TIME_12H_RE = re.compile(r'^(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)$', re.IGNORECASE)


def _normalize_time(value: str) -> str:
    """
    Normalize time strings for DRF TimeField (expects HH:MM in 24-hour).

    '2:00 PM'  → '14:00'
    '10:00 AM' → '10:00'
    '2:00'     → '02:00'  (pads single-digit hour; stays as-is without AM/PM)
    """
    if not value:
        return value
    match = _TIME_12H_RE.match(value.strip())
    if match:
        hour, minute, meridiem = int(match.group(1)), match.group(2), match.group(3).lower()
        if meridiem == 'am':
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return f'{hour:02d}:{minute}'
    parts = value.strip().split(':')
    try:
        return f'{int(parts[0]):02d}:' + ':'.join(parts[1:])
    except (ValueError, IndexError):
        return value


# ── CSV Export ────────────────────────────────────────────────────────────────

def export_attendance_csv(filters: dict) -> str:
    """
    Return CSV string for all employees matching filters on the given date.
    BOM prefix ensures Excel/WPS opens as UTF-8 without mojibake.
    """
    from apps.attendance.services_hr import get_attendance_list

    rows = get_attendance_list(filters)

    output = io.StringIO()
    output.write('﻿')  # UTF-8 BOM — required for Excel/WPS auto-detection
    writer = csv.DictWriter(output, fieldnames=[
        'employee_id', 'name', 'department', 'branch',
        'date', 'clock_in', 'clock_out', 'total_hours',
        'overtime', 'status',
    ])
    writer.writeheader()

    # DD-MM-YYYY survives Indian-locale Excel round-trip; YYYY-MM-DD gets reformatted to MM-DD-YYYY
    date_str = filters.get('date', datetime.date.today()).strftime('%d-%m-%Y')
    for row in rows:
        writer.writerow({
            'employee_id': row['employee_id'],
            'name':        row['name'],
            'department':  row['department'],
            'branch':      row['branch'],
            'date':        date_str,
            'clock_in':    _dash_to_empty(row['clock_in']),
            'clock_out':   _dash_to_empty(row['clock_out']),
            'total_hours': _dash_to_empty(row['total_hours']),
            'overtime':    _dash_to_empty(row['ot']),
            'status':      row['status'],
        })

    return output.getvalue()


def _dash_to_empty(value) -> str:
    """Replace em-dash placeholder with empty string for clean CSV output."""
    if value in ('—', '-', None):
        return ''
    return str(value)


# ── Shared helper ─────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else '??'
