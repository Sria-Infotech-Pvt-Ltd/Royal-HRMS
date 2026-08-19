from __future__ import annotations

import re
from datetime import date
from typing import Optional

from apps.attendance.models import AttendanceCorrection
from apps.voice_commands.correction_datetime_extractor import (
    _24H_TIME_RE,
    _DATE_SPAN_RE,
    _MERIDIEM_TIME_RE,
    _RELATIVE_DAY_OFFSETS,
    _parse_correction_date,
    extract_correction_date,
    extract_time,
)

# Split out from slot_extractor.py (apply_leave's own slot-filling module)
# rather than added into it — this is a different domain with a genuinely
# different shape of problem (a conditionally-required slot, and a new
# TIME slot type slot_extractor.py never needed), and slot_extractor.py is
# already sized close to this project's 300-line file convention.
#
# Date/time parsing itself lives in correction_datetime_extractor.py (this
# file was, in turn, over the same 300-line convention) — this module keeps
# punch_type/reason extraction plus the multi-slot orchestration
# (extract_correction_slots, strip_correction_slot_phrases,
# next_missing_slot, question_for_slot, parse_slot_answer) that needs both
# halves together.

# date/punch_type/reason are unconditionally required; correct_in_time and
# correct_out_time depend on punch_type — see next_missing_slot(), which is
# why this isn't a flat list like slot_extractor.REQUIRED_SLOTS.
BASE_REQUIRED_SLOTS = ['date', 'punch_type', 'reason']

_PUNCH_TYPE_SYNONYMS = {
    'both in and out': 'BOTH', 'in and out': 'BOTH', 'both': 'BOTH',
    'whole day': 'BOTH', 'entire day': 'BOTH', 'full day': 'BOTH',
    'clock in': 'IN', 'clocking in': 'IN', 'punch in': 'IN', 'punching in': 'IN', 'punched in': 'IN',
    'clock out': 'OUT', 'clocking out': 'OUT', 'punch out': 'OUT', 'punching out': 'OUT', 'punched out': 'OUT',
}
# Only trusted as a targeted answer (see extract_punch_type's targeted_answer
# flag) — as a bare substring against an arbitrary sentence, "in"/"out" would
# false-positive constantly (e.g. "in the morning", "went out for lunch").
_BARE_PUNCH_TYPE_WORDS = {'in': 'IN', 'out': 'OUT'}

_REASON_SYNONYMS = {
    'biometric': AttendanceCorrection.REASON_BIOMETRIC,
    'fingerprint': AttendanceCorrection.REASON_BIOMETRIC,
    'device malfunction': AttendanceCorrection.REASON_BIOMETRIC,
    'device': AttendanceCorrection.REASON_BIOMETRIC,
    'forgot': AttendanceCorrection.REASON_FORGOT,
    'forget': AttendanceCorrection.REASON_FORGOT,
    'field work': AttendanceCorrection.REASON_FIELD_WORK,
    'field visit': AttendanceCorrection.REASON_FIELD_WORK,
    'client visit': AttendanceCorrection.REASON_FIELD_WORK,
    'client site': AttendanceCorrection.REASON_FIELD_WORK,
    'downtime': AttendanceCorrection.REASON_SYSTEM,
    'other': AttendanceCorrection.REASON_OTHER,
}
_VALID_REASONS = frozenset(key for key, _ in AttendanceCorrection.REASON_CHOICES)
_REASON_LABELS = [label for _, label in AttendanceCorrection.REASON_CHOICES]
REASON_CHOICES_PROMPT = ', '.join(_REASON_LABELS[:-1]) + f', or {_REASON_LABELS[-1]}'

# 'system down'/'server down' as a bare substring check misses the common
# "the system WAS down"/"IS down" phrasing (the verb sits between the two
# words) — a small regex instead of another dict entry, since there's no
# fixed set of literal phrasings that would reliably cover this one.
_SYSTEM_DOWN_RE = re.compile(r'\b(system|server)\b.{0,15}\bdown\b', re.IGNORECASE)

