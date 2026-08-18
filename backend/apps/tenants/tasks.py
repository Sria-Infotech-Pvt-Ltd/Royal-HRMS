"""
Company provisioning Celery tasks.

Replaces the old detached-OS-subprocess mechanism (spawning a raw
`manage.py provision_company_subprocess` child process with Windows
job-breakaway flags to survive the web server restarting). That approach
had two production-grade problems: every provisioning run paid the full
cost of a cold Python/Django bootstrap (app registry, settings, etc.), and
a worker killed outright (not via a raised exception) left its Client row
stuck at 'pending' forever with no recovery path.

A Celery task fixes both: it runs in an already-warm worker process (no
per-company bootstrap cost), and sweep_stale_provisioning below gives any
row that's stuck (e.g. the worker was killed mid-task) a way to
self-recover instead of hanging indefinitely.
"""
import logging

from celery import shared_task
from django.utils import timezone

from apps.tenants.models import Client
from apps.tenants.services import finish_pending_provisioning

logger = logging.getLogger(__name__)


@shared_task
def finish_provisioning_task(client_id, admin_email, modules):
    """
    Finishes provisioning a pending Client row (schema + migrations +
    reference-data seed + first admin login), then flips its
    provisioning_status to 'active'. Dispatched from
    apps.tenants.views.CompanyListCreateView.post right after the row is
    created with provisioning_status='pending'.

    No automatic retry: schema creation + migration is not safely
    re-runnable from the top once partially applied, same constraint the
    old subprocess-based command had. Any failure flips the row to
    'failed' and re-raises so it still shows up in Celery's own
    logging/monitoring.
    """
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        logger.error('finish_provisioning_task: no Client row with id %s — nothing to finish.', client_id)
        return

    try:
        finish_pending_provisioning(client=client, admin_email=admin_email, modules=modules)
        logger.info('Provisioning finished for %s.', client.company_code)
    except Exception:
        Client.objects.filter(pk=client.pk).update(provisioning_status=Client.PROVISIONING_FAILED)
        logger.exception('Provisioning failed for %s.', client.company_code)
        raise


@shared_task
def sweep_stale_provisioning(stale_minutes=15):
    """
    Safety net for a worker that dies mid-task (deploy, OOM, crash) before
    finish_provisioning_task's own except-block can flip the row to
    'failed' — without this, that Client row stays 'pending' forever and
    the platform-admin UI shows "Provisioning..." with no way to recover
    short of a manual DB fix. Runs every 5 minutes (see
    CELERY_BEAT_SCHEDULE); anything still 'pending' after `stale_minutes`
    is presumed dead and marked 'failed' so a platform admin can see the
    failure and recreate the company.
    """
    cutoff = timezone.now() - timezone.timedelta(minutes=stale_minutes)
    stale = Client.objects.filter(provisioning_status=Client.PROVISIONING_PENDING, created_at__lt=cutoff)
    count = stale.update(provisioning_status=Client.PROVISIONING_FAILED)
    if count:
        logger.warning('Marked %d stale pending company provisioning row(s) as failed.', count)
    return count
