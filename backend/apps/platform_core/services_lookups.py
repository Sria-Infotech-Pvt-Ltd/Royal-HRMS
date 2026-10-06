"""
Phase 1 Task D — lookup engine service layer. Every business module that
needs to validate/resolve a configurable value against a LookupType should
go through this module, not query LookupValue directly, so caching and
the applicability rules (country/legal_entity/effective dates) stay in
one place.
"""
from __future__ import annotations

import datetime

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import LookupValue


def _cache_suffix(type_code, country, legal_entity, include_inactive) -> str:
    return f'{type_code}:{country or "-"}:{legal_entity or "-"}:{include_inactive}'


def get_values(type_code: str, *, on_date=None, country=None, legal_entity=None, include_inactive: bool = False) -> list[LookupValue]:
    """Active (or all, if include_inactive) values for a lookup type,
    filtered by applicability. `country`/`legal_entity` may be a pk or an
    instance; `on_date` defaults to today for effective-date filtering."""
    suffix = _cache_suffix(type_code, getattr(country, 'pk', country), getattr(legal_entity, 'pk', legal_entity), include_inactive)

    def _load():
        qs = LookupValue.objects.filter(lookup_type__code=type_code).select_related('lookup_type')
        if not include_inactive:
            qs = qs.filter(is_active=True)
        if country is not None:
            qs = qs.filter(models_Q_country(country))
        if legal_entity is not None:
            qs = qs.filter(models_Q_entity(legal_entity))
        return list(qs.order_by('sort_order', 'label'))

    return metadata_cache.cached('lookups', suffix, _load)


def models_Q_country(country):
    from django.db.models import Q
    country_id = getattr(country, 'pk', country)
    return Q(country__isnull=True) | Q(country_id=country_id)


def models_Q_entity(legal_entity):
    from django.db.models import Q
    entity_id = getattr(legal_entity, 'pk', legal_entity)
    return Q(legal_entity__isnull=True) | Q(legal_entity_id=entity_id)


def is_valid(type_code: str, code: str, **kwargs) -> bool:
    if not code:
        return False
    return any(v.code == code for v in get_values(type_code, include_inactive=True, **kwargs))


def get_label(type_code: str, code: str, lang: str | None = None) -> str:
    """Translated label if one exists for `lang`, else the stored label,
    else the raw code (never raises for an unknown/legacy code)."""
    for v in get_values(type_code, include_inactive=True):
        if v.code == code:
            if lang:
                from apps.platform_core.models import Translation
                t = Translation.objects.filter(
                    app_label='platform_core', model_name='LookupValue',
                    object_id=str(v.pk), field='label', language=lang,
                ).first()
                if t:
                    return t.text
            return v.label
    return code


def get_attribute(type_code: str, code: str, key: str, default=None):
    for v in get_values(type_code, include_inactive=True):
        if v.code == code:
            return v.attributes.get(key, default)
    return default


def legacy_value_to_code(type_code: str, legacy_value: str) -> str | None:
    """Resolve an OLD stored lowercase/free-text value (e.g. 'male') back
    to its new UPPER_SNAKE code ('MALE') via each seeded value's
    attributes.legacy_value — the compatibility layer every pilot field
    conversion needs. Returns None if no match (unconverted field, or a
    genuinely unrecognised legacy value)."""
    for v in get_values(type_code, include_inactive=True):
        if v.attributes.get('legacy_value') == legacy_value:
            return v.code
    return None
