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
    today, via the current Placement) User.designation, and the nearest
    is_department_level unit in the holder's Org Unit chain (self-first —
    see services_approval.resolve_employee_department_name()) onto
    User.department, when one exists in that chain.

    Each half respects its own *_synced_from_position flag independently —
    designation_synced_from_position and department_synced_from_position —
    so a manual correction to one doesn't silently freeze sync on the
    other, unless force=True (an explicit assignment always wins for both)."""
    from apps.accounts.services_approval import resolve_employee_department_name

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

    if force or holder.department_synced_from_position:
        dept_name = resolve_employee_department_name(holder)
        if dept_name and (holder.department != dept_name or not holder.department_synced_from_position):
            holder.department = dept_name
            holder.department_synced_from_position = True
            update_fields += ['department', 'department_synced_from_position']

    if update_fields:
        holder.save(update_fields=[*update_fields, 'updated_at'])


def vacate_employee(employee: 'User') -> None:
    """Closes out any open Placement for `employee` (effective_to=today),
    freeing the seat. Deactivating/deleting an employee only ever flipped
    User.is_active — the Placement itself was left open indefinitely, so
    Position.holder / current_placement() kept resolving to the departed
    employee forever, permanently under-reporting that seat as filled.
    Call this from every place an employee is deactivated or deleted."""
    from apps.accounts.models import Placement

    open_placement = Placement.objects.filter(employee=employee, effective_to__isnull=True).first()
    if open_placement is None:
        return
    today = timezone.localdate()
    if open_placement.effective_from > today:
        # Never actually started (a future-dated assignment) — nothing to
        # vacate "as of today"; just drop it rather than writing a
        # effective_to before effective_from.
        open_placement.delete()
        return
    open_placement.effective_to = today
    open_placement.save(update_fields=['effective_to', 'updated_at'])


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
    and department (when the nearest is_department_level unit in the
    position's Org Unit chain resolves one) from the position. Returns the
    new Placement."""
    from apps.accounts.models import Placement

    with transaction.atomic():
        day_before = effective_from - timedelta(days=1)

        prior_on_seat = position.placements.filter(effective_to__isnull=True).first()

        # Already exactly this placement — same employee, same open-ended
        # start date already on this seat. Re-running the close-then-create
        # logic below would try to open a second placement on the same seat
        # starting the same day, which Placement.full_clean() correctly
        # rejects as an overlap (closing "the day before" an identical start
        # date produces an inverted effective_to < effective_from window).
        # A real caller hits this whenever a position is confirmed twice for
        # the same hire — e.g. Add Employee assigns the position at creation
        # time, then Onboarding Approval re-submits that same position for
        # the same employee/date to (re-)derive designation/department.
        if (
            prior_on_seat is not None
            and prior_on_seat.employee_id == employee.id
            and prior_on_seat.effective_from == effective_from
            and effective_to is None
        ):
            placement = prior_on_seat
        else:
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
