"""
Voice Commands views.

Endpoints:
  POST /api/voice/parse/  — Normalize + fuzzy-match a transcript, execute the intent.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, success

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.language import LANG_EN, LANG_HI


class VoiceParseView(APIView):
    """
    POST /api/voice/parse/

    Body: { "transcript": "...", "lang": "en", "latitude": 17.38, "longitude": 78.48 }

    Normalizes the transcript, fuzzy-matches it against the intent registry
    for the given language, and executes the matched intent through the same
    services the equivalent REST endpoints already use. If the caller has an
    apply_leave clarification pending (see apps.voice_commands.conversation),
    the transcript is treated as the answer to it instead of a fresh command.

    latitude/longitude are optional and only meaningful for clock_in/
    clock_out — mirrors what ClockWidget's manual punch already sends
    (attendance/serializers_my_attendance.py's PunchWriteSerializer), just
    plumbed through here rather than re-validated: execute_intent -> the same
    PunchWriteSerializer -> PunchService.record_punch() runs the real
    validation exactly as the manual flow does. Every other intent ignores
    them untouched, same as they already ignore attendance_mode.

    face_embedding/liveness_passed/liveness_score/capture_session_id are the
    same kind of optional, clock_in/clock_out-only payload — carried by the
    silent resubmit FaceVerificationModal triggers once it produces a
    descriptor for the "taking facial proof" turn (see
    apps.voice_commands.conversation_clock_in_face). Not re-validated here
    either — FaceVerificationService.verify_for_punch is the one place that
    actually checks them.

    stt_language_probability is optional, sent only alongside a transcript
    that came from the Sarvam-STT retry (see lib/voiceSttFallback.ts) —
    Sarvam's own confidence in which language it heard, used by
    handle_transcript as the best available proxy for "is this transcript
    even trustworthy" before matching/classifying it at all.

    stt_used_language_hint is optional, sent only alongside a transcript
    from the Sarvam-STT retry's explicit-Hindi-hint attempt (see
    views_transcribe.py) — that mode never gets a language_probability back
    from Sarvam, so handle_transcript treats it as always needing
    confirmation instead of trying to threshold a signal that doesn't exist.

    stt_detected_language is optional (Phase 4), sent only alongside a
    transcript from the Sarvam-STT retry — views_transcribe.py's own
    `detected_language` field, forwarded verbatim by useVoiceCommand.ts.
    Only 'en'/'hi' are accepted; anything else is dropped rather than
    forwarded, same defensive normalization language.detect_language()
    itself already applies. Used by handle_transcript to pick the accurate
    EN/HI signal for text/voice selection — it plays no part in the
    STT-confirmation gate, which still reads only stt_used_language_hint/
    stt_language_probability above.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        transcript = (request.data.get('transcript') or '').strip()
        if not transcript:
            return error('transcript is required.', http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        stt_language_probability = None
        raw_probability = request.data.get('stt_language_probability')
        if raw_probability is not None:
            try:
                stt_language_probability = float(raw_probability)
            except (TypeError, ValueError):
                stt_language_probability = None

        # True only when this transcript came from the Sarvam-STT retry's
        # explicit-language-hint attempt (see views_transcribe.py) — that
        # mode gets no language_probability back from Sarvam at all, so
        # handle_transcript can't use the usual confidence check for it and
        # instead always confirms (see its own docstring).
        stt_used_language_hint = bool(request.data.get('stt_used_language_hint'))

        raw_detected_language = request.data.get('stt_detected_language')
        stt_detected_language = raw_detected_language if raw_detected_language in (LANG_EN, LANG_HI) else None

        lang = (request.data.get('lang') or 'en').strip() or 'en'
        payload = handle_transcript(
            request, transcript, lang=lang,
            latitude=request.data.get('latitude'), longitude=request.data.get('longitude'),
            face_embedding=request.data.get('face_embedding'),
            liveness_passed=request.data.get('liveness_passed'),
            liveness_score=request.data.get('liveness_score'),
            capture_session_id=request.data.get('capture_session_id') or '',
            stt_language_probability=stt_language_probability,
            stt_used_language_hint=stt_used_language_hint,
            stt_detected_language=stt_detected_language,
        )

        return success(payload['message'], payload)
