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

transcribe_audio's `mode` selects the STT output shape — see its own
docstring. views_transcribe.py uses mode="translate". mode="translit" was
tried instead (2026-08-19) hoping its narrower, less-generative task would
avoid translate's hallucination — it didn't help: on a real repro with
excellent mic signal (fixed after finding Windows' own OS-level "Voice
Focus" audio enhancement was degrading input before it ever reached the
browser), translit just as often returned nothing at all. translate was
then re-verified with that same good signal and STILL confidently
hallucinated complete, fluent, unrelated English sentences ("You should
tell me four things.", "The government should provide support to the
farmers.") for real spoken Hindi across multiple attempts — ruling out
audio quality as the cause. This is a real limitation of Saaras v3 for
short spoken Hindi/Hinglish commands via this endpoint, not something
fixable by mode, language hint, or client-side audio processing choices.
Known limitation, not silently worked around: the STT-confirmation gate in
conversation.py still means a wrong transcript is never executed without
explicit confirmation — see views_transcribe.py's own docstring for the
current scope decision (Hindi speech-to-text is unreliable; typed Hinglish
and English speech via the browser's own Web Speech API both work).

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
    language_code: Optional[str] = None, mode: str = 'translate',
) -> Optional[dict]:
    """
    POST /speech-to-text with model=saaras:v3. `mode` selects the output
    shape (confirmed against real docs.sarvam.ai docs, 2026-08-19):
      - "translate": generates fresh English text from the audio. The most
        hallucination-prone option — this is a generation task, not a
        transcription one, and real testing (2026-08-19) showed it
        confidently producing fluent, complete, but entirely unrelated
        English sentences ("Yes, yes, yes, yes, yes.", "Oh, it's a pain.")
        for real Hindi speech, rather than failing cleanly.
      - "translit": Romanized (Latin-script) output of the actual spoken
        words in whatever language was spoken — e.g. Hindi speech comes back
        as "muje clockin karo", not an invented English sentence. This is
        what views_transcribe.py now uses: a task much closer to raw
        transcription than translate's generation, and its output format
        exactly matches what a Hinglish-typing user would type directly —
        the existing intent matcher (rule engine + sarvam-105b LLM fallback,
        whose own system prompt already expects "English, Hindi, or Hinglish
        (romanized Hindi)") already handles that text with zero
        translation step needed.

    language_code (e.g. 'hi-IN'), when given, tells Sarvam which language to
    expect instead of auto-detecting it — confirmed against real docs.sarvam.ai
    docs (2026-08-18) as an accepted optional request parameter. Real live
    testing this session showed auto-detect getting the language flatly wrong
    on every genuine Hindi attempt (gu-IN/ml-IN/te-IN guessed, never hi-IN),
    so views_transcribe.py's retry now tries a Hindi hint first — see its own
    docstring. Per the same docs, Sarvam only returns language_probability in
    auto-detect mode; a hinted call gets none, which is why the returned dict
    always reports was_language_hinted — the caller has no other way to tell
    "no probability because we didn't ask" apart from "no probability because
    the field was missing for some other reason."

    Returns {'transcript': str, 'language_code': str | None,
    'language_probability': float | None, 'was_language_hinted': bool} on
    success — language_code/language_probability are Sarvam's own confidence
    in which language it heard, NOT a transcript-accuracy score (Sarvam
    doesn't expose one). A real, confirmed failure mode: identical audio
    bytes resubmitted to this same endpoint can return different transcripts
    AND different detected languages across calls (observed directly,
    2026-08-17 — see conversation.py's STT-confirmation gate, which uses
    language_probability as the best available proxy signal, and falls back
    to was_language_hinted when that signal doesn't exist). Logged on every
    successful call — previously not logged at all — so that signal can
    eventually be calibrated against real outcomes instead of only being
    visible when something already went wrong.
    Returns None on any failure, or on a successful call that came back with
    an empty transcript (silence, or audio Saaras couldn't make out at all) —
    both are treated identically by the caller as "this retry didn't help."
    """
    api_key = _api_key()
    if not api_key:
        return None

    request_payload = {'model': STT_MODEL, 'mode': mode}
    if language_code:
        request_payload['language_code'] = language_code

    try:
        response = requests.post(
            _SPEECH_TO_TEXT_URL,
            headers={'api-subscription-key': api_key},
            data=request_payload,
            files={'file': (filename, file_bytes, content_type)},
            timeout=_STT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        transcript = (data.get('transcript') or '').strip()
        if not transcript:
            return None
        language_probability = data.get('language_probability')
        logger.info(
            'Sarvam STT succeeded: requested_language=%s language_code=%s '
            'language_probability=%s transcript_len=%d',
            language_code, data.get('language_code'), language_probability, len(transcript),
        )
        return {
            'transcript': transcript,
            'language_code': data.get('language_code'),
            'language_probability': language_probability,
            'was_language_hinted': language_code is not None,
        }
    except (requests.RequestException, ValueError) as exc:
        # Includes the response body text (not just the exception) since a
        # 4xx/5xx from Sarvam often carries a real error message in the body
        # that str(exc) alone won't show — Sarvam's own service response,
        # not user speech content, so safe to log in full.
        body = getattr(exc, 'response', None)
        logger.warning(
            'Sarvam speech-to-text failed (mode=%s, requested_language=%s): %s — body=%r',
            mode, language_code, exc, body.text if body is not None else None,
        )
        return None
