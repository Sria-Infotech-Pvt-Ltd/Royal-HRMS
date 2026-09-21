from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as dateutil_parser

from apps.hrms.models import LEAVE_TYPE_CHOICES

from apps.voice_commands.language import text

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
    'bereavement': 'bereavement',
    'compensatory': 'comp_off',
    'compensatory off': 'comp_off',
    'comp off': 'comp_off',
}
_VALID_LEAVE_TYPES = frozenset(key for key, _ in LEAVE_TYPE_CHOICES)

LEAVE_TYPE_CHOICES_PROMPT = ', '.join(label for _, label in LEAVE_TYPE_CHOICES[:-1]) + f', or {LEAVE_TYPE_CHOICES[-1][1]}'
# Hindi label per LEAVE_TYPE_CHOICES code — this app's own addition (Phase
# 3.1), kept local to voice_commands rather than touching the hrms app's
# model, mirroring executor_payroll._STATUS_LABELS_HI's own reasoning for the
# same kind of model-choices label map.
_LEAVE_TYPE_LABELS_HI = {
    'casual': 'आकस्मिक छुट्टी',
    'earned': 'अर्जित छुट्टी',
    'sick': 'बीमारी की छुट्टी',
    'lwp': 'अवैतनिक छुट्टी',
    'maternity': 'मातृत्व छुट्टी',
    'paternity': 'पितृत्व छुट्टी',
    'bereavement': 'शोक अवकाश',
    'comp_off': 'प्रतिपूरक अवकाश',
}
_LEAVE_TYPE_CHOICES_PROMPT_HI = (
    ', '.join(_LEAVE_TYPE_LABELS_HI[key] for key, _ in LEAVE_TYPE_CHOICES[:-1])
    + f', या {_LEAVE_TYPE_LABELS_HI[LEAVE_TYPE_CHOICES[-1][0]]}'
)
_LEAVE_TYPE_CHOICES_PROMPT_TEXT = {'en': LEAVE_TYPE_CHOICES_PROMPT, 'hi': _LEAVE_TYPE_CHOICES_PROMPT_HI}

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


# Bilingual pairs (Phase 3.1 — Gap 1), selected through text() at every call
# site — same pattern executor_*.py's own messages already use.
_LEAVE_TYPE_QUESTION_TEMPLATE = {
    'en': 'What type of leave would you like to apply for — {choices}?',
    'hi': 'आप किस प्रकार की छुट्टी के लिए आवेदन करना चाहेंगे — {choices}?',
}
_START_DATE_QUESTION = {
    'en': 'What date would you like your leave to start?',
    'hi': 'आप अपनी छुट्टी किस तारीख से शुरू करना चाहेंगे?',
}
_END_DATE_QUESTION = {
    'en': 'What date would you like your leave to end?',
    'hi': 'आप अपनी छुट्टी किस तारीख को समाप्त करना चाहेंगे?',
}
_REASON_QUESTION = {
    'en': 'What is the reason for this leave?',
    'hi': 'इस छुट्टी का कारण क्या है?',
}
_GENERIC_SLOT_QUESTION_TEMPLATE = {
    'en': 'Could you provide {slot_name}?',
    'hi': 'क्या आप {slot_name} बता सकते हैं?',
}
_UNRECOGNIZED_LEAVE_TYPE_TEMPLATE = {
    'en': "That's not a leave type I recognize. Please say one of: {choices}.",
    'hi': 'यह मेरे लिए पहचाना जाने वाला छुट्टी का प्रकार नहीं है। कृपया इनमें से कोई एक कहें: {choices}।',
}
_DATE_NOT_UNDERSTOOD_MESSAGE = {
    'en': "I didn't catch a date there — could you say the date again?",
    'hi': 'मुझे वहां कोई तारीख समझ नहीं आई — क्या आप तारीख फिर से बता सकते हैं?',
}
_REASON_TOO_SHORT_MESSAGE = {
    'en': 'The reason needs to be at least 10 characters — could you say a bit more?',
    'hi': 'कारण कम से कम 10 अक्षरों का होना चाहिए — क्या आप थोड़ा और बता सकते हैं?',
}
_GENERIC_SLOT_PROMPT_TEMPLATE = {
    'en': 'Please provide {slot_name}.',
    'hi': 'कृपया {slot_name} बताएं।',
}


def question_for_slot(slot_name: str) -> str:
    if slot_name == 'leave_type':
        return text(_LEAVE_TYPE_QUESTION_TEMPLATE).format(choices=text(_LEAVE_TYPE_CHOICES_PROMPT_TEXT))
    if slot_name == 'start_date':
        return text(_START_DATE_QUESTION)
    if slot_name == 'end_date':
        return text(_END_DATE_QUESTION)
    if slot_name == 'reason':
        return text(_REASON_QUESTION)
    return text(_GENERIC_SLOT_QUESTION_TEMPLATE).format(slot_name=slot_name)


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
            return None, text(_UNRECOGNIZED_LEAVE_TYPE_TEMPLATE).format(choices=text(_LEAVE_TYPE_CHOICES_PROMPT_TEXT))
        return leave_type, None

    if slot_name in ('start_date', 'end_date'):
        parsed = _parse_single_date(answer, date.today())
        if parsed is None:
            return None, text(_DATE_NOT_UNDERSTOOD_MESSAGE)
        return parsed, None

    if slot_name == 'reason':
        if len(answer) < _MIN_REASON_LENGTH:
            return None, text(_REASON_TOO_SHORT_MESSAGE)
        return answer, None

    return None, text(_GENERIC_SLOT_PROMPT_TEMPLATE).format(slot_name=slot_name)
