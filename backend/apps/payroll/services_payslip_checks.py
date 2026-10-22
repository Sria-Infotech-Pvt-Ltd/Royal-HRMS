"""
Sanity checks on saved payslips before money moves.

A payslip with ₹0 gross earnings and ₹0 net pay while the employee has a CTC
set is a calculation problem, not a real salary — typically every component of the
salary works out to 0 (e.g. the only component is "% of Basic" but nothing
fills the Basic line). Such a cycle must be fixed and re-processed before the
salary transfer is confirmed or the cycle is marked paid. Nothing here
recalculates or edits payslips.
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum


_MONEY_FIELDS = ('gross_earnings', 'total_deductions', 'net_pay', 'pf_employee')


def zero_gross_payslips(cycle) -> list[str]:
    """'Name (ID)' for each payslip with no earnings and nothing to pay although a CTC is set."""
    rows = (cycle.payslips.filter(gross_earnings__lte=0, net_pay__lte=0, annual_ctc__gt=0)
            .select_related('employee').order_by('employee__full_name'))
    return [f'{p.employee.full_name} ({p.employee.employee_id or "no ID"})' for p in rows]


def zero_gross_message(labels: list[str]) -> str:
    return ('These payslips have ₹0 gross earnings and ₹0 net pay although a CTC is set: ' + ', '.join(labels)
            + '. Check each employee\'s salary components (for example a "% of Basic" component '
              'with no component on the Basic payslip line), then re-process the cycle before payment.')


def cycle_totals(payslips) -> dict:
    """Totals over every saved payslip (not just one page) — the figures the cycle page shows."""
    agg = payslips.aggregate(
        **{f'total_{f}': Sum(f) for f in _MONEY_FIELDS},
        count=Count('id'),
        zero_gross=Count('id', filter=Q(gross_earnings__lte=0, net_pay__lte=0, annual_ctc__gt=0)),
    )
    out = {k: str(agg[k] if agg[k] is not None else Decimal('0.00')) for k in (f'total_{f}' for f in _MONEY_FIELDS)}
    out['count'] = agg['count']
    out['zero_gross_count'] = agg['zero_gross']
    return out


