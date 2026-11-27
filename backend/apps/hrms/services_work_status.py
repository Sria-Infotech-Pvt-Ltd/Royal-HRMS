"""
Read model for an employee's Work Status: their current project assignment(s) plus the full, never-overwritten history.
Admins manage assignments here (see services_project_assignments.py).
"""
from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db.models import Prefetch

from apps.hrms.models import ProjectAssignment, ProjectAssignmentEvent
from apps.hrms.services_project_assignments import STATUS_ACTIVE

EVENTS_PER_ASSIGNMENT = 10


def is_current(assignment: ProjectAssignment, today: date) -> bool:
    """Active and not past its end date (includes projects that start later)."""
    return assignment.assignment_status == STATUS_ACTIVE and assignment.assignment_end_date >= today


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _event_dict(event: ProjectAssignmentEvent) -> dict:
    return {
        'event_type': event.event_type, 'source': event.source, 'triggered_by': event.triggered_by,
        'reason': event.reason, 'changes': event.changes, 'at': event.created_at.isoformat(),
    }


def assignment_dict(assignment: ProjectAssignment, today: date) -> dict:
    # `events` is prefetched newest-first by history_queryset(); the first one is "what last changed this row".
    events = list(assignment.events.all())[:EVENTS_PER_ASSIGNMENT]
    days_left = (assignment.assignment_end_date - today).days
    current = is_current(assignment, today)
    return {
        'assignment_id':             assignment.assignment_id,
        'project_id':                assignment.project_id,
        'project_code':              assignment.project_code,
        'project_name':              assignment.project_name,
        'role':                      assignment.role,
        'work_mode':                 assignment.work_mode,
        'work_mode_display':         assignment.get_work_mode_display(),
        'work_location':             assignment.work_location,
        'notes':                     assignment.notes,
        'start_date':                _iso(assignment.assignment_start_date),
        'end_date':                  _iso(assignment.assignment_end_date),
        'assignment_status':         assignment.assignment_status,
        'assignment_status_display': assignment.assignment_status_display,
        'is_current':                current,
        'is_upcoming':               current and assignment.assignment_start_date > today,
        'days_left':                 days_left if current else None,
        'is_ending_soon':            current and days_left <= settings.PROJECT_ENDING_SOON_DAYS,
        'last_change':               _event_dict(events[0]) if events else None,
        'change_log':                [_event_dict(event) for event in events],
    }


def employee_codes_on_projects(today: date | None = None):
    """Employee codes with at least one current project (a subquery, for the directory's "No project" filter)."""
    from django.utils import timezone
    today = today or timezone.localdate()
    return ProjectAssignment.objects.filter(
        assignment_status=STATUS_ACTIVE, assignment_end_date__gte=today,
    ).values('employee_code')


def history_queryset(employee_code: str):
    """Every assignment the employee has ever had, most recent first."""
    events = Prefetch('events', queryset=ProjectAssignmentEvent.objects.order_by('-created_at'))
    return (
        ProjectAssignment.objects.filter(employee_code=employee_code)
        .prefetch_related(events)
        .order_by('-assignment_start_date', '-assignment_id')
    )
