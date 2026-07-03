"""
Attendance Audit Log service.

write_audit_log() — called by other services to record events.
get_audit_history() — called by the audit view to return chronological history.

Logs are immutable — never updated or deleted after creation.
Failures in write_audit_log() are caught and logged; they must never
block the primary business operation that triggered the event.
"""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
_IST = ZoneInfo('Asia/Kolkata')


def write_audit_log(
    employee,
    date,
    event: str,
    performed_by=None,
    record=None,
    old_value: str = '',
    new_value: str = '',
    action: str = '',
    remarks: str = '',
) -> None:
    """
    Write one immutable audit entry.

    Safe to call inside or outside a database transaction.
    All exceptions are swallowed — audit log failures must never surface
    to the employee or HR user.
    """
    from apps.attendance.models import AttendanceAuditLog
    try:
        AttendanceAuditLog.objects.create(
            record=record,
            employee=employee,
            date=date,
            event=event,
            old_value=old_value or '',
            new_value=new_value or '',
            action=action or '',
            performed_by=performed_by,
            remarks=remarks or '',
        )
    except Exception as exc:
        logger.error(
            'Audit log write failed [event=%s employee=%s date=%s]: %s',
            event, getattr(employee, 'pk', '?'), date, exc,
        )


def get_audit_history(record_id: str) -> list[dict] | None:
    """
    Return chronological audit history for one AttendanceRecord.

    Returns None when the record does not exist (caller returns 404).
    Uses select_related to avoid N+1 on performed_by.
    """
    from apps.attendance.models import AttendanceAuditLog, AttendanceRecord

    try:
        record = AttendanceRecord.objects.get(id=record_id)
    except AttendanceRecord.DoesNotExist:
        return None

    logs = (
        AttendanceAuditLog.objects
        .filter(record=record)
        .select_related('performed_by')
        .order_by('created_at')
    )
    return [_build_row(log) for log in logs]


# ── Private ───────────────────────────────────────────────────────────────────

def _build_row(log) -> dict:
    if log.performed_by:
        actor = (
            getattr(log.performed_by, 'full_name', None)
            or getattr(log.performed_by, 'email', None)
            or 'Unknown'
        )
    else:
        actor = 'System'

    return {
        'event':        log.event,
        'performed_by': actor,
        'performed_at': log.created_at.astimezone(_IST).strftime('%Y-%m-%d %H:%M:%S'),
        'old_value':    log.old_value or None,
        'new_value':    log.new_value or None,
        'action':       log.action or '',
        'remarks':      log.remarks or '',
    }
