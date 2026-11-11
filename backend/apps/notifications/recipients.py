"""
Who to notify when a request reaches the HR stage with no specific HR
approver assigned (l2_approver is empty).

Mirrors who can act on such a request in the approval queues (leave:
apps.hrms.views.leave._approval_scope_filter; attendance:
apps.attendance.services_hr_corrections._approval_scope_filter) — non-manager
holders of the approve permission in the employee's branch — but notifies the
narrowest group that exists, so company-wide HR is not told about every
branch's requests:

  1. HR in the employee's branch;
  2. else that branch's Branch Admin;
  3. else company-wide HR (no branch set).
"""
from __future__ import annotations

MAX_RECIPIENTS = 25


def fallback_hr_approvers(employee, permission: str, *, staff_only: bool = False) -> list:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    base = (User.objects.filter(is_active=True, role__isnull=False)
            .exclude(pk=employee.pk)
            .select_related('role'))
    with_perm = base.filter(role__role_permissions__permission__codename=permission).distinct()
    branch = (getattr(employee, 'branch', '') or '').strip()

    def keep(users):
        out = []
        for u in users:
            if getattr(u.role, 'can_manage_team', False):
                continue                      # managers act at L1, not as fallback HR
            if staff_only:
                from apps.attendance.access import is_attendance_staff
                if not is_attendance_staff(u):
                    continue
            out.append(u)
        return out[:MAX_RECIPIENTS]

    if branch:
        hr = keep(with_perm.filter(branch__iexact=branch).filter(role__can_manage_branch=False))
        if hr:
            return hr
        admins = list(base.filter(branch__iexact=branch, role__can_manage_branch=True)[:MAX_RECIPIENTS])
        if admins:
            return admins
    return keep(with_perm.filter(branch__in=['', None]))
