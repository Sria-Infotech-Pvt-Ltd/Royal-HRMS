"""
Employee notice period (User.notice_period_days) — one validation rule shared
by the HR edit, the employee bulk import and Separation & Exit, plus the
expected last working day a resignation implies.

Days are calendar days; the expected last working day is the resignation
(request) date plus the notice period. It is only an expectation — the
confirmed date is the one on the approved separation request.
"""
from __future__ import annotations

import datetime

MAX_NOTICE_PERIOD_DAYS = 365


def parse_notice_period_days(value) -> tuple[str | None, int | None]:
    """(error, days). Blank / None means "not assigned" → (None, None)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    try:
        number = float(str(value).strip())   # Excel cells arrive as "30.0"
    except (TypeError, ValueError):
        return 'Notice period must be a whole number of days.', None
    if not number.is_integer():
        return 'Notice period must be a whole number of days.', None
    days = int(number)
    if days < 0 or days > MAX_NOTICE_PERIOD_DAYS:
        return f'Notice period must be between 0 and {MAX_NOTICE_PERIOD_DAYS} days.', None
    return None, days


def expected_last_working_day(request_date: datetime.date | None, notice_days: int | None) -> datetime.date | None:
    if request_date is None or notice_days is None:
        return None
    return request_date + datetime.timedelta(days=notice_days)
