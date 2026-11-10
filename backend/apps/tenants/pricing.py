"""
Subscription charge maths — one place for website quotes (registrations),
plan changes and the change-plan preview. Price is per employee per month;
GST is either included in the price or added on top. Also the subscription
period end (calendar months, same rule as frontend lib/saasDates.ts).
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MONTHS = {'monthly': 1, 'yearly': 12}
CENT = Decimal('0.01')


def charge(price_per_employee, gst_rate, gst_inclusive: bool, employee_count: int, billing_period: str) -> dict:
    """Amounts for one billing period. An unset period counts as monthly."""
    months = MONTHS.get(billing_period or 'monthly', 1)
    price, rate = Decimal(str(price_per_employee)), Decimal(str(gst_rate))
    subtotal = (price * employee_count * months).quantize(CENT, rounding=ROUND_HALF_UP)
    if gst_inclusive:
        gst = (subtotal - subtotal * 100 / (100 + rate)).quantize(CENT, rounding=ROUND_HALF_UP)
        total = subtotal
    else:
        gst = (subtotal * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        total = subtotal + gst
    return {'months': months, 'subtotal': subtotal, 'gst_amount': gst, 'total': total}


def plan_charge(plan, employee_count: int, billing_period: str) -> dict:
    return charge(plan.price_per_employee, plan.gst_rate, plan.gst_inclusive, employee_count, billing_period)


def add_months(d: date, months: int) -> date:
    """Calendar-month addition: the same day of the month, or the last day of
    the target month when it is shorter (31 Jan + 1 → 28/29 Feb). Never "30 days"."""
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def period_end(starts_on: date, billing_period: str) -> date | None:
    """End of one billing period from `starts_on`; None when no period is set."""
    months = MONTHS.get(billing_period or '')
    return add_months(starts_on, months) if months else None
