"""
Shared approval-chain resolution for every two-stage (L1/L2) request
workflow — leave, attendance correction, work-from-home, and any future
one. Previously copy-pasted identically into apps/hrms/views/leave.py and
apps/attendance/services_hr_corrections.py; extracted here once a third
consumer (work-from-home) needed the exact same logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import Role, User


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
