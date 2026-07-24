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
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        transcript = (request.data.get('transcript') or '').strip()
        if not transcript:
            return error('transcript is required.', http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        lang = (request.data.get('lang') or 'en').strip() or 'en'
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        payload = handle_transcript(request, transcript, lang=lang, latitude=latitude, longitude=longitude)

        return success(payload['message'], payload)
