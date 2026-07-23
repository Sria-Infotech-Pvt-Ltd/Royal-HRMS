"""Shared test-fixture helpers for creating roles/permissions/users.

Not a Django app module used at runtime — imported only by test modules
across apps (accounts, payroll, recruitment, attendance, ...).
"""
from __future__ import annotations

from apps.accounts.models import Permission, Role, RolePermission, User


def make_role(name: str, display_name: str | None = None, permission_codenames=None) -> Role:
    role, _ = Role.objects.get_or_create(
        name=name, defaults={'display_name': display_name or name.replace('_', ' ').title()},
    )
    for codename in (permission_codenames or []):
        module, _, action = codename.partition('.')
        perm, _ = Permission.objects.get_or_create(
            codename=codename, defaults={'module': module, 'action': action},
        )
        RolePermission.objects.get_or_create(role=role, permission=perm)
    return role


def make_user(email: str, role: Role | None = None, password: str = 'TestPass123!', **extra) -> User:
    full_name = extra.pop('full_name', 'Test User')
    return User.objects.create_user(
        email=email, password=password, full_name=full_name, role=role, **extra,
    )
