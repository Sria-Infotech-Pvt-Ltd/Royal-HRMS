"""
Who will approve an employee's request, stage by stage, described for people to read.

Used before a leave request is submitted (so nobody submits into a chain that cannot finish), on the employee dashboard, and
on the HR profile. It adds nothing to the decision itself: the approvers come from resolve_approval_chain(), the same function
the request is routed with, so what is shown is what will happen.
"""
from __future__ import annotations

from django.db.models import Q

from apps.accounts.models import EmployeeApprovalOverride, User
from apps.accounts.services_approval import resolve_approval_chain
from apps.accounts.services_approver_assignment import APPROVER_PERMISSION, LEAVE, user_ref
from apps.accounts.services_reporting_line import resolve_manager_with_source
from core.access import can_manage_team, users_with_permission
from core.permissions import has_perm

STAGE_ASSIGNED, STAGE_SKIPPED, STAGE_MISSING = 'assigned', 'skipped', 'missing'


def _name(user: User) -> str:
    return user.full_name or user.email


def _inactive_assignments(employee: User, workflow: str) -> dict[str, User]:
    """Approvers somebody assigned (an override, the HR partner, a manual reporting manager) who are no longer active."""
    from core.cache_service import ApprovalWorkflowCacheService

    found: dict[str, User] = {}
    override = EmployeeApprovalOverride.objects.filter(employee=employee, workflow_type=workflow).select_related('l1_override', 'l2_override').first()
    rule = ApprovalWorkflowCacheService.get_rule(workflow)
    manual_manager = employee.reporting_manager if rule and rule.l1_approver_kind == 'reporting_manager' and not employee.reporting_manager_from_org_chart else None
    hr_partner = employee.hr if rule and rule.l2_approver_kind == 'hr' else None
    candidates = {'l1': (override.l1_override if override else None) or manual_manager, 'l2': (override.l2_override if override else None) or hr_partner}
    for stage, person in candidates.items():
        if person is not None and not person.is_active:
            found[stage] = person
    return found


def _branch_pool_exists(employee: User) -> bool:
    """With no named HR approver, any leave approver in the employee's branch (or with no branch restriction) can decide the
    request: the same rule the approval screens use (leave_shared._can_hr_access_request)."""
    branch = (employee.branch or '').strip()
    pool = User.objects.filter(users_with_permission(APPROVER_PERMISSION), is_active=True).exclude(pk=employee.pk)
    return pool.filter(Q(branch__iexact=branch) | Q(branch='')).exists() if branch else pool.exists()


def _stage(stage: str, label: str, user: User | None, *, skipped: bool, inactive: User | None, detail: bool) -> dict:
    if skipped:
        return {'stage': stage, 'label': label, 'status': STAGE_SKIPPED, 'user': None,
                'note': "Managers' leave goes straight to HR."}
    if user is None:
        note = f'{_name(inactive)} is inactive and nobody else is assigned.' if inactive else 'Nobody is assigned.'
        return {'stage': stage, 'label': label, 'status': STAGE_MISSING, 'user': None, 'note': note}
    note = f'The assigned {label.lower()} ({_name(inactive)}) is inactive, so {_name(user)} will approve instead.' if inactive else ''
    return {'stage': stage, 'label': label, 'status': STAGE_ASSIGNED, 'user': user_ref(user, detail=detail), 'note': note}


def describe_chain(employee: User, workflow: str = LEAVE, *, detail: bool = False) -> dict:
    """The approval chain for `employee`: the reporting manager, each stage, warnings, and whether a request can be submitted.

    `can_submit` is False only when the request could never finish: nobody at all would decide it (no named approver and no
    leave approver in the employee's branch), or a named approver cannot act on it (no approval permission). Softer gaps
    (no L1, no L2) are warnings: the request still has a decider.
    """
    manager = resolve_manager_with_source(employee)
    l1, l2 = resolve_approval_chain(employee, workflow)
    skip_l1 = can_manage_team(employee)
    inactive = _inactive_assignments(employee, workflow)
    stages = [
        _stage('l1', 'L1 approver', l1, skipped=skip_l1, inactive=inactive.get('l1'), detail=detail),
        _stage('l2', 'L2 HR approver', l2, skipped=False, inactive=inactive.get('l2'), detail=detail),
    ]
    warnings, blocking = [], []
    for item, person in zip(stages, (l1, l2)):
        if item['status'] == STAGE_MISSING:
            warnings.append(f"{item['label']}: {item['note']}")
        elif item['note']:
            warnings.append(f"{item['label']}: {item['note']}")
        if person is not None and item['status'] == STAGE_ASSIGNED and not has_perm(person, APPROVER_PERMISSION):
            blocking.append(f"{item['label']} {_name(person)} cannot approve leave requests (missing {APPROVER_PERMISSION}). Ask HR to fix this first.")
    if stages[1]['status'] == STAGE_MISSING and _branch_pool_exists(employee):
        stages[1]['note'] = "No HR approver is named, so any leave approver in your branch can decide it."
        warnings = [w for w in warnings if not w.startswith('L2 HR approver: Nobody')] + [f"L2 HR approver: {stages[1]['note']}"]
    elif stages[0]['status'] != STAGE_ASSIGNED and stages[1]['status'] != STAGE_ASSIGNED:
        blocking.append('Nobody is available to approve this request. Ask HR to assign an approver first.')
    return {
        'workflow': workflow,
        'reporting_manager': {**(user_ref(manager.user, detail=detail) or {}), 'source': manager.source} if manager.user else None,
        'stages': stages,
        'warnings': warnings,
        'blocking': blocking,
        'can_submit': not blocking,
    }
