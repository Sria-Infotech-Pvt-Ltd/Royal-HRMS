"""
Payroll Celery tasks.

Registered in CELERY_BEAT_SCHEDULE (config/settings.py) for periodic execution.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

REMINDER_HOURS = 24


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_payroll_approval_reminders(self):
    """
    Daily task: find payroll cycles stuck in ATTENDANCE_PENDING for more than
    REMINDER_HOURS and send a reminder bell + email to each manager who still
    hasn't approved their row.

    Idempotent — re-running sends another reminder, which is the intended
    behaviour for a daily nudge. Does not fire for cycles created less than
    REMINDER_HOURS ago (the initial notification covers those).
    """
    try:
        from datetime import timedelta

        from django.utils import timezone

        from apps.payroll.models import ManagerAttendanceApproval, PayrollCycle
        from apps.payroll.notifications import _notify, _send_email

        threshold = timezone.now() - timedelta(hours=REMINDER_HOURS)
        cycles = PayrollCycle.objects.filter(
            status=PayrollCycle.STATUS_ATTENDANCE_PENDING,
            created_at__lte=threshold,
        ).select_related('branch')

        reminded_count = 0
        for cycle in cycles:
            month_label = cycle.cycle_start.strftime('%B %Y')
            ref_id = str(cycle.id)

            pending_rows = ManagerAttendanceApproval.objects.filter(
                cycle=cycle, approved_at__isnull=True,
            ).select_related('manager')

            for row in pending_rows:
                manager = row.manager
                if not manager or not manager.is_active:
                    continue
                _notify(
                    manager,
                    'Reminder: Payroll Approval Pending',
                    f'Your attendance sign-off for {month_label} payroll is still pending. Please approve at your earliest.',
                    ref_id,
                )
                _send_email(manager, 'payroll_l1_approval_required', {
                    'manager_name': manager.full_name or manager.email,
                    'month':        month_label,
                    'cycle_start':  cycle.cycle_start.strftime('%d %b %Y'),
                    'cycle_end':    cycle.cycle_end.strftime('%d %b %Y'),
                    'pay_date':     cycle.pay_date.strftime('%d %b %Y'),
                })
                reminded_count += 1

        logger.info('send_payroll_approval_reminders: reminded %s managers', reminded_count)
        return {'reminded': reminded_count}
    except Exception as exc:
        logger.error('send_payroll_approval_reminders failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
