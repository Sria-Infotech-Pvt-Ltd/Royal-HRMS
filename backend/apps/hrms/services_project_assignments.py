"""
Admin-managed project assignments: assign, edit, extend and end, plus the daily job that completes assignments whose
end date has passed.

An assignment is "active" until the day after its end date, when it becomes "completed". Extending a completed
assignment re-opens it. Every change is recorded as a ProjectAssignmentEvent; nothing is ever deleted.
"""
from __future__ import annotations

import logging
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.hrms.models import ProjectAssignment, ProjectAssignmentEvent

logger = logging.getLogger(__name__)

STATUS_ACTIVE = ProjectAssignment.STATUS_ACTIVE
STATUS_COMPLETED = ProjectAssignment.STATUS_COMPLETED
STATUS_DISPLAY = dict(ProjectAssignment.STATUS_CHOICES)
SYSTEM_ACTOR = 'daily_project_job'
_ID_ATTEMPTS = 3


class AssignmentError(Exception):
    """A request that breaks a business rule; the message is shown to the admin."""


def _actor_name(actor) -> str:
    return (getattr(actor, 'full_name', '') or getattr(actor, 'email', '') or '')[:100]


def _iso(value):
    return value.isoformat() if isinstance(value, date) else value


def _status_for(end_date: date, today: date) -> str:
    return STATUS_COMPLETED if end_date < today else STATUS_ACTIVE


def _set_status(assignment: ProjectAssignment, today: date) -> None:
    assignment.assignment_status = _status_for(assignment.assignment_end_date, today)
    assignment.assignment_status_display = STATUS_DISPLAY[assignment.assignment_status]


def _record(assignment, event_type, changes, actor, reason='', source=ProjectAssignmentEvent.SOURCE_MANUAL) -> None:
    ProjectAssignmentEvent.objects.create(
        assignment=assignment, event_type=event_type, changes=changes, source=source,
        triggered_by=_actor_name(actor) if actor else SYSTEM_ACTOR, reason=reason,
    )


def _timesheet_max(field: str) -> int:
    """Highest id an existing timesheet line already uses, so new ids never collide with old lines."""
    from apps.attendance.models_timesheet import TimesheetLine
    return TimesheetLine.objects.aggregate(top=Max(field))['top'] or 0


def _next_assignment_id() -> int:
    held = ProjectAssignment.objects.aggregate(top=Max('assignment_id'))['top'] or 0
    return max(held, _timesheet_max('assignment_id')) + 1


def project_id_for(name: str) -> int:
    """The same project name (ignoring case) always maps to the same project_id, so reports group correctly."""
    from apps.attendance.models_timesheet import TimesheetLine
    known = ProjectAssignment.objects.filter(project_name__iexact=name).values_list('project_id', flat=True).first()
    if known is None:
        known = (TimesheetLine.objects.filter(project_name__iexact=name, project_id__isnull=False)
                 .values_list('project_id', flat=True).first())
    if known is not None:
        return known
    held = ProjectAssignment.objects.aggregate(top=Max('project_id'))['top'] or 0
    return max(held, _timesheet_max('project_id')) + 1


def _check_no_duplicate(employee_code, name, start, end, exclude_pk=None) -> None:
    clash = ProjectAssignment.objects.filter(
        employee_code=employee_code, project_name__iexact=name,
        assignment_start_date__lte=end, assignment_end_date__gte=start,
    )
    if exclude_pk:
        clash = clash.exclude(pk=exclude_pk)
    if clash.exists():
        raise AssignmentError(f'This employee is already assigned to "{name}" for part of these dates.')


def assign_project(employee, data: dict, actor) -> ProjectAssignment:
    """Create a new assignment for `employee` from validated AssignProjectSerializer data."""
    name, start, end = data['project_name'], data['start_date'], data['end_date']
    _check_no_duplicate(employee.employee_id, name, start, end)
    for attempt in range(_ID_ATTEMPTS):
        try:
            with transaction.atomic():
                assignment = ProjectAssignment(
                    assignment_id=_next_assignment_id(), employee_code=employee.employee_id,
                    project_id=project_id_for(name), project_name=name,
                    assignment_start_date=start, assignment_end_date=end,
                    role=data.get('role', ''), notes=data.get('notes', ''), assigned_by=actor,
                    work_mode=data['work_mode'], work_location=data.get('work_location', ''),
                )
                _set_status(assignment, timezone.localdate())
                assignment.save()
                _record(assignment, ProjectAssignmentEvent.EVENT_CREATED, {
                    'project_name': [None, name], 'assignment_start_date': [None, _iso(start)],
                    'assignment_end_date': [None, _iso(end)], 'role': [None, assignment.role],
                    'work_mode': [None, assignment.work_mode], 'work_location': [None, assignment.work_location],
                }, actor)
                return assignment
        except IntegrityError:
            # Two admins assigned at the same moment and got the same running number; take the next one.
            if attempt == _ID_ATTEMPTS - 1:
                raise
    raise AssertionError('unreachable')


