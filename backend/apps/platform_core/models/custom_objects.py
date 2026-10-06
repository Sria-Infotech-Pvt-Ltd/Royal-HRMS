"""Phase 2 Task E — admin-created custom objects (no runtime DDL: every
custom entity's records live in ONE real table, CustomRecord, keyed by
`entity` + a JSONB `data` column — never a new Django model/table per
custom entity)."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .phase1 import LegalEntity, LookupValue
from .fields import EntityDefinition


class CustomRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey(EntityDefinition, on_delete=models.PROTECT, related_name='records')
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    record_number = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=255, blank=True, help_text='Rendered from entity.title_template at save time.')

    data = models.JSONField(default=dict, blank=True)
    # Each published custom entity gets its own status LookupType
    # (Draft/Active/Closed defaults, admin-editable) — this just stores
    # whichever LookupValue code is current, not a hardcoded choices list.
    status = models.ForeignKey(LookupValue, on_delete=models.PROTECT, null=True, blank=True, related_name='+')

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_custom_records')
    parent_content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    parent_object_id = models.CharField(max_length=64, blank=True)
    layout_version = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_custom_records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entity', 'is_deleted'], name='pcr_entity_idx'),
            models.Index(fields=['parent_content_type', 'parent_object_id'], name='pcr_parent_idx'),
            # jsonb_path_ops GIN index on `data` added via a raw-SQL
            # migration operation (Postgres-specific — see migration
            # 0003), not expressible through plain Django field options.
        ]

    def __str__(self):
        return self.title or f'{self.entity_id}:{self.pk}'
