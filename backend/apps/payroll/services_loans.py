"""Phase 7B Task F — loans and advances: EMI schedule generation, skip/defer, prepayment, F&F recovery."""
from decimal import ROUND_HALF_UP, Decimal
from dateutil.relativedelta import relativedelta

from django.db import transaction

from apps.payroll.models import EmployeeLoan, LoanEmiSchedule, LoanType

TWO_PLACES = Decimal('0.01')


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _equal_principal_schedule(principal: Decimal, tenure_months: int) -> list:
    """No-interest loans: principal split evenly, with any rounding
    remainder absorbed into the LAST installment so the sum is exact."""
    base = _round(principal / tenure_months)
    rows = [base] * tenure_months
    remainder = principal - (base * tenure_months)
    rows[-1] = _round(rows[-1] + remainder)
    return rows


def _simple_interest_schedule(principal: Decimal, annual_rate: Decimal, tenure_months: int) -> list:
    """Flat/simple interest: interest computed once on the full principal
    for the full tenure, spread evenly; principal spread evenly too."""
    total_interest = _round(principal * annual_rate / 100 * Decimal(tenure_months) / 12)
    principal_rows = _equal_principal_schedule(principal, tenure_months)
    interest_per_month = _round(total_interest / tenure_months)
    rows = [(p, interest_per_month) for p in principal_rows[:-1]]
    last_interest = total_interest - (interest_per_month * (tenure_months - 1))
    rows.append((principal_rows[-1], last_interest))
    return rows


def _reducing_balance_schedule(principal: Decimal, annual_rate: Decimal, tenure_months: int) -> list:
    """Standard reducing-balance EMI: equal total EMI each month, interest
    computed on the outstanding balance, principal portion grows over
    time. Falls back to equal-principal/no-interest math if annual_rate is 0
    (division-by-zero guard, not a separate code path)."""
    if annual_rate == 0:
        return [(p, Decimal('0')) for p in _equal_principal_schedule(principal, tenure_months)]

    monthly_rate = annual_rate / 100 / 12
    # Standard EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
    factor = (1 + monthly_rate) ** tenure_months
    emi = _round(principal * monthly_rate * factor / (factor - 1))

    rows = []
    balance = principal
    for month in range(1, tenure_months + 1):
        interest = _round(balance * monthly_rate)
        if month == tenure_months:
            principal_component = balance  # absorb any rounding remainder in the final installment
        else:
            principal_component = _round(emi - interest)
        balance -= principal_component
        rows.append((principal_component, interest))
    return rows


@transaction.atomic
def generate_emi_schedule(loan: EmployeeLoan) -> list:
    """Idempotent — clears and regenerates this loan's own schedule rather
    than appending duplicates."""
    LoanEmiSchedule.objects.filter(loan=loan).delete()

    if loan.loan_type.interest_type == LoanType.INTEREST_NONE:
        rows = [(p, Decimal('0')) for p in _equal_principal_schedule(loan.principal_amount, loan.tenure_months)]
    elif loan.loan_type.interest_type == LoanType.INTEREST_SIMPLE:
        rows = _simple_interest_schedule(loan.principal_amount, loan.loan_type.interest_rate, loan.tenure_months)
    else:
        rows = _reducing_balance_schedule(loan.principal_amount, loan.loan_type.interest_rate, loan.tenure_months)

    created = []
    for i, (principal_component, interest_component) in enumerate(rows, start=1):
        due_date = loan.disbursement_date + relativedelta(months=i)  # first EMI due one month after disbursement
        created.append(LoanEmiSchedule.objects.create(
            loan=loan, installment_number=i, due_date=due_date,
            principal_component=principal_component, interest_component=interest_component,
            emi_amount=principal_component + interest_component,
        ))
    return created


def deduct_emi(schedule_row: LoanEmiSchedule, run) -> LoanEmiSchedule:
    loan = schedule_row.loan
    schedule_row.status = LoanEmiSchedule.STATUS_DEDUCTED
    schedule_row.deducted_in_run = run
    schedule_row.save(update_fields=['status', 'deducted_in_run'])

    loan.outstanding_balance = max(Decimal('0'), loan.outstanding_balance - schedule_row.principal_component)
    if loan.outstanding_balance == 0:
        loan.status = EmployeeLoan.STATUS_CLOSED
    loan.save(update_fields=['outstanding_balance', 'status', 'updated_at'])
    return schedule_row


def skip_or_defer_emi(schedule_row: LoanEmiSchedule, *, defer: bool = False) -> LoanEmiSchedule:
    schedule_row.status = LoanEmiSchedule.STATUS_DEFERRED if defer else LoanEmiSchedule.STATUS_SKIPPED
    schedule_row.save(update_fields=['status'])
    return schedule_row


@transaction.atomic
def foreclose_loan(loan: EmployeeLoan) -> EmployeeLoan:
    LoanEmiSchedule.objects.filter(loan=loan, status=LoanEmiSchedule.STATUS_PENDING).update(status=LoanEmiSchedule.STATUS_SKIPPED)
    loan.status = EmployeeLoan.STATUS_FORECLOSED
    loan.outstanding_balance = Decimal('0')
    loan.save(update_fields=['status', 'outstanding_balance', 'updated_at'])
    return loan


def outstanding_balance_for_settlement(employee) -> Decimal:
    """Sum of every active loan's outstanding balance for an employee —
    what Task L's final settlement recovers against advances_recovery_amount."""
    from django.db.models import Sum
    return EmployeeLoan.objects.filter(
        employee=employee, status=EmployeeLoan.STATUS_ACTIVE,
    ).aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0')
