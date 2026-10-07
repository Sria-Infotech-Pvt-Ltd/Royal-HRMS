"""
Phase 3B Task G — database-backed scheduler. `JobType` is registered in
code (`job_types_registry.py`) — a DB row still exists per Task G.2's
"JobType catalogue" wording, synced the same idempotent way as
EntityDefinition/PolicyType/EventType, so admins can create
`ScheduledJob` rows that reference a `JobType.code` via FK.

Scope cut, stated plainly: this phase does NOT install `django-celery-
beat` or replace `settings.CELERY_BEAT_SCHEDULE` with a real Celery Beat
database scheduler backend — that's a dependency + deployment-config
change with its own migration/rollback risk. `ScheduledJob`/`JobRun` are
built to the full spec (cron/interval, timezone, locking, run history)
and `run_now()` executes a job type's registered callable directly and
synchronously; they are NOT yet wired as the actual source of truth
Celery Beat reads from. See PHASE3B_REPORT.md.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .phase1 import LegalEntity, TimestampedModel


class JobType(TimestampedModel):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    task_path = models.CharField(max_length=255, help_text='Dotted path to the registered callable (job_types_registry.JOB_CALLABLES key).')
    parameter_schema = models.JSONField(default=dict, blank=True)
    safe_to_run_concurrently = models.BooleanField(default=False)
    default_schedule = models.CharField(max_length=100, blank=True, help_text='Cron expression or interval description, for the seed pack.')
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_job_types'
        ordering = ['code']

    def __str__(self):
        return self.code


class ScheduledJob(TimestampedModel):
    SCHEDULE_CRON = 'cron'
    SCHEDULE_INTERVAL = 'interval'
    SCHEDULE_CHOICES = [(SCHEDULE_CRON, 'Cron'), (SCHEDULE_INTERVAL, 'Interval')]

    job_type = models.ForeignKey(JobType, on_delete=models.PROTECT, related_name='scheduled_jobs')
    name = models.CharField(max_length=150)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_CHOICES, default=SCHEDULE_CRON)
    cron_expression = models.CharField(max_length=100, blank=True)
    interval_seconds = models.PositiveIntegerField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default='Asia/Kolkata', help_text='IANA timezone name.')
    parameters = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    is_running = models.BooleanField(default=False, help_text='Locking flag — a job never runs twice at once unless its JobType allows concurrency.')

    class Meta:
        db_table = 'platform_scheduled_jobs'
        ordering = ['job_type', 'name']

    def __str__(self):
        return f'{self.job_type_id}:{self.name}'


class JobRun(models.Model):
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(STATUS_RUNNING, 'Running'), (STATUS_SUCCESS, 'Success'), (STATUS_FAILED, 'Failed')]

    TRIGGER_SCHEDULE = 'schedule'
    TRIGGER_ADMIN = 'admin_run_now'
    TRIGGER_SYSTEM = 'system'
    TRIGGER_CHOICES = [(TRIGGER_SCHEDULE, 'Schedule'), (TRIGGER_ADMIN, 'Admin run now'), (TRIGGER_SYSTEM, 'System')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_job = models.ForeignKey(ScheduledJob, on_delete=models.CASCADE, related_name='runs')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    triggered_by = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_SCHEDULE)
    triggered_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    result_counts = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True, help_text='No sensitive data — a short summary, never a full traceback with PII.')

    class Meta:
        db_table = 'platform_job_runs'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.scheduled_job_id} ({self.status})'
