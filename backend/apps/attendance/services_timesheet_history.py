"""Writing a timesheet's history: one append-only TimesheetEvent (with a snapshot of the sheet) and one AuditLog row per action."""
from __future__ import annotations

from apps.accounts.models import AuditLog
from apps.attendance.models_timesheet import Timesheet, TimesheetEvent
from apps.attendance.services_timesheet_common import sheet_snapshot

AUDIT_MODULE = 'timesheet'


def record_event(sheet: Timesheet, event_type: str, *, actor, from_status: str, reason: str = '', ip_address: str | None = None) -> TimesheetEvent:
    """Call inside the same transaction as the status change, after the new status and totals are saved: the snapshot is read
    from the database, and the audit row is rolled back together with the change if anything fails."""
    event = TimesheetEvent.objects.create(
        timesheet=sheet, event_type=event_type, actor=actor, from_status=from_status, to_status=sheet.status,
        reason=reason, snapshot=sheet_snapshot(sheet),
    )
    AuditLog.objects.create(
        user=actor, action=f'timesheet_{event_type}', module=AUDIT_MODULE, object_id=str(sheet.pk),
        changes={
            'employee_id': str(sheet.employee_id), 'week_start': sheet.week_start.isoformat(),
            'from_status': from_status, 'to_status': sheet.status, 'reason': reason, 'total_hours': str(sheet.total_hours),
        },
        ip_address=ip_address, branch=sheet.branch_name or '',
    )
    return event
