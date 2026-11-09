"""Who may do / see what — resolved from the ORG CHART (the position a person holds today), not from a Role.

Three sources:
  * the seat the person holds today (Placement covering today on an active Position),
  * the company-wide BASELINE permissions every employee gets (self-service),
  * EXTRA permissions granted to that one person (EmployeePermission).
Plus the `is_superuser` flag on the person for full access.

Use these helpers for every access decision.
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


def has_seat_flag(user, flag: str) -> bool:
    """True if the user's seat carries the scope flag."""
    return _seat_flag(user, flag)


def holders_of_position(position_id):
    """Users who hold the given position today (a queryset, so callers can narrow it further)."""
    from apps.accounts.models import User

    return User.objects.filter(_covers_today('placements__'), placements__position_id=position_id).distinct()


def can_manage_team(user) -> bool:
    return has_seat_flag(user, 'can_manage_team')


def can_manage_branch(user) -> bool:
    return has_seat_flag(user, 'can_manage_branch')


def is_full_access(user) -> bool:
    """Only a superuser has full access. settings.edit gives Settings, not everything."""
    return bool(user and getattr(user, 'is_superuser', False))


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
    """Users holding `codename` through their seat, a personal grant, or the company baseline."""
    from apps.accounts.models import User

    if codename in baseline_codenames():
        return Q(**{f'{prefix}pk__isnull': False})
    through_seat = User.objects.filter(
        _covers_today('placements__'),
        placements__position__position_permissions__permission__codename=codename,
    ).values('pk')
    granted_personally = User.objects.filter(extra_permissions__permission__codename=codename).values('pk')
    return _pk_in(prefix, through_seat) | _pk_in(prefix, granted_personally)


def _users_with_flag(flag: str, prefix: str) -> Q:
    from apps.accounts.models import User

    through_seat = User.objects.filter(_covers_today('placements__'), **{f'placements__position__{flag}': True}).values('pk')
    return _pk_in(prefix, through_seat)


def team_managers(prefix: str = '') -> Q:
    return _users_with_flag('can_manage_team', prefix)


def branch_managers(prefix: str = '') -> Q:
    return _users_with_flag('can_manage_branch', prefix)


def excluded_from_payroll(prefix: str = '') -> Q:
    return _users_with_flag('exclude_from_payroll', prefix)


def excluded_from_headcount(prefix: str = '') -> Q:
    return _users_with_flag('exclude_from_headcount', prefix)


# ── Which employees an actor may act on ────────────────────────────────────────
# Default-deny: an actor with no valid scope matches nobody. Superuser is the only company-wide rule — settings.edit
# is deliberately NOT consulted here (it gives Settings, not every employee; see is_full_access above).
# employee_in_scope() (one employee) and employees_in_scope() (a User filter) implement the same rules.

def _is_saved(instance) -> bool:
    """A User() that was never saved already has a UUID pk, so look at the instance state, not the pk."""
    return bool(instance is not None and getattr(instance, 'pk', None) and not instance._state.adding)


def _actor_is_usable(actor) -> bool:
    return bool(_is_saved(actor) and getattr(actor, 'is_active', False))


def _branch_name(value) -> str:
    return value or ''


def _same_branch(actor_fk_id, actor_name: str, employee_fk_id, employee_name: str) -> bool:
    """Both branch FKs set => compare them. If either FK is null, fall back to legacy name equality, but only when
    both names are non-blank (a blank never matches a blank)."""
    if actor_fk_id and employee_fk_id:
        return actor_fk_id == employee_fk_id
    return bool(actor_name.strip()) and actor_name == employee_name


def _employee_branches(employee) -> list[tuple]:
    """(branch_fk_id, branch_name) pairs for the employee. A candidate still being onboarded has no branch of its own
    yet (it is copied over from the Candidate on approval), so the linked candidate's branch stands in for it."""
    if employee.branch_fk_id or employee.branch:
        return [(employee.branch_fk_id, _branch_name(employee.branch))]
    return [
        (candidate.branch_id, _branch_name(candidate.branch.branch_name if candidate.branch_id else ''))
        for candidate in employee.candidate_portal.select_related('branch')
    ]


def employee_in_scope(actor, employee) -> bool:
    """True if `actor` may act on `employee`. Rules, in order:
    1. unusable actor (missing / unsaved / inactive) or missing employee -> no
    2. superuser -> yes
    3. seat has can_manage_team -> only the actor's direct reports (even if the seat also manages a branch)
    4. same branch (branch_fk, legacy name only when an FK is null and both names are non-blank)
    5. otherwise no — including an actor with no branch.
    """
    if not _actor_is_usable(actor) or not _is_saved(employee):
        return False
    if is_full_access(actor):
        return True
    if can_manage_team(actor):
        return employee.reporting_manager_id == actor.pk
    actor_name = _branch_name(actor.branch)
    if not (actor.branch_fk_id or actor_name.strip()):
        return False
    return any(_same_branch(actor.branch_fk_id, actor_name, fk_id, name) for fk_id, name in _employee_branches(employee))


def employees_in_scope(actor) -> Q:
    """Q for User.objects.filter(...) matching exactly the employees employee_in_scope() allows. Joins the candidate
    relation, so callers that combine it with other filters should call .distinct()."""
    if not _actor_is_usable(actor):
        return Q(pk__in=[])
    if is_full_access(actor):
        return Q()
    if can_manage_team(actor):
        return Q(reporting_manager_id=actor.pk)
    actor_fk_id, actor_name = actor.branch_fk_id, _branch_name(actor.branch)
    if not (actor_fk_id or actor_name.strip()):
        return Q(pk__in=[])
    no_own_branch = Q(branch_fk__isnull=True, branch='')
    condition = Q(pk__in=[])
    if actor_fk_id:
        condition |= Q(branch_fk_id=actor_fk_id)
        if actor_name.strip():
            condition |= Q(branch_fk__isnull=True, branch=actor_name)
        condition |= no_own_branch & Q(candidate_portal__branch_id=actor_fk_id)
    else:
        condition |= Q(branch=actor_name)
        condition |= no_own_branch & Q(candidate_portal__branch__branch_name=actor_name)
    return condition
