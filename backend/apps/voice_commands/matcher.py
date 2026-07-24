from __future__ import annotations

import logging
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

NO_MATCH_INTENT = 'no_match'


@dataclass
class MatchResult:
    intent: str
    confidence: float
    matched_phrase: Optional[str] = None


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
    if score < threshold:
        return MatchResult(intent=NO_MATCH_INTENT, confidence=score)

    return MatchResult(
        intent=phrase_index[matched_phrase],
        confidence=score,
        matched_phrase=matched_phrase,
    )
