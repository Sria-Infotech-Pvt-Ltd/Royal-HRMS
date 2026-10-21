"""Who may do / see what — resolved from the ORG CHART (the position a person holds today), not from a Role.

Three sources, combined so nothing is ever taken away while Roles are being retired:
  * the seat the person holds today (Placement covering today on an active Position),
  * the company-wide BASELINE permissions every employee gets (self-service),
  * the legacy Role (removed in the last phase; the `_role_*` helpers below are the only code that touches it).

Use these helpers instead of reading `user.role...` or filtering `role__...` anywhere in the codebase.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

SEAT_FLAGS = ('can_manage_team', 'can_manage_branch', 'exclude_from_payroll', 'exclude_from_headcount')


# ── The seat a person holds today ──────────────────────────────────────────────

def _covers_today(prefix: str = '') -> Q:
    """Placement rows (reached through `prefix`) that are in force today, on an active position."""
    today = timezone.localdate()
    return (
        Q(**{f'{prefix}effective_from__lte': today, f'{prefix}position__is_active': True})
        & (Q(**{f'{prefix}effective_to__isnull': True}) | Q(**{f'{prefix}effective_to__gte': today}))
    )


def current_seat(user):
    """The Position `user` holds today, or None."""
    from apps.accounts.models import Position

    if not user or not getattr(user, 'pk', None):
        return None
    today = timezone.localdate()
    return (
        Position.objects.filter(is_active=True, placements__employee=user, placements__effective_from__lte=today)
        .filter(Q(placements__effective_to__isnull=True) | Q(placements__effective_to__gte=today))
        .first()
    )


def _seat_flag(user, flag: str) -> bool:
    seat = current_seat(user)
    return bool(seat and getattr(seat, flag))


def _role_flag(user, flag: str) -> bool:
    role = getattr(user, 'role', None)
    return bool(role and getattr(role, flag, False))


def has_seat_flag(user, flag: str) -> bool:
    """True if the user's seat (or, until roles are deleted, their role) carries the scope flag."""
    return _seat_flag(user, flag) or _role_flag(user, flag)


def can_manage_team(user) -> bool:
    return has_seat_flag(user, 'can_manage_team')


def can_manage_branch(user) -> bool:
    return has_seat_flag(user, 'can_manage_branch')


def is_full_access(user) -> bool:
    """Superuser, or holds settings.edit (the codebase's "can do everything" permission)."""
    from core.permissions import has_perm

    if not user:
        return False
    return bool(getattr(user, 'is_superuser', False) or _role_flag(user, 'is_full_access') or has_perm(user, 'settings.edit'))


# ── Permissions ────────────────────────────────────────────────────────────────

def baseline_codenames() -> set[str]:
    """Permissions every employee has regardless of seat (self-service). Edited in Settings."""
    from apps.accounts.models import BaselinePermission

    return set(BaselinePermission.objects.values_list('permission__codename', flat=True))


# ── "Everyone who ..." conditions (Q objects: use in filter() AND exclude()) ───
# `prefix` is the path from the model being queried to the User, e.g. 'employee__' for
# PayrollRecord.objects.filter(users_with_permission('x', 'employee__')).
# They match on pk__in subqueries so they behave the same inside exclude().

def _pk_in(prefix: str, ids) -> Q:
    return Q(**{f'{prefix}pk__in': ids})


def users_with_permission(codename: str, prefix: str = '') -> Q:
    """Users holding `codename` through their seat, the baseline, or (legacy) their role."""
    from apps.accounts.models import User

    if codename in baseline_codenames():
        return Q(**{f'{prefix}pk__isnull': False})
    through_seat = User.objects.filter(
        _covers_today('placements__'),
        placements__position__position_permissions__permission__codename=codename,
    ).values('pk')
    through_role = User.objects.filter(role__role_permissions__permission__codename=codename).values('pk')
    return _pk_in(prefix, through_seat) | _pk_in(prefix, through_role)


def _users_with_flag(flag: str, prefix: str) -> Q:
    from apps.accounts.models import User

    through_seat = User.objects.filter(_covers_today('placements__'), **{f'placements__position__{flag}': True}).values('pk')
    through_role = User.objects.filter(**{f'role__{flag}': True}).values('pk')
    return _pk_in(prefix, through_seat) | _pk_in(prefix, through_role)


def team_managers(prefix: str = '') -> Q:
    return _users_with_flag('can_manage_team', prefix)


def branch_managers(prefix: str = '') -> Q:
    return _users_with_flag('can_manage_branch', prefix)


def excluded_from_payroll(prefix: str = '') -> Q:
    return _users_with_flag('exclude_from_payroll', prefix)


def excluded_from_headcount(prefix: str = '') -> Q:
    return _users_with_flag('exclude_from_headcount', prefix)