_WHITESPACE_RE = re.compile(r'\s+')


def extract_punch_type(text: str, *, targeted_answer: bool = False) -> Optional[str]:
    lowered = text.lower()
    for phrase, canonical in _PUNCH_TYPE_SYNONYMS.items():
        if phrase in lowered:
            return canonical
    if targeted_answer:
        # The whole answer IS the punch type this time (the question just
        # asked "clock-in, clock-out, or both?") — a bare "in"/"out" is
        # unambiguous in that context, unlike in a free-form sentence.
        for word in lowered.split():
            if word in _BARE_PUNCH_TYPE_WORDS:
                return _BARE_PUNCH_TYPE_WORDS[word]
    return None


def extract_correction_reason(text: str) -> Optional[str]:
    if _SYSTEM_DOWN_RE.search(text):
        return AttendanceCorrection.REASON_SYSTEM
    lowered = text.lower()
    for keyword, canonical in _REASON_SYNONYMS.items():
        if keyword in lowered:
            return canonical
    return None


def looks_like_correction_reason(text: str) -> bool:
    """
    Stricter than a plain extract_correction_reason(text) truthiness check —
    excludes REASON_OTHER, whose only keyword is the bare word "other". That
    one word is common enough in ordinary unrelated sentences ("any other
    options", "something other than that") that trusting it here would
    false-positive constantly. Used only by conversation.py's
    _looks_like_expired_slot_answer, which is picking a friendlier message,
    not extracting a real slot value — extract_correction_reason itself
    keeps accepting "other" everywhere it's used as an actual answer to the
    reason question, where the context already makes it unambiguous.
    """
    reason = extract_correction_reason(text)
    return reason is not None and reason != AttendanceCorrection.REASON_OTHER


def extract_correction_slots(text: str) -> dict:
    """Best-effort extraction of whichever correction slots are present in
    one utterance — mirrors slot_extractor.extract_apply_leave_slots. Only
    attempts a single time value when punch_type resolves to IN or OUT
    (unambiguous which field it belongs to); a BOTH utterance with two times
    in one breath ("in at 9, out at 6") isn't captured here — the multi-turn
    flow just asks for whichever time is still missing on the next turn."""
    slots = {}

    correction_date = extract_correction_date(text)
    if correction_date and correction_date <= date.today():
        slots['date'] = correction_date

    punch_type = extract_punch_type(text)
    if punch_type:
        slots['punch_type'] = punch_type

    reason = extract_correction_reason(text)
    if reason:
        slots['reason'] = reason

    if punch_type == 'IN':
        found_time = extract_time(text)
        if found_time:
            slots['correct_in_time'] = found_time
    elif punch_type == 'OUT':
        found_time = extract_time(text)
        if found_time:
            slots['correct_out_time'] = found_time

    return slots


def strip_correction_slot_phrases(text: str) -> str:
    """Remove a recognizable date, time(s), punch-type phrase, and reason
    clause before intent matching — mirrors
    slot_extractor.strip_leave_slot_phrases. Left in, a fully slot-filled
    utterance drags the fuzzy score against the short registered phrase down
    (e.g. "correct my clock in on july 20 2026 to 9:15 am, i forgot to
    punch" needs all four stripped to land anywhere near "correct my
    attendance").

    Several punch-type synonyms ("clock in", "clock out", "punch in",
    "punch out") are ALSO the literal registered phrases for the separate
    clock_in/clock_out intents — stripping one of those unconditionally
    would erase a genuine bare "clock in" command down to nothing before it
    ever reaches match_intent(). The guard below only applies a punch-type
    removal when it leaves at least two words behind, which is the
    difference between "clock in"/"clock in karo" (the whole command, plus
    at most one trailing filler/verb word from natural speech — must
    survive untouched) and "...my clock in time was wrong..." (a mention
    inside a much longer correction sentence — safe to strip). A one-word
    remainder threshold (bug found 2026-08-19 via real Sarvam transcripts:
    "clock in karo"/"clock in cr" were being stripped down to just "karo"/
    "cr" and then failing to match anything, silently breaking every voice
    clock-in that Sarvam transcribed with a properly-spaced "clock in"
    instead of typed-input's "clockin") was too weak — a single incidental
    word left over doesn't make an utterance a genuine correction sentence.
    """
    stripped = _SYSTEM_DOWN_RE.sub('', text)
    stripped = _DATE_SPAN_RE.sub('', stripped)
    stripped = _MERIDIEM_TIME_RE.sub('', stripped)
    stripped = _24H_TIME_RE.sub('', stripped)
    for phrase in _RELATIVE_DAY_OFFSETS:
        stripped = stripped.replace(phrase, '')

    for phrase in _PUNCH_TYPE_SYNONYMS:
        candidate = stripped.replace(phrase, '')
        if len(_WHITESPACE_RE.sub(' ', candidate).strip().split()) >= 2:
            stripped = candidate

    for keyword in _REASON_SYNONYMS:
        stripped = stripped.replace(keyword, '')

    return _WHITESPACE_RE.sub(' ', stripped).strip()


