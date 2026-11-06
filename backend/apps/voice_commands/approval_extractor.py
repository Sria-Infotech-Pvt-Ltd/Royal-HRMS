from __future__ import annotations

import re
import unicodedata
from typing import Optional

from rapidfuzz import fuzz, process

NAME_MATCH_THRESHOLD = 65

_ACTION_VERB_RE = re.compile(r'\b(approve|reject|deny)\b', re.IGNORECASE)
_POSSESSIVE_NAME_RE = re.compile(r"(?P<name>[a-z][a-z'\- ]*?)['’`]s(?=\s+leave)", re.IGNORECASE)
_FOR_NAME_RE = re.compile(r"\bfor\s+(?!leave\b)(?P<name>.+?)\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r'\s+')

# Cuts a raw "for X" capture down to just the name, dropping a trailing
# relative clause the speaker appended — e.g. "approve leave for john smith
# who has one pending leave request" -> "john smith". See
# extract_employee_name_query's docstring for why _FOR_NAME_RE itself stays
# greedy to end-of-string despite this.
_RELATIVE_CLAUSE_START_RE = re.compile(
    r"\b(?:who|which|that|having|with|whose|whom|and|but|when)\b", re.IGNORECASE,
)


def _nfc(pattern: str) -> str:
    """NFC-normalize a regex pattern literal — defensive belt-and-suspenders
    alongside parse_yes_no()'s own NFC pass on the matched-against text, so a
    combining mark (e.g. चंद्रबिंदु/chandrabindu in "हाँ") stored as either a
    single precomposed code point or a base-plus-mark decomposed sequence —
    visually identical, byte-different — still matches consistently
    regardless of which form the caller or this source file happens to use.
    """
    return unicodedata.normalize('NFC', pattern)


# Python's \b/\w classify a Devanagari nasalization mark (चंद्रबिंदु ँ U+0901,
# अनुस्वार ं U+0902 — both common WORD-FINAL letters, not decorative — as
# category Mn, "non-word") — so \b immediately after a word ENDING in one
# never matches (Python looks for a transition between the mark and
# whatever follows, but never sees the transition from the actual last
# word-character before it). Confirmed directly: 'हाँ'/'हां'/'नहीं' all failed
# to match under a trailing \b; 'बिल्कुल' (ends in a plain consonant, no
# mark) matched fine. The Hindi alternatives below use whitespace/string-
# edge lookarounds instead of \b for exactly this reason — English stays on
# \b (it has none of this, and \b also correctly allows trailing punctuation
# like "yes," that a strict whitespace boundary would reject).

# Boundary for the Devanagari alternatives below: whitespace or string-edge,
# same as \b's practical effect for English — but ALSO tolerant of "।"/"॥"
# (पूर्ण विराम / danda, Devanagari's own sentence-final punctuation, the
# equivalent of an English "."), the same way \b already tolerates English
# trailing punctuation ("yes," matches _YES_RE fine). Plain (?<!\S)/(?!\S)
# would reject "नहीं।" — a danda right after the word is not whitespace.
_HI_BEFORE = r'(?<![^\s।॥])'
_HI_AFTER = r'(?![^\s।॥])'

_YES_RE = re.compile(
    _nfc(
        r"\b(yes|yeah|yep|yup|correct|confirm|confirmed|sure|right|go ahead|do it"
        r"|haan|haanji|theek hai|thik hai|bilkul)\b"  # Hindi (romanized) — no combining marks, \b is fine
        + "|" + _HI_BEFORE + r"(?:हाँ|हां|ठीक है|बिल्कुल)" + _HI_AFTER  # Hindi (Devanagari) — see comment above
    ),
    re.IGNORECASE,
)
_NO_RE = re.compile(
    _nfc(
        r"\b(no|nope|nah|negative|cancel|stop|don't|do not"
        r"|nahi|nahin)\b"  # Hindi (romanized)
        + "|" + _HI_BEFORE + r"(?:नहीं)" + _HI_AFTER  # Hindi (Devanagari) — see _YES_RE's comment above
    ),
    re.IGNORECASE,
)
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
    """
    Best-effort extraction of the employee name mentioned in an
    approve_leave/reject_leave utterance.

    _find_name_span's own "for X" capture is greedy to end-of-string (needed
    so strip_employee_name_phrases removes a WHOLE trailing relative clause
    before intent matching, not just the name inside it — a partial strip
    would leave clause words diluting the fuzzy score against the registered
    "approve leave for" phrase). That means a sentence like "approve leave
    for john smith who has one pending leave request" raw-captures "john
    smith who has one pending leave request" as the "name" here — cut at
    the first relative-clause word so the actual person-lookup below
    (match_employee_name, WRatio) fuzzy-matches against just "john smith"
    instead. Left uncut, WRatio's leniency happens to paper over a short
    trailing clause (surviving purely on luck), but measurably degrades for
    a longer STT transcript or a 3-word name — a bug independent of, but
    easily mistaken for, an intent-classification misroute.
    """
    span = _find_name_span(text)
    if not span:
        return None
    _, _, name = span
    clause_match = _RELATIVE_CLAUSE_START_RE.search(name)
    if clause_match:
        name = name[:clause_match.start()]
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

    Recognizes both English and Hindi (romanized and Devanagari) tokens —
    see _YES_RE/_NO_RE. NFC-normalized here independently of
    normalizer.normalize_transcript's own NFC pass (every real caller
    already goes through that first) so this function is correct in
    isolation too — see _nfc's own docstring for why normalization form
    actually matters for a Devanagari match, not just belt-and-suspenders.
    """
    text = unicodedata.normalize('NFC', (text or '')).strip()
    has_yes = bool(_YES_RE.search(text)) and not _NEGATED_YES_RE.search(text)
    has_no = bool(_NO_RE.search(text))
    if has_yes and not has_no:
        return True
    if has_no and not has_yes:
        return False
    return None
