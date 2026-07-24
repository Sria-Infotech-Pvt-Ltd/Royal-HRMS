from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz, process

NAME_MATCH_THRESHOLD = 65

_ACTION_VERB_RE = re.compile(r'\b(approve|reject|deny)\b', re.IGNORECASE)
_POSSESSIVE_NAME_RE = re.compile(r"(?P<name>[a-z][a-z'\- ]*?)['’`]s(?=\s+leave)", re.IGNORECASE)
_FOR_NAME_RE = re.compile(r"\bfor\s+(?!leave\b)(?P<name>.+?)\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r'\s+')

_YES_RE = re.compile(r"\b(yes|yeah|yep|yup|correct|confirm|confirmed|sure|right|go ahead|do it)\b", re.IGNORECASE)
_NO_RE = re.compile(r"\b(no|nope|nah|negative|cancel|stop|don't|do not)\b", re.IGNORECASE)
# "not sure"/"not certain" contain a bare yes-word ("sure") but negate it —
# without this, "i'm not sure" would misparse as an affirmative confirmation
# to approve/reject someone's leave request.
_NEGATED_YES_RE = re.compile(r"\b(?:not|n't|ain't)\s+(?:sure|certain)\b", re.IGNORECASE)


def _find_name_span(text: str) -> Optional[tuple]:
    """
    Locate a name-bearing pattern in text — "approve X's leave request" or
    "approve leave for X" — but only when an approve/reject/deny verb is
    actually present, and only in the text AFTER that verb. Both restrictions
    matter: the verb guard keeps this from misfiring on unrelated phrases
    that happen to contain "for" or "'s" (e.g. check_team_leave_queue's "show
    my team's leave requests", which has no approve/reject/deny verb at all);
    searching only after the verb keeps the lazy name group from greedily
    swallowing the verb itself (e.g. "approve sarah's leave request" — without
    this, re.search's leftmost-match preference would capture "approve sarah"
    as the name instead of just "sarah").

    Returns (start, end, name) where (start, end) is the span to remove for
    matching purposes — for the possessive form that includes the "'s"
    marker itself; for the "for X" form it's just the name, leaving "for" in
    place since that word is part of the registered phrase, not slot content.
    """
    verb_match = _ACTION_VERB_RE.search(text)
    if not verb_match:
        return None
    offset = verb_match.end()
    region = text[offset:]

    match = _POSSESSIVE_NAME_RE.search(region)
    if match:
        return offset + match.start(), offset + match.end(), match.group('name').strip()

    match = _FOR_NAME_RE.search(region)
    if match:
        return offset + match.start('name'), offset + match.end('name'), match.group('name').strip()

    return None


def extract_employee_name_query(text: str) -> Optional[str]:
    """Best-effort extraction of the employee name mentioned in an approve_leave/reject_leave utterance."""
    span = _find_name_span(text)
    if not span:
        return None
    _, _, name = span
    name = name.strip(" .,'\"")
    return name or None


def strip_employee_name_phrases(text: str) -> str:
    """
    Remove the name-bearing span from text before intent matching — mirrors
    slot_extractor.strip_leave_slot_phrases for apply_leave. Left in, a name
    appended to "approve leave for" drags the fuzzy score against the
    registered action phrase down.
    """
    span = _find_name_span(text)
    if not span:
        return text
    start, end, _ = span
    stripped = text[:start] + text[end:]
    return _WHITESPACE_RE.sub(' ', stripped).strip()


def match_employee_name(name_query: Optional[str], candidates: list) -> list:
    """
    Fuzzy-match name_query against candidates' 'employee_name' field.
    candidates is a list of dicts, each with at least an 'employee_name' key.
    Returns the subset of candidates whose name scores >= NAME_MATCH_THRESHOLD,
    preserving candidates' original order and identity (duplicate names are
    matched independently by position, not deduplicated).
    """
    if not name_query or not candidates:
        return []

    names = [c['employee_name'] for c in candidates]
    results = process.extract(
        name_query, names, scorer=fuzz.WRatio, score_cutoff=NAME_MATCH_THRESHOLD, limit=None,
    )
    matched_indices = {idx for _, _, idx in results}
    return [candidate for i, candidate in enumerate(candidates) if i in matched_indices]


def parse_yes_no(text: str) -> Optional[bool]:
    """
    Parse a confirmation answer. Returns True/False for an unambiguous
    yes/no, or None when the answer doesn't clearly say either — callers
    must re-ask rather than guess (never interpret an unclear answer as
    consent to approve/reject someone's leave).
    """
    text = (text or '').strip()
    has_yes = bool(_YES_RE.search(text)) and not _NEGATED_YES_RE.search(text)
    has_no = bool(_NO_RE.search(text))
    if has_yes and not has_no:
        return True
    if has_no and not has_yes:
        return False
    return None
