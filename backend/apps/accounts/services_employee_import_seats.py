"""
Seat allocation for the bulk employee import.

A row names an Org Unit and a designation (the seat title). Several seats may share that exact pair; each employee needs a
seat of their own, so a row gets the FIRST vacant seat of its pair and a seat already handed to an earlier row of the same
file is never handed out again. "First" is fixed (oldest seat, then id), so the preview and the commit agree.

Matching is exact on org unit and title (ignoring case and surrounding spaces): no similar title is ever substituted. When
no suitable seat is left the row fails with a clear message. Nothing here writes data.

lock_candidate_seats() is for the commit: it row-locks every seat a file could use, in a fixed order, so two imports of the
same designations take turns instead of choosing the same seat.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models.functions import Lower, Trim

from apps.accounts.models import Placement, Position, PositionPermission
from apps.accounts.services_access_guards import assignment_refusal

FULL_ACCESS_CODENAME = 'settings.edit'


def _key(unit: str, title: str) -> tuple[str, str]:
    return unit.strip().lower(), title.strip().lower()


@dataclass
class Allocation:
    position: Position | None = None
    error: str = ''


class SeatPool:
    """Every active seat, loaded once for a whole validation pass, plus the seats this pass has already handed out."""

    def __init__(self, importer):
        self.importer = importer
        self.by_title: dict[tuple[str, str], list[Position]] = {}
        for position in Position.objects.filter(is_active=True).select_related('org_unit').order_by('created_at', 'pk'):
            self.by_title.setdefault(_key(position.org_unit.name, position.title), []).append(position)
        self.org_units = {unit for unit, _title in self.by_title}
        self.full_access_ids = set(
            PositionPermission.objects.filter(permission__codename=FULL_ACCESS_CODENAME).values_list('position_id', flat=True))
        self.placement_ends: dict = {}
        for position_id, effective_to in Placement.objects.values_list('position_id', 'effective_to'):
            self.placement_ends.setdefault(position_id, []).append(effective_to)
        self.claimed: dict = {}  # seat id -> Excel row that was given it

    def has_org_unit(self, unit: str) -> bool:
        return unit.strip().lower() in self.org_units

    def _is_occupied(self, position: Position, joining) -> bool:
        """A seat has one holder at a time: any placement still open on the joining date (or later) occupies it."""
        return any(end is None or end >= joining for end in self.placement_ends.get(position.pk, []))

    def _refusal(self, position: Position, title: str) -> str:
        if position.pk in self.full_access_ids:
            return f'"{title}" carries full access and cannot be filled by import.'
        refusal = assignment_refusal(self.importer, None, position)
        return refusal.message if refusal else ''

    def allocate(self, unit: str, title: str, joining, row: int) -> Allocation:
        candidates = self.by_title.get(_key(unit, title), [])
        if not candidates:
            return Allocation(error=f'No active position "{title}" exists in org unit "{unit}".')
        refusal, occupied, taken_by = '', 0, None
        for position in candidates:
            if position.pk in self.claimed:
                taken_by = taken_by or self.claimed[position.pk]
                continue
            problem = self._refusal(position, title)
            if problem:
                refusal = refusal or problem
                continue
            if joining is not None and self._is_occupied(position, joining):
                occupied += 1
                continue
            self.claimed[position.pk] = row
            return Allocation(position=position)
        return Allocation(error=refusal or _shortage(unit, title, len(candidates), taken_by))


def _shortage(unit: str, title: str, total: int, taken_by) -> str:
    if total > 1:
        return (f'No vacant "{title}" position is left in org unit "{unit}": all {total} are occupied or already used by earlier '
                f'rows of this file. Ask an administrator to create more.')
    if taken_by:
        return f'The same position is used in row {taken_by}. A seat holds one employee.'
    return f'The position "{title}" is already occupied on that joining date. Each imported employee needs their own vacant seat.'


def lock_candidate_seats(rows: list[tuple[int, dict]]) -> None:
    """Row-lock every seat the file could be given. Call inside transaction.atomic(), before validating again.

    Locks are taken in primary-key order so two imports can never deadlock; the second one waits for the first to commit and
    then sees its seats as occupied.
    """
    units = {values.get('org_unit', '').strip().lower() for _row, values in rows} - {''}
    titles = {values.get('position', '').strip().lower() for _row, values in rows} - {''}
    if not units or not titles:
        return
    locked = (Position.objects.filter(is_active=True)
              .annotate(unit_key=Lower(Trim('org_unit__name')), title_key=Lower(Trim('title')))
              .filter(unit_key__in=units, title_key__in=titles)
              .order_by('pk').select_for_update(of=('self',)))
    list(locked.values_list('pk', flat=True))  # evaluating the query is what takes the locks
