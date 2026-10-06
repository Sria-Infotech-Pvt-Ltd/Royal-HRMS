"""
Phase 2 Task H — generic attachments. Uses the SAME storage backend
`CustomFieldFileValue` already uses (core.storage.AuthenticatedImageKitStorage)
— the Phase 2 prompt's own "facts about current code" section assumed a
`private_storage` alias that does not actually exist anywhere in this
codebase (verified by grep — zero hits). Using the real existing storage
class here instead of inventing a new alias. See PHASE2_REPORT.md.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from core.storage import AuthenticatedImageKitStorage

from .fields import FieldDefinition


def _attachment_path(instance, filename):
    import os
    import uuid as _uuid
    return os.path.join(
        'platform_attachments', instance.content_type.model, str(instance.object_id),
        f'{_uuid.uuid4().hex}_{os.path.basename(filename)}',
    )


class AttachmentValue(models.Model):
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    object_id = models.CharField(max_length=64)
    field = models.ForeignKey(FieldDefinition, on_delete=models.PROTECT, related_name='attachments')

    file = models.FileField(upload_to=_attachment_path, storage=AuthenticatedImageKitStorage(), max_length=255)
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100, blank=True)
    checksum = models.CharField(max_length=64, blank=True, help_text='SHA-256 of the file content.')

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_attachment_values'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='pav_object_idx'),
        ]

    def __str__(self):
        return self.original_name
