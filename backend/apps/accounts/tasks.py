"""
Accounts Celery tasks.

Dispatched on-demand from onboarding views (via transaction.on_commit) —
not part of CELERY_BEAT_SCHEDULE; each onboarding submission enqueues its
own one-off HR-notification delivery.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_onboarding_submitted_notification_task(self, user_id):
    """
    Notify HR that the user identified by `user_id` submitted their
    onboarding wizard.

    Re-derives the HR recipient list fresh in the worker — same rule the
    synchronous path used (the submitter's assigned HR if set, otherwise
    everyone holding onboarding.approve) — rather than trusting a list
    resolved back at request time, which could be stale by the time this
    task actually runs.

    Retries (up to 3, 5 min apart) only cover the setup phase (fetching the
    submitter/HR targets); once the send loop starts, a failed recipient is
    logged and skipped so the rest still go out, and a retry can never
    re-send to someone who already received it.
    """
    from apps.accounts.models import Company, User
    from apps.accounts.utils import send_template_email

    try:
        submitter = User.objects.get(pk=user_id)

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''
        email_context = {
            'candidate_name':  submitter.full_name or submitter.email,
            'candidate_email': submitter.email,
            'company_name':    company_name,
            'portal_url':      portal_url,
        }

        if submitter.hr_id:
            hr_user = User.objects.filter(pk=submitter.hr_id, is_active=True).first()
            hr_targets = [(hr_user.email, hr_user.full_name or 'HR')] if hr_user and hr_user.email else []
        else:
            hr_targets = [
                (email, 'HR Team')
                for email in User.objects.filter(
                    role__role_permissions__permission__codename='onboarding.approve',
                    is_active=True,
                ).exclude(email='').values_list('email', flat=True)
            ]
    except User.DoesNotExist:
        logger.warning(
            'send_onboarding_submitted_notification_task: user %s no longer exists — skipping.',
            user_id,
        )
        return {'user_id': user_id, 'status': 'skipped_missing'}
    except Exception as exc:
        logger.error(
            'send_onboarding_submitted_notification_task setup failed for %s: %s',
            user_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)

    sent = 0
    for recipient_email, hr_name in hr_targets:
        try:
            send_template_email(
                recipient_email=recipient_email,
                template_name='onboarding_submitted',
                context={**email_context, 'hr_name': hr_name},
            )
            sent += 1
        except Exception as exc:
            logger.error(
                'Failed to send onboarding_submitted to %s for user %s: %s',
                recipient_email, email_context['candidate_email'], exc, exc_info=True,
            )

    result = {'user_id': user_id, 'targets': len(hr_targets), 'sent': sent}
    logger.info('send_onboarding_submitted_notification_task completed: %s', result)
    return result
