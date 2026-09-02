"""
Shared approval-chain resolution for every two-stage (L1/L2) request
workflow — leave, attendance correction, work-from-home, and any future
one. Previously copy-pasted identically into apps/hrms/views/leave.py and
apps/attendance/services_hr_corrections.py; extracted here once a third
consumer (work-from-home) needed the exact same logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

if TYPE_CHECKING:
    from apps.accounts.models import OrgUnit, Role, User


def resolve_approver(role: 'Role | None', employee: 'User') -> 'User | None':
    """Resolve a Role FK to the actual User approver for a given employee."""
    if role is None:
        return None
    if role.can_manage_team:
        return getattr(employee, 'reporting_manager', None)
    return getattr(employee, 'hr', None)


def resolve_approval_chain(employee: 'User', workflow_type: str) -> tuple:
    """
    Return (l1_approver, l2_approver) for the given employee and workflow.
    Checks EmployeeApprovalOverride first, falls back to ApprovalWorkflowRule.
    """
    from apps.accounts.models import EmployeeApprovalOverride

    override = EmployeeApprovalOverride.objects.filter(
        employee=employee, workflow_type=workflow_type,
    ).first()
    if override:
        return override.l1_override, override.l2_override

    from core.cache_service import ApprovalWorkflowCacheService
    rule = ApprovalWorkflowCacheService.get_rule(workflow_type)
    if not rule:
        return None, None

    l1 = resolve_approver(rule.l1_approver_role, employee) if rule.l1_approver_role else None
    l2 = resolve_approver(rule.l2_approver_role, employee) if rule.l2_approver_role else None
    return l1, l2


def resolve_employee_department_name(employee: 'User') -> str:
    """Best available department-equivalent NAME for this employee, for
    callers that compare against a plain string list — e.g.
    LeavePolicy.applicable_departments (a JSON list of name strings), or
    a free-text department filter UI. Walks resolve_employee_org_unit_chain()
    (self-first) and returns the name of the nearest unit marked
    `is_department_level=True`; falls back to the raw employee.department
    string AS-IS if no unit in the chain is marked, or the employee holds
    no current Position. Never re-validates the string against a master
    table — `Department` is retired, and even before that this
    deliberately preserved whatever raw value was there rather than
    silently dropping an unrecognized one (see this session's own Piece A
    note on User.department being an unvalidated free string)."""
    from apps.accounts.models import OrgUnit

    chain_ids = resolve_employee_org_unit_chain(employee)
    if chain_ids:
        marked = {
            u.id: u.name
            for u in OrgUnit.objects.filter(id__in=chain_ids, is_department_level=True)
        }
        for unit_id in chain_ids:
            if unit_id in marked:
                return marked[unit_id]
    return employee.department or ''


def resolve_employee_org_unit_chief(employee: 'User') -> 'User | None':
    """The department-level approver for `employee` — whoever currently
    holds the 'chief' Position for the nearest unit in their chain
    (self-first, via resolve_employee_org_unit_chain()), not necessarily
    their immediate Org Unit — a sub-unit with no chief of its own
    inherits its parent's. Replaces the retired Department.manager concept
    used by separation approval's Manager stage. Returns None if the
    employee holds no current Position, or no unit in their chain has a
    currently-placed chief."""
    from apps.accounts.models import Placement

    today = timezone.localdate()
    for unit_id in resolve_employee_org_unit_chain(employee):
        chief_placement = (
            Placement.objects.filter(
                position__org_unit_id=unit_id, position__is_chief=True,
                effective_from__lte=today,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .select_related('employee')
            .first()
        )
        if chief_placement:
            return chief_placement.employee
    return None


def filter_queryset_by_department_name(qs, department_name: str, *, department_lookup: str = 'department'):
    """Narrow `qs` to rows belonging to `department_name` — for the
    attendance/assessments call sites that take a free-text department
    name off a filter UI (not an OrgUnit object) and apply a plain
    `qs.filter(department=department_name)` (or `employee__department=`
    for a queryset of a model with an `employee` FK to User).

    Preferred path: if `department_name` matches a real `OrgUnit` marked
    `is_department_level=True` (case-insensitively), resolve its members
    via `filter_users_by_org_unit()` (descendant-inclusive) and filter
    `qs` by that member-id set. Fallback: if nothing matches — the name
    was typed free-text and doesn't correspond to any marked unit — filter
    by the plain string as before (case-insensitively), so a typo'd or
    since-renamed name still behaves exactly as it did before this bridge
    existed, rather than silently matching nothing.

    `department_lookup` is the ORM path to the department string field
    relative to `qs`'s model: `'department'` when `qs` is a `User`
    queryset directly, `'employee__department'` when `qs`'s model has an
    `employee` FK to `User` instead.
    """
    from apps.accounts.models import OrgUnit, User

    unit = OrgUnit.objects.filter(name__iexact=department_name, is_department_level=True).first()
    if unit is None:
        return qs.filter(**{f'{department_lookup}__iexact': department_name})

    member_ids = filter_users_by_org_unit(User.objects.all(), unit).values_list('id', flat=True)
    if department_lookup == 'department':
        return qs.filter(id__in=member_ids)
    relation_prefix = department_lookup.rsplit('__', 1)[0]
    return qs.filter(**{f'{relation_prefix}_id__in': member_ids})


def employees_depending_on_department_flag(unit: 'OrgUnit') -> list:
    """Full names of every employee (in `unit`'s subtree) for whom
    `resolve_employee_department_name()` currently resolves to `unit.name`
    — i.e. `unit` is genuinely their nearest `is_department_level=True`
    ancestor right now, not just some unrelated unit that happens to be
    marked. Used to warn before un-marking a unit that's actually
    load-bearing for Leave Policy eligibility today, rather than letting
    that change go silent (see OrgUnitDetailView.put())."""
    from apps.accounts.models import User

    members = filter_users_by_org_unit(User.objects.all(), unit)
    return [u.full_name for u in members if resolve_employee_department_name(u) == unit.name]


def resolve_employee_org_unit_chain(employee: 'User') -> list:
    """The employee's current Position's OrgUnit id, plus every ancestor
    unit id walking up via OrgUnit.parent — self-inclusive, root-last.
    Used to check whether an OrgUnit-targeted announcement (or similar)
    should reach an employee placed in one of that unit's descendant
    sub-units, without needing to walk the tree downward from the target's
    side. Returns [] if the employee holds no current Position."""
    from apps.accounts.models import Placement

    today = timezone.localdate()
    placement = (
        Placement.objects.filter(employee=employee, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related('position__org_unit')
        .first()
    )
    if not placement:
        return []
    chain = []
    unit = placement.position.org_unit
    seen = set()
    while unit is not None and unit.id not in seen:
        chain.append(unit.id)
        seen.add(unit.id)
        unit = unit.parent
    return chain


def filter_users_by_org_unit(users_qs, org_unit: 'OrgUnit'):
    """Narrow a User queryset to current members of `org_unit` OR any of
    its descendant units — the reverse direction of
    resolve_employee_org_unit_chain() (that resolves ONE employee's chain
    of units; this finds every User belonging to a GIVEN unit's subtree,
    for recipient-resolution callers like announcement delivery). Only the
    Position-derived membership applies here — OrgUnit has no legacy
    string equivalent to fall back to."""
    from apps.accounts.models import OrgUnit, Placement

    today = timezone.localdate()
    unit_ids = {org_unit.id}
    frontier = [org_unit.id]
    while frontier:
        children = list(OrgUnit.objects.filter(parent_id__in=frontier).values_list('id', flat=True))
        frontier = [c for c in children if c not in unit_ids]
        unit_ids.update(frontier)

    member_ids = (
        Placement.objects.filter(position__org_unit_id__in=unit_ids, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .values_list('employee_id', flat=True)
    )
    return users_qs.filter(id__in=member_ids)
