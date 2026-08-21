"""
Voice Commands — Hindi STT retry endpoint.

Endpoints:
  POST /api/voice/transcribe-fallback/ — Transcribe a short audio clip via
    Sarvam Saaras (translate mode) and hand back English text.

KNOWN LIMITATION (2026-08-19, extensive real-audio testing — see class
docstring below): Sarvam Saaras v3 does not reliably transcribe short
spoken Hindi/Hinglish commands through this endpoint, regardless of audio
quality, output mode, or language hint. Typed Hinglish input and English
speech via the browser's own Web Speech API both work correctly; this
retry is the one path still unreliable. Safe either way — the
STT-confirmation gate in conversation.py never lets a wrong transcript
execute — but don't expect this specific retry to succeed reliably for
Hindi speech until it's revisited with a different STT provider.

Update (2026-08-21): sarvam_client.STT_MODEL bumped to saaras:v4 (see that
module's docstring) — a drop-in swap per real docs.sarvam.ai, not a fix
Sarvam documents for this specific hallucination behavior. The limitation
above is unconfirmed on v4 pending real-audio re-testing; nothing in this
file's retry logic (hint order, hallucination detection) has changed yet.

Kept separate from views.py (which owns VoiceParseView) — a distinct
endpoint shape (multipart file upload vs JSON transcript) and this project's
300-line-file convention both argue for its own module.
"""
from __future__ import annotations

import logging
import re

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, success

logger = logging.getLogger(__name__)

from apps.voice_commands import sarvam_client
from apps.voice_commands.audit import log_no_match
from apps.voice_commands.language import LANG_EN, LANG_HI

# Whitelist, not a blacklist — matches this project's file-upload convention
# (CLAUDE.md section 3). These are the formats useVoiceCommand.ts's
# MediaRecorder retry can actually produce (webm/opus by default on Chrome/
# Edge; ogg on Firefox) plus wav as a generic fallback — anything else is
# rejected outright rather than forwarded to Sarvam.
_ALLOWED_CONTENT_TYPES = frozenset({'audio/webm', 'audio/ogg', 'audio/wav', 'audio/x-wav'})

# This retry exists specifically for Hindi (see class docstring), so it tries
# an explicit Hindi hint first. Real live testing (2026-08-18) showed
# unconstrained auto-detect guessing gu-IN/ml-IN/te-IN on every genuine Hindi
# attempt, never hi-IN. A hinted call gets no language_probability back from
# Sarvam (confirmed against real docs), so a hinted success is reported to
# the caller as was_language_hinted=True rather than silently losing the
# trust signal conversation.py's STT-confirmation gate depends on.
_PRIMARY_LANGUAGE_HINT = 'hi-IN'
# Second tier, tried if the Hindi hint fails or looks hallucinated (see
# _looks_like_hallucination). Sarvam has no parameter to restrict detection
# to a candidate LIST of languages (confirmed against real docs, 2026-08-19)
# — only a single hint or full unconstrained auto-detect across all 23
# supported languages. An explicit English hint is the closest approximation
# of "constrain to en/hi" available; falling through to unconstrained
# auto-detect is exactly what produced the original gu-IN/ml-IN/te-IN
# misdetections, so this tier deliberately never does that.
_SECONDARY_LANGUAGE_HINT = 'en-IN'
# A single ~5s retry clip is a few hundred KB at most even uncompressed;
# 2MB is generous headroom without approaching the project's general 5MB
# upload cap.
_MAX_AUDIO_BYTES = 2 * 1024 * 1024


def _looks_like_hallucination(transcript: str) -> bool:
    """
    A known ASR/LLM hallucination signature: the same single word repeated
    3+ times ("Yes, yes, yes, yes, yes.") — seen directly in this app's real
    Sarvam mode="translate" output (2026-08-18/19 repro sessions) on
    quiet/unclear audio, never on a real repeated-word phrase anyone would
    actually say to this app. \\w matches Unicode word characters (Devanagari
    included), not just ASCII, since translit's Romanized output is the
    normal case but not a hard guarantee. Only catches this one specific
    pattern — a garbled but non-repetitive hallucination like "Huh? Go, go."
    won't trip this, and isn't meant to: conversation.py's STT-confirmation
    gate is the real backstop for everything else. This just skips a wasted
    confirmation round-trip for the most obviously-garbage case.
    """
    words = re.findall(r"\w+", transcript.lower())
    return len(words) >= 3 and len(set(words)) == 1


