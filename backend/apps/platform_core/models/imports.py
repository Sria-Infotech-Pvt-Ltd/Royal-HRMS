"""
Phase 2 Task I — import/export job tracking. The MODEL here is built to
the full spec (status machine, counts, error file, idempotency). The
EXECUTION in this phase is deliberately synchronous, not async Celery —
see services_import_export.py's own docstring and PHASE2_REPORT.md
"Deferred" for why.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from .fields import EntityDefinition

# The project-wide default storage (core.storage.ImageKitStorage) is
# deliberately write-only — it has no _open() implementation, because
# every OTHER upload in this codebase is only ever served back out via a
# signed .url() for the browser to fetch directly, never re-read by the
# server itself. An ImportJob's file is the opposite case: the server
# must parse it back (validate_job/commit_job), potentially more than
# once, so it needs a storage that actually supports reading. Local disk
# under MEDIA_ROOT, not the public media namespace — these are internal
# processing artifacts, not something any endpoint serves directly.
_import_storage = FileSystemStorage(location=str(settings.MEDIA_ROOT / 'platform_imports_private'))


class ImportJob(models.Model):
    MODE_CREATE = 'create'
    MODE_UPDATE = 'update'
    MODE_UPSERT = 'upsert'
    MODE_CHOICES = [(MODE_CREATE, 'Create'), (MODE_UPDATE, 'Update'), (MODE_UPSERT, 'Upsert')]

    STATUS_UPLOADED = 'uploaded'
    STATUS_VALIDATING = 'validating'
    STATUS_VALIDATED = 'validated'
    STATUS_COMMITTING = 'committing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_ROLLED_BACK = 'rolled_back'
    STATUS_CHOICES = [
        (STATUS_UPLOADED, 'Uploaded'), (STATUS_VALIDATING, 'Validating'), (STATUS_VALIDATED, 'Validated'),
        (STATUS_COMMITTING, 'Committing'), (STATUS_COMPLETED, 'Completed'), (STATUS_FAILED, 'Failed'),
        (STATUS_ROLLED_BACK, 'Rolled back'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='import_jobs')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_CREATE)
    key_field = models.CharField(max_length=64, blank=True, help_text='Field code used to match existing records for update/upsert.')

    file = models.FileField(upload_to='uploads/', storage=_import_storage, max_length=255)
    mapping = models.JSONField(default=dict, blank=True, help_text='{csv_column: field_code}')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPLOADED)

    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    error_file = models.FileField(upload_to='errors/', storage=_import_storage, max_length=255, null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0, help_text='0-100')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=100, blank=True, db_index=True)

    # Rollback (Task I.4) tracks newly CREATED records by id — restoring an
    # UPDATE/UPSERT's prior values would need the actual previous value
    # recorded in ChangeHistory, which services_attributes._log_attribute_change
    # does not currently capture (it logs 'old': None). Documented as a real
    # limitation in PHASE2_REPORT.md rather than built on a false premise:
    # rollback in this phase only undoes newly created rows.
    created_record_ids = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'platform_import_jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.entity_id} import {self.id} ({self.status})'


class ExportJob(models.Model):
    """Companion to ImportJob for Task I.5 — async export of any list
    view/filtered query, with an expiring download link."""
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_COMPLETED, 'Completed'), (STATUS_FAILED, 'Failed'), (STATUS_EXPIRED, 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='export_jobs')
    list_view = models.ForeignKey('platform_core.ListViewDefinition', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    filters = models.JSONField(default=dict, blank=True)
    file_format = models.CharField(max_length=10, default='xlsx')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    file = models.FileField(upload_to='platform_exports/', max_length=255, null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_export_jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.entity_id} export {self.id} ({self.status})'
