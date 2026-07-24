from __future__ import annotations

import re
import unicodedata

_FILLER_WORDS = frozenset({'um', 'uh', 'please', 'kindly'})
_FILLER_PHRASES = ('can you', 'could you', 'would you')
_WHITESPACE_RE = re.compile(r'\s+')


def normalize_transcript(transcript: str) -> str:
    """Lowercase, NFC-normalize, and strip filler words/phrases from a raw voice transcript."""
    text = unicodedata.normalize('NFC', transcript or '').lower().strip()

    for phrase in _FILLER_PHRASES:
        text = text.replace(phrase, ' ')

    words = [word for word in text.split() if word not in _FILLER_WORDS]
    text = ' '.join(words)

    return _WHITESPACE_RE.sub(' ', text).strip()
