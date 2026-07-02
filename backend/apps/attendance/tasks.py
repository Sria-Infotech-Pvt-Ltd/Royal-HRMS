"""
Attendance Celery tasks.

Registered in CELERY_BEAT_SCHEDULE (config/settings.py) for periodic execution.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_missing_clockouts(self):
    """
    Periodic task: find employees who clocked IN today but never clocked OUT
    after shift_end + missing_punch_grace_minutes.

    Runs every 5 minutes (configured in CELERY_BEAT_SCHEDULE).
    Safe to run multiple times — idempotent via STATUS_INCOMPLETE exclusion
    and MissingPunchNotification dedup.
    """
    try:
        from apps.attendance.services_unpunch import detect_and_mark_unpunches
        today  = timezone.localdate()   # Uses Django TIME_ZONE = 'Asia/Kolkata'
        result = detect_and_mark_unpunches(target_date=today)
        logger.info('check_missing_clockouts: %s', result)
        return result
    except Exception as exc:
        logger.error('check_missing_clockouts failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
