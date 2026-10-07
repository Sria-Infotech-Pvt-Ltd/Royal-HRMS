"""
Phase 5B Task B — create/resolve effective-dated EmployeeRelationship
rows. Overlap ("no two open rows of a non-multiple type for the same
employee") is enforced here at the service layer, not as a DB exclusion
constraint — whether a type allows multiple concurrent rows
(`allow_multiple`) is an attribute of the LookupValue, not a column on
EmployeeRelationship itself, and Postgres exclusion constraints can only
reference columns on the constrained table. Same documented trade-off as
Phase 5A's Nomination share-total rule.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone


class RelationshipConflictError(Exception):
    pass


def _relationship_type(code: str):
    from apps.platform_core.models import LookupValue
    return LookupValue.objects.select_related('lookup_type').get(lookup_type__code='EMPLOYEE_RELATIONSHIP_TYPE', code=code)


def create_relationship(employee, relationship_type_code: str, related_employee, *,
                         effective_from, effective_to=None, source='manual'):
    """Creates a new EmployeeRelationship, closing/validating against any
    existing open row of the same (employee, type) unless that type's
    `allow_multiple` attribute is true."""
    from apps.accounts.models_relationships import EmployeeRelationship

    rel_type = _relationship_type(relationship_type_code)
    allow_multiple = bool(rel_type.attributes.get('allow_multiple', False))

    if not allow_multiple:
        overlapping = EmployeeRelationship.objects.filter(
            employee=employee, relationship_type=rel_type,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
        ).filter(
            Q(effective_from__lte=effective_to) if effective_to else Q()
        )
        if overlapping.exists():
            raise RelationshipConflictError(
                f'{employee} already has an open {relationship_type_code} relationship for that date range.'
            )

    return EmployeeRelationship.objects.create(
        employee=employee, relationship_type=rel_type, related_employee=related_employee,
        source=source, effective_from=effective_from, effective_to=effective_to,
    )


def resolve_relationship_as_of(employee, relationship_type_code: str, as_of=None):
    """The `related_employee` for (employee, type) effective on `as_of`
    (default: today) — a manual row covering that date wins; otherwise, if
    the type is configured `derived_from_org_chart`, falls back to
    `_resolve_org_chief_as_of()` (the chief of the nearest unit in the
    employee's org chain on that date), matching
    services_approval.resolve_employee_org_unit_chief()'s logic exactly
    but parametrized by date instead of always using today."""
    from apps.accounts.models_relationships import EmployeeRelationship

    as_of = as_of or timezone.localdate()
    rel_type = _relationship_type(relationship_type_code)

    manual = (
        EmployeeRelationship.objects.filter(
            employee=employee, relationship_type=rel_type, effective_from__lte=as_of,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related('related_employee')
        .order_by('-effective_from')
        .first()
    )
    if manual is not None:
        return manual.related_employee

    if rel_type.attributes.get('derived_from_org_chart'):
        return _resolve_org_chief_as_of(employee, as_of)
    return None


def _resolve_org_chief_as_of(employee, as_of):
    from apps.accounts.models import Placement

    placement = (
        Placement.objects.filter(employee=employee, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related('position__org_unit')
        .first()
    )
    if placement is None:
        return None

    unit = placement.position.org_unit
    chain = []
    while unit is not None:
        chain.append(unit.id)
        unit = unit.parent

    for unit_id in chain:
        chief_placement = (
            Placement.objects.filter(
                position__org_unit_id=unit_id, position__is_chief=True, effective_from__lte=as_of,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
            .select_related('employee')
            .first()
        )
        if chief_placement is not None:
            return chief_placement.employee
    return None
