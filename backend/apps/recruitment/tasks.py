"""
Recruitment Celery tasks.

Dispatched on-demand from apps.recruitment.views (via transaction.on_commit)
— not part of CELERY_BEAT_SCHEDULE; each candidate create/update/referral
action enqueues its own one-off notification delivery.

Both tasks are thin dispatchers: they re-fetch the Candidate fresh in the
worker and call the SAME existing email-sending functions the synchronous
path used to call directly (_send_interview_scheduled_emails,
_send_interview_scheduled_email_general, _send_referral_submission_emails)
— no email content/recipient logic is duplicated here.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_interview_scheduled_emails_task(self, candidate_id):
    """
    Background delivery for "interview scheduled" notification email(s).

    Retries (up to 3, 5 min apart) only cover fetching the candidate —
    nothing has been sent yet at that point. Once the existing send
    function is called, any failure it doesn't already swallow internally
    is logged and NOT retried, since some of the emails inside it (e.g. the
    referrer's, sent before the candidate's) may have already gone out —
    retrying the whole function again could re-send those.
    """
    from apps.recruitment.models import Candidate

    try:
        candidate = Candidate.objects.select_related('branch', 'referral_by').get(pk=candidate_id)
    except Candidate.DoesNotExist:
        logger.warning(
            'send_interview_scheduled_emails_task: candidate %s no longer exists — skipping.',
            candidate_id,
        )
        return {'candidate_id': candidate_id, 'status': 'skipped_missing'}
    except Exception as exc:
        logger.error(
            'send_interview_scheduled_emails_task setup failed for %s: %s',
            candidate_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)

    from apps.recruitment.views import _send_interview_scheduled_email_general, _send_interview_scheduled_emails

    try:
        if candidate.referral_by_id:
            _send_interview_scheduled_emails(candidate)
        else:
            _send_interview_scheduled_email_general(candidate)
    except Exception as exc:
        logger.error(
            'send_interview_scheduled_emails_task: error sending for candidate %s: %s',
            candidate_id, exc, exc_info=True,
        )
        return {'candidate_id': candidate_id, 'status': 'error'}

    return {'candidate_id': candidate_id, 'status': 'sent'}


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_referral_submission_emails_task(self, candidate_id):
    """
    Background delivery for the referral-submitted notification email(s)
    (referrer + candidate). Same retry semantics as
    send_interview_scheduled_emails_task above.
    """
    from apps.recruitment.models import Candidate

    try:
        candidate = Candidate.objects.select_related('branch', 'referral_by').get(pk=candidate_id)
    except Candidate.DoesNotExist:
        logger.warning(
            'send_referral_submission_emails_task: candidate %s no longer exists — skipping.',
            candidate_id,
        )
        return {'candidate_id': candidate_id, 'status': 'skipped_missing'}
    except Exception as exc:
        logger.error(
            'send_referral_submission_emails_task setup failed for %s: %s',
            candidate_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)

    from apps.recruitment.views import _send_referral_submission_emails

    try:
        _send_referral_submission_emails(candidate)
    except Exception as exc:
        logger.error(
            'send_referral_submission_emails_task: error sending for candidate %s: %s',
            candidate_id, exc, exc_info=True,
        )
        return {'candidate_id': candidate_id, 'status': 'error'}

    return {'candidate_id': candidate_id, 'status': 'sent'}
