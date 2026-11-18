"""Leave and work-from-home requests.

A person always sees their own. Beyond that they see what the existing pages show them: the approval queue (the module's own
_approval_scope_filter, reused as is) when they hold the approve permission, and the requests of employees they may see when they
hold employees.view. Reasons are free text people write about their health and family, so they are neither searched nor shown.
"""
from django.db.models import Q

from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec, SearchModule, register
from apps.global_search.scope import employee_scope
from apps.hrms.models import LeaveRequest, WorkFromHomeRequest
from core.permissions import has_perm

from ._helpers import choices_of, label_of, short_date


def _visible(user, approve_permission: str, approval_scope) -> Q:
    visible = Q(employee=user)
    if has_perm(user, approve_permission):
        visible |= approval_scope(user)
    if has_perm(user, 'employees.view'):
        visible |= employee_scope(user, 'employee__')
    return visible


def _leave_queryset(user):
    from apps.hrms.views.leave_shared import _approval_scope_filter
    return LeaveRequest.objects.filter(_visible(user, 'leave.approve', _approval_scope_filter)).select_related('employee')


def _wfh_queryset(user):
    from apps.hrms.views.workfromhome import _approval_scope_filter
    return WorkFromHomeRequest.objects.filter(_visible(user, 'wfh.approve', _approval_scope_filter)).select_related('employee')


def _dates(request) -> str:
    return f'{short_date(request.start_date)} to {short_date(request.end_date)}'


def _describe_leave(leave: LeaveRequest) -> dict:
    return {
        'id': str(leave.pk), 'title': leave.employee.full_name,
        'subtitle': ' · '.join(part for part in (leave.leave_type, _dates(leave)) if part),
        'meta': {'Status': label_of(leave, 'status'), 'Days': str(leave.total_days), 'Employee ID': leave.employee.employee_id},
        'url': '/dashboard/leave',
    }


def _describe_wfh(request: WorkFromHomeRequest) -> dict:
    return {
        'id': str(request.pk), 'title': request.employee.full_name, 'subtitle': _dates(request),
        'meta': {'Status': label_of(request, 'status'), 'Location': request.location_label, 'Employee ID': request.employee.employee_id},
        'url': '/dashboard/work-from-home',
    }


def _employee_fields() -> tuple[FieldSpec, ...]:
    return (
        FieldSpec('employee_name', 'Employee', f.TEXT, 'employee__full_name', searchable=True),
        FieldSpec('employee_id', 'Employee ID', f.TEXT, 'employee__employee_id', searchable=True),
        FieldSpec('branch', 'Company code', f.TEXT, 'employee__branch'),
        FieldSpec('department', 'Department', f.TEXT, 'employee__department'),
    )


LEAVE = register(SearchModule(
    key='leave', label='Leave requests', icon='ti-beach', permission=None, queryset=_leave_queryset,
    fields=_employee_fields() + (
        FieldSpec('leave_type', 'Leave type', f.TEXT, 'leave_type', searchable=True),
        FieldSpec('status', 'Status', f.CHOICE, 'status', choices=choices_of(LeaveRequest, 'status')),
        FieldSpec('duration', 'Duration', f.CHOICE, 'duration', choices=choices_of(LeaveRequest, 'duration')),
        FieldSpec('start_date', 'Start date', f.DATE, 'start_date'),
        FieldSpec('end_date', 'End date', f.DATE, 'end_date'),
        FieldSpec('total_days', 'Days', f.NUMBER, 'total_days'),
        FieldSpec('is_lwp', 'Loss of pay', f.BOOLEAN, 'is_lwp'),
        FieldSpec('created_at', 'Applied on', f.DATETIME, 'created_at'),
    ),
    describe=_describe_leave, order_by=('-created_at', '-pk'), default_url='/dashboard/leave',
))

WORK_FROM_HOME = register(SearchModule(
    key='work_from_home', label='Work from home', icon='ti-home-2', permission=None, queryset=_wfh_queryset,
    fields=_employee_fields() + (
        FieldSpec('status', 'Status', f.CHOICE, 'status', choices=choices_of(WorkFromHomeRequest, 'status')),
        FieldSpec('start_date', 'Start date', f.DATE, 'start_date'),
        FieldSpec('end_date', 'End date', f.DATE, 'end_date'),
        FieldSpec('location_label', 'Location', f.TEXT, 'location_label', searchable=True),
        FieldSpec('created_at', 'Requested on', f.DATETIME, 'created_at'),
    ),
    describe=_describe_wfh, order_by=('-created_at', '-pk'), default_url='/dashboard/work-from-home',
))
