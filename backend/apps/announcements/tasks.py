"""
Announcement Celery tasks.

Dispatched on-demand from AnnouncementListCreateView.post() (via
transaction.on_commit) — not part of CELERY_BEAT_SCHEDULE, since there is
nothing periodic here: each announcement enqueues its own one-off delivery.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Conservative recipient-per-message cap so notifying the whole company
# (2,000+ employees) is split into several BCC batches instead of one
# oversized message that many SMTP providers would reject/truncate.
_ANNOUNCEMENT_EMAIL_BATCH_SIZE = 90


def _resolve_recipients(announcement) -> list[str]:
    """Who the announcement e-mail goes to: only Active employees, by the same rule the employee directory uses (onboarding
    complete AND the account activated). Invited or still-onboarding people, and deactivated accounts, get nothing."""
    from apps.accounts.models import User
    from apps.announcements.models import Announcement

    active_employees = User.objects.filter(is_active=True).filter(User.onboarded_q())
    if announcement.visibility == Announcement.VISIBILITY_ALL:
        return list(active_employees.exclude(email='').values_list('email', flat=True))
    if announcement.visibility == Announcement.VISIBILITY_DEPARTMENT and announcement.target_org_unit_id:
        from apps.accounts.services_approval import filter_users_by_org_unit
        users = filter_users_by_org_unit(active_employees, announcement.target_org_unit)
        return list(users.exclude(email='').values_list('email', flat=True))
    if announcement.visibility == Announcement.VISIBILITY_BRANCH and announcement.target_branch_id:
        return list(active_employees.filter(
            branch=announcement.target_branch.branch_name,
        ).exclude(email='').values_list('email', flat=True))
    return []


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_announcement_email_task(self, announcement_id: int):
    """
    Background delivery for an announcement's "notify by email" option.

    Takes only the announcement's id (not a serialized object) and re-fetches
    it fresh in the worker, per this project's task convention. Retries (up
    to 3, 5 min apart) only cover the setup phase — resolving recipients and
    opening the SMTP connection — because nothing has been sent yet at that
    point. Once batches start sending, a failed batch is logged and skipped
    rather than raised, so a retry can never re-send a batch that already
    went out to its recipients.
    """
    from apps.accounts.utils import _build_message, _company_email_wrapper, _get_company_branding, _get_smtp_connection
    from apps.announcements.models import Announcement
    from apps.announcements.services_announcement_email import attach_inline_images, build_announcement_email

    try:
        try:
            announcement = Announcement.objects.select_related(
                'target_org_unit', 'target_branch'
            ).get(pk=announcement_id)
        except Announcement.DoesNotExist:
            logger.warning(
                'send_announcement_email_task: announcement %s no longer exists — skipping.',
                announcement_id,
            )
            return {'announcement_id': announcement_id, 'status': 'skipped_missing'}

        try:
            recipients = _resolve_recipients(announcement)
            if not recipients:
                logger.info(
                    'send_announcement_email_task: no recipients for announcement %s.',
                    announcement_id,
                )
                return {'announcement_id': announcement_id, 'status': 'no_recipients'}

            smtp_connection, from_email, _smtp = _get_smtp_connection()
            subject = f'[Announcement] {announcement.title}'
            # The announcement text is escaped (paragraphs and line breaks kept), with its pictures embedded, PDF links and external
            # links, then put in the branded frame. It is sent as a real HTML message with a plain-text fallback by the shared
            # builder; passing the HTML as the message's plain body once made mail clients show the markup as text.
            content   = build_announcement_email(announcement)
            html_body = _company_email_wrapper(content.body_html, *_get_company_branding())
        except RuntimeError as exc:
            # No active SMTP config — matches the previous synchronous
            # behaviour: log and give up, since retrying immediately won't
            # fix a missing configuration.
            logger.warning('Announcement email skipped for %s — %s', announcement_id, exc)
            return {'announcement_id': announcement_id, 'status': 'no_smtp_config'}

        total_batches  = (len(recipients) + _ANNOUNCEMENT_EMAIL_BATCH_SIZE - 1) // _ANNOUNCEMENT_EMAIL_BATCH_SIZE
        sent_batches   = 0
        failed_batches = 0

        with smtp_connection:
            for i in range(0, len(recipients), _ANNOUNCEMENT_EMAIL_BATCH_SIZE):
                batch     = recipients[i:i + _ANNOUNCEMENT_EMAIL_BATCH_SIZE]
                batch_num = i // _ANNOUNCEMENT_EMAIL_BATCH_SIZE + 1
                try:
                    message = _build_message(
                        subject, html_body, from_email,
                        to=[from_email],   # required "to" for RFC compliance
                        connection=smtp_connection,
                    )
                    message.body = content.text                      # plain-text version with the real addresses of links
                    attach_inline_images(message, content.images)    # fresh parts for every message
                    message.bcc = batch
                    message.send()
                    sent_batches += 1
                except Exception as exc:
                    failed_batches += 1
                    logger.error(
                        'Announcement %s email batch %d/%d failed (%d recipients): %s',
                        announcement_id, batch_num, total_batches, len(batch), exc,
                        exc_info=True,
                    )

        result = {
            'announcement_id': announcement_id,
            'recipients':      len(recipients),
            'total_batches':   total_batches,
            'sent_batches':    sent_batches,
            'failed_batches':  failed_batches,
        }
        logger.info('send_announcement_email_task completed: %s', result)
        return result
    except Exception as exc:
        # Nothing has been sent yet if setup itself failed, so a retry here is safe.
        logger.error(
            'send_announcement_email_task setup failed for %s: %s',
            announcement_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)