class VoiceTranscribeFallbackView(APIView):
    """
    POST /api/voice/transcribe-fallback/

    Body: multipart/form-data, field "audio" — a short recorded clip.

    Called by useVoiceCommand.ts exactly once per voice command, only after
    the browser's own Web Speech API transcript has already round-tripped
    through /voice/parse/ and come back as a final no_match (rule engine and
    the sarvam-105b classification tier both declined it) — see
    useVoiceCommand.ts's submitTranscript for the retry trigger. This is the
    "maybe that was Hindi, not garbled English" retry: Sarvam Saaras'
    translate mode returns English text regardless of the spoken language,
    which the caller resubmits through the exact same /voice/parse/ flow
    like any other transcript.

    mode="translate" vs mode="translit" (2026-08-19, three real repro
    rounds, the last with excellent mic signal after fixing the actual
    root cause — Windows' own OS-level "Voice Focus" audio enhancement was
    silently degrading the mic input before it ever reached the browser):
    translit (Romanized/Hinglish output, no translation step) was tried
    first, hoping its narrower task would avoid hallucination — it just as
    often returned nothing at all (empty transcript, both hints), including
    with the good signal. translate was then re-verified with that same
    good signal and STILL confidently hallucinated complete, fluent,
    grammatically perfect but entirely unrelated English sentences ("You
    should tell me four things.", "The government should provide support
    to the farmers.") for real spoken "muje clockin karo," across multiple
    attempts. This rules out audio quality, language hint, and output mode
    as the cause — it's a real limitation of Saaras v3 for this kind of
    short spoken command, not something fixable from this side. translate
    is kept as the primary mode because it at least never fails silently
    (translit's empty-both-tiers result gives nothing to react to); every
    hallucinated result is still caught by _looks_like_hallucination or
    conversation.py's STT-confirmation gate before anything executes — see
    this module's own docstring for the resulting scope decision.

    Tries an explicit hi-IN hint, then an explicit en-IN hint — never
    unconstrained auto-detect across all 23 supported languages, which
    misdetected genuine Hindi as gu-IN/ml-IN/te-IN in real testing (see
    _SECONDARY_LANGUAGE_HINT above).

    Response `data` (Phase 4) carries a `detected_language` field ('hi' or
    'en') alongside `transcript`/`language_probability`/`was_language_hinted`
    — which of the two hints above actually produced this result, known for
    free from which sequential attempt survived. useVoiceCommand.ts forwards
    this as `stt_detected_language` on the /voice/parse/ resubmit, which
    conversation.py's handle_transcript prefers over the was_language_hinted-
    derived approximation for deciding EN vs HI text/voice — see
    language.detect_language's own docstring. was_language_hinted itself is
    unchanged and still drives conversation.py's STT-confirmation gate.

    Never executes anything itself — this endpoint only returns text; the
    frontend is responsible for feeding that text back into /voice/parse/,
    which re-runs the full rule-engine + LLM-fallback pipeline on it like any
    other transcript.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        uploaded = request.FILES.get('audio')
        if not uploaded:
            return error('Attach a short audio clip as "audio".', http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if uploaded.content_type not in _ALLOWED_CONTENT_TYPES:
            return error(
                f'Unsupported audio format: {uploaded.content_type}.',
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if uploaded.size > _MAX_AUDIO_BYTES:
            return error('Audio clip is too large.', http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        audio_bytes = uploaded.read()
        # Client-side raw-stream RMS energy (voiceSttFallback.ts's AnalyserNode
        # probe, sampled from the instant getUserMedia resolves through the
        # whole recording) — tells us whether the mic stream had real signal
        # at the source, without ever touching the audio itself. Deliberately
        # NOT the raw clip: this app's voice commands carry real employee
        # speech, and writing that to disk for debugging is a real exposure,
        # not a hypothetical one (see this project's own PII-handling rules).
        # Numeric energy readings serve the same "was this actually silence"
        # question with none of that risk.
        client_energy_debug = request.POST.get('clientEnergyDebug')
        logger.warning(
            'Voice transcribe-fallback capture: bytes=%d content_type=%s energy=%s',
            len(audio_bytes), uploaded.content_type, client_energy_debug,
        )

        result = sarvam_client.transcribe_audio(
            audio_bytes, uploaded.name or 'clip.webm', content_type=uploaded.content_type,
            language_code=_PRIMARY_LANGUAGE_HINT, mode='translate',
        )
        # Which tier actually produced `result`, if any — known deterministically
        # from which of the two sequential attempts below survives (this app
        # never tries both at once), not a new computation or API call. See
        # Phase 3.1's own finding: was_language_hinted alone can't tell "Hindi
        # tier succeeded" apart from "Hindi failed, English fallback tier
        # succeeded" since both tiers pass an explicit hint and both therefore
        # report was_language_hinted=True. Tracked here and returned below as
        # detected_language so the caller (views.py -> conversation.py's
        # handle_transcript) gets the accurate signal directly, instead of
        # having to reconstruct it from a boolean that can't carry it.
        detected_language = LANG_HI
        if result is not None and _looks_like_hallucination(result['transcript']):
            logger.warning('Sarvam STT hallucination signature (hi-IN hint): %r', result['transcript'])
            result = None
        if result is None:
            # Hindi hint declined (empty transcript, not Hindi, or a
            # hallucinated repeat-loop) — try an explicit English hint next,
            # not unconstrained auto-detect (see _SECONDARY_LANGUAGE_HINT).
            detected_language = LANG_EN
            result = sarvam_client.transcribe_audio(
                audio_bytes, uploaded.name or 'clip.webm', content_type=uploaded.content_type,
                language_code=_SECONDARY_LANGUAGE_HINT, mode='translate',
            )
            if result is not None and _looks_like_hallucination(result['transcript']):
                logger.warning('Sarvam STT hallucination signature (en-IN hint): %r', result['transcript'])
                result = None
        if result is None:
            # Same fail-soft contract as the LLM fallback tier: a Sarvam
            # outage, an unconfigured key, or genuine silence/unintelligible
            # audio all land here — logged as a no-match event (there was no
            # useful transcript to act on) so /dashboard/audit's picture of
            # "how often did this retry actually help" stays accurate, and
            # reported as a plain failure so the frontend falls back to
            # today's normal no-match UI rather than looping again.
            log_no_match(request, '<transcribe-fallback: no result>', None, None)
            return error("Couldn't make out that recording — try typing your command instead.")

        result['detected_language'] = detected_language
        return success('Transcribed.', result)
