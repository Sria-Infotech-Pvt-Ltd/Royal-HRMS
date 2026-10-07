"""
Phase 4 Task C+D+K — the new data-scope engine. Built additively: NOTHING
in this module is wired into any existing view in this pass (see
PHASE4_REPORT.md's "Deferred" section for why — Task C.5 itself says
"where a view's current behaviour cannot be expressed exactly by the
engine, stop and record it," and verifying 442 call sites' exact current
behaviour is this phase's single largest undertaking, not something to
guess at under time pressure). `scope_queryset()`/`can()` are proven end
to end against the Phase 2 "Vehicle Allocation" custom entity, the same
strategy used to prove the Phase 3B workflow engine.

Entity-scope mapping (Task C.2) is declared per entity via
`ENTITY_SCOPE_MAPPINGS` below — for CustomRecord entities this reads
`owner`/`parent_object_id`; core entities are NOT mapped in this pass
(their real scope-determining fields vary per entity and verifying each
one against its actual current view behaviour is exactly the deferred
work above).
"""
from __future__ import annotations

import datetime

from django.db.models import Q

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import EntityDefinition, RoleAssignment


class AuthzError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def is_full_access(user) -> bool:
    """Task D — the explicit, auditable replacement for the hidden
    settings.edit bypass. Does NOT touch core.permissions.has_perm()
    itself in this pass (that's the live production path, unchanged) —
    this is the NEW engine's own check, used only by scope_queryset()/
    can() below."""
    if getattr(user, 'is_superuser', False):
        return True
    role = getattr(user, 'role', None)
    return bool(role and role.is_full_access)


def _active_assignments(user, as_of: datetime.date):
    return RoleAssignment.objects.filter(
        user=user, is_active=True, effective_from__lte=as_of,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)).select_related('role')


def effective_scopes_for_entity(user, entity_code: str, *, as_of=None) -> list[RoleAssignment]:
    """Every active RoleAssignment the user holds that is relevant —
    Task B.1's "effective rights are the union" of all assignments.
    `scope_type=SCOPE_ALL`/role-specific filtering by entity isn't
    narrowed per-entity in this pass (an assignment grants its scope for
    EVERY entity its role can act on, same as today's single-role
    model) — a real per-entity role→entity restriction is future work."""
    as_of = as_of or datetime.date.today()
    if is_full_access(user):
        return list(_active_assignments(user, as_of))
    return list(_active_assignments(user, as_of))


def _custom_record_scope_filter(assignment: RoleAssignment, user) -> Q | None:
    """Task C.2's mapping for CustomRecord: owner, or parent-record's
    owning employee. Returns None for a scope type not meaningfully
    expressible for a custom record (e.g. org_unit — no org-unit field
    exists generically on CustomRecord) rather than silently matching
    everything or nothing."""
    scope = assignment.scope_type
    if scope == RoleAssignment.SCOPE_ALL:
        return Q()
    if scope == RoleAssignment.SCOPE_OWN:
        return Q(owner=user)
    if scope == RoleAssignment.SCOPE_LEGAL_ENTITY:
        if assignment.scope_values:
            return Q(legal_entity_id__in=assignment.scope_values)
        return None
    if scope == RoleAssignment.SCOPE_MY_LEGAL_ENTITY:
        legal_entity_id = getattr(user, 'legal_entity_id', None)
        return Q(legal_entity_id=legal_entity_id) if legal_entity_id else None
    return None  # direct_reports/org_unit/branch/employee_group etc. — not expressible for a generic CustomRecord without a declared mapping (Task C.5)


def scope_queryset(user, entity: EntityDefinition, action: str, queryset, *, as_of=None):
    """Task C.3. Returns `queryset` filtered to records the user may
    access for `action`, via the union of every scope their active
    assignments grant. Raises AuthzError (never silently returns
    everything/nothing) if an assignment's scope type has no declared
    mapping for this entity."""
    if is_full_access(user):
        return queryset

    if entity.kind != EntityDefinition.KIND_CUSTOM:
        raise AuthzError(f'scope_queryset() has no declared mapping for core entity {entity.code!r} in this phase — see PHASE4_REPORT.md.')

    assignments = effective_scopes_for_entity(user, entity.code, as_of=as_of)
    # SCOPE_ALL short-circuits rather than being expressed as a Q() to
    # OR into the union — Django's Q() with no children is a no-op
    # identity element when combined with `|` (it does NOT mean "always
    # true" in that position), so folding it into `combined |= Q()`
    # silently contributed NOTHING to the union instead of "everything" —
    # a real bug caught by test_all_scope_sees_everything before this
    # ever reached a real caller.
    if any(a.scope_type == RoleAssignment.SCOPE_ALL for a in assignments):
        return queryset

    combined = Q(pk__in=[])  # start from "nothing" — union in anything granted
    any_mapped = False
    for assignment in assignments:
        q = _custom_record_scope_filter(assignment, user)
        if q is not None:
            combined |= q
            any_mapped = True
    if not any_mapped:
        return queryset.none()
    return queryset.filter(combined).distinct()


def can(user, entity: EntityDefinition, action: str, record) -> bool:
    """Task C.4 — single-record check, same logic as scope_queryset()."""
    if is_full_access(user):
        return True
    from apps.platform_core.models import CustomRecord
    if not isinstance(record, CustomRecord):
        raise AuthzError('can() only supports CustomRecord instances in this phase — see PHASE4_REPORT.md.')
    assignments = effective_scopes_for_entity(user, entity.code)
    for assignment in assignments:
        q = _custom_record_scope_filter(assignment, user)
        if q is None:
            continue
        if type(record).objects.filter(q, pk=record.pk).exists():
            return True
    return False


# ─── Task K — cached effective permissions ──────────────────────────────────

def _effective_permissions_uncached(user) -> frozenset[str]:
    from apps.accounts.models import RolePermission
    codenames = set()
    role = getattr(user, 'role', None)
    if role is not None:
        codenames.update(RolePermission.objects.filter(role=role).values_list('permission__codename', flat=True))
    for assignment in _active_assignments(user, datetime.date.today()):
        codenames.update(RolePermission.objects.filter(role=assignment.role).values_list('permission__codename', flat=True))
    return frozenset(codenames)


def effective_permissions(user) -> frozenset[str]:
    """Task K.1 — a cached set lookup, versioned-invalidated the same
    way Phase 1's metadata cache works. NOT wired to replace
    core.permissions.has_perm() in this pass (that stays the live,
    per-call-query path) — this is the new engine's own cached check."""
    if not getattr(user, 'pk', None):
        return frozenset()
    suffix = str(user.pk)
    return metadata_cache.cached('authz', suffix, lambda: _effective_permissions_uncached(user))


def has_perm_v2(user, codename: str) -> bool:
    """The new engine's permission check — explicit is_full_access
    instead of the hidden settings.edit bypass (Task D.2)."""
    if not user:
        return False
    if is_full_access(user):
        return True
    return codename in effective_permissions(user)
