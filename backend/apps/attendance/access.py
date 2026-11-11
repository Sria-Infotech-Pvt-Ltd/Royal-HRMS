"""
Who may see or manage other employees' attendance.

attendance.view / attendance.create are not enough on their own: ordinary
employees can hold both (they need them for their own punches, calendar and
correction requests), so they must never open up colleagues' records.

"Attendance staff" — may work with other employees' attendance, each within
their existing scope (apps.attendance.views.hr_attendance):
  * settings.edit (or superuser)  — whole company
  * branch admin (can_manage_branch) — their branch
  * manager (can_manage_team)     — their direct reports
  * HR holding attendance.edit    — their branch (or all when no branch is set)

Everyone else is an ordinary employee: their own attendance only, and no HR
attendance actions (create / edit / import / reprocess / assign ...).
"""
from __future__ import annotations

from core.permissions import has_perm


def is_attendance_staff(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False) or has_perm(user, 'settings.edit'):
        return True
    role = getattr(user, 'role', None)
    if role and (getattr(role, 'can_manage_team', False) or getattr(role, 'can_manage_branch', False)):
        return True
    return has_perm(user, 'attendance.edit')


def can_manage_attendance(user) -> bool:
    """HR attendance actions on other employees: attendance.create *and* staff."""
    return has_perm(user, 'attendance.create') and is_attendance_staff(user)
