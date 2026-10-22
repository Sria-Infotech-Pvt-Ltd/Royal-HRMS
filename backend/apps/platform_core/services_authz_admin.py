"""Phase 4 Task H — admin tools. All read-only except clone_position_access(); NO
impersonation ("login as") anywhere in this module, per Rule explicitly
repeated in Task H.4 and Section 6's MUST NOT DO."""
from __future__ import annotations

from apps.accounts.models import Permission, Position, PositionPermission, User
from apps.platform_core import services_authz as authz
from apps.platform_core.models import FieldPermission, PositionAssignment
from core.access import holders_of_position
from core.permissions import effective_permission_codenames


def who_can(codename: str) -> list[dict]:
    """Task H.2 — users who hold `codename`, and through which route
    (the position they hold, the company baseline, or an extra position assignment)."""
    from core.access import baseline_codenames, users_with_permission

    permission = Permission.objects.filter(codename=codename).first()
    if permission is None:
        return []
    results = []
    if codename in baseline_codenames():
        for user in User.objects.filter(is_active=True):
            results.append({'user_id': str(user.pk), 'email': user.email, 'via': 'baseline'})
        return results
    for user in User.objects.filter(users_with_permission(codename), is_active=True).distinct():
        results.append({'user_id': str(user.pk), 'email': user.email, 'via': 'position'})
    position_ids = set(PositionPermission.objects.filter(permission=permission).values_list('position_id', flat=True))
    for assignment in PositionAssignment.objects.filter(position_id__in=position_ids, is_active=True).select_related('user', 'position'):
        results.append({
            'user_id': str(assignment.user_id), 'email': assignment.user.email, 'via': 'position_assignment',
            'position': assignment.position.title, 'scope_type': assignment.scope_type,
        })
    return results


def what_can(user) -> dict:
    """Task H.3 — effective permissions, scopes, and field access, with
    the source of each."""
    from core.access import baseline_codenames, current_seat

    sources = []
    seat = current_seat(user)
    if seat is not None:
        for codename in PositionPermission.objects.filter(position=seat).values_list('permission__codename', flat=True):
            sources.append({'codename': codename, 'source': 'position', 'position': seat.title})
    baseline = baseline_codenames()
    for codename in sorted(baseline):
        sources.append({'codename': codename, 'source': 'baseline'})
    assignments = list(PositionAssignment.objects.filter(user=user, is_active=True).select_related('position'))
    for assignment in assignments:
        for codename in PositionPermission.objects.filter(position=assignment.position).values_list('permission__codename', flat=True):
            sources.append({'codename': codename, 'source': 'position_assignment', 'position': assignment.position.title, 'scope_type': assignment.scope_type})

    field_access = []
    for position_id in authz.positions_for_user(user):
        for fp in FieldPermission.objects.filter(position_id=position_id).select_related('entity', 'position'):
            field_access.append({'entity': fp.entity.code, 'field': fp.field_code, 'access': fp.access, 'position': fp.position.title})

    return {
        'is_full_access': authz.is_full_access(user),
        'permissions': sources,
        'effective_codenames': effective_permission_codenames(user),
        'field_access': field_access,
        'assignments': [
            {'position': a.position.title, 'scope_type': a.scope_type, 'scope_values': a.scope_values, 'effective_from': str(a.effective_from), 'effective_to': str(a.effective_to) if a.effective_to else None}
            for a in assignments
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


def clone_position_access(source: Position, target: Position, *, include_field_permissions: bool = True, actor=None) -> Position:
    """Task H.1 — copy one position's access (permissions, scope flags, optionally field permissions) onto another."""
    for position_permission in PositionPermission.objects.filter(position=source):
        PositionPermission.objects.get_or_create(
            position=target, permission=position_permission.permission, defaults={'granted_by': actor},
        )
    for flag in ('can_manage_team', 'can_manage_branch', 'exclude_from_payroll', 'exclude_from_headcount'):
        setattr(target, flag, getattr(source, flag))
    target.save(update_fields=['can_manage_team', 'can_manage_branch', 'exclude_from_payroll', 'exclude_from_headcount', 'updated_at'])
    if include_field_permissions:
        for fp in FieldPermission.objects.filter(position=source):
            FieldPermission.objects.get_or_create(
                position=target, entity=fp.entity, field_code=fp.field_code,
                defaults=dict(access=fp.access, condition=fp.condition, effective_from=fp.effective_from, effective_to=fp.effective_to),
            )
    return target


def compare_positions(position_a: Position, position_b: Position) -> dict:
    """Task H.1 — side-by-side comparison."""
    perms_a = set(PositionPermission.objects.filter(position=position_a).values_list('permission__codename', flat=True))
    perms_b = set(PositionPermission.objects.filter(position=position_b).values_list('permission__codename', flat=True))
    flags = ('can_manage_team', 'can_manage_branch')
    return {
        'only_in_a': sorted(perms_a - perms_b),
        'only_in_b': sorted(perms_b - perms_a),
        'in_both': sorted(perms_a & perms_b),
        'attributes': {
            'a': {flag: getattr(position_a, flag) for flag in flags},
            'b': {flag: getattr(position_b, flag) for flag in flags},
        },
    }


__all__ = ['who_can', 'what_can', 'simulate', 'clone_position_access', 'compare_positions', 'holders_of_position']
