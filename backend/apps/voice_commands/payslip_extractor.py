from __future__ import annotations

import re
from typing import Optional

NAME_MATCH_THRESHOLD = 65

# Reuses the exact same "because/reason is/reason being/due to" marker set as
# slot_extractor.py's reason extraction for apply_leave — that logic has no
# leave-specific coupling (it's a generic "find a marker word, return the
# trailing clause" scan), but slot_extractor.py doesn't export it as a
# standalone function (it's folded into extract_apply_leave_slots/
# strip_leave_slot_phrases), so the small regex is duplicated here rather
# than importing a leave-named helper into payroll's own conversation flow.
_DESCRIPTION_MARKER_RE = re.compile(r'\b(because|reason is|reason being|due to)\b', re.IGNORECASE)
_WHITESPACE_RE = re.compile(r'\s+')

# A lookup verb/trigger phrase gates where name search is allowed to start —
# mirrors approval_extractor.py's _ACTION_VERB_RE gate exactly, and for the
# same reason: the name group's character class has to include spaces (real
# names are multi-word), so without restricting the search to the region
# AFTER a trigger, re.search's leftmost-match preference would greedily
# capture the trigger words themselves as part of the "name" whenever they
# happen to precede the possessive marker too (e.g. "check sarah khan's
# payslip" -> "check sarah khan" instead of just "sarah khan").
_LOOKUP_TRIGGER_RE = re.compile(
    r'\b(check|show|pull up|look up|what is|what\'s|how much did)\b', re.IGNORECASE,
)
_PAYROLL_KEYWORD_RE = re.compile(r'\b(payslip|salary|paycheck|net\s+pay|pay)\b', re.IGNORECASE)
_POSSESSIVE_NAME_RE = re.compile(
    r"(?P<name>[a-z][a-z'\- ]*?)['’`]s(?=\s+(?:payslip|salary|paycheck|net\s+pay|pay)\b)",
    re.IGNORECASE,
)
_FOR_NAME_RE = re.compile(r"\bfor\s+(?!(?:me|myself)\b)(?P<name>.+?)\s*$", re.IGNORECASE)

# Keyword-based, not tied to any one registered phrase's exact wording — a
# transcript is treated as "download-flavored" purely by mentioning one of
# these, independent of which registered phrase the fuzzy matcher actually
# picked (fuzzy matching can land on a slightly different registered phrase
# than the one a human would guess, so string-comparing against a specific
# matched phrase would be fragile).
_DOWNLOAD_KEYWORD_RE = re.compile(r'\b(download|pdf|send me|email me|a copy)\b', re.IGNORECASE)


def extract_payslip_query_description(text: str) -> Optional[str]:
    """Best-effort extraction of a query's content when it's given in the same
    breath as the request, e.g. 'raise a query about my payslip because the
    HRA looks wrong' -> 'the hra looks wrong'."""
    match = _DESCRIPTION_MARKER_RE.search(text)
    if not match:
        return None
    description = text[match.end():].strip(' .,')
    return description or None


def strip_payslip_query_phrases(text: str) -> str:
    """Remove a trailing description clause before intent matching — mirrors
    slot_extractor.strip_leave_slot_phrases: left in, a fully-stated query
    like 'raise a query about my payslip because the hra looks wrong' drags
    the fuzzy score against the short registered phrase down."""
    match = _DESCRIPTION_MARKER_RE.search(text)
    if not match:
        return text
    return text[:match.start()].strip()


def looks_like_download_request(text: str) -> bool:
    """True when the transcript reads as asking for a downloadable file
    rather than to raise a query — used only to pick which preamble
    raise_payslip_query opens with; both phrasings resolve to the same
    intent (see registry/intents_en.yaml)."""
    return bool(_DOWNLOAD_KEYWORD_RE.search(text))


def _find_name_span(text: str) -> Optional[tuple]:
    """
    Returns (start, end, name) in TEXT's own coordinates, where (start, end)
    is the span to remove for matching purposes. Only searches the region
    after a lookup trigger (check/show/pull up/...) — see _LOOKUP_TRIGGER_RE
    above for why an unrestricted search is unsafe here.
    """
    trigger_match = _LOOKUP_TRIGGER_RE.search(text)
    if not trigger_match:
        return None
    offset = trigger_match.end()
    region = text[offset:]

    match = _POSSESSIVE_NAME_RE.search(region)
    if match:
        # match.end() (the whole match, not match.end('name')) intentionally
        # includes the trailing "'s" itself — mirrors
        # approval_extractor._find_name_span, so stripping this span removes
        # the possessive marker along with the name, not just the name.
        return offset + match.start('name'), offset + match.end(), match.group('name').strip()

    if not _PAYROLL_KEYWORD_RE.search(region):
        return None
    match = _FOR_NAME_RE.search(region)
    if match:
        return offset + match.start('name'), offset + match.end('name'), match.group('name').strip()

    return None


def extract_employee_name_query(text: str) -> Optional[str]:
    """Best-effort extraction of the employee name mentioned in a
    check_employee_payslip utterance, e.g. 'check sarah khan's payslip' or
    'show payslip for sarah'."""
    span = _find_name_span(text)
    if not span:
        return None
    _, _, name = span
    name = name.strip(" .,'\"")
    return name or None


def strip_employee_name_phrases(text: str) -> str:
    """Remove the name-bearing span before intent matching — mirrors
    approval_extractor.strip_employee_name_phrases for approve/reject_leave."""
    span = _find_name_span(text)
    if not span:
        return text
    start, end, _ = span
    stripped = text[:start] + text[end:]
    return _WHITESPACE_RE.sub(' ', stripped).strip()
