"""What one employee's timesheet week looks like: the grid, the day-by-day context and the totals.

Nothing here re-implements attendance rules. Holidays, weekly offs, leave and employment dates come from the same helpers
the attendance calendar uses (AttendanceDashboardService), so the two screens can never disagree about a day.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db.models import Q

from apps.accounts.services_lifecycle_status import approved_last_working_days, latest_last_working_day
from apps.attendance.models import AttendanceRecord
from apps.attendance.models_timesheet import EDITABLE_STATUSES, STATUS_DRAFT, Timesheet
from apps.attendance.services_attendance import AttendanceDashboardService as Attendance
from apps.attendance.services_timesheet_common import (
    DAILY_WARNING_HOURS, INTERNAL_LABEL, MAX_NOTE_LENGTH, WEEKLY_TARGET_HOURS, due_date, hours_text, today, week_days,
)
from apps.hrms.models import ProjectAssignment

UPCOMING = 'upcoming'                       # a future day with nothing recorded yet
DAY_LABELS = {**AttendanceRecord.STATUS_DISPLAY_MAP, UPCOMING: 'Upcoming'}
# Days on which an entry is allowed but flagged, because nobody was expected to work.
NON_WORKING = (AttendanceRecord.STATUS_HOLIDAY, AttendanceRecord.STATUS_WEEKLY_OFF, AttendanceRecord.STATUS_ON_LEAVE)


def employee_assignments(employee, week_start: datetime.date) -> list[ProjectAssignment]:
    """The employee's project assignments that overlap this week, ordered by project name."""
    if not employee.employee_id:
        return []
    week_end = week_start + datetime.timedelta(days=6)
    return list(
        ProjectAssignment.objects.filter(employee_code=employee.employee_id)
        .filter(Q(assignment_start_date__isnull=True) | Q(assignment_start_date__lte=week_end))
        .filter(Q(assignment_end_date__isnull=True) | Q(assignment_end_date__gte=week_start))
        .order_by('project_name', 'assignment_id')
    )


def employment_window(employee) -> tuple:
    """(joined, last working day) from the lifecycle rules: an approved separation ends the employment."""
    joined = employee.date_of_joining
    return joined, latest_last_working_day(joined, approved_last_working_days(employee))


def day_context(employee, week_start: datetime.date) -> list[dict]:
    """Seven dicts, Monday first: the day's status (holiday / weekly off / leave / not employed / attendance), its holiday
    name, and the hours attendance recorded (from punches, shown apart from the project hours)."""
    week_end = week_start + datetime.timedelta(days=6)
    branch_name = getattr(employee, 'branch', '') or ''
    records = {r.date: r for r in AttendanceRecord.objects.filter(employee=employee, date__gte=week_start, date__lte=week_end)}
    holiday_names = Attendance._holiday_names(week_start, week_end, branch_name)
    leave_dates = Attendance._leave_dates(employee, week_start, week_end)
    off_dates = Attendance._weekly_off_dates(employee, week_start, week_end)
    joined, last_day = employment_window(employee)
    now = today()
    days = []
    for day in week_days(week_start):
        record = records.get(day)
        status = Attendance._classify_day(day, record, set(holiday_names), off_dates, leave_dates, now, joined, last_day) or UPCOMING
        days.append({
            'date': day.isoformat(), 'weekday': day.strftime('%a'), 'status': status, 'status_label': DAY_LABELS.get(status, status),
            'holiday_name': holiday_names.get(day, ''), 'is_future': day > now,
            'is_employed': status != AttendanceRecord.STATUS_NOT_EMPLOYED,
            'attendance_minutes': record.total_working_minutes if record else 0,
        })
    return days


def _line_dict(line) -> dict:
    return {
        'id': str(line.pk), 'assignment_id': line.assignment_id, 'project_id': line.project_id, 'project_code': line.project_code,
        'project_name': INTERNAL_LABEL if line.is_internal else line.project_name, 'is_internal': line.is_internal,
        'is_billable': line.is_billable,
        'entries': {e.entry_date.isoformat(): {'hours': hours_text(e.hours), 'note': e.note} for e in line.entries.all()},
    }