_EDIT_FIELDS = {
    'project_name': 'project_name', 'start_date': 'assignment_start_date', 'end_date': 'assignment_end_date',
    'role': 'role', 'notes': 'notes', 'work_mode': 'work_mode', 'work_location': 'work_location',
}


@transaction.atomic
def edit_assignment(assignment: ProjectAssignment, data: dict, actor) -> ProjectAssignment:
    if assignment.assignment_status != STATUS_ACTIVE:
        raise AssignmentError('A completed project cannot be edited. Extend it instead.')
    new_values = {_EDIT_FIELDS[key]: value for key, value in data.items() if key in _EDIT_FIELDS}
    _check_no_duplicate(
        assignment.employee_code, new_values.get('project_name', assignment.project_name),
        new_values.get('assignment_start_date', assignment.assignment_start_date),
        new_values.get('assignment_end_date', assignment.assignment_end_date), exclude_pk=assignment.pk,
    )
    diff = {}
    for field, new in new_values.items():
        old = getattr(assignment, field)
        if old != new:
            diff[field] = [_iso(old), _iso(new)]
            setattr(assignment, field, new)
    if not diff:
        return assignment
    if 'project_name' in diff:
        assignment.project_id = project_id_for(assignment.project_name)
    if 'assignment_end_date' in diff:
        assignment.ending_soon_notified_on = None
    _set_status(assignment, timezone.localdate())
    assignment.save()
    _record(assignment, ProjectAssignmentEvent.EVENT_UPDATED, diff, actor)
    return assignment


@transaction.atomic
def extend_assignment(assignment: ProjectAssignment, end_date: date, reason: str, actor) -> ProjectAssignment:
    """Move the end date later. Re-opens a completed assignment when the new end date is today or later."""
    _check_no_duplicate(assignment.employee_code, assignment.project_name, assignment.assignment_start_date,
                        end_date, exclude_pk=assignment.pk)
    old_end, old_status = assignment.assignment_end_date, assignment.assignment_status
    assignment.assignment_end_date = end_date
    assignment.ending_soon_notified_on = None
    _set_status(assignment, timezone.localdate())
    assignment.save()
    diff = {'assignment_end_date': [_iso(old_end), _iso(end_date)]}
    if old_status != assignment.assignment_status:
        diff['assignment_status'] = [old_status, assignment.assignment_status]
    _record(assignment, ProjectAssignmentEvent.EVENT_EXTENDED, diff, actor, reason)
    return assignment


@transaction.atomic
def end_assignment(assignment: ProjectAssignment, end_date: date | None, reason: str, actor) -> ProjectAssignment:
    """Finish an assignment early. Defaults to today (or the start date, for one that hasn't started yet)."""
    if assignment.assignment_status != STATUS_ACTIVE:
        raise AssignmentError('This project has already ended.')
    today = timezone.localdate()
    end_date = end_date or max(today, assignment.assignment_start_date)
    if end_date > assignment.assignment_end_date:
        raise AssignmentError('To move the end date later, use Extend.')
    old_end, old_status = assignment.assignment_end_date, assignment.assignment_status
    assignment.assignment_end_date = end_date
    # Ended today means done today, so it is completed straight away rather than tomorrow.
    assignment.assignment_status = STATUS_COMPLETED if end_date <= today else STATUS_ACTIVE
    assignment.assignment_status_display = STATUS_DISPLAY[assignment.assignment_status]
    assignment.save()
    diff = {'assignment_end_date': [_iso(old_end), _iso(end_date)]}
    if old_status != assignment.assignment_status:
        diff['assignment_status'] = [old_status, assignment.assignment_status]
    _record(assignment, ProjectAssignmentEvent.EVENT_ENDED, diff, actor, reason)
    return assignment


def complete_finished_assignments(today: date) -> list[ProjectAssignment]:
    """Mark every active assignment whose end date has passed as completed. Returns the ones it changed."""
    finished = list(ProjectAssignment.objects.filter(assignment_status=STATUS_ACTIVE, assignment_end_date__lt=today))
    for assignment in finished:
        with transaction.atomic():
            assignment.assignment_status = STATUS_COMPLETED
            assignment.assignment_status_display = STATUS_DISPLAY[STATUS_COMPLETED]
            assignment.save(update_fields=['assignment_status', 'assignment_status_display', 'updated_at'])
            _record(assignment, ProjectAssignmentEvent.EVENT_COMPLETED,
                    {'assignment_status': [STATUS_ACTIVE, STATUS_COMPLETED]}, None,
                    source=ProjectAssignmentEvent.SOURCE_SYSTEM)
    return finished
