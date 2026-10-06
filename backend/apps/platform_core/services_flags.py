"""Phase 1 Task H — feature flag / module toggle service."""
from __future__ import annotations

import hashlib

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import FeatureFlag, FeatureFlagOverride, ModuleToggle


def _stable_bucket(flag_code: str, user_id: int) -> int:
    """Deterministic 0-99 bucket for a (flag, user) pair — same user
    always lands in the same bucket for the same flag, so a rollout
    percentage doesn't flicker for someone between requests."""
    digest = hashlib.sha256(f'{flag_code}:{user_id}'.encode('utf-8')).hexdigest()
    return int(digest[:8], 16) % 100


def is_enabled(code: str, *, user=None, legal_entity=None) -> bool:
    def _load():
        return FeatureFlag.objects.filter(code=code).first()

    flag = metadata_cache.cached('flags', f'flag:{code}', _load)
    if flag is None:
        return False  # unknown flag — fail closed, never silently enable

    user_id = getattr(user, 'pk', None)
    entity_id = getattr(legal_entity, 'pk', legal_entity)

    overrides = FeatureFlagOverride.objects.filter(flag=flag).filter(
        models_or_none(user_id=user_id, role_id=getattr(getattr(user, 'role', None), 'pk', None), legal_entity_id=entity_id)
    )
    # Most specific override wins: user > role > legal_entity.
    user_override = next((o for o in overrides if o.user_id == user_id and user_id is not None), None)
    if user_override:
        return user_override.enabled
    role_id = getattr(getattr(user, 'role', None), 'pk', None)
    role_override = next((o for o in overrides if o.role_id == role_id and role_id is not None), None)
    if role_override:
        return role_override.enabled
    entity_override = next((o for o in overrides if o.legal_entity_id == entity_id and entity_id is not None), None)
    if entity_override:
        return entity_override.enabled

    if not flag.enabled:
        return False
    if flag.rollout_percentage >= 100 or user_id is None:
        return flag.enabled
    return _stable_bucket(code, user_id) < flag.rollout_percentage


def models_or_none(**kwargs):
    from django.db.models import Q
    q = Q(pk__in=[])  # start false
    for field, value in kwargs.items():
        if value is not None:
            q |= Q(**{field: value})
    return q


def is_module_enabled(module: str, legal_entity) -> bool:
    """Stored + exposed by API only in Phase 1 — NOT enforced anywhere.
    See ModuleToggle's own docstring."""
    def _load():
        return ModuleToggle.objects.filter(module=module, legal_entity=legal_entity).first()

    toggle = metadata_cache.cached('flags', f'module:{module}:{getattr(legal_entity, "pk", legal_entity)}', _load)
    return toggle.enabled if toggle else True  # no row yet = not toggled off
