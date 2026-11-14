"""Timesheet building blocks shared by the week view, the validation and the save / submit / decide services."""
from __future__ import annotations

import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from apps.attendance.models_timesheet import HOUR_STEP, MAX_DAILY_HOURS, Timesheet

# Business defaults (one place to change them). The weekly target is shown, never enforced.
DAILY_WARNING_HOURS = Decimal('12')
WEEKLY_TARGET_HOURS = Decimal('40')
DUE_DAY_OFFSET = 4                       # Monday + 4 = Friday: the submission due date
MAX_NOTE_LENGTH = 500
INTERNAL_LABEL = 'Internal / Non-project work'


class TimesheetError(Exception):
    """A rule the request broke. `errors` lists every problem found, so the screen can show them all at once."""

    code = 'invalid'

    def __init__(self, message: str, *, errors: Iterable[str] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = list(errors or [message])


class TimesheetNotFound(TimesheetError):
    code = 'not_found'


class TimesheetConflict(TimesheetError):
    """The sheet is not in a state that allows this (already decided, locked, changed by someone else)."""

    code = 'conflict'


class TimesheetForbidden(TimesheetError):
    code = 'forbidden'


def today() -> datetime.date:
    from django.utils import timezone

    return timezone.localdate()


def monday_of(day: datetime.date) -> datetime.date:
    return day - datetime.timedelta(days=day.weekday())


def week_days(week_start: datetime.date) -> list[datetime.date]:
    return [week_start + datetime.timedelta(days=offset) for offset in range(7)]


def due_date(week_start: datetime.date) -> datetime.date:
    return week_start + datetime.timedelta(days=DUE_DAY_OFFSET)


def require_monday(week_start: datetime.date) -> None:
    if week_start.weekday() != 0:
        raise TimesheetError('A timesheet week starts on a Monday.')


def parse_hours(value) -> Decimal:
    """Hours as an exact quarter-hour amount between 0 and 24, or a TimesheetError. Floats are read through their text so
    0.1 + 0.2 style noise never sneaks in; a boolean, NaN or infinity is not a number of hours."""
    if isinstance(value, bool) or value is None or value == '':
        raise TimesheetError('Hours must be a number.')
    try:
        hours = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise TimesheetError(f'"{value}" is not a valid number of hours.') from None
    if not hours.is_finite():
        raise TimesheetError(f'"{value}" is not a valid number of hours.')
    if hours < 0 or hours > MAX_DAILY_HOURS:
        raise TimesheetError(f'Hours for a day must be between 0 and {MAX_DAILY_HOURS}.')
    if hours % HOUR_STEP != 0:
        raise TimesheetError('Hours must be in steps of 0.25 (quarter hours).')
    return hours.quantize(Decimal('0.01'))


def hours_text(value: Decimal) -> str:
    return format(value.quantize(Decimal('0.01')), 'f')


def sheet_snapshot(sheet: Timesheet) -> dict:
    """The sheet exactly as it is now, as plain JSON: stored on every history event so an earlier version can be read back."""
    lines = []
    for line in sheet.lines.all().order_by('sort_order', 'created_at'):
        lines.append({
            'assignment_id': line.assignment_id, 'project_id': line.project_id, 'project_code': line.project_code,
            'project_name': line.project_name, 'is_internal': line.is_internal, 'is_billable': line.is_billable,
            'entries': [
                {'date': entry.entry_date.isoformat(), 'hours': hours_text(entry.hours), 'note': entry.note}
                for entry in line.entries.all().order_by('entry_date')
            ],
        })
    return {
        'week_start': sheet.week_start.isoformat(), 'status': sheet.status, 'total_hours': hours_text(sheet.total_hours),
        'billable_hours': hours_text(sheet.billable_hours), 'attendance_minutes': sheet.attendance_minutes, 'lines': lines,
    }
