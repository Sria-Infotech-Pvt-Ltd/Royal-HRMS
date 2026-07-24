from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as dateutil_parser

from apps.hrms.models import LEAVE_TYPE_CHOICES

REQUIRED_SLOTS = ['leave_type', 'start_date', 'end_date', 'reason']

# Spoken synonyms -> the canonical LEAVE_TYPE_CHOICES key the API expects.
# Built from LEAVE_TYPE_CHOICES rather than a separate hardcoded list of
# valid keys, so a new leave type added to the model is picked up here too.
_LEAVE_TYPE_SYNONYMS = {
    'casual': 'casual',
    'earned': 'earned',
    'annual': 'earned',
    'sick': 'sick',
    'medical': 'sick',
    'lwp': 'lwp',
    'loss of pay': 'lwp',
    'unpaid': 'lwp',
    'without pay': 'lwp',
    'maternity': 'maternity',
    'paternity': 'paternity',
}
_VALID_LEAVE_TYPES = frozenset(key for key, _ in LEAVE_TYPE_CHOICES)

LEAVE_TYPE_CHOICES_PROMPT = ', '.join(label for _, label in LEAVE_TYPE_CHOICES[:-1]) + f', or {LEAVE_TYPE_CHOICES[-1][1]}'

_MIN_REASON_LENGTH = 10  # mirrors LeaveRequestCreateSerializer.validate_reason

_DATE_RANGE_RE = re.compile(r'\bfrom\b(.+?)\bto\b(.+)', re.IGNORECASE)
_RELATIVE_DAY_OFFSETS = {'day after tomorrow': 2, 'tomorrow': 1, 'today': 0}
_REASON_MARKER_RE = re.compile(r'\b(because|reason is|reason being|due to)\b', re.IGNORECASE)
_WHITESPACE_RE = re.compile(r'\s+')


def extract_leave_type(text: str) -> Optional[str]:
    lowered = text.lower()
    for keyword, canonical in _LEAVE_TYPE_SYNONYMS.items():
        if keyword in lowered:
            return canonical
    return None


def _parse_single_date(fragment: str, today: date, *, allow_relative: bool = True) -> Optional[date]:
    """
    allow_relative gates the today/tomorrow/day-after-tomorrow shortcut.
    It must stay off whenever fragment can be an arbitrary sentence rather
    than an actual date-answer fragment — the phrase check below is a raw
    substring match, so "tomorrow" anywhere in a full sentence (e.g. "apply
    for sick leave tomorrow") would otherwise resolve as a date even though
    it was never a targeted answer to a date question. See
    extract_date_range's no-range fallback branch and the regression tests
    in tests/test_apply_leave_conversation.py.
    """
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


def extract_date_range(text: str, today: Optional[date] = None) -> tuple[Optional[date], Optional[date]]:
    """
    Look for an explicit "from X to Y" range first (the phrasing the
    apply_leave phrases are written around) — the captured X/Y fragments are
    targeted date phrases, so relative-day words are honored there. Falls
    back to treating the whole text as a single day (start == end) when no
    range marker is found — e.g. "on july 22" as part of a full first
    utterance. Relative-day words are NOT honored in that fallback: text
    there can be an arbitrary sentence (extract_apply_leave_slots passes the
    entire first utterance), so a substring match on "today"/"tomorrow"
    would misfire on any sentence that merely mentions the word, unrelated
    to the actual leave date. Only an unambiguous absolute date (a real
    dateutil-recognized date token) is accepted in that branch; relative
    words are still resolved in parse_slot_answer(), where the whole answer
    IS the date fragment because the system specifically just asked for one.
    """
    today = today or date.today()
    range_match = _DATE_RANGE_RE.search(text)
    if range_match:
        start = _parse_single_date(range_match.group(1), today)
        end = _parse_single_date(range_match.group(2), today)
        return start, end

    single = _parse_single_date(text, today, allow_relative=False)
    return single, single


def extract_reason(text: str) -> Optional[str]:
    match = _REASON_MARKER_RE.search(text)
    if not match:
        return None
    reason = text[match.end():].strip(' .,')
    return reason or None


def extract_apply_leave_slots(text: str) -> dict:
    """Best-effort extraction of whichever apply_leave slots are present in one utterance."""
    slots = {}

    leave_type = extract_leave_type(text)
    if leave_type:
        slots['leave_type'] = leave_type

    start, end = extract_date_range(text)
    if start:
        slots['start_date'] = start
    if end:
        slots['end_date'] = end

    reason = extract_reason(text)
    if reason:
        slots['reason'] = reason

    return slots


def strip_leave_slot_phrases(text: str) -> str:
    """
    Remove recognizable leave-type keywords, "from X to Y" date ranges, and a
    trailing reason clause from text before intent matching — mirrors
    mode_extractor.extract_attendance_mode() stripping mode phrases before
    match_intent(). Left in, a fully slot-filled utterance like "apply for
    sick leave from july 22 to july 24" drags the fuzzy score against the
    short "apply for leave" registry phrase well below the match threshold.
    """
    stripped = text

    range_match = _DATE_RANGE_RE.search(stripped)
    if range_match:
        stripped = stripped[:range_match.start()] + stripped[range_match.end():]

    reason_match = _REASON_MARKER_RE.search(stripped)
    if reason_match:
        stripped = stripped[:reason_match.start()]

    for keyword in _LEAVE_TYPE_SYNONYMS:
        stripped = stripped.replace(keyword, '')

    return _WHITESPACE_RE.sub(' ', stripped).strip()


def next_missing_slot(slots: dict) -> Optional[str]:
    for name in REQUIRED_SLOTS:
        if not slots.get(name):
            return name
    return None


def question_for_slot(slot_name: str) -> str:
    if slot_name == 'leave_type':
        return f'What type of leave would you like to apply for — {LEAVE_TYPE_CHOICES_PROMPT}?'
    if slot_name == 'start_date':
        return 'What date would you like your leave to start?'
    if slot_name == 'end_date':
        return 'What date would you like your leave to end?'
    if slot_name == 'reason':
        return 'What is the reason for this leave?'
    return f'Could you provide {slot_name}?'


def parse_slot_answer(slot_name: str, answer: str) -> tuple[Optional[object], Optional[str]]:
    """
    Parse a clarification answer for the single slot currently being asked.
    Returns (value, None) on success, or (None, error_message) to re-ask —
    never guesses when the answer doesn't fit what was asked (rule 5 of the
    apply_leave flow: a bad answer re-asks, it never advances or fails silently).
    """
    answer = (answer or '').strip()

    if slot_name == 'leave_type':
        leave_type = extract_leave_type(answer)
        if leave_type is None or leave_type not in _VALID_LEAVE_TYPES:
            return None, (
                f"That's not a leave type I recognize. Please say one of: {LEAVE_TYPE_CHOICES_PROMPT}."
            )
        return leave_type, None

    if slot_name in ('start_date', 'end_date'):
        parsed = _parse_single_date(answer, date.today())
        if parsed is None:
            return None, "I didn't catch a date there — could you say the date again?"
        return parsed, None

    if slot_name == 'reason':
        if len(answer) < _MIN_REASON_LENGTH:
            return None, 'The reason needs to be at least 10 characters — could you say a bit more?'
        return answer, None

    return None, f'Please provide {slot_name}.'
