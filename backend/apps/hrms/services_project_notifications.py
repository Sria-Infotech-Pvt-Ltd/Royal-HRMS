"""
Notifications for project assignments, and the daily job that sends "ending soon" reminders and completes assignments
whose end date has passed so admins know to extend them or assign a new project.

Recipients: the employee, their reporting manager, and every active admin who can manage employees (employees.edit).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.hrms.models import ProjectAssignment
from apps.hrms.services_project_assignments import STATUS_ACTIVE, complete_finished_assignments

logger = logging.getLogger(__name__)

MODULE = 'system'
TYPE_ASSIGNED = 'project_assigned'
TYPE_ENDING_SOON = 'project_ending_soon'
TYPE_COMPLETED = 'project_completed'


def _fmt(value: date) -> str:
    return value.strftime('%d %b %Y')


def _where(assignment: ProjectAssignment) -> str:
    mode = assignment.get_work_mode_display()
    return f'{mode}, {assignment.work_location}' if assignment.work_location else mode


def _admins():
    from core.access import users_with_permission
    return (User.objects.filter(is_active=True)
            .filter(users_with_permission('employees.edit') | Q(is_superuser=True)).distinct())


def _send(users, title: str, message: str, notification_type: str, reference_id: str) -> None:
    from apps.notifications.signals import _notify
    seen = set()
    for user in users:
        if user and user.pk not in seen:
            seen.add(user.pk)
            _notify(user, title, message, notification_type, MODULE, reference_id)


def _people(assignment: ProjectAssignment, *, include_admins: bool) -> tuple[User | None, list]:
    employee = User.objects.filter(employee_id=assignment.employee_code).select_related('reporting_manager').first()
    recipients = [employee, employee.reporting_manager if employee else None]
    if include_admins:
        recipients += list(_admins())
    return employee, recipients


def notify_assigned(assignment: ProjectAssignment) -> None:
    """Tell the employee (and their manager) about a new assignment."""
    employee, recipients = _people(assignment, include_admins=False)
    name = employee.full_name if employee else assignment.employee_code
    _send(recipients, f'Assigned to {assignment.project_name}',
          f'{name} has been assigned to "{assignment.project_name}" from {_fmt(assignment.assignment_start_date)} '
          f'to {_fmt(assignment.assignment_end_date)}. Work mode: {_where(assignment)}.',
          TYPE_ASSIGNED, assignment.employee_code)


def _notify_ending_soon(assignment: ProjectAssignment, days_left: int) -> None:
    employee, recipients = _people(assignment, include_admins=True)
    name = employee.full_name if employee else assignment.employee_code
    when = 'today' if days_left == 0 else f'in {days_left} day{"s" if days_left != 1 else ""}'
    _send(recipients, f'{assignment.project_name} ends {when}',
          f'{name}\'s assignment to "{assignment.project_name}" ends on {_fmt(assignment.assignment_end_date)}. '
          'Extend it or assign a new project from the employee\'s Work Status.',
          TYPE_ENDING_SOON, assignment.employee_code)


def _notify_completed(assignment: ProjectAssignment) -> None:
    employee, recipients = _people(assignment, include_admins=True)
    name = employee.full_name if employee else assignment.employee_code
    has_next = ProjectAssignment.objects.filter(
        employee_code=assignment.employee_code, assignment_status=STATUS_ACTIVE).exists()
    follow_up = '' if has_next else f' {name} has no other project now; assign a new one or extend this one.'
    _send(recipients, f'{assignment.project_name} has ended',
          f'{name}\'s assignment to "{assignment.project_name}" ended on {_fmt(assignment.assignment_end_date)}.'
          + follow_up,
          TYPE_COMPLETED, assignment.employee_code)


def send_ending_soon_reminders(today: date) -> int:
    """One reminder per assignment per end date, sent once it is within PROJECT_ENDING_SOON_DAYS of ending."""
    horizon = today + timedelta(days=settings.PROJECT_ENDING_SOON_DAYS)
    due = ProjectAssignment.objects.filter(
        assignment_status=STATUS_ACTIVE, assignment_end_date__gte=today, assignment_end_date__lte=horizon,
        ending_soon_notified_on__isnull=True,
    )
    sent = 0
    for assignment in due:
        _notify_ending_soon(assignment, (assignment.assignment_end_date - today).days)
        ProjectAssignment.objects.filter(pk=assignment.pk).update(ending_soon_notified_on=today)
        sent += 1
    return sent


def run_daily_project_job(today: date | None = None) -> dict:
    today = today or timezone.localdate()
    completed = complete_finished_assignments(today)
    for assignment in completed:
        _notify_completed(assignment)
    reminded = send_ending_soon_reminders(today)
    logger.info('Daily project job: %s completed, %s ending-soon reminders.', len(completed), reminded)
    return {'completed': len(completed), 'reminded': reminded}
