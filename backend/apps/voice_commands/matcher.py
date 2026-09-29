from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

_REGISTRY_DIR = Path(__file__).resolve().parent / 'registry'
DEFAULT_LANG = 'en'
DEFAULT_CONFIDENCE_THRESHOLD = 80

# Below DEFAULT_CONFIDENCE_THRESHOLD but at or above this, the closest phrase
# is a plausible guess worth confirming ("did you mean: ...?") rather than an
# outright no-match — see conversation.py's clarification flow. Chosen from
# real logs/voice_commands.log near-misses: garbled speech-to-text renderings
# of registered phrases ("raise a queryAbout my Paisley" for "...my payslip",
# "raise a query about my attendance") scored 62.5-75.0, while genuinely
# unrelated transcripts ("Status", "Think", "Water and", "A playlist") topped
# out at 57.1 — a clean, empirically-observed gap to draw the line in.
CLARIFICATION_CONFIDENCE_THRESHOLD = 60

NO_MATCH_INTENT = 'no_match'

# Guards the clarification band below — see _shares_meaningful_word's own
# docstring for why a raw fuzzy score alone isn't enough there (BUG-002,
# 2026-09-23: "what is the weather today?" got a confident-sounding "did you
# mean: who's present today?" purely from shared filler words). Deliberately
# small and English-only (a handful of near-universal function words), not an
# exhaustive stopword list — it only needs to strip enough noise that overlap
# in what's LEFT is a meaningful signal, not eliminate every possible filler.
_STOPWORDS = frozenset({
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'am', 'be', 'been', 'being',
    'what', 'when', 'where', 'who', 'whom', 'which', 'why', 'how',
    'i', 'me', 'my', 'mine', 'you', 'your', 'yours', 'he', 'him', 'his', 'she', 'her', 'hers',
    'it', 'its', 'we', 'us', 'our', 'ours', 'they', 'them', 'their', 'theirs',
    'do', 'does', 'did', 'done', 'doing', 'have', 'has', 'had',
    'to', 'of', 'in', 'on', 'at', 'for', 'with', 'from', 'by', 'about', 'as', 'into', 'through',
    'and', 'or', 'but', 'if', 'so', 'than', 'that', 'this', 'these', 'those', 'there',
    'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must',
    'not', 'no', 'yes', 'please', 'today', 'now', 'right', 'just', 'get', 'give', 'tell', 'show',
})
_WORD_RE = re.compile(r"[a-z']+")


def _meaningful_words(text: str) -> frozenset:
    return frozenset(w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1)


_FUZZY_WORD_MATCH_THRESHOLD = 70


def _shares_meaningful_word(normalized_text: str, matched_phrase: str) -> bool:
    """
    True when normalized_text and matched_phrase share at least one
    non-filler word, or a close (typo/concatenation-tolerant) variant of one.
    A clarification-band score (60-79) can be reached purely through shared
    filler words ("what"/"is"/"how"/"who"/"the"/...) between a completely
    unrelated transcript and a registered phrase — rapidfuzz's
    token_sort_ratio has no concept of which words actually carry the
    meaning. Without this check, "what is the weather today?" scored 60.6
    against "what is my net pay" (shares only "what"/"is"), producing a
    confusingly HR-flavored "did you mean: what is my net pay?" for a
    question with nothing to do with Royal HRMS at all. Confident matches
    (>= DEFAULT_CONFIDENCE_THRESHOLD) are never subject to this — an 80+
    token_sort_ratio already requires the words themselves to line up
    closely, not just a filler-word coincidence.

    An exact set intersection alone is too strict for two real, intentional
    shapes already in this registry/this app's transcripts, so a fuzzy
    fallback covers both:
      - Concatenated registry entries built for STT-dropped-space artifacts
        (e.g. "leavebalance", "rejectleave" — see registry/intents_en.yaml's
        own "toclockin"-style entries) tokenize as ONE word, so "balance"
        can never appear in a literal word-set built from "leavebalance" —
        substring containment catches it.
      - A genuinely garbled STT transcript can typo a word beyond exact
        match ("Paisley" for "payslip", "Praise" for "raise") — this is
        precisely what rapidfuzz's own scoring already tolerates for the
        phrase AS A WHOLE; per-word fuzz.ratio applies that same tolerance
        here instead of demanding letter-perfect words.
    """
    query_words = _meaningful_words(normalized_text)
    phrase_words = _meaningful_words(matched_phrase)
    if not query_words or not phrase_words:
        return False
    if query_words & phrase_words:
        return True

    phrase_compact = matched_phrase.replace(' ', '')
    for query_word in query_words:
        if len(query_word) < 4:
            continue  # too short for either fuzzy check to mean anything
        if query_word in phrase_compact:
            return True
        if any(fuzz.ratio(query_word, phrase_word) >= _FUZZY_WORD_MATCH_THRESHOLD for phrase_word in phrase_words):
            return True
    return False


