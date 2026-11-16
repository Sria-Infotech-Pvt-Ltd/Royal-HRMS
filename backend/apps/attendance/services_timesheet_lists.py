"""Row shapes for the timesheet lists (the employee's history and the approver's queue)."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db.models import QuerySet

from apps.attendance.models_timesheet import STATUS_SUBMITTED, Timesheet
from apps.attendance.services_timesheet_access import decidable_q
from apps.attendance.services_timesheet_common import hours_text


def sheet_row(sheet: Timesheet, *, can_decide: bool = False) -> dict:
    employee = sheet.employee
    return {
        'id': str(sheet.pk),
        'employee': {'id': str(employee.pk), 'name': employee.full_name or employee.email, 'employee_id': employee.employee_id},
        'week_start': sheet.week_start.isoformat(),
        'week_end': (sheet.week_start + datetime.timedelta(days=6)).isoformat(),
        'status': sheet.status, 'is_late': sheet.is_late,
        'total_hours': hours_text(sheet.total_hours), 'billable_hours': hours_text(sheet.billable_hours),
        'attendance_hours': hours_text(Decimal(sheet.attendance_minutes) / 60),
        'submitted_at': sheet.submitted_at.isoformat() if sheet.submitted_at else None,
        'decided_at': sheet.decided_at.isoformat() if sheet.decided_at else None,
        'approver': (sheet.approver.full_name or sheet.approver.email) if sheet.approver else None,
        'return_reason': sheet.return_reason, 'can_decide': can_decide,
    }


def my_history(employee) -> QuerySet:
    """The employee's own sheets, newest week first (every status, drafts included)."""
    return Timesheet.objects.select_related('employee', 'approver').filter(employee=employee).order_by('-week_start')


def team_rows(sheets: list[Timesheet]) -> list[dict]:
    """Every sheet in the approver's queue is decidable while it is submitted, because the queue IS the decidable set."""
    return [sheet_row(sheet, can_decide=sheet.status == STATUS_SUBMITTED) for sheet in sheets]


def pending_count(actor) -> int:
    """How many submitted sheets are waiting for this person (the tab badge)."""
    return Timesheet.objects.exclude(employee=actor).filter(status=STATUS_SUBMITTED).filter(decidable_q(actor)).count()
