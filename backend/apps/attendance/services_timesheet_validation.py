"""Checking a timesheet: the shape of what was sent (structure) and the business rules (employment, projects, hours).

`normalise_payload` raises TimesheetError listing every structural problem. `business_issues` returns (errors, warnings):
errors block a submit, warnings are shown but never block. Saving a draft only needs the structure to be valid, so a half-filled
sheet can always be kept.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from apps.accounts.services_lifecycle_status import ATTENDANCE_DATE_PROBLEMS, approved_last_working_days, attendance_date_problem_code
from apps.attendance.models_timesheet import MAX_DAILY_HOURS, Timesheet
from apps.attendance.services_timesheet_common import (
    DAILY_WARNING_HOURS, INTERNAL_LABEL, MAX_NOTE_LENGTH, TimesheetError, hours_text, monday_of, parse_hours, today, week_days,
)
from apps.attendance.services_timesheet_week import NON_WORKING, day_context, employee_assignments
from apps.hrms.models import ProjectAssignment

Cell = tuple  # (date, hours Decimal, note str)


@dataclass
class LineInput:
    assignment: ProjectAssignment | None
    is_internal: bool
    is_billable: bool
    entries: list[Cell] = field(default_factory=list)

    @property
    def label(self) -> str:
        return INTERNAL_LABEL if self.is_internal else (self.assignment.project_name if self.assignment else 'Project')


def _day_text(day: datetime.date) -> str:
    return f'{day.strftime("%a")} {day.day} {day.strftime("%b")}'


def _parse_assignment_id(raw) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, str)) or str(raw).strip() == '':
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_entry(raw, week: set, label: str, errors: list) -> Cell | None:
    if not isinstance(raw, dict):
        errors.append(f'{label}: each day must have a date and hours.')
        return None
    try:
        day = datetime.date.fromisoformat(str(raw.get('date', '')))
    except ValueError:
        errors.append(f'{label}: "{raw.get("date")}" is not a valid date.')
        return None
    if day not in week:
        errors.append(f'{label}: {day.isoformat()} is outside this week.')
        return None
    try:
        hours = parse_hours(raw.get('hours', 0))
    except TimesheetError as exc:
        errors.append(f'{label}, {_day_text(day)}: {exc.message}')
        return None
    note = raw.get('note') or ''
    if not isinstance(note, str) or len(note) > MAX_NOTE_LENGTH:
        errors.append(f'{label}, {_day_text(day)}: a note can be at most {MAX_NOTE_LENGTH} characters.')
        return None
    return day, hours, note.strip()


def _parse_line(raw, week: set, allowed: dict, errors: list) -> LineInput | None:
    if not isinstance(raw, dict) or not isinstance(raw.get('entries', []), list):
        errors.append('Each row needs a project (or Internal work) and a list of days.')
        return None
    is_internal = raw.get('is_internal') is True
    assignment = None
    if not is_internal:
        assignment = allowed.get(_parse_assignment_id(raw.get('assignment_id')))
        if assignment is None:
            errors.append('A project row is not one of your assignments for this week.')
            return None
    line = LineInput(assignment, is_internal, raw.get('is_billable') is True)
    seen: set = set()
    for item in raw.get('entries', []):
        cell = _parse_entry(item, week, line.label, errors)
        if cell is None:
            continue
        if cell[0] in seen:
            errors.append(f'{line.label}: {_day_text(cell[0])} appears twice.')
        elif cell[1] > 0 or cell[2]:
            seen.add(cell[0])
            line.entries.append(cell)
    return line


def normalise_payload(employee, week_start: datetime.date, payload) -> list[LineInput]:
    """Structure only. Every problem found is reported together, not just the first."""
    if not isinstance(payload, dict) or not isinstance(payload.get('lines'), list):
        raise TimesheetError('The timesheet must contain a list of rows.')
    allowed = {a.assignment_id: a for a in employee_assignments(employee, week_start)}
    week, errors, lines = set(week_days(week_start)), [], []
    for raw in payload['lines']:
        line = _parse_line(raw, week, allowed, errors)
        if line is not None:
            lines.append(line)
    ids = [line.assignment.assignment_id for line in lines if line.assignment]
    if len(ids) != len(set(ids)):
        errors.append('A project appears in more than one row.')
    if sum(line.is_internal for line in lines) > 1:
        errors.append('There can be only one Internal / Non-project row.')
    if errors:
        raise TimesheetError('Some hours need fixing.', errors=errors)
    return lines


def lines_from_sheet(sheet: Timesheet) -> list[LineInput]:
    """The saved sheet as LineInputs, with each project's assignment looked up again for its dates."""
    found = {a.assignment_id: a for a in ProjectAssignment.objects.filter(
        assignment_id__in=[line.assignment_id for line in sheet.lines.all() if line.assignment_id is not None])}
    result = []
    for line in sheet.lines.all():
        item = LineInput(found.get(line.assignment_id), line.is_internal, line.is_billable)
        item.entries = [(e.entry_date, e.hours, e.note) for e in line.entries.all()]
        if not line.is_internal and item.assignment is None:
            item.assignment = ProjectAssignment(project_name=line.project_name)   # the row is gone: no dates to check against
        result.append(item)
    return result


