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

# Used by strip_payroll_period_phrases below — deliberately narrower than
# _MONTH_NAME_RE (requires a leading "in") so it never eats a bare
# month-shaped word out of an unrelated sentence (e.g. "may" as the modal
# verb) — only an unambiguous "in <month>" phrase.
#
# Deliberately does NOT also strip "this/last/previous/past/current
# cycle|month|payroll" the way extract_period_offset's own _PREVIOUS_PERIOD_RE
# recognizes it — check_attendance_stats/check_attendance_summary's own
# registered phrases legitimately contain "this month" as core phrase
# content, not a bare payroll period modifier layered on top (e.g. "how's my
# attendance this month"); stripping it there previously cost that phrase its
# own match entirely (regression caught by
# test_clarification_dispatch_matrix.py's BORDERLINE['check_attendance_stats']
# case, 2026-09). check_payroll_cost_summary's own "this month"/"last month"
# phrasing is instead handled by registering the bare phrases directly
# (registry/intents_en.yaml) rather than stripping — see that file.
_PERIOD_PHRASE_STRIP_RE = re.compile(
    r'\bin\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun[e]?|jul[y]?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r'\s+')


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


def strip_payroll_period_phrases(text: str) -> str:
    """
    Remove an "in <month>" phrase from text before intent matching — mirrors
    slot_extractor.strip_leave_slot_phrases. Left in, "payroll cost summary
    in march" drags the fuzzy score against the registered
    check_payroll_cost_summary phrases below match_intent()'s confidence
    threshold (measured 2026-09: ~79 instead of the 90s+ a bare "payroll cost
    summary" gets), landing in the clarification band purely because of the
    period words, not any real ambiguity about which intent was meant.
    "this month"/"last month" are deliberately NOT stripped here — see
    _PERIOD_PHRASE_STRIP_RE's own comment for why (they collide with other
    intents' own registered phrasing); check_payroll_cost_summary's bare
    "this month"/"last month" phrasing is instead handled by registering
    those exact phrases directly (registry/intents_en.yaml).
    Safe to strip before matching only — extract_period_month/
    extract_period_offset (called separately by executor_payroll_analytics.py)
    always read the period straight out of the UNSTRIPPED raw_text, so
    nothing here costs that extraction any information.
    """
    stripped = _PERIOD_PHRASE_STRIP_RE.sub('', text)
    return _WHITESPACE_RE.sub(' ', stripped).strip()
