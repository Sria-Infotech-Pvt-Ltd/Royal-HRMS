"""Who may see or decide a timesheet, and the approver's queue. One definition, so the queue a person sees is always exactly the
set they can act on (the same promise the work-from-home queue makes).

A person may DECIDE a submitted sheet when they are not its owner, are active, and any of these holds:
  * they are a superuser;
  * they are the approver assigned to it when it was submitted (the manager / HR partner the approval rule picked);
  * they hold `timesheet.approve` and the employee is inside their scope (their direct reports for a team seat, their branch
    for a branch seat: core.access.employee_in_scope).
Nobody ever decides their own sheet. A manager is therefore limited to their authorised scope: the assigned-approver route is
the only way outside it, and that is the approval rule's own choice, not the manager's.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.attendance.models_timesheet import STATUS_APPROVED, STATUS_DRAFT, Timesheet
from core.access import employee_in_scope, employees_in_scope
from core.permissions import has_perm

PERM_APPROVE = 'timesheet.approve'
PERM_UNLOCK = 'timesheet.unlock'
PERM_REPORT = 'timesheet.report'


def _usable(actor) -> bool:
    return bool(actor is not None and getattr(actor, 'pk', None) and actor.is_active)


def can_decide(actor, sheet: Timesheet) -> bool:
    if not _usable(actor) or actor.pk == sheet.employee_id:
        return False
    if actor.is_superuser or sheet.approver_id == actor.pk:
        return True
    return has_perm(actor, PERM_APPROVE) and employee_in_scope(actor, sheet.employee)


def can_unlock(actor, sheet: Timesheet) -> bool:
    """HR reopening an approved sheet: needs the unlock permission AND the employee in scope; never your own sheet."""
    if not _usable(actor) or actor.pk == sheet.employee_id or sheet.status != STATUS_APPROVED:
        return False
    return actor.is_superuser or (has_perm(actor, PERM_UNLOCK) and employee_in_scope(actor, sheet.employee))


def can_view(actor, sheet: Timesheet) -> bool:
    """The owner, anyone who may decide it, and report holders for employees in their scope. Drafts stay private to the owner."""
    if not _usable(actor):
        return False
    if actor.pk == sheet.employee_id:
        return True
    if sheet.status == STATUS_DRAFT:
        return False
    if can_decide(actor, sheet):
        return True
    return has_perm(actor, PERM_REPORT) and employee_in_scope(actor, sheet.employee)


def _in_scope_employees(actor) -> Q:
    return Q(employee_id__in=User.objects.filter(employees_in_scope(actor)).values('pk'))


def decidable_q(actor) -> Q:
    """The same rule as can_decide, as a filter (a superuser's own sheets are still excluded by the caller)."""
    if not _usable(actor):
        return Q(pk__in=[])
    if actor.is_superuser:
        return Q()
    condition = Q(approver=actor)
    if has_perm(actor, PERM_APPROVE):
        condition |= _in_scope_employees(actor)
    return condition


def visible_q(actor) -> Q:
    """Sheets a person may open from a list: what they can decide, plus report scope. Never someone's draft."""
    condition = decidable_q(actor)
    if _usable(actor) and not actor.is_superuser and has_perm(actor, PERM_REPORT):
        condition |= _in_scope_employees(actor)
    return condition


def team_queryset(actor, *, status: str = '', week_start=None, for_reports: bool = False) -> QuerySet:
    """Submitted-or-later sheets of other people that `actor` may decide (or, for reports, may see), newest week first."""
    queryset = (
        Timesheet.objects.select_related('employee', 'approver', 'decided_by')
        .exclude(employee=actor).exclude(status=STATUS_DRAFT)
        .filter(visible_q(actor) if for_reports else decidable_q(actor))
    )
    if status:
        queryset = queryset.filter(status__in=[s.strip() for s in status.split(',') if s.strip()])
    if week_start is not None:
        queryset = queryset.filter(week_start=week_start)
    return queryset.order_by('-week_start', '-submitted_at')
