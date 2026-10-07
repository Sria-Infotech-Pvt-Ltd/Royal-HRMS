"""
Phase 5B Task A.4 — reads EMPLOYMENT_TYPE/EMPLOYMENT_STATUS behavior
attributes (seeded by seed_employment_lookups) instead of comparing
`User.employee_type`/`employment_status` strings against hardcoded
literals. Additive: callers opt in to these functions; no existing code
comparing `employee_type == 'Permanent'` was rewritten in this phase (that
sweep is Task A.4's own "list every change" follow-through, deferred
alongside Task L — see PHASE5B_REPORT.md).

Resolution is by the CURRENT CharField value (`employee.employee_type`,
a legacy display string like "Permanent"), matched against each
LookupValue's `attributes['legacy_value']` — not by a new FK column,
since Task A.3's actual column migration is deferred.
"""
from __future__ import annotations

from django.core.cache import cache


def _lookup_attrs_by_legacy_value(lookup_code: str) -> dict:
    cache_key = f'employment_lookup_attrs:{lookup_code}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    from apps.platform_core.models import LookupValue
    result = {
        value.attributes.get('legacy_value', ''): value.attributes
        for value in LookupValue.objects.filter(lookup_type__code=lookup_code, is_active=True)
    }
    cache.set(cache_key, result, 300)
    return result


def get_employment_type_attributes(employee_type: str) -> dict:
    """Returns the EMPLOYMENT_TYPE LookupValue's behavior attributes for a
    `User.employee_type` display string (e.g. 'Permanent'), or {} if no
    seeded lookup row matches (an unseeded/custom value — callers should
    treat an empty dict as "unknown, don't assume any behavior flag")."""
    return _lookup_attrs_by_legacy_value('EMPLOYMENT_TYPE').get(employee_type, {})


def get_employment_status_category(employment_status: str) -> str | None:
    """Returns the EMPLOYMENT_STATUS LookupValue's `status_category`
    (pre_joining/active/inactive/separated) for a `User.employment_status`
    code, or None if unmatched."""
    attrs = _lookup_attrs_by_legacy_value('EMPLOYMENT_STATUS').get(employment_status, {})
    return attrs.get('status_category')


def is_probation_applicable(employee_type: str) -> bool:
    return bool(get_employment_type_attributes(employee_type).get('probation_applicable', False))


def is_temporary_employment_type(employee_type: str) -> bool:
    return bool(get_employment_type_attributes(employee_type).get('is_temporary', False))
