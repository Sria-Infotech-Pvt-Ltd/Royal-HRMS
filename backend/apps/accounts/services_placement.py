"""
Position-assignment write path — the single place that creates a
`Placement` and keeps `User.designation`/`department` in sync with it.
Moved here from apps/accounts/views.py (formerly `_current_placement`/
`_sync_designation_from_position`, module-private helpers) once a second
consumer (Create Employee's Position picker) needed the exact same
auto-close-prior-placement logic that `PositionPlacementListCreateView`
already had, per this codebase's convention: business logic lives in
services, not views.
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

if TYPE_CHECKING:
    from apps.accounts.models import Placement, Position, User


def current_placement(position: 'Position', as_of=None) -> 'Placement | None':
    """The Placement occupying `position` on `as_of` (default: today), or
    None if the seat is vacant on that date."""
    as_of = as_of or timezone.localdate()
    return (
        position.placements
        .filter(effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related('employee')
        .first()
    )


def sync_from_position(position: 'Position', *, force: bool = False) -> None:
    """Push the Position's effective title onto its current holder's (as of
    today, via the current Placement) User.designation, and the position's
    OrgUnit's linked Department name onto User.department when that link
    exists (the OrgUnit<->Department bridge added in Phase 3 Stage 1).

    Each half respects its own *_synced_from_position flag independently —
    designation_synced_from_position and department_synced_from_position —
    so a manual correction to one doesn't silently freeze sync on the
    other, unless force=True (an explicit assignment always wins for both)."""
    current = current_placement(position)
    if current is None:
        return
    holder = current.employee
    update_fields = []

    if force or holder.designation_synced_from_position:
        effective_title = position.job_template.name if position.job_template_id else position.title
        if holder.designation != effective_title or not holder.designation_synced_from_position:
            holder.designation = effective_title
            holder.designation_synced_from_position = True
            update_fields += ['designation', 'designation_synced_from_position']

    if position.org_unit.department_id and (force or holder.department_synced_from_position):
        dept_name = position.org_unit.department.name
        if holder.department != dept_name or not holder.department_synced_from_position:
            holder.department = dept_name
            holder.department_synced_from_position = True
            update_fields += ['department', 'department_synced_from_position']

    if update_fields:
        holder.save(update_fields=[*update_fields, 'updated_at'])


def assign_position(
    employee: 'User', position: 'Position', *, effective_from, effective_to=None,
    note: str = '', created_by: 'User | None' = None,
) -> 'Placement':
    """Assigns `employee` to `position` starting `effective_from`. Closes
    whichever placement is currently open on that seat (turning "assign"
    and "reassign" into the same operation for the position side), AND
    whichever placement `employee` currently holds elsewhere — required
    because a company-wide "one active position per employee" rule is
    enforced at the DB level (`placement_employee_no_overlap`), so moving
    someone to a different seat would otherwise collide with their own
    still-open placement on the old one. Then syncs designation (always)
    and department (when the position's OrgUnit has one linked) from the
    position. Returns the new Placement."""
    from apps.accounts.models import Placement

    with transaction.atomic():
        day_before = effective_from - timedelta(days=1)

        prior_on_seat = position.placements.filter(effective_to__isnull=True).first()
        if prior_on_seat is not None and prior_on_seat.effective_from < effective_from:
            prior_on_seat.effective_to = day_before
            prior_on_seat.save(update_fields=['effective_to', 'updated_at'])

        prior_for_employee = (
            Placement.objects.filter(employee=employee, effective_to__isnull=True)
            .exclude(pk=getattr(prior_on_seat, 'pk', None))
            .first()
        )
        if prior_for_employee is not None and prior_for_employee.effective_from < effective_from:
            prior_for_employee.effective_to = day_before
            prior_for_employee.save(update_fields=['effective_to', 'updated_at'])

        placement = Placement(
            position=position, employee=employee,
            effective_from=effective_from, effective_to=effective_to,
            note=note, created_by=created_by,
        )
        placement.full_clean()  # friendly-path 400 for an overlap the pre-close above didn't resolve
        placement.save()

    sync_from_position(position, force=True)
    return placement
