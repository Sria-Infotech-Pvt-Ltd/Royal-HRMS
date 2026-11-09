"""
Who may be an employee's reporting manager, L1 approver or L2 HR approver, and how those assignments are saved.

One set of rules for every place that picks an approver (the hire wizard, the employee profile, the options list and the
approval-matrix API), so a dropdown only offers people a save will accept.

What is stored where (no new models):
  - reporting manager : User.reporting_manager (manual assignment; blank means "follow the org chart");
  - L1 approver       : EmployeeApprovalOverride.l1_override for the leave workflow (blank means "follow the approval rule");
  - L2 HR approver    : User.hr, the HR partner that the approval rules' "hr" kind resolves to.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import ApprovalWorkflowRule, AuditLog, EmployeeApprovalOverride, User
from core.access import can_manage_team, employees_in_scope, is_full_access, users_with_permission
from core.permissions import has_perm

KIND_REPORTING_MANAGER = 'reporting_manager'
KIND_L1 = 'l1'
KIND_L2_HR = 'l2'
KINDS = (KIND_REPORTING_MANAGER, KIND_L1, KIND_L2_HR)
APPROVER_PERMISSION = 'leave.approve'   # the capability the leave approval screens require of whoever acts on a request
LEAVE = ApprovalWorkflowRule.WORKFLOW_LEAVE
LABELS = {KIND_REPORTING_MANAGER: 'reporting manager', KIND_L1: 'L1 approver', KIND_L2_HR: 'L2 HR approver'}
FIELD_KINDS = {'reporting_manager_id': KIND_REPORTING_MANAGER, 'l1_approver_id': KIND_L1, 'hr_id': KIND_L2_HR}
_MAX_CHAIN_DEPTH = 100
_OPTION_SCAN_LIMIT = 300


class AssignmentError(Exception):
    """A choice that cannot be saved; `field` names the request key so the screen can show it beside the right box."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field, self.message = field, message


def _name(user: User) -> str:
    return user.full_name or user.email


def user_ref(user: User | None, *, detail: bool = True) -> dict | None:
    """What a screen shows for a person. `detail=False` is the employee-facing form: name and role only."""
    if user is None:
        return None
    ref = {'full_name': _name(user), 'role': user.designation or ''}
    if detail:
        ref.update({'id': str(user.pk), 'employee_id': user.employee_id, 'branch': user.branch, 'is_active': user.is_active})
    return ref


def _reports_up_to(candidate: User, employee: User) -> bool:
    cursor, depth = candidate.reporting_manager, 0
    while cursor is not None and depth < _MAX_CHAIN_DEPTH:
        if cursor.pk == employee.pk:
            return True
        cursor, depth = cursor.reporting_manager, depth + 1
    return False


def approver_refusal(candidate: User, employee: User | None, kind: str) -> str | None:
    """Why `candidate` cannot be `employee`'s `kind`, or None. `employee` is None for a hire that does not exist yet."""
    label, name = LABELS[kind], _name(candidate)
    if not candidate.is_active:
        return f'{name} is inactive and cannot be the {label}.'
    if not candidate.employee_id:
        return f'{name} has no employee record and cannot be the {label}.'
    if employee is not None and candidate.pk == employee.pk:
        return f'An employee cannot be their own {label}.'
    if kind != KIND_REPORTING_MANAGER and not has_perm(candidate, APPROVER_PERMISSION):
        return f'{name} cannot approve leave requests (missing {APPROVER_PERMISSION}), so cannot be the {label}.'
    if kind == KIND_REPORTING_MANAGER and employee is not None:
        if can_manage_team(employee):
            return 'Managers do not have a reporting manager.'
        if _reports_up_to(candidate, employee):
            return f'{name} already reports up to {_name(employee)}; this would create a reporting cycle.'
    return None


