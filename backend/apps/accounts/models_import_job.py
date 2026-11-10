"""
A bulk employee import as a durable background job, plus its row-level errors.

The browser confirms an import and immediately gets a job id back; Celery workers then create the employees in short database
transactions ("commit batches"). `next_row` is the recovery checkpoint and is advanced INSIDE the same transaction that creates the
employees of that batch, so after a worker crash, a Redis outage or a restart the job resumes at exactly the first row that has not
been committed: nobody is created twice and nobody is skipped.

The uploaded workbook is kept in `content` only while the job needs it and is cleared as soon as the job finishes. Row-level errors
keep only the non-sensitive core columns (the same ones the downloadable error report shows) and are purged after the retention
period. The job id is also the `batch_id` of the invitations (EmployeeImportInvite), so progress covers both.
"""
from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

STATUS_QUEUED = 'queued'
STATUS_RUNNING = 'running'
STATUS_COMPLETED = 'completed'
STATUS_COMPLETED_WITH_ERRORS = 'completed_with_errors'
STATUS_FAILED = 'failed'
STATUS_CANCELLED = 'cancelled'
ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_RUNNING)
TERMINAL_STATUSES = (STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS, STATUS_FAILED, STATUS_CANCELLED)


class EmployeeImportJob(models.Model):
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'), (STATUS_RUNNING, 'Running'), (STATUS_COMPLETED, 'Completed'),
        (STATUS_COMPLETED_WITH_ERRORS, 'Completed with errors'), (STATUS_FAILED, 'Failed'), (STATUS_CANCELLED, 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)         # also the batch_id of the invitations
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    file_name = models.CharField(max_length=255, blank=True)
    file_sha256 = models.CharField(max_length=64, db_index=True)
    content = models.BinaryField(editable=False, default=bytes)                          # cleared when the job finishes
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    total_rows = models.PositiveIntegerField(default=0)
    next_row = models.PositiveIntegerField(default=0, help_text='Recovery checkpoint: rows already committed (created or recorded as failed).')
    created_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    chunk_size = models.PositiveIntegerField(default=2000, help_text='Rows handled per Celery task run before the next run is queued.')
    commit_batch_size = models.PositiveSmallIntegerField(default=25, help_text='Rows per database transaction.')
    cancel_requested = models.BooleanField(default=False)
    stalls = models.PositiveSmallIntegerField(default=0, help_text='Consecutive failed runs at the same checkpoint.')
    failure_code = models.CharField(max_length=40, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True, help_text='A worker owns the job until then. If it dies the lease simply expires and the sweep re-queues the job.')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_import_jobs'
        ordering = ['-created_at']
        constraints = [
            # The same file cannot be imported twice at the same time (a double click, two tabs, a retry that raced the first).
            models.UniqueConstraint(fields=['file_sha256'], condition=Q(status__in=ACTIVE_STATUSES), name='uniq_active_import_job_per_file'),
        ]
        indexes = [models.Index(fields=['status', 'lease_until'], name='import_job_status_lease_idx'),
                   models.Index(fields=['created_by', 'created_at'], name='import_job_owner_idx')]

    def __str__(self) -> str:
        return f'import job {self.id} ({self.status})'


class EmployeeImportJobError(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(EmployeeImportJob, on_delete=models.CASCADE, related_name='errors')
    row_number = models.PositiveIntegerField()
    messages = models.JSONField(default=list)
    values = models.JSONField(default=dict, help_text='Non-sensitive core columns only.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_import_job_errors'
        ordering = ['row_number']
        constraints = [models.UniqueConstraint(fields=['job', 'row_number'], name='uniq_import_job_error_row')]

    def __str__(self) -> str:
        return f'row {self.row_number} of {self.job_id}'
