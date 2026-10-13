"""Phase 8B Task A — expense category seeding (migrates CATEGORY_CHOICES exactly), claim/line migration, and the one policy rule this pass implements."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.hrms.models import (
    STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED, Expense, ExpenseCategory, ExpenseClaim, ExpenseLine,
)


def seed_expense_categories() -> dict:
    """Idempotent. Reproduces Expense.CATEGORY_CHOICES exactly — nothing invented."""
    created = {}
    for code, name in Expense.CATEGORY_CHOICES:
        category, _ = ExpenseCategory.objects.get_or_create(
            legacy_category_code=code, defaults={'code': code, 'name': name},
        )
        created[code] = category
    return created


def next_claim_number() -> int:
    """Continues the existing expense_number sequence — never starts a
    second, colliding sequence from 1."""
    from django.db.models import Max
    max_expense = Expense.objects.aggregate(m=Max('expense_number'))['m'] or 0
    max_claim = ExpenseClaim.objects.aggregate(m=Max('claim_number'))['m'] or 0
    return max(max_expense, max_claim) + 1


@transaction.atomic
def migrate_expense_to_claim(expense: Expense) -> ExpenseClaim:
    """Idempotent. 'An old Expense = a claim with one line' — exact amount,
    date, category preserved."""
    existing = getattr(expense, 'claim_v2', None)
    if existing is not None:
        return existing

    categories = seed_expense_categories()
    category = categories.get(expense.category)
    if category is None:
        raise ValueError(f'No ExpenseCategory seeded for legacy code {expense.category!r} — run seed_expense_categories() first.')

    claim = ExpenseClaim.objects.create(
        claim_number=expense.expense_number or next_claim_number(),
        employee=expense.employee, purpose=expense.title, status=_map_status(expense.status),
        legacy_expense=expense,
    )
    ExpenseLine.objects.create(
        claim=claim, category=category, expense_date=expense.expense_date,
        quantity=Decimal('1'), amount=expense.amount, currency_code='INR', exchange_rate=Decimal('1'),
        base_amount=expense.amount, description=expense.description,
        status=_map_status(expense.status),
    )
    return claim


def _map_status(legacy_status: str) -> str:
    return {
        STATUS_PENDING: ExpenseClaim.STATUS_SUBMITTED,
        STATUS_APPROVED: ExpenseClaim.STATUS_APPROVED,
        STATUS_REJECTED: ExpenseClaim.STATUS_REJECTED,
    }.get(legacy_status, ExpenseClaim.STATUS_DRAFT)


def evaluate_policy(category: ExpenseCategory, employee, amount: Decimal, period_start, period_end) -> tuple:
    """The one real policy rule this pass implements: a per-category limit
    over [period_start, period_end] (a day/claim/month window — the
    caller decides which) against this employee's OTHER lines in that
    category/window, PLUS the receipt-required threshold. Returns
    (result_code, explanation) — never blocks by itself (out-of-policy
    routing per Task A.3 is the caller's job), just reports the result."""
    if category.requires_receipt_above_amount is not None and amount > category.requires_receipt_above_amount:
        return ExpenseLine.POLICY_RESULT_OVER_LIMIT, f'Amount {amount} exceeds the receipt-required threshold {category.requires_receipt_above_amount} — receipt mandatory.'

    if category.period_limit_amount is not None:
        existing_total = ExpenseLine.objects.filter(
            claim__employee=employee, category=category,
            expense_date__gte=period_start, expense_date__lte=period_end,
        ).exclude(status=ExpenseLine.STATUS_REJECTED).aggregate(total=Sum('base_amount'))['total'] or Decimal('0')

        if existing_total + amount > category.period_limit_amount:
            return (
                ExpenseLine.POLICY_RESULT_OVER_LIMIT,
                f'{existing_total + amount} would exceed the {category.period_limit_amount} limit for {category.code} '
                f'in this period (already claimed: {existing_total}).',
            )

    return ExpenseLine.POLICY_RESULT_WITHIN_POLICY, ''
