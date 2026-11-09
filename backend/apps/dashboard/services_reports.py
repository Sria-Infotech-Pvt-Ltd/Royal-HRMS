"""
The report registry behind the Reports screen.

Every report is built on the server, for the signed-in person, from data that person may already see:

  - it needs the same permission the underlying module requires (employees.export, attendance.view, leave.approve, ...);
  - it reuses that module's own scoping (employees in scope, the approval scope of a workflow, the Face ID reviewer scope,
    the recruitment branch rule), so a report can never show more than the module's own screens do;
  - filters are validated here; unknown filters are ignored.

Nothing here accepts report content from the browser. Delivery (download, email) lives in services_report_delivery.py.
"""
from __future__ import annotations

import csv
import datetime
import io
from dataclasses import dataclass, field
from typing import Callable

from core.permissions import has_perm

MAX_ROWS = 20000


@dataclass(frozen=True)
class FilterSpec:
    key: str
    label: str
    kind: str                                   # "select" or "date"
    options: tuple[tuple[str, str], ...] = ()
    default: str = ''


@dataclass
class ReportData:
    headers: list[str]
    rows: list[list]

    def without_columns(self, names: tuple[str, ...]) -> 'ReportData':
        keep = [index for index, header in enumerate(self.headers) if header not in names]
        return ReportData([self.headers[i] for i in keep], [[row[i] for i in keep] for row in self.rows])


@dataclass(frozen=True)
class ReportSpec:
    key: str
    title: str
    description: str
    permission: str
    builder: Callable[..., ReportData]
    filters: tuple[FilterSpec, ...] = ()
    # Columns left out of an EMAILED copy (contact details); a download keeps them for people who may see them.
    sensitive_columns: tuple[str, ...] = field(default_factory=tuple)


def _status_filter(*pairs: tuple[str, str]) -> FilterSpec:
    return FilterSpec('status', 'Status', 'select', (('', 'All'), *pairs))


def _text(value) -> str:
    return '' if value is None else str(value)


def _person(user) -> str:
    return (user.full_name or user.email) if user else ''


# ── Builders ────────────────────────────────────────────────────────────────

def _employee_status(user) -> str:
    from apps.accounts.services_onboarding import is_onboarding

    if not user.is_active:
        return 'Exited'
    return 'Onboarding' if (is_onboarding(user) or not user.is_onboarded()) else 'Active'


def _employees(user, params: dict) -> ReportData:
    from apps.accounts.models import User
    from apps.accounts.services_placement import org_unit_names_for
    from core.access import employees_in_scope

    people = list(
        User.objects.filter(employees_in_scope(user)).exclude(employee_id='').select_related('reporting_manager')
        .distinct().order_by('employee_id')[:MAX_ROWS]
    )
    wanted = (params.get('status') or '').lower()
    if wanted:
        people = [person for person in people if _employee_status(person).lower() == wanted]
    units = org_unit_names_for([person.pk for person in people])
    # Lifecycle columns come last so existing column positions are unchanged. One query finds everyone already terminated.
    from apps.accounts.services_lifecycle_status import ACCOUNT_LABELS, STAGE_LABELS, account_status, employment_stage, ended_employee_ids

    ended = ended_employee_ids(people)
    headers = [
        'Employee ID', 'Name', 'Designation', 'Org unit', 'Branch', 'Date of joining', 'Status', 'Reporting manager', 'Email', 'Phone',
        'Employment stage', 'Account status',
    ]
    rows = [[
        person.employee_id, _person(person), person.designation, units.get(person.pk) or person.department, person.branch,
        _text(person.date_of_joining), _employee_status(person), _person(person.reporting_manager), person.email, person.phone,
        STAGE_LABELS[employment_stage(person, ended=person.pk in ended)], ACCOUNT_LABELS[account_status(person)],
    ] for person in people]
    return ReportData(headers, rows)


