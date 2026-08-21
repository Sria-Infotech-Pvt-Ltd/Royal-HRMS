"""
Ambient "which language should this response be in" signal for
voice_commands — Phase 3 of the voice-commands AI pivot (Hindi response
strings + language routing).

Deliberately NOT threaded as an explicit parameter through every executor/
conversation function (conversation.py's handle_transcript and its dispatch
chain, all five executor_*.py modules, and the seven independent `_payload()`
builders across conversation*.py) — that would mean adding a parameter to
dozens of call sites across nine files for one cross-cutting concern. This
mirrors Django's own built-in i18n shape instead: django.utils.translation
.activate()/get_language() sets a per-request thread-local once, and
gettext() reads it ambiently wherever it's called, with no explicit
threading. Same idea here, scoped to the two fixed, hardcoded languages this
phase's plan calls for (not Django's full gettext/.po pipeline, which would
be a much bigger, unrequested change for a small fixed message set).

set_current_language() is called exactly once per request, at the very top
of conversation.py's handle_transcript() — the single entry point every
transcript passes through (VoiceParseView.post() calls nothing else first).
So a stale contextvar value from a previous request on a reused WSGI worker
thread is always overwritten before anything downstream reads it. Safe under
both sync (thread-per-request) and async (this project's Daphne/channels
ASGI stack) dispatch: contextvars.Context is fresh per native thread and per
asyncio Task by default, so one request can never see another's value.

Any code path that reaches an executor function WITHOUT going through
handle_transcript first (e.g. existing tests that call execute_intent()/
execute_check_leave_balance() etc. directly, such as test_audit.py) simply
never calls set_current_language() — get_current_language() then returns the
default, LANG_EN, so every such existing call site keeps producing exactly
the English text it always has, with zero changes needed on their part.
"""
from __future__ import annotations

import contextvars

LANG_EN = 'en'
LANG_HI = 'hi'

_current_language: contextvars.ContextVar[str] = contextvars.ContextVar(
    'voice_commands_current_language', default=LANG_EN,
)


def set_current_language(language: str) -> None:
    """Normalizes anything other than LANG_HI to LANG_EN — this app only ever
    has two response languages (see this module's docstring), so an
    unexpected value fails safe to English rather than propagating a typo'd
    language code into every downstream text() lookup."""
    _current_language.set(LANG_HI if language == LANG_HI else LANG_EN)


def get_current_language() -> str:
    return _current_language.get()


def detect_language(stt_used_language_hint: bool, stt_detected_language: str | None = None) -> str:
    """
    stt_detected_language (Phase 4 — completes Phase 3.1's Gap 2): the
    accurate signal, preferred whenever present. views_transcribe.py's
    Hindi-capture retry (VoiceTranscribeFallbackView) tries an explicit
    hi-IN hint first, falling back to an explicit en-IN hint only if that
    fails or looks hallucinated (see that module's own docstring) — it
    already knows deterministically which of the two tiers actually
    produced the returned transcript, and now reports that directly as
    `detected_language` in its response. useVoiceCommand.ts forwards it
    verbatim as `stt_detected_language` on the /voice/parse/ resubmit. When
    present (and a recognized 'en'/'hi' value), it is used as-is — no
    approximation needed, since it names the tier directly rather than
    inferring it from a shared boolean.

    stt_used_language_hint: the fallback, used only when stt_detected_language
    is absent (older/typed/browser-STT-sourced transcripts have no such
    signal at all) — reused rather than adding a second, separate language-
    detection call (see conversation.py's handle_transcript, which already
    receives this same stt_used_language_hint to drive the STT-confirmation
    gate; that gate's own trust logic is untouched by this parameter).

    Approximation, not a true per-request language code — flagged explicitly
    rather than silently treated as exact: stt_used_language_hint is True
    whenever EITHER hint tier succeeded, so a transcript that only succeeded
    via the second (en-IN) tier is still reported here as Hindi UNLESS
    stt_detected_language is also present to disambiguate it (see Phase 3.1's
    own DetectLanguageAmbiguityTests, which pins down this exact gap for the
    case where the caller doesn't have the newer signal). Browser-STT-only
    and typed transcripts never set either signal, so they always resolve to
    English here, which matches reality: neither has ever gone through a
    Hindi-specific STT path.
    """
    if stt_detected_language in (LANG_EN, LANG_HI):
        return stt_detected_language
    return LANG_HI if stt_used_language_hint else LANG_EN


def text(texts: dict) -> str:
    """
    Select the current-language entry from a `{'en': ..., 'hi': ...}` pair —
    every bilingual message in executor_*.py is defined as one of these
    dicts (see those modules) rather than a `_EN`/`_HI` constant-name suffix
    pair, mirroring registry/intents_en.yaml's own "one entry, parallel
    fields" shape at message granularity. Falls back to English for any
    language the dict doesn't have an entry for (defensive only — every
    dict this app defines always has both keys; see test_language.py's
    structural-parity tests, which enforce that everywhere these dicts are
    defined).
    """
    return texts.get(get_current_language(), texts[LANG_EN])
