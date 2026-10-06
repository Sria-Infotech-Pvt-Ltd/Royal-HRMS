"""Phase 1 Task C — currency conversion. Admin-entered rates only in this
phase; no external feed."""
from __future__ import annotations

import datetime
from decimal import Decimal

from apps.platform_core.models import Currency, ExchangeRate


class NoExchangeRateAvailable(Exception):
    pass


def convert(amount: Decimal, from_currency: str | Currency, to_currency: str | Currency, on_date: datetime.date | None = None) -> Decimal:
    """Converts `amount` using the latest ExchangeRate on or before
    `on_date` (defaults to today). Raises NoExchangeRateAvailable if no
    rate exists yet — callers decide how to handle that, this never
    silently assumes a 1:1 rate."""
    from_code = from_currency if isinstance(from_currency, str) else from_currency.code
    to_code = to_currency if isinstance(to_currency, str) else to_currency.code
    if from_code == to_code:
        return amount

    on_date = on_date or datetime.date.today()
    rate_row = (
        ExchangeRate.objects
        .filter(from_currency__code=from_code, to_currency__code=to_code, effective_date__lte=on_date)
        .order_by('-effective_date')
        .first()
    )
    if rate_row is None:
        raise NoExchangeRateAvailable(f'No {from_code}->{to_code} exchange rate on or before {on_date}')
    return (amount * rate_row.rate).quantize(Decimal('0.01'))
