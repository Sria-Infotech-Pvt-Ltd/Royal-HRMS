"""
Notifications Celery tasks.

Dispatched on-demand from apps.notifications.signals (via
transaction.on_commit) — not part of CELERY_BEAT_SCHEDULE; each lifecycle
event (leave submitted/approved/rejected/etc.) enqueues its own one-off
email delivery alongside the in-app Notification row the signal already
creates synchronously.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_lifecycle_email_task(self, user_id, template_name: str, context: dict):
    """
    Background delivery for a single lifecycle-event email (leave
    submitted/approved/rejected/forwarded/cancelled, etc.)

    Takes the recipient's user id (not a User instance) and re-fetches it
    fresh in the worker. `context` is plain lifecycle-event data captured at
    signal-fire time (e.g. old/new status, approver name) — it is inherently
    transient to that event, not something re-derivable from the DB later,
    so it is passed through as-is (all string/primitive values, same as
    every other template-email call in this codebase).

    Retries (up to 3, 5 min apart) only cover fetching the user — nothing
    has been sent yet at that point, so retrying is safe. The actual send
    is delegated to send_template_email, matching every other email path.
    """
    from apps.accounts.models import User
    from apps.accounts.utils import send_template_email
    from apps.notifications.signals import _company_name

    try:
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning(
                'send_lifecycle_email_task: user %s no longer exists — skipping "%s".',
                user_id, template_name,
            )
            return {'user_id': user_id, 'status': 'skipped_missing'}

        if not user.email:
            return {'user_id': user_id, 'status': 'no_email'}

        try:
            send_template_email(
                recipient_email=user.email,
                template_name=template_name,
                context={**context, 'company_name': _company_name()},
                module='notifications',
            )
        except Exception as exc:
            logger.exception('Failed to send lifecycle email "%s" to %s: %s', template_name, user.email, exc)
            return {'user_id': user_id, 'status': 'send_failed'}

        return {'user_id': user_id, 'status': 'sent'}
    except Exception as exc:
        logger.error(
            'send_lifecycle_email_task setup failed for user %s: %s',
            user_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)
