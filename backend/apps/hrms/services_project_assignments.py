"""
Applying an employee's project assignments from Project Budgeting to our ProjectAssignment history.

Every path in (push webhook, per-employee pull, scheduled reconcile) hands this module the employee's COMPLETE current
list. Nothing is ever deleted: rows are upserted by assignment_id, rows that vanished from the list are marked removed
and closed, and every real change is recorded as a ProjectAssignmentEvent. Re-applying an identical list changes
nothing and records nothing, so retries and duplicate syncs are harmless.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.hrms.models import ProjectAssignment, ProjectAssignmentEvent
from apps.hrms.models_project_assignment import END_DATE_SOURCE_AUTO_CLOSED, END_DATE_SOURCE_BUDGETING

logger = logging.getLogger(__name__)

STATUS_REMOVED = 'removed'
STATUS_COMPLETED = 'completed'
OPEN_STATUSES = ('active', 'on_hold')

_TRACKED_FIELDS = (
    'project_id', 'project_code', 'project_name', 'project_status', 'project_status_display',
    'project_start_date', 'project_end_date', 'assignment_start_date', 'assignment_end_date',
    'assignment_status', 'assignment_status_display', 'milestone_name', 'role', 'allocation_percent',
)
# Project Budgeting may send null for these; we store blank.
_BLANK_WHEN_NULL = ('project_code', 'milestone_name', 'role')


def _jsonable(value):
    if isinstance(value, (date, Decimal)):
        return value.isoformat() if isinstance(value, date) else str(value)
    return value


def _normalise(row: dict) -> dict:
    values = {field: row.get(field) for field in _TRACKED_FIELDS}
    for field in _BLANK_WHEN_NULL:
        values[field] = values[field] or ''
    for field in ('project_status', 'project_status_display', 'assignment_status', 'assignment_status_display'):
        values[field] = values[field] or ''
    return values


def _is_stale(assignment: ProjectAssignment, row: dict) -> bool:
    """An older copy of a row (retry/out-of-order delivery) must not overwrite a newer one we already hold."""
    incoming, stored = row.get('updated_at'), assignment.source_updated_at
    return bool(incoming and stored and incoming < stored)


def _record(assignment, event_type, changes, source, triggered_by) -> None:
    ProjectAssignmentEvent.objects.create(
        assignment=assignment, event_type=event_type, changes=changes, source=source, triggered_by=triggered_by,
    )


def _protect_auto_close(assignment: ProjectAssignment, values: dict) -> None:
    """A row we auto-closed still looks open-ended in Project Budgeting, so every later sync would re-open it. Keep our
    close until Project Budgeting itself sends an end date."""
    if assignment.end_date_source == END_DATE_SOURCE_AUTO_CLOSED and values['assignment_end_date'] is None:
        values['assignment_end_date'] = assignment.assignment_end_date
        values['assignment_status'] = assignment.assignment_status
        values['assignment_status_display'] = assignment.assignment_status_display


def _event_type_for(assignment: ProjectAssignment, diff: dict) -> str:
    new_status = diff.get('assignment_status', [assignment.assignment_status, assignment.assignment_status])[1]
    if assignment.assignment_status == STATUS_REMOVED and new_status != STATUS_REMOVED:
        return ProjectAssignmentEvent.EVENT_RESTORED
    end_change = diff.get('assignment_end_date')
    if end_change and end_change[0] is None:
        return ProjectAssignmentEvent.EVENT_ENDED
    return ProjectAssignmentEvent.EVENT_UPDATED


def _update_existing(assignment, row, values, employee_code, now, source, triggered_by) -> bool:
    if _is_stale(assignment, row):
        return False
    _protect_auto_close(assignment, values)
    diff = {}
    for field, new in values.items():
        old = getattr(assignment, field)
        if old != new:
            diff[field] = [_jsonable(old), _jsonable(new)]
    if assignment.employee_code != employee_code:
        diff['employee_code'] = [assignment.employee_code, employee_code]
    if not diff:
        return False
    event_type = _event_type_for(assignment, diff)
    for field, new in values.items():
        setattr(assignment, field, new)
    assignment.employee_code = employee_code
    if values['assignment_end_date'] is not None and assignment.end_date_source == END_DATE_SOURCE_AUTO_CLOSED \
            and 'assignment_end_date' in diff:
        assignment.end_date_source = END_DATE_SOURCE_BUDGETING
    assignment.source_updated_at = row.get('updated_at') or assignment.source_updated_at
    assignment.last_synced_at = now
    assignment.save()
    _record(assignment, event_type, diff, source, triggered_by)
    return True


def _mark_removed(assignment: ProjectAssignment, today: date, now, source, triggered_by) -> None:
    """The row vanished from Project Budgeting (resource removed, milestone or project deleted). Keep it, closed."""
    diff = {'assignment_status': [assignment.assignment_status, STATUS_REMOVED]}
    assignment.assignment_status = STATUS_REMOVED
    assignment.assignment_status_display = 'Removed'
    end = assignment.assignment_end_date
    if end is None or end > today:
        diff['assignment_end_date'] = [_jsonable(end), today.isoformat()]
        assignment.assignment_end_date = today
        assignment.end_date_source = END_DATE_SOURCE_BUDGETING
    assignment.last_synced_at = now
    assignment.save()
    _record(assignment, ProjectAssignmentEvent.EVENT_REMOVED, diff, source, triggered_by)


def auto_close_previous(new: ProjectAssignment, created_now: set, source: str, triggered_by: str) -> int:
    """When an employee moves to a new project, end their still-open assignments on OTHER projects the day before the
    new one starts. Skipped when allocation % is recorded on either side (they may legitimately run concurrently), and
    switched off entirely by PROJECT_ASSIGNMENT_AUTO_CLOSE_OPEN_ENDED=False."""
    if not getattr(settings, 'PROJECT_ASSIGNMENT_AUTO_CLOSE_OPEN_ENDED', True) or new.allocation_percent is not None:
        return 0
    previous = (
        ProjectAssignment.objects
        .filter(
            employee_code=new.employee_code, assignment_end_date__isnull=True,
            assignment_status__in=OPEN_STATUSES, assignment_start_date__lt=new.assignment_start_date,
            allocation_percent__isnull=True,
        )
        .exclude(project_id=new.project_id)
        .exclude(pk__in=created_now)
    )
    closed = 0
    for old in previous:
        end = new.assignment_start_date - timedelta(days=1)
        diff = {
            'assignment_end_date': [None, end.isoformat()],
            'assignment_status': [old.assignment_status, STATUS_COMPLETED],
        }
        old.assignment_end_date = end
        old.assignment_status = STATUS_COMPLETED
        old.assignment_status_display = 'Completed'
        old.end_date_source = END_DATE_SOURCE_AUTO_CLOSED
        old.save()
        _record(old, ProjectAssignmentEvent.EVENT_AUTO_CLOSED, diff, source, triggered_by)
        closed += 1
    return closed


@transaction.atomic
def apply_employee_snapshot(employee_code: str, rows: list[dict], *, source: str, triggered_by: str) -> dict:
    """Make our history for `employee_code` reflect `rows` (already validated), keeping everything we had.
    Returns counts: saved (rows in the list), changed (rows created/updated), removed (rows closed because they vanished),
    auto_closed."""
    now = timezone.now()
    today = timezone.localdate()
    incoming_ids = [row['assignment_id'] for row in rows]
    held = {
        a.assignment_id: a
        for a in ProjectAssignment.objects.select_for_update().filter(employee_code=employee_code)
    }
    had_history = bool(held)
    for assignment in ProjectAssignment.objects.select_for_update().filter(assignment_id__in=incoming_ids):
        held.setdefault(assignment.assignment_id, assignment)

    changed, created_now = 0, []
    for row in rows:
        values = _normalise(row)
        assignment = held.get(row['assignment_id'])
        if assignment is None:
            assignment = ProjectAssignment.objects.create(
                assignment_id=row['assignment_id'], employee_code=employee_code,
                source_updated_at=row.get('updated_at'), last_synced_at=now, **values,
            )
            _record(assignment, ProjectAssignmentEvent.EVENT_CREATED,
                    {field: [None, _jsonable(value)] for field, value in values.items()}, source, triggered_by)
            created_now.append(assignment)
            changed += 1
        else:
            if _update_existing(assignment, row, values, employee_code, now, source, triggered_by):
                changed += 1
            else:
                ProjectAssignment.objects.filter(pk=assignment.pk).update(last_synced_at=now)

    removed = 0
    vanished = (
        ProjectAssignment.objects
        .filter(employee_code=employee_code)
        .exclude(assignment_id__in=incoming_ids)
        # Already-completed rows naturally drop off a "current projects" list; they aren't removals.
        .exclude(assignment_status__in=(STATUS_REMOVED, STATUS_COMPLETED))
    )
    for assignment in vanished:
        _mark_removed(assignment, today, now, source, triggered_by)
        removed += 1

    auto_closed = 0
    if had_history:
        created_ids = {a.pk for a in created_now}
        for assignment in created_now:
            auto_closed += auto_close_previous(assignment, created_ids, source, triggered_by)
    return {'saved': len(rows), 'changed': changed, 'removed': removed, 'auto_closed': auto_closed}