def _attendance(user, params: dict) -> ReportData:
    from apps.attendance.services_hr_ops import export_attendance_csv
    from apps.attendance.views.hr_attendance_shared import _branch_scope, _manager_scope_employee_ids

    filters = {
        'date': params.get('date') or datetime.date.today(), 'branch': _branch_scope(user, ''), 'department': '',
        'status': params.get('status') or '', 'search': '', 'sort_by': 'name', 'sort_dir': 'asc',
        'employee_ids': _manager_scope_employee_ids(user),
    }
    parsed = list(csv.reader(io.StringIO(export_attendance_csv(filters).lstrip('﻿'))))
    return ReportData(parsed[0] if parsed else [], parsed[1:MAX_ROWS + 1])


def _leave(user, params: dict) -> ReportData:
    from apps.hrms.models import LeaveRequest
    from apps.hrms.views.leave_shared import _approval_scope_filter

    queryset = LeaveRequest.objects.select_related('employee', 'l1_approver', 'l2_approver').filter(_approval_scope_filter(user))
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    if params.get('year'):
        queryset = queryset.filter(start_date__year=int(params['year']))
    headers = ['Employee ID', 'Name', 'Leave type', 'From', 'To', 'Days', 'Status', 'L1 approver', 'L2 approver', 'Submitted']
    rows = [[
        r.employee.employee_id, _person(r.employee), r.get_leave_type_display(), _text(r.start_date), _text(r.end_date), _text(r.total_days),
        r.get_status_display(), _person(r.l1_approver), _person(r.l2_approver), _text(r.created_at.date()),
    ] for r in queryset.order_by('-created_at')[:MAX_ROWS]]
    return ReportData(headers, rows)


def _wfh(user, params: dict) -> ReportData:
    from apps.hrms.models import WorkFromHomeRequest
    from apps.hrms.views.workfromhome import _approval_scope_filter

    queryset = WorkFromHomeRequest.objects.select_related('employee', 'l1_approver', 'l2_approver').filter(_approval_scope_filter(user))
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    headers = ['Employee ID', 'Name', 'From', 'To', 'Location', 'Status', 'L1 approver', 'L2 approver', 'Submitted']
    rows = [[
        r.employee.employee_id, _person(r.employee), _text(r.start_date), _text(r.end_date), r.location_label, r.get_status_display(),
        _person(r.l1_approver), _person(r.l2_approver), _text(r.created_at.date()),
    ] for r in queryset.order_by('-created_at')[:MAX_ROWS]]
    return ReportData(headers, rows)


def _separation(user, params: dict) -> ReportData:
    from apps.hrms.models import SeparationRequest
    from apps.hrms.views.separation import _approval_scope_filter

    queryset = SeparationRequest.objects.select_related('employee').filter(_approval_scope_filter(user))
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    headers = ['Request no.', 'Employee ID', 'Name', 'Type', 'Request date', 'Proposed last working day', 'Notice days', 'Status']
    rows = [[
        _text(r.request_number), r.employee.employee_id, _person(r.employee), r.get_separation_type_display(), _text(r.request_date),
        _text(r.proposed_last_working_day), _text(r.notice_period_days), r.get_status_display(),
    ] for r in queryset.order_by('-request_date')[:MAX_ROWS]]
    return ReportData(headers, rows)


def _face_registrations(user, params: dict) -> ReportData:
    from apps.attendance.services_face_approval import visible_to

    queryset = visible_to(user).select_related('employee', 'approved_by', 'branch')
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    headers = ['Employee ID', 'Name', 'Branch', 'Status', 'Liveness passed', 'Submitted', 'Reviewed by', 'Reviewed on', 'Reviewer notes']
    rows = [[
        r.employee.employee_id, _person(r.employee), r.branch.branch_name if r.branch_id else r.employee.branch, r.get_status_display(),
        'Yes' if r.liveness_passed else 'No', _text(r.created_at.date()), _person(r.approved_by),
        _text(r.approved_at.date()) if r.approved_at else '', r.notes,
    ] for r in queryset.order_by('-created_at')[:MAX_ROWS]]
    return ReportData(headers, rows)


