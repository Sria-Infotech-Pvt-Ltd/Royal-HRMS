"""
Invalid Punch Management — assign, discard, convert.

The list endpoint (get_invalid_punches) detects invalid punches dynamically
from raw punch data.  These services persist HR action state in InvalidPunch,
created lazily on first action.  The {id} in every action URL is the
AttendancePunch.id returned by the list endpoint.

All mutating operations run inside transaction.atomic().
"""
from __future__ import annotations

import datetime
import logging
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendancePunch, InvalidPunch

logger = logging.getLogger(__name__)
User = get_user_model()
_IST = ZoneInfo('Asia/Kolkata')


# ── Public actions ─────────────────────────────────────────────────────────────

def assign_invalid_punch(punch_id: str, assigned_to_id: str, performed_by) -> dict:
    """Assign an invalid punch to an HR user for investigation."""
    with transaction.atomic():
        invalid = _get_or_register(punch_id)
        _guard_resolved(invalid, allow_reassign=True)

        try:
            assignee = User.objects.get(id=assigned_to_id)
        except User.DoesNotExist:
            raise ValueError('Assignee not found.')

        invalid.status      = InvalidPunch.STATUS_ASSIGNED
        invalid.assigned_to = assignee
        invalid.assigned_by = performed_by
        invalid.assigned_at = timezone.now()
        invalid.save(update_fields=[
            'status', 'assigned_to', 'assigned_by', 'assigned_at', 'updated_at',
        ])

    logger.info('InvalidPunch %s assigned to %s by %s', punch_id, assigned_to_id, performed_by.pk)
    return _build_row(invalid)


def discard_invalid_punch(punch_id: str, remarks: str, performed_by) -> dict:
    """Discard an invalid punch — marks it as an accidental duplicate or non-actionable."""
    with transaction.atomic():
        invalid = _get_or_register(punch_id)
        if invalid.status == InvalidPunch.STATUS_DISCARDED:
            raise ValueError('Punch is already discarded.')
        if invalid.status == InvalidPunch.STATUS_CONVERTED:
            raise ValueError('Cannot discard: punch has already been converted.')

        invalid.status       = InvalidPunch.STATUS_DISCARDED
        invalid.discarded_by = performed_by
        invalid.discarded_at = timezone.now()
        invalid.resolved_at  = timezone.now()
        invalid.remarks      = (remarks or '').strip()
        invalid.save(update_fields=[
            'status', 'discarded_by', 'discarded_at', 'resolved_at', 'remarks', 'updated_at',
        ])

        _write_discard_audit(invalid, performed_by)

    logger.info('InvalidPunch %s discarded by %s', punch_id, performed_by.pk)
    return _build_row(invalid)


def convert_invalid_punch(
    punch_id: str,
    target_punch_type: str,
    target_time_str: str,
    performed_by,
) -> dict:
    """
    Convert an invalid punch by creating a valid attendance punch and reprocessing.

    target_punch_type: 'IN' or 'OUT'
    target_time_str:   'HH:MM' — the correct time for the new punch
    """
    from apps.attendance.services_attendance import AttendanceProcessorService

    with transaction.atomic():
        invalid = _get_or_register(punch_id)
        if invalid.status == InvalidPunch.STATUS_DISCARDED:
            raise ValueError('Cannot convert: punch is discarded.')
        if invalid.status == InvalidPunch.STATUS_CONVERTED:
            raise ValueError('Punch is already converted.')

        punch       = invalid.punch
        target_time = _parse_time(target_time_str)
        new_punched_at = datetime.datetime.combine(punch.punch_date, target_time).replace(tzinfo=_IST)

        new_punch, _ = AttendancePunch.objects.get_or_create(
            employee=punch.employee,
            punched_at=new_punched_at,
            punch_type=target_punch_type,
            defaults={
                'source':          AttendancePunch.SOURCE_MANUAL,
                'attendance_mode': punch.attendance_mode,
                'is_regularized':  True,
            },
        )

        record = AttendanceProcessorService.process_day(punch.employee, punch.punch_date)

        invalid.status          = InvalidPunch.STATUS_CONVERTED
        invalid.converted_punch = new_punch
        invalid.resolved_at     = timezone.now()
        invalid.save(update_fields=['status', 'converted_punch', 'resolved_at', 'updated_at'])

        _write_convert_audit(invalid, punch, target_punch_type, target_time_str, record, performed_by)

    logger.info('InvalidPunch %s converted to %s @ %s by %s', punch_id, target_punch_type, target_time_str, performed_by.pk)
    return _build_row(invalid)


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_or_register(punch_id: str) -> InvalidPunch:
    """Fetch the punch, then get or lazily create its InvalidPunch tracking record."""
    try:
        punch = AttendancePunch.objects.select_related('employee').get(id=punch_id)
    except AttendancePunch.DoesNotExist:
        raise ValueError('Punch not found.')

    invalid, _ = InvalidPunch.objects.get_or_create(
        punch=punch,
        defaults={'issue_type': 'registered', 'issue': 'Registered via HR action'},
    )
    return invalid