def _daily_totals(lines: list[LineInput]) -> dict:
    totals: dict = {}
    for line in lines:
        for day, hours, _ in line.entries:
            totals[day] = totals.get(day, Decimal('0')) + hours
    return totals


def _entry_errors(line: LineInput, day, hours: Decimal, joined, last_days, now) -> list[str]:
    if hours <= 0:
        return []
    problems = []
    code = attendance_date_problem_code(joined, last_days, day)
    if code:
        problems.append(f'{_day_text(day)}: {ATTENDANCE_DATE_PROBLEMS[code]}')
    assignment = line.assignment
    if assignment is not None and assignment.assignment_id is not None:
        starts, ends = assignment.assignment_start_date, assignment.assignment_end_date
        if (starts and day < starts) or (ends and day > ends):
            problems.append(f'{_day_text(day)}: you were not assigned to "{line.label}" on this day.')
    if day > now:
        problems.append(f'{_day_text(day)}: hours cannot be logged for a day that has not happened yet.')
    return problems


def business_issues(employee, week_start: datetime.date, lines: list[LineInput], *, for_submit: bool, days: list | None = None) -> tuple:
    """(errors, warnings). `days` can be passed in when the caller already built the week's day context."""
    errors, warnings = [], []
    now = today()
    if week_start > monday_of(now):
        errors.append('A timesheet cannot be filled in for a week that has not started yet.')
    joined, last_days = employee.date_of_joining, approved_last_working_days(employee)
    status_by_date = {d['date']: d['status'] for d in (days or day_context(employee, week_start))}
    for line in lines:
        for day, hours, _ in line.entries:
            errors += _entry_errors(line, day, hours, joined, last_days, now)
            if hours > 0 and status_by_date.get(day.isoformat()) in NON_WORKING:
                warnings.append({'code': 'non_working_day', 'date': day.isoformat(),
                                 'message': f'{_day_text(day)}: hours entered on a holiday, weekly off or leave day.'})
    totals = _daily_totals(lines)
    for day, total in sorted(totals.items()):
        if total > MAX_DAILY_HOURS:
            errors.append(f'{_day_text(day)}: the total across projects is {hours_text(total)} hours, more than {MAX_DAILY_HOURS} in a day.')
        elif total > DAILY_WARNING_HOURS:
            warnings.append({'code': 'long_day', 'date': day.isoformat(),
                             'message': f'{_day_text(day)}: {hours_text(total)} hours in one day.'})
    if for_submit and sum(totals.values(), Decimal('0')) <= 0:
        errors.append('Enter some hours before submitting.')
    return errors, warnings
