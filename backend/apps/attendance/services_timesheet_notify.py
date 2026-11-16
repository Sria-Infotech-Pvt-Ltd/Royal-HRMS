"""Timesheet notifications: the in-app notice and the email for submit / send back / approve (and unlock), through the shared
notification services, so every person's notification settings are respected (a switched-off category sends neither the notice
nor the email). They run AFTER the transaction commits and can never raise: a failed notice must not undo a decision.
"""
from __future__ import annotations

import datetime
import logging

from django.db import transaction

from apps.attendance.models_timesheet import Timesheet
from apps.attendance.services_timesheet_common import hours_text

logger = logging.getLogger(__name__)

MODULE = 'timesheet'
TYPE_SUBMITTED = 'timesheet_submitted'
TYPE_RETURNED = 'timesheet_returned'
TYPE_APPROVED = 'timesheet_approved'
TYPE_REMINDER = 'timesheet_reminder'
# Notification-setting categories: what the approver is asked to act on vs. what happened to the employee's own sheet.
CATEGORY_APPROVER = 'approval'
CATEGORY_EMPLOYEE = 'attendance'


def week_label(week_start: datetime.date) -> str:
    end = week_start + datetime.timedelta(days=6)
    return f'{week_start.day} {week_start.strftime("%b")} – {end.day} {end.strftime("%b %Y")}'


def _name(user) -> str:
    return (user.full_name or user.email) if user else 'someone'


def _send(recipient, *, title: str, message: str, notice_type: str, sheet: Timesheet, category: str, actor, email_template: str, email_context: dict) -> None:
    """One in-app notice plus one email to `recipient`. Each part is skipped on its own if the person has that category off."""
    from apps.notifications.signals import _category_enabled, _notify, _send_lifecycle_email

    if recipient is None:
        return
    # "<week start>:<sheet id>": the bell uses the week to open the right sheet (see frontend/lib/notificationRoutes.ts).
    _notify(recipient, title, message, notice_type, MODULE, f'{sheet.week_start.isoformat()}:{sheet.pk}', actor, category=category)
    if _category_enabled(recipient, category):
        _send_lifecycle_email(recipient, email_template, email_context)


def _after_commit(action, *args) -> None:
    """Run `action(*args)` once the surrounding transaction has committed; swallow and log any failure."""
    def run():
        try:
            action(*args)
        except Exception:
            logger.exception('Timesheet notification failed (%s); the timesheet change itself was saved.', getattr(action, '__name__', 'action'))

    transaction.on_commit(run)


def _submitted(sheet_id, is_resubmission: bool) -> None:
    sheet = Timesheet.objects.select_related('employee', 'approver').get(pk=sheet_id)
    employee, week = sheet.employee, week_label(sheet.week_start)
    late_note = ' It was submitted after the Friday due date.' if sheet.is_late else ''
    verb = 'resubmitted' if is_resubmission else 'submitted'
    _send(
        sheet.approver, title=f'Timesheet {verb} for approval',
        message=f'{_name(employee)} {verb} their timesheet for {week} ({hours_text(sheet.total_hours)} hours).',
        notice_type=TYPE_SUBMITTED, sheet=sheet, category=CATEGORY_APPROVER, actor=employee, email_template='timesheet_submitted',
        email_context={
            'approver_name': _name(sheet.approver), 'employee_name': _name(employee), 'week': week,
            'total_hours': hours_text(sheet.total_hours), 'billable_hours': hours_text(sheet.billable_hours), 'late_note': late_note,
        },
    )


def _returned(sheet_id, reason: str, is_reopen: bool) -> None:
    sheet = Timesheet.objects.select_related('employee', 'decided_by').get(pk=sheet_id)
    week = week_label(sheet.week_start)
    what = 'was reopened by HR for correction' if is_reopen else 'was sent back for changes'
    _send(
        sheet.employee, title='Timesheet reopened' if is_reopen else 'Timesheet sent back',
        message=f'Your timesheet for {week} {what}. Reason: {reason}',
        notice_type=TYPE_RETURNED, sheet=sheet, category=CATEGORY_EMPLOYEE, actor=sheet.decided_by, email_template='timesheet_returned',
        email_context={'employee_name': _name(sheet.employee), 'week': week, 'decided_by': _name(sheet.decided_by), 'reason': reason},
    )


def _approved(sheet_id) -> None:
    sheet = Timesheet.objects.select_related('employee', 'decided_by').get(pk=sheet_id)
    week = week_label(sheet.week_start)
    _send(
        sheet.employee, title='Timesheet approved', message=f'Your timesheet for {week} was approved by {_name(sheet.decided_by)}.',
        notice_type=TYPE_APPROVED, sheet=sheet, category=CATEGORY_EMPLOYEE, actor=sheet.decided_by, email_template='timesheet_approved',
        email_context={
            'employee_name': _name(sheet.employee), 'week': week, 'decided_by': _name(sheet.decided_by),
            'total_hours': hours_text(sheet.total_hours), 'billable_hours': hours_text(sheet.billable_hours),
        },
    )


def notify_submitted(sheet: Timesheet, *, is_resubmission: bool) -> None:
    _after_commit(_submitted, sheet.pk, is_resubmission)


def notify_returned(sheet: Timesheet, reason: str, *, is_reopen: bool = False) -> None:
    _after_commit(_returned, sheet.pk, reason, is_reopen)


def notify_approved(sheet: Timesheet) -> None:
    _after_commit(_approved, sheet.pk)

