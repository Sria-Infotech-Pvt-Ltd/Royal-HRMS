"""Employee-side timesheet actions: read a week, save a draft, submit (or resubmit). Deciding a sheet is in
services_timesheet_decisions.py. Each action runs in one transaction under a lock on the employee's own row, so two
simultaneous requests from the same person (a double click, two tabs) cannot both create or both submit the sheet."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.attendance.models_timesheet import (
    EDITABLE_STATUSES, EVENT_RESUBMITTED, EVENT_SUBMITTED, STATUS_DRAFT, STATUS_RETURNED, STATUS_SUBMITTED,
    Timesheet, TimesheetEntry, TimesheetLine,
)
from apps.attendance.services_timesheet_validation import (
    LineInput, business_issues, lines_from_sheet, normalise_payload,
)
from apps.attendance.services_timesheet_approval import resolve_approver
from apps.attendance.services_timesheet_common import (
    TimesheetConflict, TimesheetError, TimesheetNotFound, due_date, monday_of, require_monday, today,
)
from apps.attendance.services_timesheet_history import record_event
from apps.attendance.services_timesheet_notify import notify_submitted
from apps.attendance.services_timesheet_week import build_week_view, load_sheet


def get_week(employee, any_day: datetime.date) -> dict:
    """Any date inside the week is accepted when reading; the sheet shown is that week's Monday-to-Sunday."""
    return build_week_view(employee, monday_of(any_day))


def _lock_employee(employee) -> None:
    """The employee's own row stands in as the mutex: it always exists, even before their first sheet does."""
    User.objects.select_for_update().get(pk=employee.pk)


def _locked_sheet(employee, week_start: datetime.date) -> Timesheet | None:
    return Timesheet.objects.select_for_update().filter(employee=employee, week_start=week_start).first()


def _reject_future_week(week_start: datetime.date) -> None:
    if week_start > monday_of(today()):
        raise TimesheetError('A timesheet cannot be filled in for a week that has not started yet.')


def _replace_lines(sheet: Timesheet, lines: list[LineInput]) -> None:
    sheet.lines.all().delete()          # a draft is rewritten whole; the history events keep every submitted version
    total = billable = Decimal('0')
    for order, item in enumerate(lines):
        assignment = item.assignment
        line = TimesheetLine.objects.create(
            timesheet=sheet, is_internal=item.is_internal, is_billable=item.is_billable, sort_order=order,
            assignment_id=assignment.assignment_id if assignment else None,
            project_id=assignment.project_id if assignment else None,
            project_code=assignment.project_code if assignment else '',
            project_name=assignment.project_name if assignment else '',
        )
        TimesheetEntry.objects.bulk_create([TimesheetEntry(line=line, entry_date=d, hours=h, note=n) for d, h, n in item.entries])
        hours = sum((h for _, h, _ in item.entries), Decimal('0'))
        total += hours
        billable += hours if item.is_billable else Decimal('0')
    sheet.total_hours, sheet.billable_hours = total, billable


def save_draft(employee, week_start: datetime.date, payload, *, actor=None) -> dict:
    """Keep the hours without submitting. Allowed while the sheet is a draft or has been returned; a submitted or approved
    sheet is read-only. Only the structure is checked here, so a half-filled sheet can always be saved; the business rules
    are returned as `issues` for the screen and enforced on submit."""
    require_monday(week_start)
    _reject_future_week(week_start)
    lines = normalise_payload(employee, week_start, payload)
    with transaction.atomic():
        _lock_employee(employee)
        sheet = _locked_sheet(employee, week_start)
        if sheet is None:
            sheet = Timesheet(employee=employee, week_start=week_start, status=STATUS_DRAFT, branch_name=employee.branch or '')
        elif sheet.status not in EDITABLE_STATUSES:
            raise TimesheetConflict(f'This timesheet is {sheet.get_status_display().lower()} and cannot be changed.')
        _replace_lines(sheet, lines)
        sheet.save()
        errors, warnings = business_issues(employee, week_start, lines, for_submit=False)
    view = build_week_view(employee, week_start, load_sheet(employee, week_start))
    return {**view, 'issues': {'errors': errors, 'warnings': warnings}}


def _attendance_minutes(employee, week_start: datetime.date) -> int:
    week_end = week_start + datetime.timedelta(days=6)
    rows = AttendanceRecord.objects.filter(employee=employee, date__gte=week_start, date__lte=week_end)
    return rows.aggregate(total=Sum('total_working_minutes'))['total'] or 0


def submit(employee, week_start: datetime.date, *, actor=None, ip_address: str | None = None) -> dict:
    """Submit (or resubmit a returned) sheet for approval. Every business rule is checked; if anything fails nothing changes."""
    require_monday(week_start)
    _reject_future_week(week_start)
    with transaction.atomic():
        _lock_employee(employee)
        sheet = _locked_sheet(employee, week_start)
        if sheet is None:
            raise TimesheetNotFound('Save your hours before submitting.')
        if sheet.status not in EDITABLE_STATUSES:
            raise TimesheetConflict(f'This timesheet is already {sheet.get_status_display().lower()}.')
        errors, warnings = business_issues(employee, week_start, lines_from_sheet(sheet), for_submit=True)
        if errors:
            raise TimesheetError('This timesheet cannot be submitted yet.', errors=errors)
        approver = resolve_approver(employee)
        previous = sheet.status
        sheet.status, sheet.approver, sheet.submitted_at = STATUS_SUBMITTED, approver, timezone.now()
        sheet.decided_at = sheet.decided_by = None
        sheet.return_reason = ''
        sheet.submit_count += 1
        sheet.is_late = today() > due_date(week_start)
        sheet.attendance_minutes = _attendance_minutes(employee, week_start)
        sheet.branch_name = employee.branch or sheet.branch_name
        sheet.save()
        is_resubmission = previous == STATUS_RETURNED
        record_event(
            sheet, EVENT_RESUBMITTED if is_resubmission else EVENT_SUBMITTED,
            actor=actor or employee, from_status=previous, ip_address=ip_address,
        )
        notify_submitted(sheet, is_resubmission=is_resubmission)
    view = build_week_view(employee, week_start, load_sheet(employee, week_start))
    return {**view, 'issues': {'errors': [], 'warnings': warnings}}
