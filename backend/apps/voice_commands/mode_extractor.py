from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from apps.attendance.models import AttendancePunch

_REGISTRY_DIR = Path(__file__).resolve().parent / 'registry'
DEFAULT_LANG = 'en'
_WHITESPACE_RE = re.compile(r'\s+')

_MODE_CONSTANTS = {
    'office':          AttendancePunch.MODE_OFFICE,
    'wfh':             AttendancePunch.MODE_WFH,
    'field':           AttendancePunch.MODE_FIELD,
    'client_location': AttendancePunch.MODE_CLIENT_LOCATION,
    'remote_office':   AttendancePunch.MODE_REMOTE_OFFICE,
}

# A mode phrase spoken with a leading preposition ("from office", "at client
# location", "for field work") must have that preposition stripped along
# with the phrase itself — left in, it drags the fuzzy score against the
# intent's own phrase list below match_intent()'s threshold, exactly the
# "clock in from home" bug, just triggered by whichever preposition/phrase
# combination the registry doesn't happen to spell out. Handled generically
# below instead of enumerating "from X"/"at X"/"for X" as separate registry
# phrases per mode.
#
# "in" is deliberately NOT in this set: clock_in's own phrases ("clock in",
# "clock me in", "punch in") end in "in", so a mode phrase spoken right after
# one of those ("clock in office") would otherwise have that verb-final "in"
# mistaken for the mode's leading preposition and stripped along with it —
# breaking the clock_in match instead of fixing it. The two mode phrases
# that need "in" ("in office", "in the field") are registered as literal
# phrases instead, so "in" is only ever consumed as part of an exact match.
_LEADING_PREPOSITIONS = ('from', 'at', 'for')
_TRAILING_PREPOSITION_RE = re.compile(r'\b(?:' + '|'.join(_LEADING_PREPOSITIONS) + r')\s*$')


def _registry_path_for(lang: str) -> Path:
    path = _REGISTRY_DIR / f'intents_{lang}.yaml'
    if path.exists():
        return path
    return _REGISTRY_DIR / f'intents_{DEFAULT_LANG}.yaml'


@lru_cache(maxsize=8)
def _get_mode_phrase_index(registry_path: Path) -> dict:
    """
    Map every registered mode phrase -> its mode key, e.g. {'home': 'wfh'},
    ordered longest phrase first. Order matters: "office" is a substring of
    "remote office", so checking the short bare phrase first would misread
    "clock in at remote office" as plain office mode instead of remote_office.
    """
    with open(registry_path, 'r', encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}

    index = {}
    for mode_key, phrases in data.get('mode_phrases', {}).items():
        for phrase in phrases:
            index[phrase] = mode_key
    return dict(sorted(index.items(), key=lambda item: len(item[0]), reverse=True))


def extract_attendance_mode(normalized_text: str, lang: str = DEFAULT_LANG) -> tuple[Optional[str], str]:
    """
    Scan normalized_text for a registered attendance-mode phrase, strip it
    (and any leading preposition introducing it — see _LEADING_PREPOSITIONS)
    out, and return (mode_constant_or_None, remaining_text).

    Must run BEFORE intent matching, not after: a mode phrase left in the
    transcript (e.g. 'clock in from home') drags the fuzzy score against the
    intent's own phrase list ('clock in') below match_intent()'s confidence
    threshold, causing a false no_match. Stripping the mode phrase first
    leaves the clean intent phrase for the matcher to score.

    Returns (None, normalized_text unchanged) when no mode phrase is found —
    None, not a default, because clock_in and clock_out apply different
    fallback policies when nothing was said explicitly (see executor.py):
    clock_in defaults to MODE_OFFICE like a fresh web punch does, while
    clock_out inherits the mode from today's still-open IN punch.
    """
    phrase_index = _get_mode_phrase_index(_registry_path_for(lang))

    for phrase, mode_key in phrase_index.items():
        start = normalized_text.find(phrase)
        if start == -1:
            continue

        before = normalized_text[:start]
        preposition_match = _TRAILING_PREPOSITION_RE.search(before)
        removal_start = preposition_match.start() if preposition_match else start

        remaining = normalized_text[:removal_start] + normalized_text[start + len(phrase):]
        remaining = _WHITESPACE_RE.sub(' ', remaining).strip()
        return _MODE_CONSTANTS[mode_key], remaining

    return None, normalized_text