def _empty_line(assignment: ProjectAssignment | None) -> dict:
    return {
        'id': None, 'assignment_id': assignment.assignment_id if assignment else None,
        'project_id': assignment.project_id if assignment else None, 'project_code': assignment.project_code if assignment else '',
        'project_name': assignment.project_name if assignment else INTERNAL_LABEL, 'is_internal': assignment is None,
        'is_billable': False, 'entries': {},
    }


def _merge_prefill(lines: list[dict], employee, week_start: datetime.date) -> list[dict]:
    """Add an empty row for every current assignment (and the Internal row) that the saved sheet does not have yet."""
    have = {line['assignment_id'] for line in lines if line['assignment_id'] is not None}
    merged = list(lines)
    merged += [_empty_line(a) for a in employee_assignments(employee, week_start) if a.assignment_id not in have]
    if not any(line['is_internal'] for line in merged):
        merged.append(_empty_line(None))
    return merged


def _totals(lines: list[dict], days: list[dict]) -> dict:
    daily = {day['date']: Decimal('0') for day in days}
    billable = Decimal('0')
    for line in lines:
        for iso, cell in line['entries'].items():
            hours = Decimal(cell['hours'])
            daily[iso] = daily.get(iso, Decimal('0')) + hours
            billable += hours if line['is_billable'] else Decimal('0')
    week = sum(daily.values(), Decimal('0'))
    return {
        'daily': {iso: hours_text(h) for iso, h in daily.items()}, 'week': hours_text(week), 'billable': hours_text(billable),
        'non_billable': hours_text(week - billable), 'target': hours_text(WEEKLY_TARGET_HOURS),
        'attendance_hours': hours_text(Decimal(sum(d['attendance_minutes'] for d in days)) / 60),
    }


def _person(user) -> dict | None:
    return {'id': str(user.pk), 'name': user.full_name or user.email, 'employee_id': user.employee_id} if user else None


def _event_dict(event) -> dict:
    return {
        'id': str(event.pk), 'event_type': event.event_type, 'from_status': event.from_status, 'to_status': event.to_status,
        'reason': event.reason, 'actor': _person(event.actor), 'at': event.created_at.isoformat(), 'snapshot': event.snapshot,
    }


def load_sheet(employee, week_start: datetime.date) -> Timesheet | None:
    return (
        Timesheet.objects.select_related('employee', 'approver', 'decided_by')
        .prefetch_related('lines__entries', 'events__actor')
        .filter(employee=employee, week_start=week_start).first()
    )


def build_week_view(employee, week_start: datetime.date, sheet: Timesheet | None = None) -> dict:
    """The whole screen for one week: the saved sheet if there is one, otherwise a draft prefilled from the employee's
    project assignments. An editable sheet also gets an empty row for any assignment that appeared after it was saved."""
    sheet = sheet if sheet is not None else load_sheet(employee, week_start)
    status = sheet.status if sheet else STATUS_DRAFT
    is_editable = status in EDITABLE_STATUSES
    days = day_context(employee, week_start)
    lines = [_line_dict(line) for line in sheet.lines.all()] if sheet else []
    if is_editable:
        lines = _merge_prefill(lines, employee, week_start)
    is_late = sheet.is_late if sheet and sheet.submitted_at else today() > due_date(week_start)
    return {
        'id': str(sheet.pk) if sheet else None, 'employee': _person(employee), 'week_start': week_start.isoformat(),
        'week_end': (week_start + datetime.timedelta(days=6)).isoformat(), 'due_date': due_date(week_start).isoformat(),
        'status': status, 'is_editable': is_editable, 'is_late': is_late, 'return_reason': sheet.return_reason if sheet else '',
        'submitted_at': sheet.submitted_at.isoformat() if sheet and sheet.submitted_at else None,
        'decided_at': sheet.decided_at.isoformat() if sheet and sheet.decided_at else None,
        'approver': _person(sheet.approver) if sheet else None, 'decided_by': _person(sheet.decided_by) if sheet else None,
        'days': days, 'lines': lines, 'totals': _totals(lines, days),
        'limits': {'daily_warning_hours': hours_text(DAILY_WARNING_HOURS), 'daily_max_hours': '24.00', 'hour_step': '0.25',
                   'weekly_target_hours': hours_text(WEEKLY_TARGET_HOURS), 'max_note_length': MAX_NOTE_LENGTH},
        'events': [_event_dict(e) for e in sheet.events.all()] if sheet else [],
    }
