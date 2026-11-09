"""
Per-user rate limits for the PAID voice paths (each call bills a third-party provider).

Reuses the project's existing mechanism: DRF throttle classes whose scope names map to rates in
settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] (same as apps/accounts/throttles.py). The rates are configurable through
environment variables, never hard-coded here:

    VOICE_SPEAK_RATE        text-to-speech  (POST /api/voice/speak/)              default 150/hour
    VOICE_TRANSCRIBE_RATE   speech-to-text  (POST /api/voice/transcribe-fallback/) default 60/hour
    VOICE_LLM_RATE          AI intent fallback (inside /api/voice/parse/)          default 40/hour

Each is keyed by the signed-in user (UserRateThrottle), so one employee cannot use up a colleague's allowance. Free
paths (the rule-engine match in /api/voice/parse/) are not limited here, and no other endpoint's limit changes.
"""
from __future__ import annotations

import logging

from rest_framework.throttling import UserRateThrottle

logger = logging.getLogger(__name__)


class VoiceSpeakRateThrottle(UserRateThrottle):
    scope = 'voice_speak'


class VoiceTranscribeRateThrottle(UserRateThrottle):
    scope = 'voice_transcribe'


class VoiceLLMRateThrottle(UserRateThrottle):
    scope = 'voice_llm'


def llm_fallback_allowed(request) -> bool:
    """Whether this user may spend one more AI intent-fallback call this hour.

    The LLM fallback is an inner step of /voice/parse/ (a normal, mostly free request), so it cannot be a view-level
    throttle: the check runs right before the paid call and counts it. Over the limit the caller simply skips the AI
    step and answers with the ordinary no-match message, so the voice flow never breaks.

    Fails OPEN: a cache/throttle error must never make voice worse than before, so any exception allows the call.
    """
    try:
        return VoiceLLMRateThrottle().allow_request(request, None)
    except Exception:  # noqa: BLE001 - deliberately broad, see docstring
        logger.warning('Voice LLM rate check failed; allowing the call', exc_info=True)
        return True
