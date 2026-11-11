"""Daily approval reminders / escalation — registered in CELERY_BEAT_SCHEDULE."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def run_approval_escalations(self):
    """Once per active company; each company's own settings decide (off by default)."""
    from apps.tenants.utils import run_for_all_tenants

    def _one():
        from apps.approvals.escalation import run_escalations
        return run_escalations()

    try:
        result = run_for_all_tenants(_one, task_name='run_approval_escalations')
        logger.info('run_approval_escalations: %s', result)
        return result
    except Exception as exc:
        logger.error('run_approval_escalations failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
