"""Phase 8B gap-closure — travel requests/advance settlement, per-diem/mileage/deadline/duplicate-detection policy rules, out-of-policy routing."""
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.hrms.models import ExpenseCategory, ExpenseLine, TravelExpenseClaimLink, TravelRequest


def compute_unit_based_amount(category: ExpenseCategory, quantity: Decimal) -> Decimal:
    if not category.is_unit_based or category.unit_rate is None:
        raise ValueError(f'{category.code} is not unit-based (or has no unit_rate configured).')
    return quantity * category.unit_rate


def compute_per_diem(category: ExpenseCategory, city_tier: str) -> Decimal:
    rate = category.per_diem_by_city_tier.get(city_tier)
    if rate is None:
        raise ValueError(f'{category.code}: no per-diem rate configured for city tier {city_tier!r}.')
    return Decimal(str(rate))


def check_submission_deadline(category: ExpenseCategory, expense_date: datetime.date, submitted_on: datetime.date) -> bool:
    """True = within deadline (or no deadline configured)."""
    if category.submission_deadline_days is None:
        return True
    return (submitted_on - expense_date).days <= category.submission_deadline_days


def find_duplicate_lines(employee, amount: Decimal, expense_date: datetime.date, merchant: str):
    """Same amount, date and merchant — the real 'duplicate detection'
    rule from Task A.3, scoped to one employee."""
    return ExpenseLine.objects.filter(
        claim__employee=employee, amount=amount, expense_date=expense_date, merchant=merchant,
    )


def route_out_of_policy(category: ExpenseCategory, line: ExpenseLine) -> str:
    """Returns the behavior code the caller (a view/workflow) should act
    on — this function never silently blocks or approves anything itself,
    matching every other policy function in this codebase that reports
    rather than enforces."""
    if line.policy_result != ExpenseLine.POLICY_RESULT_OVER_LIMIT:
        return ''
    return category.out_of_policy_behavior


@transaction.atomic
def link_claim_to_trip(claim, travel_request: TravelRequest) -> TravelExpenseClaimLink:
    return TravelExpenseClaimLink.objects.create(travel_request=travel_request, claim=claim)


def travel_advance_balance(travel_request: TravelRequest) -> Decimal:
    """advance_requested minus the total of every claim settled against
    this trip so far — positive = still owed to the employee, negative =
    employee owes the difference back."""
    settled_total = Decimal('0')
    for link in travel_request.claim_links.select_related('claim'):
        settled_total += link.claim.total_base_amount
    return travel_request.advance_requested - settled_total