@dataclass
class MatchResult:
    intent: str
    confidence: float
    matched_phrase: Optional[str] = None
    # Set only when confidence fell in [CLARIFICATION_CONFIDENCE_THRESHOLD,
    # DEFAULT_CONFIDENCE_THRESHOLD) — the intent matched_phrase belongs to,
    # for conversation.py to build a "did you mean" clarification from.
    # None whenever intent is itself a confident match (nothing to clarify)
    # or the score was too low even for a guess.
    candidate_intent: Optional[str] = None


def _registry_path_for(lang: str) -> Path:
    path = _REGISTRY_DIR / f'intents_{lang}.yaml'
    if path.exists():
        return path
    return _REGISTRY_DIR / f'intents_{DEFAULT_LANG}.yaml'


@lru_cache(maxsize=8)
def _get_intent_registry(registry_path: Path) -> dict:
    """Full per-intent config (phrases, required_permission, ...), keyed by intent name."""
    with open(registry_path, 'r', encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}
    return data.get('intents', {})


@lru_cache(maxsize=8)
def _get_phrase_index(registry_path: Path) -> dict:
    """Map every registered phrase -> its owning intent, e.g. {'clock in': 'clock_in'}."""
    index = {}
    for intent_name, config in _get_intent_registry(registry_path).items():
        for phrase in config.get('phrases', []):
            index[phrase] = intent_name
    return index


def get_required_permission(intent: str, lang: str = DEFAULT_LANG) -> Optional[str]:
    """
    Return the permission codename `intent` requires, or None if it needs no
    domain-specific permission beyond being authenticated (the case for all
    three intents defined today — see registry/intents_en.yaml).
    """
    config = _get_intent_registry(_registry_path_for(lang)).get(intent, {})
    return config.get('required_permission')


def get_conversational(intent: str, lang: str = DEFAULT_LANG) -> bool:
    """
    Return whether `intent` is registered as multi-turn (registry/intents_en.yaml's
    `conversational` field) — false for any intent that isn't in the registry
    at all, which correctly covers NO_MATCH_INTENT.
    """
    config = _get_intent_registry(_registry_path_for(lang)).get(intent, {})
    return bool(config.get('conversational', False))


def match_intent(
    normalized_text: str,
    lang: str = DEFAULT_LANG,
    threshold: int = DEFAULT_CONFIDENCE_THRESHOLD,
) -> MatchResult:
    """Fuzzy-match normalized_text against every phrase in the intent registry for `lang`."""
    if not normalized_text:
        return MatchResult(intent=NO_MATCH_INTENT, confidence=0.0)

    phrase_index = _get_phrase_index(_registry_path_for(lang))
    if not phrase_index:
        logger.warning('Voice intent registry is empty for lang=%s', lang)
        return MatchResult(intent=NO_MATCH_INTENT, confidence=0.0)

    best = process.extractOne(normalized_text, phrase_index.keys(), scorer=fuzz.token_sort_ratio)
    if best is None:
        return MatchResult(intent=NO_MATCH_INTENT, confidence=0.0)

    matched_phrase, score, _ = best
    candidate_intent = phrase_index[matched_phrase]

    if score < threshold:
        in_clarification_band = (
            score >= CLARIFICATION_CONFIDENCE_THRESHOLD
            and _shares_meaningful_word(normalized_text, matched_phrase)
        )
        return MatchResult(
            intent=NO_MATCH_INTENT,
            confidence=score,
            matched_phrase=matched_phrase,
            candidate_intent=candidate_intent if in_clarification_band else None,
        )

    return MatchResult(
        intent=candidate_intent,
        confidence=score,
        matched_phrase=matched_phrase,
    )