def _candidates(user, params: dict) -> ReportData:
    from apps.recruitment.models import Candidate

    queryset = Candidate.objects.select_related('branch', 'interviewer')
    branch = (getattr(user, 'branch', '') or '').strip()
    if not has_perm(user, 'settings.edit') and branch:
        queryset = queryset.filter(branch__branch_name__iexact=branch)
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    headers = ['Candidate', 'Position', 'Branch', 'Status', 'Interview date', 'Interviewer', 'Added']
    rows = [[
        c.name, c.position_applied, c.branch.branch_name if c.branch_id else '', c.get_status_display(), _text(c.interview_date),
        _person(c.interviewer), _text(c.created_at.date()),
    ] for c in queryset.order_by('-created_at')[:MAX_ROWS]]
    return ReportData(headers, rows)


_REQUEST_STATUS = (('pending', 'Pending'), ('l2_pending', 'Awaiting HR'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'))

REPORTS: tuple[ReportSpec, ...] = (
    ReportSpec('employees', 'Employee directory', 'People in your scope with status, branch and manager.', 'employees.export', _employees,
               (_status_filter(('active', 'Active'), ('onboarding', 'Onboarding'), ('exited', 'Exited')),), ('Email', 'Phone')),
    ReportSpec('attendance', 'Attendance (one day)', "Everyone's attendance on a chosen date.", 'attendance.view', _attendance,
               (FilterSpec('date', 'Date', 'date'), _status_filter(('present', 'Present'), ('late', 'Late'), ('absent', 'Absent'),
                                                                    ('half_day', 'Half day'), ('on_leave', 'On leave')))),
    ReportSpec('leave', 'Leave requests', 'Leave requests in your approval scope.', 'leave.approve', _leave,
               (_status_filter(*_REQUEST_STATUS), FilterSpec('year', 'Year', 'select',
                                                             (('', 'All years'), *((str(y), str(y)) for y in range(datetime.date.today().year, datetime.date.today().year - 4, -1)))))),
    ReportSpec('wfh', 'Work from home requests', 'Work from home requests in your approval scope.', 'wfh.approve', _wfh, (_status_filter(*_REQUEST_STATUS),)),
    ReportSpec('separation', 'Separation requests', 'Resignations and other separations in your scope.', 'separation.approve', _separation,
               (_status_filter(('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')),)),
    ReportSpec('face_registrations', 'Face ID registrations', 'Registrations you may review. No biometric data is included.',
               'facial_recognition.approve', _face_registrations, (_status_filter(('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')),)),
    ReportSpec('candidates', 'Recruitment candidates', 'Candidates by stage, without contact details.', 'recruitment.view', _candidates,
               (_status_filter(('pending', 'Pending'), ('screening', 'Screening'), ('interview_scheduled', 'Interview scheduled'),
                               ('interview_done', 'Interview done'), ('selected', 'Selected'), ('offer_sent', 'Onboarding link sent'),
                               ('converted', 'Converted'), ('rejected', 'Rejected')),)),
)

_BY_KEY = {spec.key: spec for spec in REPORTS}


def get_report(key: str) -> ReportSpec | None:
    return _BY_KEY.get(key)


def reports_for(user) -> list[ReportSpec]:
    """The reports this person may run: the ones whose underlying permission they hold."""
    return [spec for spec in REPORTS if has_perm(user, spec.permission)]


def clean_params(spec: ReportSpec, raw: dict) -> dict:
    """Keep only this report's filters, each checked against its allowed values. A bad value is dropped, not trusted."""
    cleaned: dict = {}
    for item in spec.filters:
        value = str((raw or {}).get(item.key, item.default) or '').strip()
        if item.kind == 'select' and value in {option[0] for option in item.options}:
            cleaned[item.key] = value
        elif item.kind == 'date' and value:
            try:
                cleaned[item.key] = datetime.date.fromisoformat(value)
            except ValueError:
                pass
    return cleaned


def build_report(user, spec: ReportSpec, raw_params: dict) -> ReportData:
    return spec.builder(user, clean_params(spec, raw_params))
