"""
Separation-of-duties guards for position (seat) based access.

Access follows the seat a person holds today (core.access / core.permissions). These guards stop a person from using the
screens that CHANGE access to enlarge their own, and stop a seat from being filled with more power than the person
filling it is allowed to hand out. They add no permission of their own: every check reuses core.permissions.has_perm,
core.access and the existing Placement dates.

Placement rule (placement_refusal), in order:
  1. nobody places themselves on a seat;
  2. a superuser or a `settings.edit` holder may fill any other seat. They can already edit any seat's permissions through
     PUT /org-structure/positions/<id>/permissions/, so a ceiling would only make administration impossible;
  3. everyone else may only fill a seat whose permissions they can grant: the permissions of THEIR OWN seat plus the
     company baseline. Personal extras do not count (they were given to the person, not to a seat they may hand on);
  4. a seat that manages a whole branch (`can_manage_branch`) needs the actor to hold that flag as well.
     `can_manage_team` is deliberately not enforced: it only exposes the holder's direct reports and HR fills manager
     seats every day. `exclude_from_*` flags only take access away, so they are not checked either.
"""
from __future__ import annotations

from typing import NamedTuple

from core.access import baseline_codenames, current_seat, has_seat_flag, holders_of_position
from core.permissions import has_perm

FULL_ACCESS_PERMISSION = 'settings.edit'
_LISTED_PERMISSIONS = 4  # how many codenames the refusal message names

# Permissions a non-full-access actor may only hand to someone through a hiring / editing workflow if their OWN seat (plus
# the company baseline) already holds them. Explicit codenames, no wildcards; every one exists in the permission catalogue
# (tests_assignment_guards.SensitivePermissionListTests checks that). Everyday HR permissions and `can_manage_team` are NOT here.
SENSITIVE_PERMISSIONS = frozenset({
    # 1. full access and permission administration
    'settings.edit', 'settings.view',
    'org_structure.create', 'org_structure.edit', 'org_structure.delete', 'org_structure.backdate',
    # 2. money and company-wide data (payroll.view_own is self-service and stays out)
    'payroll.create', 'payroll.edit', 'payroll.delete', 'payroll.export', 'payroll.view',
    'tax_declarations.approve', 'employees.view_sensitive', 'employees.view_workspace', 'employees.export',
    'employees.delete', 'dashboard.view_company_wide', 'reports.export',
    # 3. account takeover and oversight
    'employees.reset_password', 'facial_recognition.approve', 'audit.view', 'email_logs.view', 'email_logs.resend',
    'privacy.manage_dsr',
    # 4. company structure and branch scope (`branches.*` is enforced by the branch module; `branch.*` and `legal_entity.*`
    #    are catalogue entries with no enforcing endpoint today, listed so they cannot become a back door later)
    'branch.create', 'branch.edit', 'branch.delete', 'branch.export', 'branch.import', 'branch.view',
    'branches.create', 'branches.edit', 'branches.delete', 'branches.view',
    'legal_entity.create', 'legal_entity.edit', 'legal_entity.delete', 'legal_entity.export', 'legal_entity.import',
    'legal_entity.view',
})


def holds_position(user, position) -> bool:
    """True if `user` holds `position` today (an open Placement covering today, on an active position)."""
    return holders_of_position(position.pk).filter(pk=user.pk).exists()


def seat_codenames(position) -> set[str]:
    return set(position.position_permissions.values_list('permission__codename', flat=True))


def seat_carries_full_access(position) -> bool:
    return position.position_permissions.filter(permission__codename=FULL_ACCESS_PERMISSION).exists()


def is_full_access_actor(actor) -> bool:
    """May edit any seat's permissions (superuser, or `settings.edit` through their seat or a personal grant)."""
    return bool(actor.is_superuser or has_perm(actor, FULL_ACCESS_PERMISSION))


def grantable_codenames(actor) -> set[str]:
    """What `actor` may hand out by placing someone on a seat: their own seat's permissions plus the company baseline."""
    seat = current_seat(actor)
    own = seat_codenames(seat) if seat is not None else set()
    return own | baseline_codenames()


