"""
Absence Alert service.

Reads the AttendanceAbsenceAlert config (embedded in AttendanceSettings) and
creates notifications for managers / HR when an employee accumulates N+
consecutive absent working days without an approved leave.

Called daily by the `check_absence_alerts` Celery task.

Exclusions from the streak:
  - Configured weekly-off days (skipped, do not break streak)
  - Company holidays recorded in AttendanceRecord (skipped, do not break streak)
  - Days covered by an approved LeaveRequest (break the streak)

De-duplication: if a notification with title='Absence Alert' and
reference_id=<employee.id> was already created today, the alert is suppressed
so re-running the task never double-fires.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Config reader ─────────────────────────────────────────────────────────────

def _get_config():
    """Return the active AttendanceAbsenceAlert record, or None."""
    from apps.attendance.models import AttendanceSettings
    cfg = (
        AttendanceSettings.objects
        .select_related('absence_alert')
        .filter(is_active=True)
        .order_by('-created_at')
        .first()
    )
    if cfg is None:
        return None
    try:
        return cfg.absence_alert
    except Exception:
        return None


def _get_weekly_off_days(employee, start: date, end: date) -> dict:
    """
    Per-employee, per-day weekly-off resolution for [start, end] — via the
    same centralized WeeklyOffCacheService.get_effective_range() resolver
    AttendanceProcessorService/AttendanceDashboardService/leave.py all use, so
    an employee's assigned pattern (not just the org default) is respected
    when deciding which days to skip in their absence streak.
    """
    from core.cache_service import WeeklyOffCacheService
    return WeeklyOffCacheService.get_effective_range(employee, start, end)


# ─── Per-employee helpers ──────────────────────────────────────────────────────

def _get_approved_leave_dates(employee, start: date, today: date) -> set:
    """Return the set of dates (start <= d < today) covered by approved leaves."""
    from apps.hrms.models import LeaveRequest, REQ_APPROVED
    leave_dates: set = set()
    for lr in LeaveRequest.objects.filter(
        employee=employee,
        status=REQ_APPROVED,
        start_date__lt=today,
        end_date__gte=start,
    ):
        cursor = max(lr.start_date, start)
        while cursor <= lr.end_date and cursor < today:
            leave_dates.add(cursor)
            cursor += timedelta(days=1)
    return leave_dates


def _count_consecutive_absent_days(
    employee, today: date, threshold: int
) -> int:
    """
    Walk backwards from yesterday counting consecutive absent working days.
    Stops as soon as a non-absent, non-skip day is found or threshold is reached.
    """
    from apps.attendance.models import AttendanceRecord
    look_back = threshold + 14          # buffer for week-offs / holidays
    start = today - timedelta(days=look_back)

    records = {
        r.date: r.status
        for r in AttendanceRecord.objects.filter(
            employee=employee, date__gte=start, date__lt=today,
        )
    }
    leave_dates = _get_approved_leave_dates(employee, start, today)
    off_days_by_date = _get_weekly_off_days(employee, start, today - timedelta(days=1))

    consecutive = 0
    current = today - timedelta(days=1)

    while current >= start:
        if current.strftime('%A').lower() in off_days_by_date[current]:
            current -= timedelta(days=1)
            continue
        if current in leave_dates:
            break
        status = records.get(current)
        if status == AttendanceRecord.STATUS_HOLIDAY:
            current -= timedelta(days=1)
            continue
        if status in (AttendanceRecord.STATUS_ABSENT, None):
            consecutive += 1
        else:
            break
        if consecutive >= threshold:
            break
        current -= timedelta(days=1)

    return consecutive


def _alert_sent_today(employee, today: date) -> bool:
    """True if an absence alert notification was already created for this employee today."""
    from apps.notifications.models import Notification
    return Notification.objects.filter(
        notification_type='attendance',
        reference_id=str(employee.id),
        title='Absence Alert',
        created_at__date=today,
    ).exists()


def _fire_alert(employee, consecutive_days: int, notify_whom: str) -> None:
    """Create one Notification per configured recipient (manager, HR, or both)."""
    from apps.notifications.models import Notification
    message = (
        f'{employee.full_name} has been absent for {consecutive_days} consecutive '
        'working day(s) without an approved leave.'
    )
    recipients = []
    if notify_whom in ('manager_only', 'manager_and_hr'):
        manager = getattr(employee, 'reporting_manager', None)
        if manager:
            recipients.append(manager)
    if notify_whom in ('hr_only', 'manager_and_hr'):
        hr = getattr(employee, 'hr', None)
        if hr:
            recipients.append(hr)

    for recipient in recipients:
        Notification.objects.create(
            user=recipient,
            title='Absence Alert',
            message=message,
            notification_type='attendance',
            module='attendance',
            reference_id=str(employee.id),
        )
    logger.info(
        'Absence alert fired: employee=%s consecutive_days=%d recipients=%d',
        employee.id, consecutive_days, len(recipients),
    )


# ─── Main entry point ─────────────────────────────────────────────────────────

def detect_absence_alerts() -> dict:
    """
    Scan all active employees and fire absence alerts where the configured
    threshold is met. Called by the `check_absence_alerts` Celery task.
    Returns a summary dict used for task logging.
    """
    config = _get_config()
    if config is None or not config.is_enabled:
        return {'skipped': True, 'reason': 'no config or disabled'}

    threshold   = config.alert_after_days
    notify_whom = config.notify_whom
    today       = timezone.localdate()

    from apps.accounts.models import User
    employees = (
        User.objects
        .filter(is_active=True, onboarding_status='complete')
        .exclude(employee_id='')
        .select_related('reporting_manager', 'hr')
    )

    checked     = 0
    alerts_sent = 0

    for employee in employees:
        checked += 1
        consecutive = _count_consecutive_absent_days(employee, today, threshold)
        if consecutive < threshold:
            continue
        if _alert_sent_today(employee, today):
            continue
        _fire_alert(employee, consecutive, notify_whom)
        alerts_sent += 1

    logger.info(
        'detect_absence_alerts complete: checked=%d threshold=%d alerts_sent=%d',
        checked, threshold, alerts_sent,
    )
    return {'checked': checked, 'threshold': threshold, 'alerts_sent': alerts_sent}
