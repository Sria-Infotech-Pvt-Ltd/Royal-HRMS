"""
Phase 7B Task C — pre-run validation checks and pay holds. Each check is a
plain Python function registered in CHECK_REGISTRY by code (the master
prompt's "3A rule expression" scoped down to real functions — see
models_payroll_check.py's own docstring for why), taking a PayrollRun and
an iterable of EmployeePayslip and yielding (employee, message) pairs for
every failure found.
"""
from decimal import Decimal

from apps.payroll.models import PayrollCheck, PayrollCheckResult, PayrollHold


def _check_negative_net_pay(run, payslips):
    for p in payslips:
        if p.net_pay < 0:
            yield p.employee, f'Net pay is negative ({p.net_pay}).'


def _check_missing_bank_account(run, payslips):
    for p in payslips:
        if not p.employee.bank_accounts.filter(status='active').exists():
            yield p.employee, 'No active bank account on file.'


def _check_zero_working_days(run, payslips):
    for p in payslips:
        if p.total_working_days == 0:
            yield p.employee, 'Zero working days recorded for this period.'


def _check_employee_on_hold(run, payslips):
    held_employee_ids = set(
        PayrollHold.objects.filter(employee__in=[p.employee_id for p in payslips], released_at__isnull=True)
        .values_list('employee_id', flat=True)
    )
    for p in payslips:
        if p.employee_id in held_employee_ids:
            yield p.employee, 'Employee pay is on hold.'


def _check_net_pay_change_threshold(run, payslips):
    """> 50% change vs the employee's previous payslip, same pay group."""
    threshold = Decimal('0.5')
    for p in payslips:
        previous = (
            p.employee.payslips.filter(cycle__cycle_start__lt=p.cycle.cycle_start)
            .order_by('-cycle__cycle_start').first()
        )
        if previous is None or previous.net_pay == 0:
            continue
        change = abs(p.net_pay - previous.net_pay) / previous.net_pay
        if change > threshold:
            yield p.employee, f'Net pay changed by {change * 100:.0f}% vs. the previous period.'


CHECK_REGISTRY = {
    'negative_net_pay':        _check_negative_net_pay,
    'missing_bank_account':    _check_missing_bank_account,
    'zero_working_days':       _check_zero_working_days,
    'employee_on_hold':        _check_employee_on_hold,
    'net_pay_change_threshold': _check_net_pay_change_threshold,
}


def run_checks(run, payslips) -> list:
    """Evaluates every active PayrollCheck against `payslips`, persists a
    PayrollCheckResult per failure, and returns the created results.
    Re-running clears this run's previous results first (idempotent)."""
    payslips = list(payslips)
    PayrollCheckResult.objects.filter(run=run).delete()

    results = []
    for check in PayrollCheck.objects.filter(is_active=True):
        check_fn = CHECK_REGISTRY.get(check.check_function_code)
        if check_fn is None:
            continue
        for employee, message in check_fn(run, payslips):
            results.append(PayrollCheckResult.objects.create(
                run=run, payroll_check=check, employee=employee, message=message,
            ))
    return results


def has_blocking_unacknowledged_failures(run) -> bool:
    return PayrollCheckResult.objects.filter(
        run=run, is_acknowledged=False, payroll_check__severity=PayrollCheck.SEVERITY_ERROR,
    ).exists()


def acknowledge_result(result: PayrollCheckResult, user, reason: str) -> PayrollCheckResult:
    from django.utils import timezone
    if not reason.strip():
        raise ValueError('An acknowledgement reason is required.')
    result.is_acknowledged = True
    result.acknowledged_by = user
    result.acknowledgement_reason = reason
    result.acknowledged_at = timezone.now()
    result.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledgement_reason', 'acknowledged_at'])
    return result


def place_hold(employee, reason: str, placed_by=None) -> PayrollHold:
    return PayrollHold.objects.create(employee=employee, reason=reason, placed_by=placed_by)


def release_hold(hold: PayrollHold, released_by=None) -> PayrollHold:
    from django.utils import timezone
    hold.released_at = timezone.now()
    hold.released_by = released_by
    hold.save(update_fields=['released_at', 'released_by'])
    return hold


def active_hold_employee_ids(employee_ids) -> set:
    return set(
        PayrollHold.objects.filter(employee_id__in=employee_ids, released_at__isnull=True)
        .values_list('employee_id', flat=True)
    )
