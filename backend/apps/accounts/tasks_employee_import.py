"""
Celery tasks of the bulk employee import: the import job, the activation invitations, and their recovery sweeps.

Kept in their own module (apps.accounts.tasks imports them so Celery's discovery finds them) and given explicit names so the beat
schedule and the job-type registry keep pointing at `apps.accounts.tasks.<name>`.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


# ── Bulk employee import: activation invitations (see services_employee_import_invites) ──────────────────────────────────

@shared_task(bind=True, name='apps.accounts.tasks.send_import_invite', acks_late=True, reject_on_worker_lost=True, rate_limit=getattr(settings, 'EMPLOYEE_IMPORT_INVITE_RATE_LIMIT', '20/m'))
def send_import_invite(self, invite_id):
    """Send ONE import invitation. Safe to run twice or on two workers: the row is claimed under a lock and finished work is skipped."""
    from apps.accounts.services_employee_import_invites import process_invite, retry_delay_seconds

    outcome = process_invite(invite_id)
    if outcome == 'retry':
        try:
            self.apply_async(args=[invite_id], countdown=retry_delay_seconds(invite_id))
        except Exception:                                                  # noqa: BLE001 - broker unavailable; the sweep re-queues it
            logger.warning('Could not schedule the retry of an import invitation; the recovery sweep will pick it up')
    return outcome


@shared_task(bind=True, name='apps.accounts.tasks.run_employee_import_job', acks_late=True, reject_on_worker_lost=True)
def run_employee_import_job(self, job_id):
    """Run ONE chunk of a bulk import job, then queue the next so other tasks can interleave. State lives in the database checkpoint."""
    from apps.accounts.services_employee_import_job import run_job

    outcome = run_job(job_id)
    if outcome in ('running', 'retry_later'):
        try:
            self.apply_async(args=[job_id], countdown=60 if outcome == 'retry_later' else 0)
        except Exception:                                                  # noqa: BLE001 - broker unavailable; the sweep re-queues it
            logger.warning('Could not queue the next chunk of an import job; the recovery sweep will pick it up')
    return outcome


@shared_task(name='apps.accounts.tasks.requeue_stale_import_jobs')
def requeue_stale_import_jobs():
    """Beat task: queue import jobs nobody picked up, and jobs whose worker died (lease expired)."""
    from apps.accounts.services_employee_import_job import requeue_stale_jobs

    return requeue_stale_jobs()


@shared_task(name='apps.accounts.tasks.purge_old_import_jobs')
def purge_old_import_jobs():
    """Beat task (daily): delete finished import jobs and their row errors after the 30-day retention."""
    from apps.accounts.services_employee_import_job import purge_old_jobs

    return purge_old_jobs(30)


@shared_task(name='apps.accounts.tasks.requeue_stale_import_invites')
def requeue_stale_import_invites():
    """Beat task: re-queue invitations whose worker died, whose retry is due, or that were never queued (Redis was down)."""
    from apps.accounts.services_employee_import_invites import requeue_stale

    return requeue_stale()
