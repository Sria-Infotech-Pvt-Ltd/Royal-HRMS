"""
HR Attendance Operations — OT Entry, CSV Import, CSV Export.
"""
from __future__ import annotations

import csv
import datetime
import io
import logging
import re
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

def list_overtime(date: datetime.date | None, branch: str, department: str) -> list[dict]:
    """Return OT rows filtered by optional date/branch/department."""
    qs = (
        AttendanceOvertime.objects
        .select_related('employee', 'approved_by')
        .order_by('-date', '-created_at')
    )
    if date:
        qs = qs.filter(date=date)
    if branch:
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


def create_overtime(data: dict, created_by) -> AttendanceOvertime:
    """Create an OT entry from validated OvertimeWriteSerializer data."""
    try:
        employee = User.objects.get(employee_id=data['employee_id'])
    except User.DoesNotExist:
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

def import_attendance_csv(file, imported_by) -> dict:
    """
    Parse a CSV file and create/update AttendanceRecord rows.

    Expected CSV columns (case-insensitive):
        employee_id, date, punch_in, punch_out (optional)

    Returns import log summary dict.
    """
    content = file.read().decode('utf-8-sig')
    reader  = csv.DictReader(io.StringIO(content))

    rows = list(reader)
    total = len(rows)

    import_log = AttendanceImportLog.objects.create(
        imported_by=imported_by,
        file_name=getattr(file, 'name', 'upload.csv'),
        total_rows=total,
        status=AttendanceImportLog.STATUS_PROCESSING,
    )

    success = 0
    failed  = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, 1):
        normalized = _normalize_row(row)
        ser = ImportRowSerializer(data=normalized)

        if not ser.is_valid():
            failed += 1
            errors.append({'row': i, 'data': normalized, 'errors': ser.errors})
            continue

        v = ser.validated_data
        try:
            _upsert_attendance_record(v, imported_by)
            success += 1
        except Exception as exc:
            logger.warning('Import row %d failed: %s', i, exc)
            failed += 1
            errors.append({'row': i, 'data': normalized, 'errors': str(exc)})

    import_log.success_rows = success
    import_log.failed_rows  = failed
    import_log.status = (
        AttendanceImportLog.STATUS_COMPLETED
        if failed == 0
        else AttendanceImportLog.STATUS_FAILED
    )
    import_log.errors = errors[:100]
    import_log.save(update_fields=['success_rows', 'failed_rows', 'status', 'errors', 'updated_at'])

    return {
        'import_id':   str(import_log.id),
        'total_rows':  total,
        'success':     success,
        'failed':      failed,
        'status':      import_log.status,
        'errors':      errors[:10],
    }


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
