"""
Read model for an employee's Work Status: their current project assignment(s) plus the full, never-overwritten history.
Assignments are managed in Project Budgeting and read-only here.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Prefetch

from apps.hrms.models import ProjectAssignment, ProjectAssignmentEvent, ProjectSyncLog
from apps.hrms.services_project_assignments import OPEN_STATUSES

MANAGED_IN = 'Project Budgeting'
MAX_ALLOCATION_PERCENT = Decimal('100')
EVENTS_PER_ASSIGNMENT = 10


def is_current(assignment: ProjectAssignment, today: date) -> bool:
    """On a project right now: still open in Project Budgeting and not past its end date."""
    return assignment.assignment_status in OPEN_STATUSES and (
        assignment.assignment_end_date is None or assignment.assignment_end_date >= today
    )


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _event_dict(event: ProjectAssignmentEvent) -> dict:
    return {
        'event_type': event.event_type, 'source': event.source, 'triggered_by': event.triggered_by,
        'changes': event.changes, 'at': event.created_at.isoformat(),
    }


def assignment_dict(assignment: ProjectAssignment, today: date) -> dict:
    # `events` is prefetched newest-first by history_queryset(); the first one is "what last changed this row".
    events = list(assignment.events.all())[:EVENTS_PER_ASSIGNMENT]
    return {
        'assignment_id':             assignment.assignment_id,
        'project_id':                assignment.project_id,
        'project_code':              assignment.project_code,
        'project_name':              assignment.project_name,
        'project_status':            assignment.project_status,
        'project_status_display':    assignment.project_status_display,
        'milestone_name':            assignment.milestone_name,
        'role':                      assignment.role,
        'allocation_percent':        str(assignment.allocation_percent) if assignment.allocation_percent is not None else None,
        'start_date':                _iso(assignment.assignment_start_date),
        'end_date':                  _iso(assignment.assignment_end_date),
        'is_ongoing':                assignment.assignment_end_date is None and assignment.assignment_status in OPEN_STATUSES,
        'assignment_status':         assignment.assignment_status,
        'assignment_status_display': assignment.assignment_status_display,
        'is_current':                is_current(assignment, today),
        'last_change':               _event_dict(events[0]) if events else None,
        'change_log':                [_event_dict(event) for event in events],
    }


def history_queryset(employee_code: str):
    """Every assignment the employee has ever had, most recent first."""
    events = Prefetch('events', queryset=ProjectAssignmentEvent.objects.order_by('-created_at'))
    return (
        ProjectAssignment.objects.filter(employee_code=employee_code)
        .prefetch_related(events)
        .order_by('-assignment_start_date', '-assignment_id')
    )


def _overlap(first: ProjectAssignment, second: ProjectAssignment) -> bool:
    far_future = date.max
    return (
        first.assignment_start_date <= (second.assignment_end_date or far_future)
        and second.assignment_start_date <= (first.assignment_end_date or far_future)
    )


def find_conflicts(current: list[ProjectAssignment]) -> list[dict]:
    """Flags worth a human look among the CURRENT assignments. Informational only — Project Budgeting owns the data,
    so we report, never block or rewrite."""
    conflicts = []
    allocated = [a.allocation_percent for a in current if a.allocation_percent is not None]
    if sum(allocated, Decimal('0')) > MAX_ALLOCATION_PERCENT:
        conflicts.append({
            'type': 'allocation_over_100',
            'message': f'Allocation across current projects totals {sum(allocated, Decimal("0"))}%, above 100%.',
        })
    for index, first in enumerate(current):
        for second in current[index + 1:]:
            if first.project_id != second.project_id and _overlap(first, second):
                conflicts.append({
                    'type': 'concurrent_projects',
                    'message': f'Working on "{first.project_name}" and "{second.project_name}" at the same time.',
                })
    return conflicts


def last_synced_at() -> str | None:
    """When Project Budgeting data last arrived successfully (push, pull or reconcile)."""
    log = ProjectSyncLog.objects.filter(status__in=(ProjectSyncLog.STATUS_SUCCESS, ProjectSyncLog.STATUS_UNMATCHED)).first()
    return log.created_at.isoformat() if log else None
