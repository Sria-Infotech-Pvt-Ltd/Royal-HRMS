from __future__ import annotations


def has_required_permission(user, codename: str) -> bool:
    """
    Scoped to voice_commands only. The codename itself must be held — by the seat the user holds or the company
    baseline — with NO full-access bypass: a voice command never gets more reach than the exact permission it needs.
    """
    from core.permissions import has_perm

    return has_perm(user, codename, full_access_bypass=False)
