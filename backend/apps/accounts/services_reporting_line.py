"""
Who is this employee's manager? One answer, used by every screen and workflow (directory, profile, drawer, edit form, approval
matrix, separation, leave, attendance corrections, feedback), so they can never disagree again (UAT-012).

Fallback order, documented and fixed:
  1. the reporting manager stored on the employee (if that person is still active and is not the employee);
  2. otherwise the chief of the nearest org unit in the employee's chain (the same person hire's "Auto-assign" stores);
  3. otherwise nobody: every screen then says "Not assigned". There is no silent default such as "CEO Office".

Managers (can_manage_team) are not resolved here: they have no reporting manager by design (see _employee_dict).
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.models import User

SOURCE_ASSIGNED = 'assigned'
SOURCE_ORG_CHART = 'org_chart'
SOURCE_NONE = 'none'


@dataclass(frozen=True)
class ManagerResolution:
    user: User | None
    source: str  # SOURCE_ASSIGNED / SOURCE_ORG_CHART / SOURCE_NONE


def _usable(candidate: User | None, employee: User) -> bool:
    return candidate is not None and candidate.is_active and candidate.pk != employee.pk


def resolve_manager_with_source(employee: User) -> ManagerResolution:
    assigned = getattr(employee, 'reporting_manager', None)
    if _usable(assigned, employee):
        return ManagerResolution(assigned, SOURCE_ASSIGNED)

    from apps.accounts.services_approval import resolve_employee_org_unit_chief
    chief = resolve_employee_org_unit_chief(employee)
    if _usable(chief, employee):
        return ManagerResolution(chief, SOURCE_ORG_CHART)
    return ManagerResolution(None, SOURCE_NONE)


def resolve_manager(employee: User) -> User | None:
    return resolve_manager_with_source(employee).user
