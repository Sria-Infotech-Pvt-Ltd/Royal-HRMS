"""Bumps the relevant metadata-cache namespace whenever a platform_core
model changes — see cache.py's own docstring for why this is a version
bump, not a per-key delete."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import (
    Country, Currency, ExchangeRate, FeatureFlag, FeatureFlagOverride,
    LegalEntity, LookupType, LookupValue, ModuleToggle, NumberSeries, Timezone,
    Translation, Policy, PolicyAssignment, RuleVersion, RoleAssignment, FieldPermission,
)

_NAMESPACE_BY_MODEL = {
    Country: 'geo', Currency: 'geo', Timezone: 'geo', ExchangeRate: 'geo',
    LookupType: 'lookups', LookupValue: 'lookups', Translation: 'lookups',
    LegalEntity: 'entities',
    NumberSeries: 'numbering',
    FeatureFlag: 'flags', FeatureFlagOverride: 'flags', ModuleToggle: 'flags',
    # Task D.4 — ANY policy/assignment/rule-version write invalidates every
    # cached resolution at once (see services_policies.py's own docstring
    # for why coarse-but-correct beats fine-grained-but-risky here).
    Policy: 'policies', PolicyAssignment: 'policies', RuleVersion: 'policies',
    # Phase 4 Task K.1 — same coarse-but-correct invalidation for cached
    # effective permissions. RolePermission (apps.accounts) also bumps
    # this namespace — see apps/accounts/signals.py.
    RoleAssignment: 'authz', FieldPermission: 'authz',
}


def _bump(sender, **kwargs):
    namespace = _NAMESPACE_BY_MODEL.get(sender)
    if namespace:
        metadata_cache.bump_version(namespace)


def connect():
    for model in _NAMESPACE_BY_MODEL:
        post_save.connect(_bump, sender=model, weak=False)
        post_delete.connect(_bump, sender=model, weak=False)