def next_missing_slot(slots: dict) -> Optional[str]:
    """Unlike slot_extractor.next_missing_slot's flat REQUIRED_SLOTS walk,
    which slot(s) come after punch_type depend on ITS value — the serializer
    itself enforces this same conditional requirement (CorrectionWriteSerializer
    .validate(), apps/attendance/serializers_my_attendance.py:80-104), so the
    voice flow asks the same way it would eventually be rejected otherwise."""
    if not slots.get('date'):
        return 'date'
    if not slots.get('punch_type'):
        return 'punch_type'

    punch_type = slots['punch_type']
    if punch_type in ('IN', 'BOTH') and not slots.get('correct_in_time'):
        return 'correct_in_time'
    if punch_type in ('OUT', 'BOTH') and not slots.get('correct_out_time'):
        return 'correct_out_time'

    if not slots.get('reason'):
        return 'reason'
    return None


def question_for_slot(slot_name: str) -> str:
    if slot_name == 'date':
        return 'What date was the punch you need corrected?'
    if slot_name == 'punch_type':
        return 'Was this for your clock-in, clock-out, or both?'
    if slot_name == 'correct_in_time':
        return 'What should the correct clock-in time be?'
    if slot_name == 'correct_out_time':
        return 'What should the correct clock-out time be?'
    if slot_name == 'reason':
        return f'What is the reason — {REASON_CHOICES_PROMPT}?'
    return f'Could you provide {slot_name}?'


def parse_slot_answer(slot_name: str, answer: str) -> tuple[Optional[object], Optional[str]]:
    """Parse a clarification answer for the single slot currently being
    asked — mirrors slot_extractor.parse_slot_answer: a bad answer re-asks,
    it never advances or fails silently."""
    answer = (answer or '').strip()

    if slot_name == 'date':
        parsed = _parse_correction_date(answer, date.today(), allow_relative=True)
        if parsed is None:
            return None, "I didn't catch a date there — could you say the date again?"
        if parsed > date.today():
            return None, (
                "That date is in the future — corrections can only be filed for a past punch. "
                "What date was it?"
            )
        return parsed, None

    if slot_name == 'punch_type':
        punch_type = extract_punch_type(answer, targeted_answer=True)
        if punch_type is None:
            return None, 'Please say clock-in, clock-out, or both.'
        return punch_type, None

    if slot_name in ('correct_in_time', 'correct_out_time'):
        parsed_time = extract_time(answer)
        if parsed_time is None:
            return None, "I didn't catch a time there — could you say it again, like '9:15 AM'?"
        return parsed_time, None

    if slot_name == 'reason':
        reason = extract_correction_reason(answer)
        if reason is None or reason not in _VALID_REASONS:
            return None, f"That's not a reason I recognize. Please say one of: {REASON_CHOICES_PROMPT}."
        return reason, None

    return None, f'Please provide {slot_name}.'
