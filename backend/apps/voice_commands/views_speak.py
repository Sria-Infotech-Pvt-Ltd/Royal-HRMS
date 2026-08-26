"""
Voice Commands — spoken-reply endpoint (Phase 2 of the voice-commands AI
pivot: backend Sarvam Bulbul TTS integration).

Endpoints:
  POST /api/voice/speak/ — Convert a short piece of text into spoken audio
    via Sarvam Bulbul TTS and hand back the raw audio bytes.

Kept separate from views.py/views_transcribe.py (this project's 300-line-
file convention, and a distinct endpoint shape again — JSON in, binary audio
out, unlike either of those) rather than folded into an existing module.

Nothing in this app calls this endpoint yet — that's later-phase frontend
work (Phase 4, explicitly out of scope here). This phase only adds the route
and proves it works end-to-end via its own tests.
"""
from __future__ import annotations

import logging

from adrf.views import APIView
from asgiref.sync import sync_to_async
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.responses import error

logger = logging.getLogger(__name__)

from apps.voice_commands import sarvam_client

# Sarvam's own bulbul:v3 REST cap (sarvam_client.TTS_MAX_TEXT_LENGTH) is
# enforced inside text_to_speech() itself; this is just the request-body
# validation message shown when the caller's JSON is missing/blank, matching
# views.py/views_transcribe.py's existing "required field" phrasing.
_TEXT_TO_SPEECH_ERROR_STATUS = {
    sarvam_client.SarvamTTSInputError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    # Auth/config errors mean this feature is unusable until an admin fixes
    # SARVAM_API_KEY — nothing the caller can do differently, so this is a
    # service-availability problem from their point of view, not a bad
    # request. SarvamTTSConfigError is a subclass of SarvamTTSAuthError and
    # is matched by that entry (see the isinstance walk in post() below).
    sarvam_client.SarvamTTSAuthError: status.HTTP_503_SERVICE_UNAVAILABLE,
    sarvam_client.SarvamTTSRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
    sarvam_client.SarvamTTSTimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    # Catch-all for anything else text_to_speech() raises (a bare 500 from
    # Sarvam, a network failure, an unrecognized response shape) — mirrors
    # accounts/views.py's DocumentDownloadView, which uses the same 502 for
    # "the real upstream failure reason isn't the caller's to fix."
    sarvam_client.SarvamTTSServiceError: status.HTTP_502_BAD_GATEWAY,
}


class VoiceSpeakView(APIView):
    """
    POST /api/voice/speak/

    Body: { "text": "...", "language_code": "hi-IN" }  (JSON)

    Always calls sarvam_client.text_to_speech() with
    speaker=sarvam_client.TTS_DEFAULT_SPEAKER ("shubh") — this app's one
    chosen voice for both Hindi and English output, per the Phase 2 task.
    Callers don't choose a speaker; only text/language_code are accepted.

    Response: on success, 200 with the raw synthesized audio as the response
    body (Content-Type: audio/wav) — not the JSON success()/error() envelope
    this app uses everywhere else, and not Sarvam's own base64-in-JSON shape
    either. Chosen to match this codebase's existing precedent for binary
    payloads (e.g. accounts/views.py's document-download endpoints, and the
    payroll/attendance export endpoints), which all return decoded bytes
    with a real Content-Type rather than a base64 string wrapped in JSON —
    the caller (an <audio> element or Web Audio API buffer, in the eventual
    Phase 4 frontend work) can use the bytes directly with no decode step.

    On any failure, falls back to the normal JSON error() envelope instead
    of a binary body — a real HTTP status code and human-readable message,
    not audio bytes describing an error. See sarvam_client.text_to_speech's
    own docstring for the distinct exception types this maps from.
    """

    permission_classes = [IsAuthenticated]

    async def post(self, request: Request) -> Response:
        """
        Scale-1 (2026-08-25 scalability-audit fix): dispatches the entire
        request — unchanged, still fully synchronous — to a dedicated
        per-request thread via sync_to_async(thread_sensitive=True), rather
        than running it inline. Under WSGI (this project's current
        deployment — see deploy.yml) this changes nothing observable: Django
        wraps the whole coroutine in async_to_sync and runs it to completion
        on the same calling worker thread regardless. It only pays off once
        HTTP traffic is actually served over ASGI (daphne today only serves
        the separate websocket path — see config/asgi.py) — a deployment
        change outside this repo's application code. At that point, a slow/
        rate-limited Sarvam call here (this module's own retry/backoff can
        run up to ~46.5s worst case) ties up only its own dedicated thread,
        not the shared event loop/worker other requests need. See
        _post_sync's docstring — business logic is byte-for-byte unchanged.
        """
        return await sync_to_async(self._post_sync, thread_sensitive=True)(request)

    def _post_sync(self, request: Request) -> Response:
        """The real, unchanged view logic — see post()'s docstring for why
        this is a separate method rather than post()'s own body."""
        text = (request.data.get('text') or '').strip()
        if not text:
            return error('text is required.', http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        language_code = (request.data.get('language_code') or '').strip()
        if not language_code:
            return error('language_code is required.', http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        try:
            audio_bytes = sarvam_client.text_to_speech(
                text, language_code, speaker=sarvam_client.TTS_DEFAULT_SPEAKER,
            )
        except sarvam_client.SarvamTTSError as exc:
            # Walked in subclass-first order so SarvamTTSConfigError (a
            # SarvamTTSAuthError subclass) still hits the right status via
            # its parent's entry — a plain dict lookup by exact type would
            # miss it. Every branch in this function's Raises: docstring is
            # a subclass of SarvamTTSError, so this always resolves to a
            # concrete status rather than falling through unhandled.
            http_status = status.HTTP_502_BAD_GATEWAY
            for exc_type, mapped_status in _TEXT_TO_SPEECH_ERROR_STATUS.items():
                if isinstance(exc, exc_type):
                    http_status = mapped_status
                    break
            logger.warning(
                'Voice speak failed: %s: %s (language_code=%s text_len=%d)',
                type(exc).__name__, exc, language_code, len(text),
            )
            return error(str(exc) or 'Could not generate speech right now.', http_status=http_status)

        response = HttpResponse(audio_bytes, content_type='audio/wav')
        response['Content-Disposition'] = 'inline; filename="voice-reply.wav"'
        # Freshly synthesized from this request's own text every time — an
        # intermediary caching this by URL alone would serve stale/wrong
        # audio for a different text/language_code on the same route.
        response['Cache-Control'] = 'no-store'
        return response
