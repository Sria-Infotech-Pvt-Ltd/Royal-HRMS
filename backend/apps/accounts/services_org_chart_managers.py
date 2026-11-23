"""
Keeps each employee's stored reporting manager (their L1 approver, "the immediate head") in step with the org chart.

The rule, in one place:
  - a manager someone chose by hand (reporting_manager set and reporting_manager_from_org_chart False) is never touched;
  - everyone else follows the org chart: the chief of the nearest org unit in their chain, walking up when their own unit has none
    (a head therefore reports to the head above). The head may be in any branch;
  - no seat in the org chart, or nobody placed as chief above them, means no manager (screens then say "Not assigned").

The stored value is a copy of what the org chart says, so it used to go stale: assigned once at hire, then left alone when a unit
got a new head or the person changed unit. This module recomputes it, and the receivers in signals.py call it whenever a
placement, a position or an org unit changes. The L2 (HR) approver is not part of this: it stays the HR person.
"""
from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import OrgUnit, Placement, User

logger = logging.getLogger(__name__)


def is_manually_assigned(employee: User) -> bool:
    """A manager somebody picked: stored, and not copied from the org chart."""
    return employee.reporting_manager_id is not None and not employee.reporting_manager_from_org_chart


def _current_placements(employee_ids) -> dict:
    today = timezone.localdate()
    rows = (
        Placement.objects.filter(employee_id__in=list(employee_ids), effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related('position')
    )
    found: dict = {}
    for placement in rows:
        found.setdefault(placement.employee_id, []).append(placement)
    return found


def _chief_for(employee: User, placements: list, page_cache: dict) -> User | None:
    from apps.accounts.services_approval import resolve_employee_org_unit_chief
    from apps.accounts.services_reporting_line import _chain_from_placement, _usable

    chain = _chain_from_placement(placements[0], page_cache) if placements else []
    chief = resolve_employee_org_unit_chief(employee, chain=chain, chief_cache=page_cache.setdefault('chiefs', {}))
    return chief if _usable(chief, employee) else None


def org_chart_manager_for(employee: User) -> User | None:
    """The immediate head the org chart gives this one employee today, or None."""
    return _chief_for(employee, _current_placements([employee.pk]).get(employee.pk, []), {})


def sync_employees(employees, *, dry_run: bool = False) -> list:
    """Bring each non-manually-assigned employee's stored manager in line with the org chart.

    Returns [(employee, old_manager_id, new_manager_id)] for every employee whose stored manager changed (or would, for a dry run)."""
    candidates = [employee for employee in employees if not is_manually_assigned(employee)]
    if not candidates:
        return []
    placements = _current_placements(employee.pk for employee in candidates)
    page_cache: dict = {}
    changes = []
    for employee in candidates:
        chief = _chief_for(employee, placements.get(employee.pk, []), page_cache)
        new_id, is_from_chart = (chief.pk if chief else None), chief is not None
        if employee.reporting_manager_id == new_id and employee.reporting_manager_from_org_chart == is_from_chart:
            continue
        changes.append((employee, employee.reporting_manager_id, new_id))
        if not dry_run:
            User.objects.filter(pk=employee.pk).update(
                reporting_manager=chief, reporting_manager_from_org_chart=is_from_chart, updated_at=timezone.now(),
            )
    return changes


def _units_with_descendants(unit_ids) -> set:
    children: dict = {}
    for unit_id, parent_id in OrgUnit.objects.values_list('id', 'parent_id'):
        children.setdefault(parent_id, []).append(unit_id)
    found, stack = set(), list(unit_ids)
    while stack:
        unit_id = stack.pop()
        if unit_id in found:
            continue
        found.add(unit_id)
        stack.extend(children.get(unit_id, []))
    return found


def resync_units(unit_ids, *, dry_run: bool = False) -> list:
    """Everyone currently seated in these org units or any unit below them (their chain runs through the changed units)."""
    units = _units_with_descendants(unit_ids)
    today = timezone.localdate()
    seated = (
        Placement.objects.filter(position__org_unit_id__in=units, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .values_list('employee_id', flat=True)
    )
    return sync_employees(User.objects.filter(pk__in=list(seated), is_active=True), dry_run=dry_run)


def resync_all(*, dry_run: bool = False) -> list:
    """Every active employee whose manager is not hand-picked: blank, or copied from the org chart earlier."""
    employees = (
        User.objects.filter(is_active=True).exclude(employee_id='')
        .filter(Q(reporting_manager__isnull=True) | Q(reporting_manager_from_org_chart=True))
    )
    return sync_employees(employees, dry_run=dry_run)
