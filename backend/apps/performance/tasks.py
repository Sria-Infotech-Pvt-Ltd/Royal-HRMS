"""
Performance app Celery tasks.

Registered in CELERY_BEAT_SCHEDULE (config/settings.py) for periodic execution.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def close_expired_review_cycles(self):
    """
    Daily task: any 'active' ReviewCycle whose period_end has passed is
    flipped to 'closed' — no more self/manager review submissions are
    accepted for it (MyReviewView/SubmitManagerReviewView both key off
    _active_cycle(), which only ever returns a status='active' cycle, so
    closing here is what actually stops new submissions).

    Idempotent: only ever touches rows still in 'active' status, so a
    retried or duplicate run is a no-op the second time.
    """
    from apps.performance.models import CYCLE_ACTIVE, CYCLE_CLOSED, ReviewCycle

    try:
        today = timezone.localdate()
        closed = ReviewCycle.objects.filter(status=CYCLE_ACTIVE, period_end__lt=today).update(status=CYCLE_CLOSED)
        result = {'date': today.isoformat(), 'closed': closed}
        logger.info('close_expired_review_cycles completed: %s', result)
        return result
    except Exception as exc:
        logger.error('close_expired_review_cycles error: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
