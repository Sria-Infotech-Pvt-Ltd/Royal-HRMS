"""Timesheet reports for the Reports screen: employee-wise, project-wise, billable vs non-billable, and a weekly summary.

All four read only the sheets the person may see: `timesheet.report` is required (checked by the registry), and the rows come from
`team_queryset(..., for_reports=True)`, which is the sheets they can decide plus those of employees in their scope, never
someone's draft and never their own. Totals count only submitted and approved sheets (a draft or returned sheet is not final).
Builders import the registry's helpers inside the functions: the registry imports this module, so a top-level import would loop.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db.models import Count, Max, Q, QuerySet, Sum

from apps.attendance.models_timesheet import STATUS_APPROVED, STATUS_SUBMITTED, TimesheetEntry
from apps.attendance.services_timesheet_access import team_queryset
from apps.attendance.services_timesheet_common import INTERNAL_LABEL, hours_text, monday_of

FINAL_STATUSES = (STATUS_SUBMITTED, STATUS_APPROVED)


def _week(value) -> datetime.date | None:
    return monday_of(value) if isinstance(value, datetime.date) else None


def _scoped(user, params: dict, *, statuses: tuple | None = FINAL_STATUSES) -> QuerySet:
    """The person's visible sheets, narrowed by the status filter (or `statuses` when none was chosen) and the week range."""
    sheets = team_queryset(user, for_reports=True)
    chosen = params.get('status')
    if chosen:
        sheets = sheets.filter(status=chosen)
    elif statuses:
        sheets = sheets.filter(status__in=statuses)
    first, last = _week(params.get('from')), _week(params.get('to'))
    if first:
        sheets = sheets.filter(week_start__gte=first)
    if last:
        sheets = sheets.filter(week_start__lte=last)
    return sheets


def _entries(sheets: QuerySet) -> QuerySet:
    return TimesheetEntry.objects.filter(line__timesheet_id__in=sheets.order_by().values('pk'))


def _hours(value) -> str:
    return hours_text(value or Decimal('0'))


def employee_wise(user, params: dict):
    from apps.dashboard.services_reports import MAX_ROWS, ReportData, _person, _text

    sheets = _scoped(user, params, statuses=None)         # every status except drafts, so a sent-back sheet is visible too
    headers = [
        'Employee ID', 'Name', 'Branch', 'Week starting', 'Status', 'Project hours', 'Billable hours', 'Non-billable hours',
        'Attendance hours', 'Submitted', 'Late', 'Approver', 'Decided by', 'Decided on',
    ]
    rows = [[
        s.employee.employee_id, _person(s.employee), s.branch_name, _text(s.week_start), s.get_status_display(), _hours(s.total_hours),
        _hours(s.billable_hours), _hours(s.total_hours - s.billable_hours), _hours(Decimal(s.attendance_minutes) / 60),
        _text(s.submitted_at.date()) if s.submitted_at else '', 'Yes' if s.is_late else 'No', _person(s.approver), _person(s.decided_by),
        _text(s.decided_at.date()) if s.decided_at else '',
    ] for s in sheets.order_by('employee__employee_id', '-week_start')[:MAX_ROWS]]
    return ReportData(headers, rows)


def project_wise(user, params: dict):
    from apps.dashboard.services_reports import MAX_ROWS, ReportData, _text

    grouped = (
        _entries(_scoped(user, params))
        .values('line__project_id', 'line__is_internal')
        .annotate(
            code=Max('line__project_code'), name=Max('line__project_name'), total=Sum('hours'),
            billable=Sum('hours', filter=Q(line__is_billable=True)), people=Count('line__timesheet__employee', distinct=True),
            sheets=Count('line__timesheet', distinct=True),
        )
        .order_by('line__is_internal', 'name')
    )
    headers = ['Project code', 'Project', 'Total hours', 'Billable hours', 'Non-billable hours', 'Employees', 'Timesheets']
    rows = [[
        '' if row['line__is_internal'] else row['code'], INTERNAL_LABEL if row['line__is_internal'] else row['name'], _hours(row['total']),
        _hours(row['billable']), _hours((row['total'] or Decimal('0')) - (row['billable'] or Decimal('0'))), _text(row['people']), _text(row['sheets']),
    ] for row in grouped[:MAX_ROWS]]
    return ReportData(headers, rows)


def billable_split(user, params: dict):
    from apps.dashboard.services_reports import MAX_ROWS, ReportData, _text

    grouped = (
        _entries(_scoped(user, params))
        .values('line__timesheet__employee__employee_id', 'line__timesheet__employee__full_name')
        .annotate(total=Sum('hours'), billable=Sum('hours', filter=Q(line__is_billable=True)))
        .order_by('line__timesheet__employee__employee_id')
    )
    headers = ['Employee ID', 'Name', 'Total hours', 'Billable hours', 'Non-billable hours', 'Billable %']
    rows = []
    for row in grouped[:MAX_ROWS]:
        total, billable = row['total'] or Decimal('0'), row['billable'] or Decimal('0')
        percent = (billable / total * 100).quantize(Decimal('0.1')) if total else Decimal('0.0')
        rows.append([
            row['line__timesheet__employee__employee_id'], row['line__timesheet__employee__full_name'] or '', _hours(total), _hours(billable),
            _hours(total - billable), _text(percent),
        ])
    return ReportData(headers, rows)


def weekly_summary(user, params: dict):
    from apps.dashboard.services_reports import MAX_ROWS, ReportData, _text

    grouped = (
        _scoped(user, params, statuses=None).order_by().values('week_start')
        .annotate(
            sheets=Count('pk'), submitted=Count('pk', filter=Q(status=STATUS_SUBMITTED)), approved=Count('pk', filter=Q(status=STATUS_APPROVED)),
            returned=Count('pk', filter=Q(status='returned')), late=Count('pk', filter=Q(is_late=True)), total=Sum('total_hours'),
            billable=Sum('billable_hours'), attendance=Sum('attendance_minutes'),
        )
        .order_by('-week_start')
    )
    headers = [
        'Week starting', 'Timesheets', 'Awaiting approval', 'Approved', 'Sent back', 'Late', 'Project hours', 'Billable hours',
        'Non-billable hours', 'Attendance hours',
    ]
    rows = [[
        _text(row['week_start']), _text(row['sheets']), _text(row['submitted']), _text(row['approved']), _text(row['returned']), _text(row['late']),
        _hours(row['total']), _hours(row['billable']), _hours((row['total'] or Decimal('0')) - (row['billable'] or Decimal('0'))),
        _hours(Decimal(row['attendance'] or 0) / 60),
    ] for row in grouped[:MAX_ROWS]]
    return ReportData(headers, rows)

