"""
Full & Final settlement calculation for a separation request.

Computes the parts that can be derived from data already in the system —
pro-rated final salary, earned-leave encashment, and notice-period
shortfall recovery — matching the standard India F&F process (pending
salary, leave encashment, less notice-period recovery, before Finance's own
additions for gratuity/bonus/reimbursements/TDS, which stay manual — see
SeparationSettlement's own docstring for why).

Known simplifications, deliberately not hidden:
- Per-day rate uses a flat 30-day-month convention on the employee's
  monthly CTC. Many companies instead use Basic+DA over a 26-day month —
  this system doesn't reliably track a separate Basic/DA figure per
  employee (EmployeeSalaryConfig only stores one CTC number), so CTC/30 is
  the closest defensible number without inventing data that isn't there.
- Leave encashment only counts LEAVE_EARNED (Earned/Privilege Leave) —
  the type actually encashable at exit under standard Indian practice;
  Casual/Sick/LWP are excluded on purpose.
- pro_rata_salary assumes the employee worked from the 1st of their final
  month through proposed_last_working_day — it does not reconcile against
  actual attendance/LOP for that month (that's payroll's own regular
  payslip run, a separate process).

Every computed field here is still a plain, editable model field — this
function only ever produces a *draft* HR/Finance can adjust before
finalizing, exactly like the real-world process it mirrors.
"""
from __future__ import annotations

from calendar import monthrange
from decimal import ROUND_HALF_UP, Decimal

from .models import LEAVE_EARNED, LeaveBalance, SeparationSettlement

_CENTS = Decimal('0.01')


def _q(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _per_day_rate(monthly_ctc: Decimal) -> Decimal:
    return _q(monthly_ctc / Decimal(30))


def compute_draft(sep_request) -> SeparationSettlement:
    """(Re)computes the auto-derived fields of a separation's settlement —
    creates the row on first call. Manual fields (gratuity, bonus,
    reimbursements, advances, TDS, other) are left untouched so HR's own
    entries are never silently overwritten by a later recompute."""
    settlement, _created = SeparationSettlement.objects.get_or_create(request=sep_request)

    employee = sep_request.employee
    salary_config = employee.salary_configs.filter(is_active=True).first()
    monthly_ctc = salary_config.monthly_ctc if salary_config else Decimal(0)
    per_day = _per_day_rate(monthly_ctc)

    last_day = sep_request.proposed_last_working_day
    monthrange(last_day.year, last_day.month)  # validates the (year, month) pair
    settlement.pro_rata_salary = _q(per_day * Decimal(last_day.day))

    leave_balance = LeaveBalance.objects.filter(
        employee=employee, leave_type=LEAVE_EARNED, year=last_day.year,
    ).first()
    encashable_days = leave_balance.available_days if leave_balance else Decimal(0)
    if encashable_days < 0:
        encashable_days = Decimal(0)
    settlement.leave_encashment_days = encashable_days
    settlement.leave_encashment_amount = _q(encashable_days * per_day)

    served_days = max(0, (last_day - sep_request.request_date).days)
    required_days = sep_request.notice_period_days
    shortfall = max(0, required_days - served_days)
    settlement.notice_period_required_days = required_days
    settlement.notice_period_served_days = served_days
    settlement.notice_period_shortfall_days = shortfall
    settlement.notice_period_recovery_amount = _q(Decimal(shortfall) * per_day)

    recompute_net_payable(settlement)
    settlement.save()
    return settlement


def recompute_net_payable(settlement: SeparationSettlement) -> None:
    """Sets net_payable_amount from the settlement's current field values —
    called after compute_draft() and after any manual-field edit, never
    saves on its own (callers save once, after this)."""
    settlement.net_payable_amount = _q(
        settlement.pro_rata_salary
        + settlement.leave_encashment_amount
        + settlement.gratuity_amount
        + settlement.statutory_bonus_amount
        + settlement.reimbursements_amount
        + settlement.other_adjustment_amount
        - settlement.notice_period_recovery_amount
        - settlement.advances_recovery_amount
        - settlement.tds_amount
    )
