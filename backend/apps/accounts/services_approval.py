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
