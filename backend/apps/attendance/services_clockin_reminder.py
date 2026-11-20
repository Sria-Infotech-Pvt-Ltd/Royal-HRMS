"""
Clock-in reminder: an email to each person who is expected at work today and has not punched in yet.

The mirror of the missing clock-out reminder (services_unpunch.py). A background job runs every few minutes (tasks.py); once the
reminder time has passed (10:00 by default, a field on the default punch policy) it emails everyone who still has no punch today.

Skipped, so the email only reaches people who really should have punched in:
  - anyone with a punch today (an HR-entered punch counts);
  - anyone whose attendance for today HR or an admin has already marked (a present / late / half day / incomplete / on leave / weekly
    off / holiday record, with or without times): the day is accounted for, so "you have not clocked in" would be wrong. Marking someone
    Absent does not stop the reminder;
  - anyone on approved leave today (a half day in the afternoon still has to come in the morning, so that one is reminded);
  - weekly offs and holidays;
  - people who have not joined, have left, or are past an approved last working day, and accounts with no employee id.
Each person is emailed at most once a day (ClockInReminder). Nothing is sent after the shift has ended: the clock-out reminder and the
end-of-day processing take over then.
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.date_utils import format_date_display

logger = logging.getLogger(__name__)

REMINDER_TEMPLATE = 'attendance_missing_clockin'
DEFAULT_REMINDER_TIME = time(10, 0)
DEFAULT_SHIFT_END = time(18, 0)


def _marked_today_statuses() -> tuple[str, ...]:
    """Statuses that mean the day is already accounted for. Absent is left out: it says they did not come, not that they are covered."""
    from apps.attendance.models import AttendanceRecord
    return (
        AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_INCOMPLETE,
        AttendanceRecord.STATUS_ON_LEAVE, AttendanceRecord.STATUS_WEEKLY_OFF, AttendanceRecord.STATUS_HOLIDAY,
    )


def reminder_settings() -> tuple[bool, time]:
    """(enabled, time of day) from the default active punch policy; the shipped defaults (on, 10:00) when no policy exists."""
    from apps.attendance.models import PunchRulesPolicy
    policy = PunchRulesPolicy.objects.filter(is_default=True, is_active=True).first()
    if policy is None:
        return True, DEFAULT_REMINDER_TIME
    return policy.clock_in_reminder_enabled, policy.clock_in_reminder_time or DEFAULT_REMINDER_TIME


def _shift_end() -> time:
    from apps.attendance.services_attendance import _get_settings
    cfg = _get_settings()
    working_hours = getattr(cfg, 'working_hours', None) if cfg else None
    return getattr(working_hours, 'shift_end', None) or DEFAULT_SHIFT_END


def send_clock_in_reminders(now: Optional[datetime] = None) -> dict:
    """Email every expected, not-yet-punched-in employee once today. Safe to run every few minutes."""
    from apps.accounts.models import User
    from apps.accounts.services_lifecycle_status import attendance_eligible_q
    from apps.attendance.models import AttendancePunch, AttendanceRecord, ClockInReminder
    from apps.attendance.services_attendance import AttendanceProcessorService
    from apps.hrms.models import DURATION_AFTERNOON, REQ_APPROVED, LeaveRequest

    local_now = timezone.localtime(now or timezone.now())
    today = local_now.date()

    enabled, remind_at = reminder_settings()
    if not enabled:
        return {'sent': 0, 'reason': 'disabled'}
    if local_now.time() < remind_at:
        return {'sent': 0, 'reason': 'too_early'}
    if local_now.time() >= _shift_end():
        return {'sent': 0, 'reason': 'shift_over'}

    employees = list(User.objects.filter(attendance_eligible_q(as_of=today)).exclude(employee_id=''))
    ids = [employee.pk for employee in employees]
    punched = set(AttendancePunch.objects.filter(employee_id__in=ids, punched_at__date=today).values_list('employee_id', flat=True))
    # HR / an admin may have marked today without any punch or times; the dashboard's punch button can't know that, this can.
    marked = set(
        AttendanceRecord.objects.filter(employee_id__in=ids, date=today, status__in=_marked_today_statuses())
        .values_list('employee_id', flat=True)
    )
    on_leave = set(
        LeaveRequest.objects.filter(employee_id__in=ids, status=REQ_APPROVED, start_date__lte=today, end_date__gte=today)
        .exclude(duration=DURATION_AFTERNOON).values_list('employee_id', flat=True)
    )
    already = set(ClockInReminder.objects.filter(employee_id__in=ids, date=today).values_list('employee_id', flat=True))

    sent = 0
    for employee in employees:
        if employee.pk in punched or employee.pk in marked or employee.pk in on_leave or employee.pk in already or not employee.email:
            continue
        if AttendanceProcessorService._is_holiday(today, employee.branch or ''):
            continue
        if AttendanceProcessorService._is_weekly_off(employee, today):
            continue
        if _remind(employee, today):
            sent += 1
    logger.info('Clock-in reminders for %s: sent=%d', today, sent)
    return {'sent': sent, 'reason': 'ok'}


def _remind(employee, today) -> bool:
    """Record that the reminder goes out today, then email it. False when another run already took this person."""
    from apps.attendance.models import ClockInReminder
    try:
        with transaction.atomic():
            ClockInReminder.objects.create(employee=employee, date=today)
    except IntegrityError:
        return False
    # One attempt a day, like the clock-out reminder: a failed send is written to the Email Log (with its Resend button) and logged here.
    try:
        from apps.accounts.models import Company
        from apps.accounts.utils import send_template_email
        company = Company.objects.first()
        send_template_email(
            recipient_email=employee.email,
            template_name=REMINDER_TEMPLATE,
            context={
                'employee_name': getattr(employee, 'full_name', None) or employee.email,
                'date_display':  f"{today.strftime('%A')}, {format_date_display(today)}",
                'company_name':  company.company_name if company else '',
            },
            module='attendance',
        )
        return True
    except Exception as exc:
        logger.error('Clock-in reminder email failed for employee=%s date=%s: %s', employee.pk, today, exc)
        return False
