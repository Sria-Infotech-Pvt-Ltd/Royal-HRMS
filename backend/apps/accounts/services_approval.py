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
    from apps.accounts.models import Department, Role, User


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


def resolve_employee_department(employee: 'User') -> 'Department | None':
    """Which Department this employee belongs to, for anything still keyed
    off Department (e.g. the separation approval chain's manager stage).

    Prefers the employee's current Position's OrgUnit -> OrgUnit.department
    link (the Phase 3 migration bridge — see TEAMCONTEXT.md) when one
    exists; falls back to the legacy exact-string match on
    employee.department otherwise, since not every employee has been
    placed on a Position yet. This is the pattern every other
    Department-reading subsystem should reuse as they migrate in turn —
    consolidates what used to be 3 independent, identical
    Department.objects.filter(name=employee.department).first() copies in
    apps/hrms/{serializers,views/separation,views/separation_workflow}.py.
    """
    from apps.accounts.models import Department, Placement

    today = timezone.localdate()
    placement = (
        Placement.objects.filter(employee=employee, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related('position__org_unit__department')
        .first()
    )
    if placement and placement.position.org_unit.department_id:
        return placement.position.org_unit.department
    if not employee.department:
        return None
    return Department.objects.filter(name=employee.department).first()


def resolve_employee_department_name(employee: 'User') -> str:
    """Best available department NAME for this employee, for callers that
    compare against a plain string list rather than a Department FK — e.g.
    LeavePolicy.applicable_departments (a JSON list of Department name
    strings). Prefers the Position-derived OrgUnit.department link's name,
    same as resolve_employee_department(); falls back to the raw
    employee.department string AS-IS otherwise.

    Deliberately does NOT fall back through resolve_employee_department()
    itself for the legacy case — that function re-validates the string
    against the Department table and returns None if nothing matches,
    which would silently change eligibility results for any employee whose
    department string doesn't correspond to a real Department row (a real,
    known possibility — see this session's own Piece A note on
    User.department being an unvalidated free string). The string-list
    callers this feeds were already comparing the raw string directly and
    must keep doing so in the fallback case."""
    from apps.accounts.models import Placement

    today = timezone.localdate()
    placement = (
        Placement.objects.filter(employee=employee, effective_from__lte=today)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related('position__org_unit__department')
        .first()
    )
    if placement and placement.position.org_unit.department_id:
        return placement.position.org_unit.department.name
    return employee.department or ''


def filter_users_by_department(users_qs, department: 'Department'):
    """Narrow a User queryset to only members of `department` — the
    reverse direction of resolve_employee_department() (that resolves ONE
    employee's department; this finds every User belonging to a GIVEN
    department, for recipient-resolution callers like announcement
    delivery). Includes both the Position-derived membership (current
    Placement -> Position -> OrgUnit.department) and the legacy exact
    string match, since not every employee has been placed on a Position
    yet and both sets of members should be reachable."""
    from apps.accounts.models import Placement

    today = timezone.localdate()
    position_user_ids = (
        Placement.objects.filter(effective_from__lte=today, position__org_unit__department=department)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .values_list('employee_id', flat=True)
    )
    return users_qs.filter(Q(id__in=position_user_ids) | Q(department=department.name)).distinct()


def filter_queryset_by_department_name(qs, department_name: str, *, department_lookup: str = 'department'):
    """Narrow `qs` to rows belonging to `department_name` — for the ~9
    attendance/assessments call sites that take a free-text department
    name off a filter UI (not a `Department` object) and apply a plain
    `qs.filter(department=department_name)` (or `employee__department=`
    for a queryset of a model with an `employee` FK to User).

    Preferred path: if `department_name` matches a real `Department` row
    (case-insensitively), resolve its members via `filter_users_by_department`
    (Position-derived + legacy string, unioned) and filter `qs` by that
    member-id set. Fallback: if no real Department matches — the name was
    typed free-text and doesn't correspond to any row — filter by the
    plain string as before (case-insensitively), so a typo'd or
    since-renamed department name still behaves exactly as it did before
    this bridge existed, rather than silently matching nothing.

    `department_lookup` is the ORM path to the department string field
    relative to `qs`'s model: `'department'` when `qs` is a `User`
    queryset directly, `'employee__department'` when `qs`'s model has an
    `employee` FK to `User` instead.
    """
    from apps.accounts.models import Department, User

    dept = Department.objects.filter(name__iexact=department_name).first()
    if dept is None:
        return qs.filter(**{f'{department_lookup}__iexact': department_name})

    member_ids = filter_users_by_department(User.objects.all(), dept).values_list('id', flat=True)
    if department_lookup == 'department':
        return qs.filter(id__in=member_ids)
    relation_prefix = department_lookup.rsplit('__', 1)[0]
    return qs.filter(**{f'{relation_prefix}_id__in': member_ids})
