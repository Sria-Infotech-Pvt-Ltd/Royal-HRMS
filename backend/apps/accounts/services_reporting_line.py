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


# ─── Approver route: who actually decides when the manager cannot ──────────────────────────────────────────────────────────

APPROVER_SOURCES = ('reporting_manager', 'reporting_approver', 'branch_hr', 'company_admin')
SOURCE_LABELS = {
    'reporting_manager': 'reporting manager',
    'reporting_approver': 'reporting approver',
    'branch_hr': 'branch HR',
    'company_admin': 'company HR/admin',
}


def approver_fallback_order() -> tuple:
    """The configured order (settings.APPROVER_FALLBACK_ORDER, env APPROVER_FALLBACK_ORDER); unknown names are ignored."""
    from django.conf import settings

    configured = getattr(settings, 'APPROVER_FALLBACK_ORDER', None) or APPROVER_SOURCES
    order = tuple(name for name in configured if name in APPROVER_SOURCES)
    return order or APPROVER_SOURCES


@dataclass(frozen=True)
class ApproverRoute:
    user: User | None
    source: str                 # one of APPROVER_SOURCES, or '' when nobody could be found
    skipped: tuple = ()         # sources tried first that had nobody, in order

    def skipped_note(self) -> str:
        """'Manager stage skipped - no manager assigned' style text, or '' when nothing was skipped."""
        if not self.skipped:
            return ''
        names = ', '.join(SOURCE_LABELS[name] for name in self.skipped)
        target = SOURCE_LABELS.get(self.source, 'nobody')
        return f'No {names} could be found, so this was routed to the {target}.' if self.user else f'No {names} could be found and nobody else could approve.'


def _branch_hr(employee: User) -> User | None:
    from core.access import users_with_permission
    from apps.branch.models import Branch

    if _usable(getattr(employee, 'hr', None), employee):
        return employee.hr
    branch_name = (employee.branch or '').strip()
    if not branch_name:
        return None
    branch = Branch.objects.select_related('hr').filter(branch_name__iexact=branch_name).first()
    if branch and _usable(branch.hr, employee):
        return branch.hr
    return (
        User.objects.filter(users_with_permission('leave.approve'), is_active=True, branch__iexact=branch_name)
        .exclude(pk=employee.pk).order_by('date_joined').first()
    )


def _company_admin(employee: User) -> User | None:
    from core.access import users_with_permission

    return User.objects.filter(users_with_permission('settings.edit'), is_active=True).exclude(pk=employee.pk).order_by('date_joined').first()


def resolve_approver_route(employee: User, exclude_sources: tuple = ()) -> ApproverRoute:
    """The first person who can decide for `employee`, trying the configured order and remembering which sources had nobody.

    Default order: reporting manager -> reporting approver -> branch HR -> company HR/admin. `exclude_sources` lets a stage that
    is NOT the manager stage (for example the HR stage) start further down the list."""
    skipped = []
    for source in approver_fallback_order():
        if source in exclude_sources:
            continue
        if source == 'reporting_manager':
            candidate = resolve_manager(employee)
        elif source == 'reporting_approver':
            candidate = getattr(employee, 'reporting_approver', None)
            candidate = candidate if _usable(candidate, employee) else None
        elif source == 'branch_hr':
            candidate = _branch_hr(employee)
        else:
            candidate = _company_admin(employee)
        if candidate is not None:
            return ApproverRoute(candidate, source, tuple(skipped))
        skipped.append(source)
    return ApproverRoute(None, '', tuple(skipped))
