"""Who decides an employee's timesheet. Uses the shared approval resolver, so the admin's approval settings (and a per-employee
override) apply exactly as they do for leave, work from home and attendance corrections."""
from __future__ import annotations

from apps.accounts.models import ApprovalWorkflowRule
from apps.accounts.services_approval import resolve_approval_chain
from apps.accounts.services_reporting_line import resolve_approver_route
from apps.attendance.services_timesheet_common import TimesheetError

NO_APPROVER_MESSAGE = 'No approver could be found for your timesheet. Please ask HR to set your reporting manager.'


def resolve_approver(employee):
    """The first usable person: the configured level-1 approver (normally the reporting manager), then level 2 (HR partner),
    then the standard fallback route (reporting approver, branch HR, company admin). A manager whose own manager is not set
    therefore lands on a higher-level approver or HR, never on themselves, and a sheet is never left with nobody to decide it.

    The resolvers already skip an inactive person and the employee themselves; the check here is a last guard."""
    level_one, level_two = resolve_approval_chain(employee, ApprovalWorkflowRule.WORKFLOW_TIMESHEET)
    approver = level_one or level_two or resolve_approver_route(employee).user
    if approver is None or not approver.is_active or approver.pk == employee.pk:
        raise TimesheetError(NO_APPROVER_MESSAGE)
    return approver