def placement_refusal(actor, employee, position) -> str | None:
    """Why `actor` may not place `employee` on `position`, or None when it is allowed."""
    if employee.pk == actor.pk:
        return 'You cannot assign yourself to a position.'
    if is_full_access_actor(actor):
        return None
    if seat_carries_full_access(position):
        return 'Only a full-access user can fill a position that carries full access.'
    excess = sorted(seat_codenames(position) - grantable_codenames(actor))
    if excess:
        shown = ', '.join(excess[:_LISTED_PERMISSIONS]) + (', ...' if len(excess) > _LISTED_PERMISSIONS else '')
        return f'You cannot assign this position: it carries permissions you cannot grant yourself ({shown}).'
    if position.can_manage_branch and not has_seat_flag(actor, 'can_manage_branch'):
        return 'You cannot assign this position: it manages a whole branch and your own position does not.'
    return None


class AssignmentRefusal(NamedTuple):
    status: int
    message: str


def assignment_refusal(actor, employee, position) -> AssignmentRefusal | None:
    """
    Why `actor` may not put `employee` on `position` through a hiring / editing workflow (not the placement screen, which has
    its own, stricter placement_refusal). `employee` is None for a person who does not exist yet (hire, create, import).
      * nothing new is granted when the person already holds this seat today, so a form that re-sends the current position
        is never refused;
      * nobody assigns themselves a different position (403);
      * a seat that carries full access (`settings.edit`) is for full-access actors only (400, like the sibling doors);
      * a seat carrying other SENSITIVE permissions (SENSITIVE_PERMISSIONS) or `can_manage_branch` needs the actor to hold them
        in their own seat (403). Everyday seats pass untouched.
    """
    if employee is not None and holds_position(employee, position):
        return None
    if employee is not None and employee.pk == actor.pk:
        return AssignmentRefusal(403, 'You cannot assign yourself to a position.')
    if is_full_access_actor(actor):
        return None
    if seat_carries_full_access(position):
        return AssignmentRefusal(400, f'"{position.title}" carries full access and can only be assigned by a full-access user.')
    sensitive = sensitive_assignment_refusal(actor, position)
    return AssignmentRefusal(403, sensitive) if sensitive else None


def sensitive_assignment_refusal(actor, position) -> str | None:
    """Why `actor` may not hand out the SENSITIVE part of `position`, or None. Full-access actors are exempt (they can already
    edit any seat's permissions). Everyone else needs every sensitive permission on the seat in their OWN seat or the company
    baseline (personal extras do not count), and the `can_manage_branch` flag if the seat carries it."""
    if is_full_access_actor(actor):
        return None
    excess = sorted((seat_codenames(position) & SENSITIVE_PERMISSIONS) - grantable_codenames(actor))
    if excess:
        shown = ', '.join(excess[:_LISTED_PERMISSIONS]) + (', ...' if len(excess) > _LISTED_PERMISSIONS else '')
        return f'You cannot assign this position: it carries sensitive permissions you do not hold yourself ({shown}).'
    if position.can_manage_branch and not has_seat_flag(actor, 'can_manage_branch'):
        return 'You cannot assign this position: it manages a whole branch and your own position does not.'
    return None


def anonymous_assignment_refusal(position) -> str | None:
    """For a change that has NO recorded human behind it (an employment action with neither creator nor applier): nobody is
    answerable for granting power, so such a change may only place someone on an everyday seat. Anything sensitive, full-access
    or branch-wide needs a person who holds it (or a full-access person) on record."""
    if seat_carries_full_access(position) or (seat_codenames(position) & SENSITIVE_PERMISSIONS) or position.can_manage_branch:
        return 'An action with no recorded creator or applier cannot place someone on a position with sensitive permissions.'
    return None


def seat_permission_refusal(actor, positions) -> str | None:
    """Why `actor` may not change the permissions of these positions: one of them is the seat the actor holds."""
    for position in positions:
        if holds_position(actor, position):
            return 'You cannot change the permissions of a position you hold yourself.'
    return None
