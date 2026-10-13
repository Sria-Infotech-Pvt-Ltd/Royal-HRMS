"""
Phase 7B Task D — off-cycle runs: a component subset on top of the Task J
composer, and reversal entries that never edit the original payslip.

Tax treatment on an off-cycle payment: this pass implements the
"marginal" method ONLY (the payment is taxed at the employee's current
monthly TDS rate, i.e. no re-projection of the annual tax position) —
documented here, not hidden, as the simpler of the two methods the master
prompt names ("marginal on the payment, or spread"). A "spread" method
(re-running the full annual projection with the one-off payment folded in)
is a real follow-on, not built in this pass.
"""
from decimal import Decimal

from apps.payroll.models import ReversalEntry


# Which PayComponent codes a given off-cycle run_type actually computes —
# e.g. a bonus run only ever touches BONUS + TDS, never recomputes BASIC/
# HRA/PF from scratch for a period already paid regularly.
OFF_CYCLE_COMPONENT_SUBSETS = {
    'off_cycle_bonus': ['BONUS', 'TDS'],
    'off_cycle_correction': None,  # correction runs use whatever Task E's arrears diff produced — no fixed subset
}


def compute_bonus_run_amount(bonus_amount: Decimal, marginal_monthly_tds_rate: Decimal) -> dict:
    """Marginal-method off-cycle bonus: TDS on the bonus itself is the
    bonus amount x the employee's current effective monthly tax rate
    (monthly_tds / monthly_gross) — a real, if simplified, marginal
    withholding approach; NOT a full annual re-projection (see module
    docstring)."""
    bonus_amount = Decimal(bonus_amount)
    tds = (bonus_amount * marginal_monthly_tds_rate).quantize(Decimal('0.01'))
    return {'BONUS': bonus_amount, 'TDS': tds, 'net': bonus_amount - tds}


def create_reversal(run, original_payslip, reason: str) -> list:
    """Reverses every non-zero component line on `original_payslip` with a
    negative ReversalEntry — the original payslip itself is never touched
    (no .save() call on it anywhere in this function)."""
    if not reason.strip():
        raise ValueError('A reversal reason is required.')

    entries = []
    for line in original_payslip.lines.all():
        if line.amount == 0:
            continue
        entries.append(ReversalEntry.objects.create(
            run=run, original_payslip=original_payslip, component_code=line.component_code,
            amount=-line.amount, reason=reason,
        ))
    return entries


def reversal_net_total(run) -> Decimal:
    from django.db.models import Sum
    return ReversalEntry.objects.filter(run=run).aggregate(total=Sum('amount'))['total'] or Decimal('0')
