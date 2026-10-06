"""
Phase 1 Task F — generic change-history capture. A registry + signal
handlers that any model can opt into via `register()`; diffs are computed
by comparing pre_save's incoming instance against the row currently in
the database.

NOT yet wired to any existing production model in this phase (see
PHASE1_REPORT.md — registering it on live models like User/EmployeeProfile
is exactly the kind of change that needs its own dedicated, carefully
tested pass, not to be done as a side effect of building the mechanism).
Phase 1 registers it only on the new platform_core models themselves,
proving the mechanism works end-to-end.

Known limitation carried over from request_context.py: `actor` will be
None until the DRF-level actor-resolution gap noted there is closed.
"""
from __future__ import annotations

import hashlib
import hmac

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.platform_core import request_context

_registry: dict[type, dict] = {}


def register(model, *, include: list[str] | None = None, exclude: list[str] | None = None, sensitive: list[str] | None = None):
    """Call once per model, typically in that app's AppConfig.ready().
    `include`/`exclude` are field names (mutually exclusive — pass one);
    `sensitive` field values are masked (see _mask_value) rather than
    stored in clear."""
    _registry[model] = {
        'include': set(include) if include else None,
        'exclude': set(exclude) if exclude else set(),
        'sensitive': set(sensitive) if sensitive else set(),
    }
    pre_save.connect(_capture_update_or_create, sender=model, weak=False)
    post_save.connect(_flush_pending_signal, sender=model, weak=False)
    post_delete.connect(_capture_delete, sender=model, weak=False)


def _tracked_fields(model, config) -> list[str]:
    # `.attname`, not `.name` — for a ForeignKey, `.name` is "lookup_type"
    # (accessing it triggers a related-object fetch and returns a model
    # instance, which a JSONField cannot serialize); `.attname` is
    # "lookup_type_id" (the raw, JSON-safe column value). Identical to
    # `.name` for every non-FK field.
    all_fields = [f.attname for f in model._meta.fields if f.attname != 'id']
    if config['include'] is not None:
        return [f for f in all_fields if f in config['include'] or f.removesuffix('_id') in config['include']]
    return [f for f in all_fields if f not in config['exclude'] and f.removesuffix('_id') not in config['exclude']]


def _mask_value(value, is_sensitive: bool):
    if not is_sensitive or value in (None, ''):
        return value
    key = getattr(settings, 'FIELD_INDEX_HMAC_KEY', 'phase1-fallback-key').encode('utf-8')
    fingerprint = hmac.new(key, str(value).encode('utf-8'), hashlib.sha256).hexdigest()[:8]
    return f'***{fingerprint}'


def _write_entry(*, instance, action, changes, reason=''):
    # Import here, not at module load, to avoid a circular import between
    # this module and models.py (register() is typically called from an
    # AppConfig.ready(), which runs after models are loaded, but this
    # module itself gets imported earlier).
    from apps.platform_core.models import ChangeHistory

    ctx = request_context.get_context()
    ChangeHistory.objects.create(
        actor_id=ctx.actor_id,
        channel=ctx.channel,
        request_id=ctx.request_id,
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
        content_type=ContentType.objects.get_for_model(type(instance)),
        object_id=str(instance.pk),
        object_repr=str(instance)[:200],
        action=action,
        changes=changes,
        reason=reason,
    )


def _capture_update_or_create(sender, instance, **kwargs):
    config = _registry.get(sender)
    if config is None:
        return
    fields = _tracked_fields(sender, config)

    if instance.pk is None:
        # Create — nothing to diff against; record the initial values.
        changes = [
            {'field': f, 'old': None, 'new': _mask_value(getattr(instance, f, None), f in config['sensitive'])}
            for f in fields
        ]
        instance._platform_history_pending = ('create', changes)
        return

    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._platform_history_pending = ('create', [])
        return

    changes = []
    for f in fields:
        old_value = getattr(previous, f, None)
        new_value = getattr(instance, f, None)
        if old_value != new_value:
            is_sensitive = f in config['sensitive']
            changes.append({
                'field': f,
                'old': _mask_value(old_value, is_sensitive),
                'new': _mask_value(new_value, is_sensitive),
            })
    instance._platform_history_pending = ('update', changes) if changes else None


def _capture_delete(sender, instance, **kwargs):
    config = _registry.get(sender)
    if config is None:
        return
    _write_entry(instance=instance, action='delete', changes=[])


def _flush_pending_signal(sender, instance, **kwargs):
    flush_pending(instance)


def flush_pending(instance):
    """Call from the model's post_save (or have the base model do it) —
    writes whatever pre_save computed, now that instance.pk is guaranteed
    to exist. Kept as an explicit second step (rather than one pre_save
    write) so a create's real pk is captured correctly."""
    pending = getattr(instance, '_platform_history_pending', None)
    if not pending:
        return
    action, changes = pending
    if action == 'update' and not changes:
        return
    _write_entry(instance=instance, action=action, changes=changes)
    instance._platform_history_pending = None
