"""Bumps the relevant metadata-cache namespace whenever a platform_core
model changes — see cache.py's own docstring for why this is a version
bump, not a per-key delete."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import (
    Country, Currency, ExchangeRate, FeatureFlag, FeatureFlagOverride,
    LegalEntity, LookupType, LookupValue, ModuleToggle, NumberSeries, Timezone,
    Translation,
)

_NAMESPACE_BY_MODEL = {
    Country: 'geo', Currency: 'geo', Timezone: 'geo', ExchangeRate: 'geo',
    LookupType: 'lookups', LookupValue: 'lookups', Translation: 'lookups',
    LegalEntity: 'entities',
    NumberSeries: 'numbering',
    FeatureFlag: 'flags', FeatureFlagOverride: 'flags', ModuleToggle: 'flags',
}


def _bump(sender, **kwargs):
    namespace = _NAMESPACE_BY_MODEL.get(sender)
    if namespace:
        metadata_cache.bump_version(namespace)


def connect():
    for model in _NAMESPACE_BY_MODEL:
        post_save.connect(_bump, sender=model, weak=False)
        post_delete.connect(_bump, sender=model, weak=False)
