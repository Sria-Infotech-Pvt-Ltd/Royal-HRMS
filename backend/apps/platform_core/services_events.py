"""
Phase 3B Task E.2 — event emission. `emit()` ALWAYS writes an
`EventOutbox` row inside the caller's transaction (so a rollback un-emits
it too) and schedules delivery via `transaction.on_commit` — matching
Phase 1's own `metadata_cache.bump_version` convention for "never act on
data that might get rolled back."

Scope cut, stated plainly: actual delivery in this phase is SYNCHRONOUS
(calling `drain_outbox()` inline via on_commit, not a real Celery task) —
same deferred-async reasoning as Phase 2's import/export and Phase 3A's
policy resolution. The `EventOutbox` table and its idempotent
status machine (pending -> processing -> sent/failed) are built to the
full spec so swapping in a real Celery task later is a one-line change
to what `on_commit` schedules, not a schema change.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.platform_core.models import EventOutbox, EventType


class EventError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def emit(code: str, payload: dict, *, actor=None, legal_entity=None) -> EventOutbox:
    event_type = EventType.objects.filter(code=code).first()
    if event_type is None:
        raise EventError(f'Unknown event type: {code!r}. Register it in event_types_registry.py first.')

    entry = EventOutbox.objects.create(event_type=event_type, payload=payload, actor=actor, legal_entity=legal_entity)
    transaction.on_commit(lambda: drain_outbox(limit=1, only_id=entry.pk))
    return entry


def drain_outbox(*, limit: int = 100, only_id=None) -> dict:
    """Task G.4 — also registered as a scheduled job type, so a Celery
    outage (nothing calls on_commit's inline drain because the process
    crashed before the callback ran, or a row was left PROCESSING by a
    crash) is recovered by the next scheduled drain, not lost. Processes
    each row inside its own transaction with select_for_update() so two
    concurrent drains (an on_commit callback AND a scheduled job racing)
    can never process the same row twice."""
    from apps.platform_core import services_notifications as notifications

    qs = EventOutbox.objects.filter(status=EventOutbox.STATUS_PENDING).order_by('created_at')
    if only_id:
        qs = qs.filter(pk=only_id)
    else:
        qs = qs[:limit]

    sent = failed = 0
    for entry_id in list(qs.values_list('pk', flat=True)):
        with transaction.atomic():
            entry = EventOutbox.objects.select_for_update(skip_locked=True).filter(pk=entry_id, status=EventOutbox.STATUS_PENDING).first()
            if entry is None:
                continue  # already claimed by a concurrent drain, or no longer pending
            entry.status = EventOutbox.STATUS_PROCESSING
            entry.attempts += 1
            entry.save(update_fields=['status', 'attempts'])
            try:
                notifications.dispatch_for_event(entry.event_type, entry.payload, actor=entry.actor, legal_entity=entry.legal_entity)
                entry.status = EventOutbox.STATUS_SENT
                entry.processed_at = timezone.now()
                entry.save(update_fields=['status', 'processed_at'])
                sent += 1
            except Exception as exc:
                entry.status = EventOutbox.STATUS_FAILED
                entry.last_error = str(exc)[:2000]
                entry.save(update_fields=['status', 'last_error'])
                failed += 1
    return {'sent': sent, 'failed': failed}
