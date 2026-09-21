from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from dateutil import parser as dateutil_parser

# "last cycle"/"previous month" phrasing -> go back one period from the
# branch's own latest non-cancelled cycle (see
# apps.payroll.views.analytics._resolve_period_cycle's own `offset` param,
# which this feeds). No "this cycle"/"current month" entry needed — offset 0
# is already the default when nothing matches.
_PREVIOUS_PERIOD_RE = re.compile(r'\b(last|previous|past)\s+(cycle|month|payroll)\b', re.IGNORECASE)

# Guards dateutil.parser.parse(fuzzy=True) below. Fuzzy mode will happily
# manufacture a date out of an unrelated number anywhere in the sentence
# (e.g. "top 3 branches" -> day 3 of the current month) if let loose on
# arbitrary text — extract_period_month only ever calls it once a real
# month-name token has actually been found first.
_MONTH_NAME_RE = re.compile(
    r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun[e]?|jul[y]?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
    re.IGNORECASE,
)


def extract_period_offset(text: str) -> int:
    """
    0 unless a "last/previous/past cycle/month/payroll" phrase is present,
    then 1 — feeds apps.payroll.views.analytics._resolve_period_cycle's own
    `offset` param via executor_payroll_analytics.py. No support for going
    back more than one period by voice today; extend _PREVIOUS_PERIOD_RE's
    phrase set (and this function's return value) if a "two cycles ago"
    phrasing is ever registered.
    """
    return 1 if _PREVIOUS_PERIOD_RE.search(text) else 0


def extract_period_month(text: str) -> Optional[str]:
    """
    Best-effort 'YYYY-MM' extraction for a spoken month, e.g. "payroll cost
    for March" -> "2026-03" (year defaults to the current year, same
    default-fill convention slot_extractor._parse_single_date already uses
    for dateutil.parser.parse's `default` argument).

    Returns None unless a real month-name token is found FIRST
    (_MONTH_NAME_RE) — see that pattern's own comment for why an unguarded
    dateutil.parser.parse(fuzzy=True) call is unsafe on arbitrary voice
    transcripts.
    """
    if not _MONTH_NAME_RE.search(text):
        return None
    today = date.today()
    try:
        parsed = dateutil_parser.parse(text, fuzzy=True, default=datetime(today.year, today.month, 1))
    except (ValueError, OverflowError):
        return None
    return parsed.strftime('%Y-%m')
