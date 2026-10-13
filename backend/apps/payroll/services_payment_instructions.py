"""
Phase 7B Task G — salary splits and payment instructions, built on the
real Phase 5A `accounts.BankAccount` split fields (split_type: remainder/
percentage/fixed; priority; is_primary) — no new split model.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.accounts.models_identity_bank import BankAccount
from apps.payroll.models import PaymentInstruction

TWO_PLACES = Decimal('0.01')


@transaction.atomic
def generate_payment_instructions(payslip) -> list:
    """Idempotent — clears and regenerates this payslip's own instructions.
    Fallback: if the employee has no active bank accounts at all, falls
    back to a single pending bank_transfer instruction with no bank_account
    (will fail Task C's missing_bank_account check, as it should — never
    silently invents an account)."""
    PaymentInstruction.objects.filter(payslip=payslip).delete()

    accounts = list(
        BankAccount.objects.filter(employee_id=payslip.employee_id, status=BankAccount.STATUS_ACTIVE)
        .order_by('-is_primary', 'priority')
    )
    net_pay = Decimal(payslip.net_pay)

    if not accounts:
        return [PaymentInstruction.objects.create(payslip=payslip, bank_account=None, amount=net_pay)]

    fixed_accounts = [a for a in accounts if a.split_type == BankAccount.SPLIT_FIXED]
    percentage_accounts = [a for a in accounts if a.split_type == BankAccount.SPLIT_PERCENTAGE]
    remainder_accounts = [a for a in accounts if a.split_type == BankAccount.SPLIT_REMAINDER]

    instructions = []
    allocated = Decimal('0')

    for account in fixed_accounts:
        amount = min(Decimal(account.split_value or 0), net_pay - allocated)
        amount = max(Decimal('0'), amount)
        instructions.append((account, amount))
        allocated += amount

    remaining_after_fixed = net_pay - allocated
    for account in percentage_accounts:
        pct = Decimal(account.split_value or 0)
        amount = (remaining_after_fixed * pct / 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        instructions.append((account, amount))
        allocated += amount

    # Remainder accounts split whatever's left evenly, with the first
    # remainder (or primary, if it's a remainder account) absorbing any
    # final rounding cent so the total always equals net_pay exactly.
    remaining = net_pay - allocated
    if remainder_accounts:
        share = (remaining / len(remainder_accounts)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        for i, account in enumerate(remainder_accounts):
            amount = share
            instructions.append((account, amount))
            allocated += amount
        # Absorb rounding drift into the last remainder account.
        drift = net_pay - allocated
        if drift != 0 and instructions:
            last_account, last_amount = instructions[-1]
            instructions[-1] = (last_account, last_amount + drift)
    elif remaining != 0:
        # No remainder account at all (e.g. only fixed/percentage splits
        # configured) and they don't sum to net_pay — fall back to the
        # primary account for whatever's left over, rather than silently
        # dropping money. Never invents a NEW account; only redirects to
        # one already on file.
        primary = next((a for a in accounts if a.is_primary), accounts[0])
        instructions.append((primary, remaining))

    created = []
    for account, amount in instructions:
        if amount == 0:
            continue
        created.append(PaymentInstruction.objects.create(payslip=payslip, bank_account=account, amount=amount))
    return created


def total_instructed_amount(payslip) -> Decimal:
    from django.db.models import Sum
    return PaymentInstruction.objects.filter(payslip=payslip).aggregate(total=Sum('amount'))['total'] or Decimal('0')
