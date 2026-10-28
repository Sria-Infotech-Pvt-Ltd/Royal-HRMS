"""
Org-unit clean-up tools: a read-only report that lists every unit with its numbers and probable duplicates, and a merge that moves
one unit's employees and positions into another from a mapping the business has approved.

Nothing here decides what to merge. The report only suggests (by name similarity); the merge needs an explicit source -> target
mapping, defaults to a dry run, and writes an audit entry for every unit it merges. A merged unit is deactivated, never deleted:
its history (placements, past positions) is a compliance record.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.models import AuditLog, OrgUnit, Placement, Position
from apps.accounts.services_placement import sync_from_position

SIMILARITY_THRESHOLD = 0.8
_STOP_WORDS = {'and', 'of', 'the', 'team', 'dept', 'department', 'unit', 'division'}


class OrgUnitMergeError(Exception):
    """The mapping is not safe to run; nothing was changed."""


# ─── Report ──────────────────────────────────────────────────────────────────

def _tokens(name: str) -> frozenset:
    return frozenset(re.findall(r'[a-z0-9]+', name.lower())) - _STOP_WORDS


def names_look_alike(first: str, second: str) -> bool:
    """Similar spelling, or one name's words are all inside the other's ('Development' / 'Application Development')."""
    a, b = first.strip().lower(), second.strip().lower()
    if SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD:
        return True
    tokens_a, tokens_b = _tokens(first), _tokens(second)
    return bool(tokens_a and tokens_b and (tokens_a <= tokens_b or tokens_b <= tokens_a))


def build_org_unit_report() -> list[dict]:
    """One row per unit: id, name, parent, employee_count, position_count, vacancy_count, probable_duplicates (names)."""
    today = timezone.localdate()
    current_placement = Placement.objects.filter(
        position=OuterRef('pk'), effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
    positions = Position.objects.filter(is_active=True).annotate(is_filled=Exists(current_placement))

    employees_by_unit, positions_by_unit, vacancies_by_unit = {}, {}, {}
    for position in positions.only('org_unit_id'):
        unit_id = position.org_unit_id
        positions_by_unit[unit_id] = positions_by_unit.get(unit_id, 0) + 1
        if position.is_filled:
            employees_by_unit[unit_id] = employees_by_unit.get(unit_id, 0) + 1
        else:
            vacancies_by_unit[unit_id] = vacancies_by_unit.get(unit_id, 0) + 1

    units = list(OrgUnit.objects.select_related('parent').order_by('name'))
    rows = []
    for unit in units:
        duplicates = [other.name for other in units if other.pk != unit.pk and names_look_alike(unit.name, other.name)]
        rows.append({
            'id': str(unit.pk),
            'name': unit.name,
            'parent': unit.parent.name if unit.parent_id else '',
            'is_active': unit.is_active,
            'employee_count': employees_by_unit.get(unit.pk, 0),
            'position_count': positions_by_unit.get(unit.pk, 0),
            'vacancy_count': vacancies_by_unit.get(unit.pk, 0),
            'probable_duplicates': duplicates,
        })
    return rows


# ─── Merge ───────────────────────────────────────────────────────────────────

@dataclass
class MergeStep:
    source: OrgUnit
    target: OrgUnit
    positions_moved: int = 0
    employees_moved: int = 0
    children_reparented: int = 0
    chief_demoted: str = ''
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        extra = f'; the moved chief seat "{self.chief_demoted}" is no longer chief (target already has one)' if self.chief_demoted else ''
        return (f'{self.source.name} -> {self.target.name}: {self.positions_moved} position(s), {self.employees_moved} employee(s), '
                f'{self.children_reparented} child unit(s){extra}')


def _descendant_ids(unit: OrgUnit) -> set:
    found, frontier = set(), [unit.pk]
    while frontier:
        children = list(OrgUnit.objects.filter(parent_id__in=frontier).values_list('pk', flat=True))
        frontier = [pk for pk in children if pk not in found]
        found.update(children)
    return found


def _resolve(reference: str) -> OrgUnit:
    unit = OrgUnit.objects.filter(pk=reference).first() if re.fullmatch(r'[0-9a-fA-F-]{32,36}', reference) else None
    if unit is None:
        matches = list(OrgUnit.objects.filter(name__iexact=reference))
        if len(matches) > 1:
            raise OrgUnitMergeError(f'More than one org unit is named "{reference}"; use its id.')
        unit = matches[0] if matches else None
    if unit is None:
        raise OrgUnitMergeError(f'No org unit matches "{reference}".')
    return unit


def plan_merge(mapping: list[tuple[str, str]]) -> list[MergeStep]:
    """Validates the whole mapping up front; raises OrgUnitMergeError (and changes nothing) when any pair is unsafe."""
    steps = [MergeStep(source=_resolve(source), target=_resolve(target)) for source, target in mapping]
    sources = [step.source.pk for step in steps]
    for step in steps:
        if step.source.pk == step.target.pk:
            raise OrgUnitMergeError(f'"{step.source.name}" cannot be merged into itself.')
        if sources.count(step.source.pk) > 1:
            raise OrgUnitMergeError(f'"{step.source.name}" appears as a source more than once.')
        if step.target.pk in sources:
            raise OrgUnitMergeError(f'"{step.target.name}" is both a target and a source; run chained merges one at a time.')
        if step.target.pk in _descendant_ids(step.source):
            raise OrgUnitMergeError(f'"{step.target.name}" sits under "{step.source.name}"; merging a unit into its own child is not allowed.')
        if not step.target.is_active:
            raise OrgUnitMergeError(f'Target "{step.target.name}" is inactive.')
    return steps


def _count_employees(unit: OrgUnit) -> int:
    today = timezone.localdate()
    return Placement.objects.filter(position__org_unit=unit, effective_from__lte=today).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)).aggregate(n=Count('employee', distinct=True))['n']


def _apply_step(step: MergeStep, actor) -> None:
    source, target = step.source, step.target
    target_has_chief = Position.objects.filter(org_unit=target, is_chief=True).exists()
    moving = list(Position.objects.filter(org_unit=source))
    step.positions_moved = len(moving)
    step.employees_moved = _count_employees(source)
    for position in moving:
        if position.is_chief and target_has_chief:
            position.is_chief = False  # one chief per unit is a database rule; the target's chief stays
            step.chief_demoted = position.title
        position.org_unit = target
        position.save(update_fields=['org_unit', 'is_chief', 'updated_at'])
        sync_from_position(position, force=True)  # refresh the holder's department/designation text
    step.children_reparented = OrgUnit.objects.filter(parent=source).update(parent=target)
    source.is_active = False
    source.save(update_fields=['is_active', 'updated_at'])
    AuditLog.objects.create(
        user=actor, action='org_unit_merged', module='org_structure', object_id=str(source.pk),
        changes={
            'source': source.name, 'source_id': str(source.pk), 'target': target.name, 'target_id': str(target.pk),
            'positions_moved': step.positions_moved, 'employees_moved': step.employees_moved,
            'children_reparented': step.children_reparented, 'chief_demoted': step.chief_demoted,
        },
    )


def merge_org_units(mapping: list[tuple[str, str]], actor=None, dry_run: bool = True) -> list[MergeStep]:
    """Runs (or, by default, only previews) the approved mapping. All pairs are applied in one transaction, or none."""
    steps = plan_merge(mapping)
    if dry_run:
        for step in steps:
            step.positions_moved = Position.objects.filter(org_unit=step.source).count()
            step.employees_moved = _count_employees(step.source)
            step.children_reparented = OrgUnit.objects.filter(parent=step.source).count()
        return steps
    with transaction.atomic():
        for step in steps:
            _apply_step(step, actor)
    return steps
