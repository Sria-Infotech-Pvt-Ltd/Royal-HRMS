"""
Thin HTTP wrapper around the three Sarvam AI endpoints this app uses:
  - chat completions (sarvam-105b) — voice_commands/llm_fallback.py's intent
    classifier.
  - speech-to-text (Saaras v4)     — voice_commands/views_transcribe.py's
    Hindi-capture retry.
  - text-to-speech (Bulbul v3)     — voice_commands/views_speak.py's spoken-
    reply endpoint (Phase 2 of the voice-commands AI pivot).

Both endpoints and shapes below were confirmed against the real Sarvam docs
(docs.sarvam.ai) on 2026-08-11, not assumed from memory:
  https://docs.sarvam.ai/api-reference/chat/chat-completions
  https://docs.sarvam.ai/api-reference-docs/models/saaras

text_to_speech()'s endpoint/schema were separately confirmed against real
docs.sarvam.ai on 2026-08-21:
  https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert (request/
    response shape — note the actual POST path is /text-to-speech, not
    /text-to-speech/convert; "convert" is only the docs page's URL slug)
  https://docs.sarvam.ai/api-reference-docs/errors-troubleshooting (error
    shape + which status codes are retryable)
  https://docs.sarvam.ai/api/getting-started/ratelimits (bulbul:v3 REST rate
    limits by plan, and that a TTS 503 during backend overload is documented
    as "handled identically" to a 429 — see text_to_speech()'s docstring)

Phase 5 added retry-with-backoff to text_to_speech() for the 429/500/503
responses Sarvam's own docs recommend retrying (see _TTS_MAX_ATTEMPTS'
comment) — this account's Sarvam plan tier (Starter/Pro/Business, which
would set real rate-limit numbers to tune against) still could not be
determined from repo config or dashboard access, so the retry budget below
is a conservative default, not one sized to a known limit.

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

Update (2026-08-21): STT_MODEL bumped from saaras:v3 to saaras:v4 (request/
response shape unchanged, confirmed against real docs.sarvam.ai — same
/speech-to-text endpoint, same mode values, no new required params). v4's
only documented change is added Global English coverage alongside the
existing 22 Indic languages; it is NOT documented as fixing the Hindi
hallucination behavior above. The v3 findings stay accurate as history of
what was tested — treat the "real limitation" conclusion as unconfirmed on
v4 until it's re-tested with real audio, not as already resolved.

Every function here returns None on ANY failure (missing key, network error,
timeout, non-2xx, unrecognized response shape) rather than raising — a
Sarvam outage must never 500 a request or surface a worse experience than
this app had before either feature existed. Callers treat None exactly like
"Sarvam had nothing to add" and fall back to the existing rule-engine
behavior unchanged.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_URL = 'https://api.sarvam.ai/v1/chat/completions'
_SPEECH_TO_TEXT_URL = 'https://api.sarvam.ai/speech-to-text'
_TEXT_TO_SPEECH_URL = 'https://api.sarvam.ai/text-to-speech'

CHAT_MODEL = 'sarvam-105b'  # NOT sarvam-30b — deprecated, never use it here.
STT_MODEL = 'saaras:v4'
TTS_MODEL = 'bulbul:v3'
# This app's one chosen voice for both hi-IN and en-IN spoken output (Phase 2
# task decision) — a lowercase string, independent of language_code, per
# real docs.sarvam.ai. Sent explicitly on every request rather than relying
# on Sarvam's own default, same reasoning as pinning CHAT_MODEL/STT_MODEL
# above: protects against Sarvam silently changing a default under us.
TTS_DEFAULT_SPEAKER = 'shubh'
# bulbul:v3's documented REST character cap (confirmed against real
# docs.sarvam.ai, 2026-08-21) — bulbul:v2 is capped lower (1500) but this app
# never requests v2. Enforced client-side in text_to_speech() below so a
# too-long call fails with a specific, actionable message instead of
# whatever generic 400/422 Sarvam itself would return.
TTS_MAX_TEXT_LENGTH = 2500

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
# TTS is a text-only request like chat, but a short spoken reply (well under
# TTS_MAX_TEXT_LENGTH in practice) synthesizes fast — sized between the two
# above, not given chat's 20s headroom since there's no hidden-reasoning-
# token failure mode here to protect against.
_TTS_TIMEOUT_SECONDS = 15

# Phase 5 retry/backoff for text_to_speech(). Sarvam's own docs recommend
# retrying 429/500/503-class responses with backoff; this client could not
# determine the account's Sarvam plan tier (Starter/Pro/Business — not
# visible from repo config or the dashboard access available while building
# this), so the budget below is a deliberately conservative default rather
# than one tuned to a known rate limit: few attempts, short backoff. Only
# these three statuses retry — 403 (bad key), 400/422 (bad input), and a
# network-level timeout/connection failure are never retried (see the
# branches in text_to_speech() below): none of those are made more likely to
# succeed by trying again, and retrying a hung request would only multiply
# _TTS_TIMEOUT_SECONDS' already-real wait per extra attempt.
_TTS_MAX_ATTEMPTS = 3
_TTS_RETRY_BACKOFF_SECONDS = (0.5, 1.0)  # before attempt 2, then before attempt 3
_TTS_RETRYABLE_STATUS_CODES = frozenset({429, 500, 503})


def _api_key() -> str:
    return getattr(settings, 'SARVAM_API_KEY', '') or ''


def is_configured() -> bool:
    """Callers check this before doing any work that only makes sense with a key
    (e.g. building a prompt) — cheap enough to skip that work entirely."""
    return bool(_api_key())


class SarvamTTSError(Exception):
    """
    Base class for every text_to_speech() failure.

    Deliberately NOT the fail-soft "return None on any failure" contract
    chat_completion()/transcribe_audio() use above (see this module's own
    docstring) — the Phase 2 task this was built for explicitly needs
    distinguishable failure categories (auth/API-key, rate-limit, timeout,
    bad input) for a later error-handling phase to build targeted behavior
    on, which a single None can't carry. views_speak.py catches these
    subclasses and maps each to a distinct HTTP response; a caller that
    only wants the old "swallow and treat as unavailable" behavior can
    catch this base class once instead.
    """


class SarvamTTSInputError(SarvamTTSError):
    """Empty text, text over TTS_MAX_TEXT_LENGTH (checked before ever calling
    Sarvam), or Sarvam itself rejecting the request as malformed (400/422 —
    e.g. an unsupported language_code)."""


class SarvamTTSAuthError(SarvamTTSError):
    """Sarvam rejected the configured API key. Confirmed against real
    docs.sarvam.ai/api-reference-docs/errors-troubleshooting (2026-08-21):
    Sarvam auth failures use HTTP 403, not 401."""


class SarvamTTSConfigError(SarvamTTSAuthError):
    """SARVAM_API_KEY is not configured — Sarvam was never even called.
    A subclass of SarvamTTSAuthError (not a sibling) since both are "we have
    no usable credential" from the caller's point of view; catch the parent
    to handle both identically, or this subclass to log the distinction."""


class SarvamTTSRateLimitError(SarvamTTSError):
    """Sarvam rate limit/credits exhausted (429), or a 503 backend-overload
    response — confirmed against real docs.sarvam.ai/api/getting-started/
    ratelimits (2026-08-21) as "handled identically" to 429 for this
    endpoint. Safe to retry with backoff per Sarvam's own guidance; this
    module does not retry itself (see views_speak.py for caller policy)."""


class SarvamTTSTimeoutError(SarvamTTSError):
    """No response from Sarvam within _TTS_TIMEOUT_SECONDS."""


class SarvamTTSServiceError(SarvamTTSError):
    """Any other non-2xx response (e.g. a bare 500), network failure, or a
    2xx response whose body doesn't match the documented {"audios": [...]}
    shape."""


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
    POST /speech-to-text with model=saaras:v4. `mode` selects the output
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


def text_to_speech(
    text: str, language_code: str, *, speaker: str = TTS_DEFAULT_SPEAKER,
) -> bytes:
    """
    POST /text-to-speech with model=bulbul:v3. Confirmed against real
    docs.sarvam.ai (2026-08-21) — see this module's own docstring for the
    exact pages checked, including the note that the real path is
    /text-to-speech (the docs page slug "/convert" is not part of the URL).

    text/language_code are both required by Sarvam; speaker defaults to
    TTS_DEFAULT_SPEAKER ("shubh" — this app's one chosen voice for both
    hi-IN and en-IN output, per the Phase 2 task this was built for).

    Raises SarvamTTSInputError before ever making a network call if text is
    empty or longer than TTS_MAX_TEXT_LENGTH — failing clearly here instead
    of letting Sarvam reject an oversized request with a less specific
    400/422, per the Phase 2 task's explicit requirement.

    Unlike chat_completion()/transcribe_audio() above, this function does
    NOT fail soft to None — see SarvamTTSError's docstring for why. On
    success, returns the raw decoded WAV bytes: Sarvam's own response wraps
    a base64 string in {"request_id": ..., "audios": [...]}; this function
    decodes it once so every caller gets real bytes rather than duplicating
    that step. Only audios[0] is used — a single `text` request always
    yields exactly one audio in Sarvam's own documented example.

    Retries up to _TTS_MAX_ATTEMPTS times, with a short backoff
    (_TTS_RETRY_BACKOFF_SECONDS) between attempts, when Sarvam responds with
    one of _TTS_RETRYABLE_STATUS_CODES (429/500/503 — see that constant's
    comment for why this errs conservative on attempt count). Every other
    failure below — auth, bad input, timeout, network error, unrecognized
    response shape — still raises on the first attempt exactly as in Phase
    2; only the exception types in the Raises: section are unchanged, not
    when they're raised.

    Raises:
      SarvamTTSConfigError    — SARVAM_API_KEY is not configured.
      SarvamTTSInputError     — empty/too-long text (checked locally), or
        Sarvam rejected the request as malformed (400/422).
      SarvamTTSAuthError      — Sarvam rejected the API key (HTTP 403).
      SarvamTTSRateLimitError — Sarvam rate limit/credits exceeded (429), or
        backend overload (503 — documented as handled identically to 429),
        after _TTS_MAX_ATTEMPTS retries.
      SarvamTTSTimeoutError   — no response within _TTS_TIMEOUT_SECONDS.
      SarvamTTSServiceError   — a bare 500 after _TTS_MAX_ATTEMPTS retries,
        any other non-2xx response, a network failure, or a 2xx response
        with an unrecognized body shape.
    """
    if not text or not text.strip():
        raise SarvamTTSInputError('text must not be empty.')
    if len(text) > TTS_MAX_TEXT_LENGTH:
        raise SarvamTTSInputError(
            f'text is {len(text)} characters, exceeding the {TTS_MAX_TEXT_LENGTH}-character '
            f'REST limit for {TTS_MODEL}.'
        )

    api_key = _api_key()
    if not api_key:
        raise SarvamTTSConfigError('SARVAM_API_KEY is not configured.')

    request_json = {
        'text': text,
        'language_code': language_code,
        'speaker': speaker,
        'model': TTS_MODEL,
    }

    # attempt is referenced after the loop (success log below) — Python
    # leaks for-loop variables into the enclosing scope, so this is always
    # the count of attempts actually made once the loop exits via `break`.
    for attempt in range(1, _TTS_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                _TEXT_TO_SPEECH_URL,
                headers={'api-subscription-key': api_key, 'Content-Type': 'application/json'},
                json=request_json,
                timeout=_TTS_TIMEOUT_SECONDS,
            )
        except requests.Timeout as exc:
            logger.warning('Sarvam text-to-speech timed out after %ss: %s', _TTS_TIMEOUT_SECONDS, exc)
            raise SarvamTTSTimeoutError(f'Sarvam did not respond within {_TTS_TIMEOUT_SECONDS}s.') from exc
        except requests.RequestException as exc:
            logger.warning('Sarvam text-to-speech request failed: %s', exc)
            raise SarvamTTSServiceError(str(exc)) from exc

        # Status-code branches checked before raise_for_status() so each
        # failure mode raises its own distinct exception type — see this
        # function's Raises: section — rather than collapsing them all into
        # one generic HTTPError branch the way chat_completion()/
        # transcribe_audio() do.
        if response.status_code == 403:
            logger.warning('Sarvam text-to-speech auth failure: %s', response.text)
            raise SarvamTTSAuthError('Sarvam rejected the configured API key.')
        if response.status_code in (400, 422):
            logger.warning(
                'Sarvam text-to-speech rejected the request (status=%s): %s', response.status_code, response.text,
            )
            raise SarvamTTSInputError(f'Sarvam rejected the request: {response.text}')

        if response.status_code in _TTS_RETRYABLE_STATUS_CODES:
            if attempt < _TTS_MAX_ATTEMPTS:
                backoff_seconds = _TTS_RETRY_BACKOFF_SECONDS[attempt - 1]
                logger.warning(
                    'Sarvam text-to-speech retryable failure (status=%s, attempt=%d/%d) — retrying in %ss: %s',
                    response.status_code, attempt, _TTS_MAX_ATTEMPTS, backoff_seconds, response.text,
                )
                time.sleep(backoff_seconds)
                continue
            logger.warning(
                'Sarvam text-to-speech retries exhausted (status=%s, attempts=%d): %s',
                response.status_code, attempt, response.text,
            )
            if response.status_code in (429, 503):
                raise SarvamTTSRateLimitError('Sarvam rate limit exceeded or backend overloaded.')
            raise SarvamTTSServiceError(f'Sarvam returned HTTP {response.status_code}.')

        # Any other status (2xx success, or a non-retryable non-2xx this
        # module doesn't special-case, e.g. 501) — handled below exactly as
        # before, never retried.
        break

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.warning(
            'Sarvam text-to-speech failed (status=%s): %s — body=%r',
            response.status_code, exc, response.text,
        )
        raise SarvamTTSServiceError(f'Sarvam returned HTTP {response.status_code}.') from exc

    try:
        data: dict[str, Any] = response.json()
        audio_b64 = data['audios'][0]
        audio_bytes = base64.b64decode(audio_b64)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning('Sarvam text-to-speech returned an unrecognized response shape: %s', exc)
        raise SarvamTTSServiceError('Sarvam returned an unrecognized response shape.') from exc

    logger.info(
        'Sarvam TTS succeeded: language_code=%s speaker=%s text_len=%d audio_bytes=%d attempts=%d',
        language_code, speaker, len(text), len(audio_bytes), attempt,
    )
    return audio_bytes
