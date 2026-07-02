"""
HR Attendance Operations — OT Entry, CSV Import, CSV Export.
"""
from __future__ import annotations

import csv
import datetime
import io
import logging
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
        normalized = {k.strip().lower().replace(' ', '_'): v.strip() for k, v in row.items()}
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
    employee = User.objects.get(employee_id=data['employee_id'])
    punch_in  = data['punch_in']
    punch_out = data.get('punch_out')

    minutes = 0
    if punch_out:
        start_dt = datetime.datetime.combine(data['date'], punch_in)
        end_dt   = datetime.datetime.combine(data['date'], punch_out)
        if end_dt > start_dt:
            minutes = int((end_dt - start_dt).total_seconds() / 60)

    status = AttendanceRecord.STATUS_PRESENT if minutes >= 240 else AttendanceRecord.STATUS_ABSENT

    AttendanceRecord.objects.update_or_create(
        employee=employee,
        date=data['date'],
        defaults={
            'status':                status,
            'first_punch_in':        punch_in,
            'last_punch_out':        punch_out,
            'total_working_minutes': minutes,
        },
    )


# ── CSV Export ────────────────────────────────────────────────────────────────

def export_attendance_csv(filters: dict) -> str:
    """
    Return CSV string for all employees matching filters on the given date.
    """
    from apps.attendance.services_hr import get_attendance_list

    rows = get_attendance_list(filters)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'employee_id', 'name', 'department', 'branch',
        'date', 'clock_in', 'clock_out', 'total_hours',
        'overtime', 'status',
    ])
    writer.writeheader()

    date_str = filters.get('date', datetime.date.today()).strftime('%Y-%m-%d')
    for row in rows:
        writer.writerow({
            'employee_id': row['employee_id'],
            'name':        row['name'],
            'department':  row['department'],
            'branch':      row['branch'],
            'date':        date_str,
            'clock_in':    row['clock_in'],
            'clock_out':   row['clock_out'],
            'total_hours': row['total_hours'],
            'overtime':    row['ot'],
            'status':      row['status'],
        })

    return output.getvalue()


# ── Shared helper ─────────────────────────────────────────────────────────────

def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else '??'
