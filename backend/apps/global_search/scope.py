"""Who a viewer may see, expressed the way each existing module already decides it.

Global search must never show more than the module's own page does, so these mirror those rules instead of inventing new ones.
They are also default-deny: where a page falls back to "everyone" for a viewer with no branch and no team (an unconfigured
account), search shows nobody. A Q() with no conditions is an identity element under `|` (it does NOT mean "all"), so "all" is
spelled out as ALL here.
"""
from __future__ import annotations

from django.db.models import Q

from core.access import can_manage_team
from core.permissions import has_perm


def all_rows(prefix: str = '') -> Q:
    """An explicit always-true condition that still combines correctly with `|`."""
    return Q(**{f'{prefix}pk__isnull': False})


def no_rows(prefix: str = '') -> Q:
    return Q(**{f'{prefix}pk__in': []})


def employee_scope(user, prefix: str = '') -> Q:
    """The employees (User rows, reached through `prefix`, e.g. 'employee__') this viewer may see.

    Mirrors the Employee directory: settings.edit sees everyone; a team manager sees their direct reports; anyone else sees their
    own branch. A viewer with none of those sees nobody."""
    if has_perm(user, 'settings.edit'):
        return all_rows(prefix)
    if can_manage_team(user):
        return Q(**{f'{prefix}reporting_manager_id': user.pk})
    branch = (getattr(user, 'branch', '') or '').strip()
    if branch:
        return Q(**{f'{prefix}branch': branch})
    return no_rows(prefix)


def own_or_in_scope(user, employee_path: str, *, permission: str | None) -> Q:
    """A person's own rows, plus the rows of the employees they may see when they hold `permission` (None: never widen)."""
    own = Q(**{employee_path: user})
    if permission and has_perm(user, permission):
        return own | employee_scope(user, f'{employee_path}__')
    return own
