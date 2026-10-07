"""Phase 3B Task G.3 — JobRun history + the run_now() entry point with
locking (a job never runs twice at once unless its JobType allows it)."""
from __future__ import annotations

import datetime
import importlib

from django.db import transaction
from django.utils import timezone

from apps.platform_core import job_runners  # noqa: F401 - imported so the module (and its callables) is guaranteed loaded
from apps.platform_core.models import JobRun, ScheduledJob


class SchedulerError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _resolve_callable(task_path: str):
    module_path, _, func_name = task_path.rpartition('.')
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


@transaction.atomic
def run_now(scheduled_job_id, *, triggered_by: str = JobRun.TRIGGER_ADMIN, triggered_by_user=None) -> JobRun:
    job = ScheduledJob.objects.select_for_update().get(pk=scheduled_job_id)
    if job.is_running and not job.job_type.safe_to_run_concurrently:
        raise SchedulerError(f'{job.name} is already running and is not marked safe to run concurrently.')

    job.is_running = True
    job.last_run_at = timezone.now()
    job.save(update_fields=['is_running', 'last_run_at'])

    run = JobRun.objects.create(scheduled_job=job, triggered_by=triggered_by, triggered_by_user=triggered_by_user)
    try:
        fn = _resolve_callable(job.job_type.task_path)
        result = fn(**job.parameters)
        run.status = JobRun.STATUS_SUCCESS
        run.result_counts = result if isinstance(result, dict) else {}
    except Exception as exc:
        run.status = JobRun.STATUS_FAILED
        run.error_summary = str(exc)[:500]
    run.ended_at = timezone.now()
    run.save(update_fields=['status', 'result_counts', 'error_summary', 'ended_at'])

    job.is_running = False
    job.save(update_fields=['is_running'])
    return run


def overdue_scheduled_jobs(*, grace_minutes: int = 30) -> list[ScheduledJob]:
    """Task G.3's "overdue/missed-run detection" — a job whose
    next_run_at has passed by more than `grace_minutes` and hasn't run
    since. Detection only in this phase (returns the list); emitting an
    alert event for each is left to the caller (e.g. a future scheduled
    job of its own) rather than this function reaching into events
    itself, so it stays a pure query."""
    cutoff = timezone.now() - datetime.timedelta(minutes=grace_minutes)
    return list(ScheduledJob.objects.filter(enabled=True, next_run_at__lt=cutoff))
