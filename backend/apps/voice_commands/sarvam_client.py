"""
Thin HTTP wrapper around the two Sarvam AI endpoints this app uses:
  - chat completions (sarvam-105b) — voice_commands/llm_fallback.py's intent
    classifier.
  - speech-to-text (Saaras v3)     — voice_commands/views_transcribe.py's
    Hindi-capture retry.

Both endpoints and shapes below were confirmed against the real Sarvam docs
(docs.sarvam.ai) on 2026-08-11, not assumed from memory:
  https://docs.sarvam.ai/api-reference/chat/chat-completions
  https://docs.sarvam.ai/api-reference-docs/models/saaras

Auth: both endpoints accept the SAME header, `api-subscription-key: <key>` —
used exclusively here rather than mixing in the also-supported
`Authorization: Bearer` scheme, so there's one auth code path for both calls.

mode="translate" on the STT call converts any of Saaras's 22 supported Indic
languages (Hindi included) DIRECTLY to English text, auto-detecting the
source language with no language_code needed on the request — see
transcribe_audio's docstring for why that's what lets Hindi capture skip
every other language-aware code path in this app.

Every function here returns None on ANY failure (missing key, network error,
timeout, non-2xx, unrecognized response shape) rather than raising — a
Sarvam outage must never 500 a request or surface a worse experience than
this app had before either feature existed. Callers treat None exactly like
"Sarvam had nothing to add" and fall back to the existing rule-engine
behavior unchanged.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_URL = 'https://api.sarvam.ai/v1/chat/completions'
_SPEECH_TO_TEXT_URL = 'https://api.sarvam.ai/speech-to-text'

CHAT_MODEL = 'sarvam-105b'  # NOT sarvam-30b — deprecated, never use it here.
STT_MODEL = 'saaras:v3'

# sarvam-105b is a reasoning model: it can silently spend a large, variable
# number of hidden "reasoning_content" tokens before ever emitting the
# requested {"intent": ...} JSON. Measured directly against the real API
# (2026-08-17): a "fast path" with no reasoning answers in ~1.2-1.4s using
# ~20 completion tokens, but a "reasoning path" — which can trigger on the
# exact same transcript on a different call, same temperature — took
# 15-17s and consumed 987-1203 completion tokens on reasoning alone before
# the final answer. The previous settings here (timeout=6, max_tokens=512)
# guaranteed that path always failed: killed by the timeout before
# finishing, and even if it hadn't, truncated by max_tokens (finish_reason
# "length") with the actual `content` field left null — silently
# indistinguishable from a genuine no_match/outage to every caller. Sized
# with real headroom above both observed worst cases, not guessed.
_CHAT_TIMEOUT_SECONDS = 20
# STT uploads a short audio file on top of the round trip — a little more
# headroom than the text-only chat call, still well under any UI patience.
_STT_TIMEOUT_SECONDS = 10


def _api_key() -> str:
    return getattr(settings, 'SARVAM_API_KEY', '') or ''


def is_configured() -> bool:
    """Callers check this before doing any work that only makes sense with a key
    (e.g. building a prompt) — cheap enough to skip that work entirely."""
    return bool(_api_key())


def chat_completion(
    messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 2048,
) -> Optional[str]:
    """
    POST /v1/chat/completions with model=sarvam-105b, response_format=json_object
    (so the assistant reliably replies with a parseable JSON string — see
    llm_fallback.py for what it asks for). Returns the raw assistant message
    string (choices[0].message.content) on success, or None on any failure —
    see this module's docstring for the fail-soft contract.

    max_tokens default sized at 2048, not the classification answer's own
    ~20-token footprint — see _CHAT_TIMEOUT_SECONDS' comment above on why:
    hidden reasoning tokens alone measured up to ~1200 on this model for a
    single short classification prompt.
    """
    api_key = _api_key()
    if not api_key:
        return None

    try:
        response = requests.post(
            _CHAT_COMPLETIONS_URL,
            headers={'api-subscription-key': api_key, 'Content-Type': 'application/json'},
            json={
                'model': CHAT_MODEL,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'response_format': {'type': 'json_object'},
            },
            timeout=_CHAT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data['choices'][0]['message']['content']
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.warning('Sarvam chat completion failed: %s', exc)
        return None


def transcribe_audio(
    file_bytes: bytes, filename: str, content_type: str = 'audio/webm',
) -> Optional[dict]:
    """
    POST /speech-to-text with model=saaras:v3, mode="translate" — converts
    speech in any of Saaras's 22 supported Indic languages (or English)
    directly to English text, auto-detecting the source language. This is
    the one call that lets views_transcribe.py's Hindi-capture retry hand
    back plain English to the exact same /voice/parse/ pipeline every other
    transcript already goes through, with no Hindi-aware code anywhere else
    in this app.

    Returns {'transcript': str, 'language_code': str | None} on success —
    language_code is logged for telemetry only, never shown to the user.
    Returns None on any failure, or on a successful call that came back with
    an empty transcript (silence, or audio Saaras couldn't make out at all) —
    both are treated identically by the caller as "this retry didn't help."
    """
    api_key = _api_key()
    if not api_key:
        return None

    try:
        response = requests.post(
            _SPEECH_TO_TEXT_URL,
            headers={'api-subscription-key': api_key},
            data={'model': STT_MODEL, 'mode': 'translate'},
            files={'file': (filename, file_bytes, content_type)},
            timeout=_STT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        transcript = (data.get('transcript') or '').strip()
        if not transcript:
            return None
        return {'transcript': transcript, 'language_code': data.get('language_code')}
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Sarvam speech-to-text failed: %s', exc)
        return None
