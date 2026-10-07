"""Phase 3B Task E — domain event catalogue and the outbox."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .fields import EntityDefinition
from .phase1 import LegalEntity, TimestampedModel


class EventType(TimestampedModel):
    code = models.CharField(max_length=100, unique=True, help_text='e.g. "leave.submitted", "workflow.task.assigned".')
    entity = models.ForeignKey(EntityDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name='event_types')
    module = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    # {"var_name": {"type": "string", "sensitive": false}, ...} — Task E.1.
    payload_schema = models.JSONField(default=dict, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_event_types'
        ordering = ['code']

    def __str__(self):
        return self.code

    def sensitive_vars(self) -> set[str]:
        return {name for name, spec in self.payload_schema.items() if spec.get('sensitive')}


class EventOutbox(TimestampedModel):
    """Task E.2 — guarantees no event is lost if the async worker is
    down: emit() always writes a row here (committed with the triggering
    transaction); a drain job processes pending rows idempotently
    (status flips PROCESSING->SENT only once, guarded by
    select_for_update(), so a crash mid-drain never double-delivers)."""
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_PROCESSING, 'Processing'), (STATUS_SENT, 'Sent'), (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name='outbox_entries')
    payload = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_event_outbox'
        ordering = ['created_at']
        indexes = [models.Index(fields=['status', 'created_at'], name='peo_status_created_idx')]

    def __str__(self):
        return f'{self.event_type_id} ({self.status})'
