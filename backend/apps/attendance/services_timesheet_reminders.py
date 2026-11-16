"""Timesheet reminders, run by Celery beat: employees on Friday (their week's sheet is still not submitted) and approvers on Monday
(sheets are waiting for them). Each person gets at most one reminder per week (employees) or per day (approvers): the reminder's own
Notification row, keyed by week or date, is the record, so a repeated or retried run, or two workers, never sends it twice.
In-app only; the person's notification settings are respected by the shared notifier.
"""
from __future__ import annotations

import datetime
import logging

from django.db.models import Count, Exists, Min, OuterRef, QuerySet

from apps.accounts.models import User
from apps.accounts.services_lifecycle_status import ACCOUNT_ACTIVE, account_status_q, attendance_eligible_q
from apps.attendance.models_timesheet import STATUS_APPROVED, STATUS_SUBMITTED, Timesheet
from apps.attendance.services_timesheet_common import due_date, monday_of, today
from apps.attendance.services_timesheet_notify import CATEGORY_APPROVER, CATEGORY_EMPLOYEE, MODULE, TYPE_REMINDER, week_label
from apps.hrms.models import STATUS_APPROVED as LEAVE_APPROVED
from apps.hrms.models import LeaveRequest
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def employee_key(week_start: datetime.date) -> str:
    return f'employee-week:{week_start.isoformat()}'


def approver_key(day: datetime.date) -> str:
    return f'approver-day:{day.isoformat()}'


def employees_to_remind(week_start: datetime.date, as_of: datetime.date) -> QuerySet:
    """Active, activated employees expected at work, whose sheet for this week is not yet submitted or approved, and who are not on
    approved leave for the whole working week (Monday to the due Friday)."""
    handed_in = Timesheet.objects.filter(employee=OuterRef('pk'), week_start=week_start, status__in=(STATUS_SUBMITTED, STATUS_APPROVED))
    away_all_week = LeaveRequest.objects.filter(
        employee=OuterRef('pk'), status=LEAVE_APPROVED, start_date__lte=week_start, end_date__gte=due_date(week_start),
    )
    return (
        User.objects.filter(attendance_eligible_q(as_of), account_status_q(ACCOUNT_ACTIVE))
        .exclude(Exists(handed_in)).exclude(Exists(away_all_week))
    )


def _already_reminded(user_ids, key: str) -> set:
    return set(Notification.objects.filter(
        user_id__in=user_ids, notification_type=TYPE_REMINDER, module=MODULE, reference_id=key,
    ).values_list('user_id', flat=True))


def send_employee_reminders(week_start: datetime.date | None = None, as_of: datetime.date | None = None) -> dict:
    """Remind each employee whose timesheet for the week is outstanding. Safe to run again: nobody is reminded twice for a week."""
    from apps.notifications.signals import _notify

    day = as_of or today()
    week = week_start or monday_of(day)
    key = employee_key(week)
    people = list(employees_to_remind(week, day))
    skip = _already_reminded([person.pk for person in people], key)
    sent = 0
    for person in people:
        if person.pk in skip:
            continue
        _notify(
            person, 'Timesheet due', f'Your timesheet for {week_label(week)} is due {due_date(week).strftime("%a %d %b")} and has not been '
            'submitted yet. Open Attendance and fill in your hours per project.', TYPE_REMINDER, MODULE, key, None, category=CATEGORY_EMPLOYEE,
        )
        sent += 1
    result = {'week': week.isoformat(), 'eligible': len(people), 'already_reminded': len(skip), 'attempted': sent}
    logger.info('Timesheet employee reminders: %s', result)
    return result


def send_approver_reminders(as_of: datetime.date | None = None) -> dict:
    """Tell each approver how many submitted timesheets are waiting for them. At most one reminder per approver per day."""
    from apps.notifications.signals import _notify

    day = as_of or today()
    key = approver_key(day)
    waiting = list(
        Timesheet.objects.filter(status=STATUS_SUBMITTED, approver__is_active=True)
        .values('approver').annotate(total=Count('id'), oldest=Min('week_start'))
    )
    skip = _already_reminded([row['approver'] for row in waiting], key)
    approvers = {user.pk: user for user in User.objects.filter(pk__in=[row['approver'] for row in waiting])}
    sent = 0
    for row in waiting:
        if row['approver'] in skip or row['approver'] not in approvers:
            continue
        count = row['total']
        _notify(
            approvers[row['approver']], 'Timesheets waiting for approval',
            f'You have {count} timesheet{"" if count == 1 else "s"} waiting for approval (oldest: week of {row["oldest"].strftime("%d %b")}). '
            'Open Approvals and choose Timesheets.', TYPE_REMINDER, MODULE, key, None, category=CATEGORY_APPROVER,
        )
        sent += 1
    result = {'date': day.isoformat(), 'approvers': len(waiting), 'already_reminded': len(skip), 'attempted': sent}
    logger.info('Timesheet approver reminders: %s', result)
    return result