def _guard_resolved(invalid: InvalidPunch, allow_reassign: bool = False) -> None:
    if invalid.status == InvalidPunch.STATUS_DISCARDED:
        raise ValueError('Cannot act on a discarded punch.')
    if invalid.status == InvalidPunch.STATUS_CONVERTED:
        raise ValueError('Cannot act on a converted punch.')
    if not allow_reassign and invalid.status == InvalidPunch.STATUS_ASSIGNED:
        raise ValueError('Punch is already assigned.')


def _parse_time(time_str: str) -> datetime.time:
    try:
        return datetime.time.fromisoformat(time_str)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid time format '{time_str}'. Use HH:MM.")


def _write_discard_audit(invalid: InvalidPunch, performed_by) -> None:
    from apps.attendance.models import AttendanceAuditLog, AttendanceRecord
    from apps.attendance.services_audit_log import write_audit_log

    record = AttendanceRecord.objects.filter(
        employee=invalid.punch.employee, date=invalid.punch.punch_date,
    ).first()
    write_audit_log(
        employee=invalid.punch.employee,
        date=invalid.punch.punch_date,
        event=AttendanceAuditLog.EVENT_INVALID_DISCARDED,
        performed_by=performed_by,
        record=record,
        old_value=f'{invalid.punch.punch_type} @ {invalid.punch.punch_time_display}',
        action='Invalid punch discarded by HR',
        remarks=invalid.remarks,
    )


def _write_convert_audit(invalid, punch, target_type, target_time_str, record, performed_by) -> None:
    from apps.attendance.models import AttendanceAuditLog
    from apps.attendance.services_audit_log import write_audit_log

    write_audit_log(
        employee=punch.employee,
        date=punch.punch_date,
        event=AttendanceAuditLog.EVENT_INVALID_CONVERTED,
        performed_by=performed_by,
        record=record,
        old_value=f'{punch.punch_type} @ {punch.punch_time_display}',
        new_value=f'{target_type} @ {target_time_str}',
        action='Invalid punch converted to valid attendance',
    )


def _build_row(invalid: InvalidPunch) -> dict:
    punch = invalid.punch

    def _fmt_dt(dt):
        return dt.astimezone(_IST).strftime('%Y-%m-%d %H:%M') if dt else None

    return {
        'punch_id':      str(punch.id),
        'status':        invalid.status,
        'issue_type':    invalid.issue_type,
        'issue':         invalid.issue,
        'assigned_to':   getattr(invalid.assigned_to, 'full_name', None) if invalid.assigned_to else None,
        'assigned_at':   _fmt_dt(invalid.assigned_at),
        'discarded_by':  getattr(invalid.discarded_by, 'full_name', None) if invalid.discarded_by else None,
        'discarded_at':  _fmt_dt(invalid.discarded_at),
        'remarks':       invalid.remarks or '',
        'resolved_at':   _fmt_dt(invalid.resolved_at),
    }