def approver_options(actor: User, kind: str, employee: User | None, search: str = '') -> list[dict]:
    """People `actor` may pick as `kind` for `employee`, each already checked against approver_refusal()."""
    pool = User.objects.filter(is_active=True).exclude(employee_id='')
    if employee is not None:
        pool = pool.exclude(pk=employee.pk)
    if kind != KIND_REPORTING_MANAGER:
        pool = pool.filter(users_with_permission(APPROVER_PERMISSION) | Q(is_superuser=True))
    if not is_full_access(actor):
        pool = pool.filter(employees_in_scope(actor))
    if search.strip():
        pool = pool.filter(Q(full_name__icontains=search.strip()) | Q(employee_id__icontains=search.strip()))
    people = [u for u in pool.select_related('reporting_manager').order_by('full_name')[:_OPTION_SCAN_LIMIT]
              if approver_refusal(u, employee, kind) is None]
    from apps.accounts.services_placement import org_unit_names_for
    units = org_unit_names_for([u.pk for u in people])
    return [{**user_ref(u), 'department': units.get(u.pk) or u.department} for u in people]


def _resolve(field: str, raw, employee: User | None) -> User | None:
    if raw in (None, ''):
        return None
    try:
        user = User.objects.filter(pk=raw).first()
    except (ValidationError, ValueError):
        user = None
    if user is None:
        raise AssignmentError(field, 'Selected person was not found.')
    refusal = approver_refusal(user, employee, FIELD_KINDS[field])
    if refusal:
        raise AssignmentError(field, refusal)
    return user


def validate_assignments(employee: User | None, data: dict) -> dict:
    """{field: User | None} for the keys present in `data`; raises AssignmentError on the first choice that cannot be saved."""
    return {field: _resolve(field, data[field], employee) for field in FIELD_KINDS if field in data}


def set_leave_l1_override(actor: User, employee: User, user: User | None) -> None:
    row, _ = EmployeeApprovalOverride.objects.get_or_create(employee=employee, workflow_type=LEAVE)
    row.l1_override, row.updated_by = user, actor
    row.save(update_fields=['l1_override', 'updated_by', 'updated_at'])
    if row.l1_override_id is None and row.l2_override_id is None:
        row.delete()   # nothing left to override: the approval rule applies again


def current_l1_override(employee: User) -> User | None:
    row = EmployeeApprovalOverride.objects.filter(employee=employee, workflow_type=LEAVE).select_related('l1_override').first()
    return row.l1_override if row else None


def assign_approvers(actor: User, employee: User, data: dict, *, ip_address: str | None = None) -> dict:
    """Validate then save the assignments present in `data`; returns {field: {'from': name, 'to': name}} for what changed."""
    resolved = validate_assignments(employee, data)
    before = {
        'reporting_manager_id': employee.reporting_manager,
        'hr_id': employee.hr,
        'l1_approver_id': current_l1_override(employee) if 'l1_approver_id' in resolved else None,
    }
    changes: dict = {}
    with transaction.atomic():
        update_fields = []
        if 'reporting_manager_id' in resolved:
            employee.reporting_manager, employee.reporting_manager_from_org_chart = resolved['reporting_manager_id'], False
            update_fields += ['reporting_manager', 'reporting_manager_from_org_chart']
        if 'hr_id' in resolved:
            employee.hr = resolved['hr_id']
            update_fields.append('hr')
        if update_fields:
            employee.save(update_fields=[*update_fields, 'updated_at'])
        if 'l1_approver_id' in resolved:
            set_leave_l1_override(actor, employee, resolved['l1_approver_id'])
        for field, new_user in resolved.items():
            old_user = before[field]
            if (old_user.pk if old_user else None) != (new_user.pk if new_user else None):
                changes[field] = {'from': _name(old_user) if old_user else None, 'to': _name(new_user) if new_user else None}
        if changes:
            AuditLog.objects.create(
                user=actor, action='approver_assignment_changed', module='accounts', object_id=str(employee.pk),
                changes={'employee': employee.employee_id, **changes}, branch=employee.branch or '', ip_address=ip_address,
            )
    return changes
