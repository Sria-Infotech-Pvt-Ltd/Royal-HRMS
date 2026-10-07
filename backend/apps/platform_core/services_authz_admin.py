"""Phase 4 Task H — admin tools. All read-only except clone_role(); NO
impersonation ("login as") anywhere in this module, per Rule explicitly
repeated in Task H.4 and Section 6's MUST NOT DO."""
from __future__ import annotations

from apps.accounts.models import Permission, Role, RolePermission
from apps.platform_core import services_authz as authz
from apps.platform_core.models import FieldPermission, RoleAssignment


def who_can(codename: str) -> list[dict]:
    """Task H.2 — users who hold `codename`, and through which
    assignment (primary role vs. a RoleAssignment)."""
    permission = Permission.objects.filter(codename=codename).first()
    if permission is None:
        return []
    role_ids = set(RolePermission.objects.filter(permission=permission).values_list('role_id', flat=True))

    from apps.accounts.models import User
    results = []
    for user in User.objects.filter(role_id__in=role_ids, is_active=True):
        results.append({'user_id': str(user.pk), 'email': user.email, 'via': 'primary_role', 'role': user.role.name})
    for assignment in RoleAssignment.objects.filter(role_id__in=role_ids, is_active=True).select_related('user', 'role'):
        results.append({'user_id': str(assignment.user_id), 'email': assignment.user.email, 'via': 'role_assignment', 'role': assignment.role.name, 'scope_type': assignment.scope_type})
    return results


def what_can(user) -> dict:
    """Task H.3 — effective permissions, scopes, and field access, with
    the source of each."""
    sources = []
    role = getattr(user, 'role', None)
    if role is not None:
        for codename in RolePermission.objects.filter(role=role).values_list('permission__codename', flat=True):
            sources.append({'codename': codename, 'source': 'primary_role', 'role': role.name})
    for assignment in RoleAssignment.objects.filter(user=user, is_active=True).select_related('role'):
        for codename in RolePermission.objects.filter(role=assignment.role).values_list('permission__codename', flat=True):
            sources.append({'codename': codename, 'source': 'role_assignment', 'role': assignment.role.name, 'scope_type': assignment.scope_type})

    field_access = []
    roles_held = {role} if role else set()
    roles_held |= {a.role for a in RoleAssignment.objects.filter(user=user, is_active=True).select_related('role')}
    for r in roles_held:
        for fp in FieldPermission.objects.filter(role=r).select_related('entity'):
            field_access.append({'entity': fp.entity.code, 'field': fp.field_code, 'access': fp.access, 'role': r.name})

    return {
        'is_full_access': authz.is_full_access(user),
        'permissions': sources,
        'field_access': field_access,
        'assignments': [
            {'role': a.role.name, 'scope_type': a.scope_type, 'scope_values': a.scope_values, 'effective_from': str(a.effective_from), 'effective_to': str(a.effective_to) if a.effective_to else None}
            for a in RoleAssignment.objects.filter(user=user, is_active=True).select_related('role')
        ],
    }


def simulate(user, *, codename: str, entity=None, record=None) -> dict:
    """Task H.4 — "can user X do action Y on record Z, and what fields
    would they see" WITHOUT impersonation: this never logs in as the
    user, never issues them a session — it's a pure read-only
    evaluation using the same functions a real request would use,
    returning an explanation path."""
    has_permission = authz.has_perm_v2(user, codename)
    explanation = {'codename': codename, 'granted': has_permission, 'is_full_access': authz.is_full_access(user)}
    if entity is not None and record is not None:
        try:
            can_access_record = authz.can(user, entity, codename, record)
            explanation['can_access_this_record'] = can_access_record
        except authz.AuthzError as exc:
            explanation['can_access_this_record'] = None
            explanation['scope_error'] = exc.message
    return explanation


def clone_role(source_role: Role, *, new_name: str, new_display_name: str, include_field_permissions: bool = True, actor=None) -> Role:
    """Task H.1 — clone a role (with or without field permissions)."""
    clone = Role.objects.create(
        name=new_name, display_name=new_display_name,
        can_manage_team=source_role.can_manage_team, can_manage_branch=source_role.can_manage_branch,
        is_full_access=source_role.is_full_access, exclude_from_payroll=source_role.exclude_from_payroll,
        exclude_from_headcount=source_role.exclude_from_headcount,
    )
    for role_permission in RolePermission.objects.filter(role=source_role):
        RolePermission.objects.get_or_create(role=clone, permission=role_permission.permission)
    if include_field_permissions:
        for fp in FieldPermission.objects.filter(role=source_role):
            FieldPermission.objects.create(
                role=clone, entity=fp.entity, field_code=fp.field_code, access=fp.access,
                condition=fp.condition, effective_from=fp.effective_from, effective_to=fp.effective_to,
            )
    return clone


def compare_roles(role_a: Role, role_b: Role) -> dict:
    """Task H.1 — side-by-side comparison."""
    perms_a = set(RolePermission.objects.filter(role=role_a).values_list('permission__codename', flat=True))
    perms_b = set(RolePermission.objects.filter(role=role_b).values_list('permission__codename', flat=True))
    return {
        'only_in_a': sorted(perms_a - perms_b),
        'only_in_b': sorted(perms_b - perms_a),
        'in_both': sorted(perms_a & perms_b),
        'attributes': {
            'a': {'is_full_access': role_a.is_full_access, 'can_manage_team': role_a.can_manage_team, 'can_manage_branch': role_a.can_manage_branch},
            'b': {'is_full_access': role_b.is_full_access, 'can_manage_team': role_b.can_manage_team, 'can_manage_branch': role_b.can_manage_branch},
        },
    }
