"""
Voice Commands — Hindi STT retry endpoint.

Endpoints:
  POST /api/voice/transcribe-fallback/ — Transcribe a short audio clip via
    Sarvam Saaras (translate mode) and hand back plain English text.

Kept separate from views.py (which owns VoiceParseView) — a distinct
endpoint shape (multipart file upload vs JSON transcript) and this project's
300-line-file convention both argue for its own module.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, success

from apps.voice_commands import sarvam_client
from apps.voice_commands.audit import log_no_match

# Whitelist, not a blacklist — matches this project's file-upload convention
# (CLAUDE.md section 3). These are the formats useVoiceCommand.ts's
# MediaRecorder retry can actually produce (webm/opus by default on Chrome/
# Edge; ogg on Firefox) plus wav as a generic fallback — anything else is
# rejected outright rather than forwarded to Sarvam.
_ALLOWED_CONTENT_TYPES = frozenset({'audio/webm', 'audio/ogg', 'audio/wav', 'audio/x-wav'})
# A single ~5s retry clip is a few hundred KB at most even uncompressed;
# 2MB is generous headroom without approaching the project's general 5MB
# upload cap.
_MAX_AUDIO_BYTES = 2 * 1024 * 1024


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
    translate mode auto-detects the spoken language (22 Indic languages plus
    English) and returns English text regardless, so the caller can resubmit
    the result through the exact same /voice/parse/ flow with no language-
    aware handling needed anywhere else.

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

        result = sarvam_client.transcribe_audio(
            uploaded.read(), uploaded.name or 'clip.webm', content_type=uploaded.content_type,
        )
        if result is None:
            # Same fail-soft contract as the LLM fallback tier: a Sarvam
            # outage, an unconfigured key, or genuine silence/unintelligible
            # audio all land here — logged as a no-match event (there was no
            # useful transcript to act on) so /dashboard/audit's picture of
            # "how often did this retry actually help" stays accurate, and
            # reported as a plain failure so the frontend falls back to
            # today's normal no-match UI rather than looping again.
            log_no_match(request, '<transcribe-fallback: no result>', None, None)
            return error("Couldn't make out that recording — please try again.")

        return success('Transcribed.', result)
