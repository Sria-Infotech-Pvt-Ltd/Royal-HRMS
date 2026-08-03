from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Optional

from dateutil import parser as dateutil_parser

# Split out of correction_slot_extractor.py (over this project's 300-line
# file convention) — this half owns date/time parsing, the other half
# (correction_slot_extractor.py) owns punch_type/reason extraction plus the
# multi-slot orchestration that ties both halves together. Mirrors how
# mode_extractor.py and slot_extractor.py are already separate concerns for
# apply_leave, though the split here is within a single domain rather than
# between two unrelated ones.

_RELATIVE_DAY_OFFSETS = {'day before yesterday': -2, 'yesterday': -1, 'today': 0}

# Correction dates are inherently past-oriented (regularizing a punch that
# already happened) — unlike apply_leave's forward-looking
# today/tomorrow/day-after-tomorrow shortcuts, so this is its own small
# offsets table rather than reused from slot_extractor.py.

# Literal digit-based times only ("9 am", "9:30 pm", "17:30") — idiomatic
# phrasing like "quarter past nine" or "half nine" is NOT supported.
# Deliberately NOT built on dateutil_parser like the date helpers below:
# dateutil's fuzzy mode can silently misread a bare number ("5 in the
# evening") as a date component instead of an hour, defaulting the time to
# midnight without raising — a regex that requires an unambiguous time
# marker (a colon, or am/pm) is safer than trusting fuzzy parsing here.
_MERIDIEM_TIME_RE = re.compile(
    r'\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<meridiem>a\.?m\.?|p\.?m\.?)\b', re.IGNORECASE,
)
_24H_TIME_RE = re.compile(r'\b(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)\b')

# Used only by strip_correction_slot_phrases, to remove a spoken date span
# before intent matching — mirrors why apply_leave's strip_leave_slot_phrases
# removes its "from X to Y" range. Covers "<month> <day>[, <year>]" and
# "<day> <month>[, <year>]"; deliberately a separate regex from the
# extraction path above (_parse_correction_date/dateutil), since stripping
# needs the matched SPAN, not just the parsed value dateutil returns.
_MONTH_NAMES_RE = (
    r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?'
)
_DATE_SPAN_RE = re.compile(
    rf'\b(?:{_MONTH_NAMES_RE})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?\b'
    rf'|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTH_NAMES_RE})\.?(?:,?\s*\d{{4}})?\b'
    rf'|\b\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\b',
    re.IGNORECASE,
)


def _parse_correction_date(fragment: str, today: date, *, allow_relative: bool) -> Optional[date]:
    """Same fuzzy-dateutil approach as slot_extractor._parse_single_date, but
    with past-oriented relative words (yesterday/today/day before yesterday)
    instead of apply_leave's forward-looking ones — corrections regularize a
    punch that already happened, so "tomorrow" makes no sense as a shortcut
    here even though the underlying parsing mechanism is the same idea."""
    fragment = fragment.strip()
    if not fragment:
        return None
    if allow_relative:
        for phrase, offset in _RELATIVE_DAY_OFFSETS.items():
            if phrase in fragment.lower():
                return today + timedelta(days=offset)
    try:
        parsed = dateutil_parser.parse(
            fragment, fuzzy=True, default=datetime(today.year, today.month, today.day),
        )
    except (ValueError, OverflowError):
        return None
    return parsed.date()


def extract_correction_date(text: str, today: Optional[date] = None) -> Optional[date]:
    """First-utterance extraction — allow_relative=False for the same reason
    slot_extractor.extract_date_range's fallback branch gives: text here can
    be an arbitrary sentence, so a bare substring check for "today"/
    "yesterday" would misfire on any sentence merely mentioning the word."""
    today = today or date.today()
    return _parse_correction_date(text, today, allow_relative=False)


def extract_time(text: str) -> Optional[time]:
    match = _MERIDIEM_TIME_RE.search(text)
    if match:
        hour = int(match.group('hour'))
        minute = int(match.group('minute') or 0)
        if not (1 <= hour <= 12) or not (0 <= minute <= 59):
            return None
        meridiem = match.group('meridiem').lower().replace('.', '')
        if meridiem == 'pm' and hour != 12:
            hour += 12
        elif meridiem == 'am' and hour == 12:
            hour = 0
        return time(hour, minute)

    match = _24H_TIME_RE.search(text)
    if match:
        return time(int(match.group('hour')), int(match.group('minute')))

    return None
