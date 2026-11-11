"""
Bulk employee import as a durable background job (see models_import_job for the data model and the recovery idea).

  create_job()      validates the whole file exactly as the preview does, stores the job and returns at once;
  run_job()         (a Celery task) claims the job under a time-limited lease and creates the employees in short transactions
                    of `commit_batch_size` rows. Each transaction also advances the checkpoint `next_row`, records rows that no
                    longer validate as row-level errors, and writes the invitation rows. Invitation tasks are queued AFTER it commits;
  requeue_stale_jobs() (a beat task) re-queues jobs whose worker died, so they resume at the checkpoint.

Behaviour to know about
  - Up to one commit batch (25 rows by default) is all-or-nothing, as before. A larger file is committed batch by batch: if the job
    is cancelled or fails part-way, the employees of the committed batches exist and the rest do not. Nobody is ever created twice.
  - Rows were valid when the job was confirmed. If something changed since (a seat was taken, an email now exists), that row is
    recorded as a row-level error and skipped; the other rows still import.
  - Throughput is limited by the per-employee creation cost (see the measurements in the test report); it is not a bulk path.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import AuditLog, EmployeeIdSeriesExhausted, EmployeeImportJob, EmployeeImportJobError, User
from apps.accounts.models_import_job import (
    ACTIVE_STATUSES, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS, STATUS_FAILED, STATUS_QUEUED, STATUS_RUNNING, TERMINAL_STATUSES,
)
from apps.accounts.services_employee_import import COLUMNS, ImportFileError, ParsedFile, RowResult, file_sha256, parse_workbook, summarise, validate_rows
from apps.accounts.services_employee_import_commit import ImportRejected, _create_one
from apps.accounts.services_employee_import_invites import batch_progress, create_invites, enqueue_ids
from apps.accounts.services_employee_import_seats import lock_candidate_seats
from apps.accounts.services_employee_import_template import build_error_report

logger = logging.getLogger(__name__)

CORE_KEYS = tuple(column.key for column in COLUMNS if column.is_core)
MAX_STALLS = 3
QUEUED_GRACE = timedelta(seconds=120)
# Row-level messages for conflicts that appear only after a row was validated (another import or a manual hire got there first).
# They name no person, email or employee id.
EMAIL_TAKEN_MESSAGE = 'An employee with this email already exists (it was created while this import was running). This row was skipped.'
CONFLICT_MESSAGE = 'This row conflicts with an employee created while this import was running (duplicate employee record). This row was skipped.'
SEAT_TAKEN_MESSAGE = 'The seat for this row was taken by someone else while this import was running. This row was skipped.'


def _cfg(name: str, default):
    return getattr(settings, name, default)


# ── creating and queueing ────────────────────────────────────────────────────────────────────────────────────────────────

def create_job(importer: User, content: bytes, *, batch_id, expected_hash: str, file_name: str = '') -> tuple[EmployeeImportJob, bool]:
    """Validate everything now (like the preview), store the job, return (job, created). The same batch id returns the same job."""
    job_id = uuid.UUID(str(batch_id))
    existing = EmployeeImportJob.objects.filter(pk=job_id).first()
    if existing is not None:
        return existing, False
    if file_sha256(content) != (expected_hash or '').lower():
        raise ImportRejected('The file is not the one you previewed. Upload it again and review the preview.')
    parsed = parse_workbook(content, max_rows=_cfg('EMPLOYEE_IMPORT_JOB_MAX_ROWS', 5000))
    results = validate_rows(importer, parsed)
    summary = summarise(results)
    if not summary.can_import:
        raise ImportRejected(f'{summary.invalid} of {summary.total} rows have errors. No employees will be created.', results)
    try:
        with transaction.atomic():
            job = EmployeeImportJob.objects.create(
                id=job_id, created_by=importer, file_name=file_name[:255], file_sha256=file_sha256(content), content=content,
                total_rows=len(parsed.rows), chunk_size=_cfg('EMPLOYEE_IMPORT_CHUNK_SIZE', 2000), commit_batch_size=_cfg('EMPLOYEE_IMPORT_COMMIT_BATCH', 25))
            AuditLog.objects.create(user=importer, action='employee_bulk_import_job_created', module='accounts', object_id=str(job_id),
                                    changes={'job_id': str(job_id), 'file_sha256': job.file_sha256, 'total': job.total_rows}, branch=importer.branch)
    except IntegrityError:                                       # the same file is already queued/running, or the same job id raced us
        again = EmployeeImportJob.objects.filter(pk=job_id).first()
        if again is not None:
            return again, False
        raise ImportRejected('This file is already being imported. Open that import to follow its progress.')
    return job, True


def dispatch_job(job_id) -> bool:
    """Queue the Celery task. If the broker is down the job simply stays queued; requeue_stale_jobs() queues it later."""
    from apps.accounts.tasks import run_employee_import_job

    try:
        run_employee_import_job.delay(str(job_id))
    except Exception:                                            # noqa: BLE001 - broker (Redis) unavailable
        logger.warning('Could not queue import job %s (broker unavailable); the recovery sweep will queue it', job_id)
        return False
    return True


# ── running ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _lease_end(now):
    return now + timedelta(seconds=_cfg('EMPLOYEE_IMPORT_JOB_LEASE_SECONDS', 600))


def _finish(job_id, status: str, code: str = '') -> None:
    now = timezone.now()
    # Only a job that is not finished yet can be finished, so two workers racing to end it write one audit entry and never overwrite
    # the first outcome (a cancelled job cannot turn into "completed" afterwards).
    changed = (EmployeeImportJob.objects.filter(pk=job_id).exclude(status__in=TERMINAL_STATUSES)
               .update(status=status, finished_at=now, content=b'', lease_until=None, failure_code=code, updated_at=now))
    if not changed:
        return
    job = EmployeeImportJob.objects.get(pk=job_id)
    AuditLog.objects.create(user=job.created_by, action='employee_bulk_import_job_finished', module='accounts', object_id=str(job_id),
                            changes={'job_id': str(job_id), 'status': status, 'failure_code': code, 'total': job.total_rows,
                                     'created': job.created_count, 'failed_rows': job.failed_count})


def _claim(job_id) -> EmployeeImportJob | None:
    """Take the job for one run, under a lease. None when it is finished, owned by a live worker, or has just been cancelled."""
    now = timezone.now()
    with transaction.atomic():
        job = EmployeeImportJob.objects.select_for_update(skip_locked=True, of=('self',)).select_related('created_by').filter(pk=job_id).first()
        if job is None or job.status in TERMINAL_STATUSES:
            return None
        if job.cancel_requested:
            _finish(job.pk, STATUS_CANCELLED)
            return None
        if job.lease_until and job.lease_until > now:
            return None                                          # another worker holds a live lease
        job.status, job.started_at, job.lease_until = STATUS_RUNNING, job.started_at or now, _lease_end(now)
        job.save(update_fields=['status', 'started_at', 'lease_until', 'updated_at'])
        return job


def _create_isolated(importer: User, result: RowResult) -> tuple[User | None, str]:
    """Create one employee inside its own savepoint: a database conflict (a duplicate email or employee record created by someone
    else after validation, or a seat taken in the meantime) rolls back ONLY this row. Returns (user, '') or (None, row error)."""
    try:
        with transaction.atomic():
            return _create_one(importer, result, None), ''
    except IntegrityError:
        taken = User.objects.filter(email__iexact=result.values.get('email', '')).exists()
        return None, EMAIL_TAKEN_MESSAGE if taken else CONFLICT_MESSAGE
    except DjangoValidationError:                                # the database's one-holder-per-seat rule refused the placement
        return None, SEAT_TAKEN_MESSAGE


def _process_batch(job_id, importer: User, rows: list, expected_next: int) -> bool:
    """One database transaction: create the employees of these rows, record row errors, write invitation rows, advance the checkpoint."""
    with transaction.atomic():
        job = EmployeeImportJob.objects.select_for_update().get(pk=job_id)
        if job.next_row != expected_next or job.status != STATUS_RUNNING or job.cancel_requested:
            return False                                         # another worker advanced the job, or it was cancelled: do nothing
        lock_candidate_seats(rows)
        created: list[tuple[RowResult, User]] = []
        failed: list[RowResult] = []
        for result in validate_rows(importer, ParsedFile(rows=rows)):
            user, problem = _create_isolated(importer, result) if result.is_valid else (None, '')
            if user is not None:
                created.append((result, user))
                continue
            if problem:
                result.errors.append(problem)
            failed.append(result)
        if failed:
            EmployeeImportJobError.objects.bulk_create(
                [EmployeeImportJobError(job_id=job.pk, row_number=r.row, messages=r.errors, values={k: r.values.get(k, '') for k in CORE_KEYS}) for r in failed],
                ignore_conflicts=True)
        invites = create_invites(importer, job.pk, [(r.row, str(u.pk), u.employee_id) for r, u in created]) if created else {'pending_ids': []}
        EmployeeImportJob.objects.filter(pk=job.pk).update(
            next_row=F('next_row') + len(rows), created_count=F('created_count') + len(created), failed_count=F('failed_count') + len(failed),
            stalls=0, lease_until=_lease_end(timezone.now()), updated_at=timezone.now())
    enqueue_ids(invites['pending_ids'])                          # only now that the employees are committed
    return True


def _stalled(job_id) -> bool:
    EmployeeImportJob.objects.filter(pk=job_id).update(stalls=F('stalls') + 1, lease_until=None)
    return EmployeeImportJob.objects.get(pk=job_id).stalls >= MAX_STALLS


def run_job(job_id, *, max_rows: int | None = None) -> str:
    """Process up to `max_rows` (default: the job's chunk size) and return the job's status, or 'not_runnable'."""
    job = _claim(job_id)
    if job is None:
        current = EmployeeImportJob.objects.filter(pk=job_id).values_list('status', flat=True).first()
        return STATUS_CANCELLED if current == STATUS_CANCELLED else 'not_runnable'
    try:
        parsed = parse_workbook(bytes(job.content), max_rows=_cfg('EMPLOYEE_IMPORT_JOB_MAX_ROWS', 5000))
    except ImportFileError:
        _finish(job.pk, STATUS_FAILED, 'file_unreadable')
        return STATUS_FAILED
    budget = max_rows or job.chunk_size
    while job.next_row < job.total_rows and budget > 0:
        if EmployeeImportJob.objects.filter(pk=job.pk, cancel_requested=True).exists():
            _finish(job.pk, STATUS_CANCELLED)
            return STATUS_CANCELLED
        size = min(job.commit_batch_size, budget, job.total_rows - job.next_row)
        try:
            _process_batch(job.pk, job.created_by, parsed.rows[job.next_row:job.next_row + size], job.next_row)
        except EmployeeIdSeriesExhausted:
            _finish(job.pk, STATUS_FAILED, 'employee_id_range_full')
            return STATUS_FAILED
        except Exception as exc:                                 # noqa: BLE001 - never log the exception text: it can contain personal data
            logger.error('Import job %s: a batch failed (%s); it will be retried', job.pk, type(exc).__name__)
            if _stalled(job.pk):
                _finish(job.pk, STATUS_FAILED, 'batch_failed')
                return STATUS_FAILED
            return 'retry_later'
        job.refresh_from_db(fields=['next_row', 'created_count', 'failed_count'])      # not `content`: it can be megabytes
        budget -= size
    if job.next_row >= job.total_rows:
        status = STATUS_COMPLETED_WITH_ERRORS if job.failed_count else STATUS_COMPLETED
        _finish(job.pk, status)
        return status
    EmployeeImportJob.objects.filter(pk=job.pk).update(lease_until=None)         # this run is done; the next run may start at once
    return STATUS_RUNNING


def requeue_stale_jobs() -> dict:
    """Beat task: queue jobs nobody picked up (broker was down) and jobs whose worker died (lease expired)."""
    now = timezone.now()
    queued = list(EmployeeImportJob.objects.filter(status=STATUS_QUEUED, updated_at__lte=now - QUEUED_GRACE).values_list('pk', flat=True))
    orphaned = list(EmployeeImportJob.objects.filter(status=STATUS_RUNNING, updated_at__lte=now - QUEUED_GRACE).exclude(lease_until__gt=now).values_list('pk', flat=True))
    sent = 0
    for pk in queued + orphaned:
        if not dispatch_job(pk):
            break
        sent += 1
    return {'queued_waiting': len(queued), 'lease_expired': len(orphaned), 'dispatched': sent}


def cancel_job(job: EmployeeImportJob) -> EmployeeImportJob:
    """Safe cancellation: a queued job is cancelled at once; a running job stops after its current batch. Committed employees stay."""
    with transaction.atomic():
        job = EmployeeImportJob.objects.select_for_update().get(pk=job.pk)
        if job.status in TERMINAL_STATUSES:
            return job
        if job.status == STATUS_QUEUED:
            _finish(job.pk, STATUS_CANCELLED)
        else:
            EmployeeImportJob.objects.filter(pk=job.pk).update(cancel_requested=True)
    return EmployeeImportJob.objects.get(pk=job.pk)


def purge_old_jobs(days: int = 30) -> int:
    """Remove finished jobs (and their row errors) older than the retention period."""
    old = EmployeeImportJob.objects.filter(status__in=TERMINAL_STATUSES, finished_at__lt=timezone.now() - timedelta(days=days))
    count = old.count()
    old.delete()
    return count


# ── reading ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def get_job_for(user: User, job_id) -> EmployeeImportJob | None:
    return EmployeeImportJob.objects.filter(pk=job_id, created_by=user).first()


def job_progress(job: EmployeeImportJob) -> dict:
    invites = batch_progress(job.pk)
    return {
        'job_id': str(job.pk), 'status': job.status, 'is_active': job.status in ACTIVE_STATUSES, 'file_name': job.file_name,
        'total_rows': job.total_rows, 'processed_rows': job.next_row, 'created': job.created_count, 'failed_rows': job.failed_count,
        'percent': 100 if job.total_rows == 0 else int(100 * job.next_row / job.total_rows), 'cancel_requested': job.cancel_requested,
        'failure_code': job.failure_code, 'created_at': job.created_at, 'started_at': job.started_at, 'finished_at': job.finished_at,
        'invitations': {'held': invites['held'], 'total': invites['total'], 'pending': invites['pending'], 'processing': invites['processing'], 'sent': invites['sent'],
                        'skipped': invites['skipped'], 'failed': len(invites['failed'])},
        'invitation_failures': invites['failed'],
    }


def list_jobs(user: User, limit: int = 20) -> list[dict]:
    return [job_progress(job) for job in EmployeeImportJob.objects.filter(created_by=user)[:limit]]


def job_error_report(job: EmployeeImportJob) -> bytes:
    """The rows that could not be imported, as the same Excel error report the preview offers (non-sensitive columns only)."""
    results = [RowResult(row=e.row_number, values=e.values, errors=list(e.messages)) for e in job.errors.all()]
    return build_error_report(results)
