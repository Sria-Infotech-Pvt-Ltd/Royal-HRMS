"""Shared test-fixture helpers for creating access profiles/permissions/users.

Not a Django app module used at runtime — imported only by test modules
across apps (accounts, payroll, recruitment, attendance, ...).

Access follows the ORG CHART, not a Role: `make_role()` returns an `AccessProfile` (a plain description of the
access a seat should carry) and `make_user(..., role=profile)` places the new user in a seat that carries it. A
profile with no permissions and no scope flags (a plain employee) needs no seat — every employee already gets the
company baseline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from apps.accounts.models import OrgUnit, Permission, Placement, Position, PositionPermission, User

ACCESS_UNIT_NAME = 'Access Test Unit'
SEAT_FLAGS = ('can_manage_team', 'can_manage_branch', 'exclude_from_payroll', 'exclude_from_headcount')


@dataclass(eq=False)
class AccessProfile:
    """What access a test user's seat should carry. Mutate before calling make_user()."""
    name: str
    display_name: str
    permission_codenames: list[str] = field(default_factory=list)
    can_manage_team: bool = False
    can_manage_branch: bool = False
    exclude_from_payroll: bool = False
    exclude_from_headcount: bool = False

    def save(self) -> None:  # tests written for Role call .save() after tweaking flags — nothing to persist here
        return None

    @property
    def has_access(self) -> bool:
        return bool(self.permission_codenames) or any(getattr(self, flag) for flag in SEAT_FLAGS)


def make_role(
    name: str, display_name: str | None = None, permission_codenames=None,
    can_manage_team: bool = False, **flags,
) -> AccessProfile:
    return AccessProfile(
        name=name, display_name=display_name or name.replace('_', ' ').title(),
        permission_codenames=list(permission_codenames or []), can_manage_team=can_manage_team,
        **{flag: value for flag, value in flags.items() if flag in SEAT_FLAGS},
    )


def make_permission(codename: str) -> Permission:
    module, _, action = codename.partition('.')
    return Permission.objects.get_or_create(codename=codename, defaults={'module': module, 'action': action})[0]


def place_in_seat(user: User, profile: AccessProfile) -> Position:
    """Create a seat carrying `profile`'s access and place `user` in it from the start of time."""
    unit, _ = OrgUnit.objects.get_or_create(name=ACCESS_UNIT_NAME)
    seat = Position.objects.create(
        org_unit=unit, title=profile.display_name, grade='L1',
        **{flag: getattr(profile, flag) for flag in SEAT_FLAGS},
    )
    for codename in profile.permission_codenames:
        PositionPermission.objects.get_or_create(position=seat, permission=make_permission(codename))
    Placement.objects.create(position=seat, employee=user, effective_from=date(2000, 1, 1))
    return seat


def make_user(email: str, role: AccessProfile | None = None, password: str = 'TestPass123!', **extra) -> User:
    full_name = extra.pop('full_name', 'Test User')
    user = User.objects.create_user(email=email, password=password, full_name=full_name, **extra)
    if role is not None and role.has_access:
        place_in_seat(user, role)
    return user
