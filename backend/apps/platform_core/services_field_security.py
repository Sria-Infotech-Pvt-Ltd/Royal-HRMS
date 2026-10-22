"""
Phase 4 Task E — field-level security. `resolve_field_access()` and
`apply_field_security()` are the ONE place access level is computed and
enforced — built additively, not yet wired into the Phase 2 generic data
API/serializers/exports/history views/search/voice (see
PHASE4_REPORT.md). Proven directly against a custom entity's own
FieldDefinition.is_sensitive default (Task E.2).
"""
from __future__ import annotations

from apps.platform_core import services_rules as rules
from apps.platform_core.models import FieldPermission


class FieldSecurityError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _default_access(field_def, user) -> str:
    """Task E.2 — sensitive fields are masked by default for everyone
    unless granted otherwise; other fields default to read (never a
    silent "edit" default — that would silently widen access)."""
    if field_def.is_sensitive:
        return FieldPermission.ACCESS_MASKED
    return FieldPermission.ACCESS_READ


_ACCESS_RANK = {
    FieldPermission.ACCESS_HIDDEN: 0, FieldPermission.ACCESS_MASKED: 1,
    FieldPermission.ACCESS_READ: 2, FieldPermission.ACCESS_EDIT: 3,
}


def resolve_field_access(user, entity, field_def, *, context: dict | None = None) -> str:
    """Returns one of hidden/masked/read/edit for this (person, field).

    A person's grants come from the position they hold plus any extra positions assigned to them; when several
    apply, the most permissive one wins (the same union rule as permissions).
    """
    from apps.platform_core.services_authz import positions_for_user

    grants = FieldPermission.objects.filter(
        position_id__in=positions_for_user(user), entity=entity, field_code=field_def.code,
    )
    levels = [g.access for g in grants if not g.condition or rules.evaluate(g.condition, context or {})]
    if not levels:
        return _default_access(field_def, user)
    return max(levels, key=lambda level: _ACCESS_RANK[level])


def mask_value(value, field_def) -> str:
    """Task E.3's "returned in a masked format defined per field type
    (for example last 4 digits)"."""
    if value in (None, ''):
        return value
    text = str(value)
    if field_def.data_type in ('text', 'string') and len(text) > 4:
        return '*' * (len(text) - 4) + text[-4:]
    return '***'


def apply_field_security(user, entity, field_defs: list, values: dict, *, context: dict | None = None, for_write: bool = False) -> dict:
    """Applied to a {field_code: value} dict (the same shape
    services_attributes.read()/validate() already use) — hidden fields
    are dropped entirely; masked fields are replaced; read-only fields
    reject a write attempt (Task E.3's field-level 403)."""
    result = {}
    for field_def in field_defs:
        code = field_def.code
        if code not in values:
            continue
        access = resolve_field_access(user, entity, field_def, context=context)
        if access == FieldPermission.ACCESS_HIDDEN:
            continue
        if for_write:
            if access != FieldPermission.ACCESS_EDIT:
                raise FieldSecurityError(f'You do not have permission to edit "{field_def.label}".')
            result[code] = values[code]
            continue
        if access == FieldPermission.ACCESS_MASKED:
            result[code] = mask_value(values[code], field_def)
        else:
            result[code] = values[code]
    return result


def validate_filter_sort_fields(user, entity, field_defs_by_code: dict, *, filter_fields: list[str], sort_field: str | None) -> None:
    """Task E.3's "filtering or sorting by a hidden or masked field is
    rejected" — raises FieldSecurityError rather than silently dropping
    the filter (which could itself be a signal that leaks information:
    "my filter on X did nothing" vs. a clear "you cannot filter on X")."""
    for code in filter_fields:
        field_def = field_defs_by_code.get(code)
        if field_def is None:
            continue
        access = resolve_field_access(user, entity, field_def)
        if access in (FieldPermission.ACCESS_HIDDEN, FieldPermission.ACCESS_MASKED):
            raise FieldSecurityError(f'Cannot filter by "{field_def.label}" — this field is {access} for your position.')
    if sort_field:
        field_def = field_defs_by_code.get(sort_field.lstrip('-'))
        if field_def is not None:
            access = resolve_field_access(user, entity, field_def)
            if access in (FieldPermission.ACCESS_HIDDEN, FieldPermission.ACCESS_MASKED):
                raise FieldSecurityError(f'Cannot sort by "{field_def.label}" — this field is {access} for your position.')
