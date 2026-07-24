from __future__ import annotations


def has_required_permission(user, codename: str) -> bool:
    """
    Scoped to voice_commands only — deliberately not imported from any of the
    19 existing per-app `_has_perm` copies (accounts, assessments, attendance,
    branch, hrms, recruitment), since none of them are exported/importable
    (each is a private, file-local function) and their behavior isn't even
    consistent across apps (some add a system_admin bypass, one uses Django's
    built-in permission system instead of the custom Role/RolePermission
    tables). This follows the most common variant exactly, on purpose:

        if not user or not user.role: return False
        return user.role.role_permissions.filter(permission__codename=codename).exists()

    No system_admin bypass — a codename either exists on the role's
    RolePermission rows or it doesn't, same as most existing call sites
    (e.g. hrms/views/leave.py, hrms/views/expenses.py, branch/views_access.py).
    """
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()
