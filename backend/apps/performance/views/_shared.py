from ..models import CYCLE_ACTIVE, ReviewCycle


def _active_cycle():
    return ReviewCycle.objects.filter(status=CYCLE_ACTIVE).order_by('-period_start').first()


def _resolve_manager(employee):
    """Same fallback chain the Separation module already documents for
    resolving "who approves this employee's stuff" — reporting_manager
    first, reporting_approver (set specifically for manager/HR-role users
    with no manager above them) otherwise."""
    return employee.reporting_manager or employee.reporting_approver
