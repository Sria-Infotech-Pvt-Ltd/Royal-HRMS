"""
POST /api/attendance/face-capture-telemetry/

Receives one summary per client-side face-capture camera session (see
FaceCaptureTelemetry's docstring). Numbers only — the payload is validated
and bounded so a client cannot use it to store arbitrary data, and a bad
payload is answered with a 400 the client simply ignores.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.models import FaceCaptureTelemetry

_MAX_DETAILS_KEYS = 40
_MAX_DETAILS_CHARS = 4000


class FaceCaptureTelemetrySerializer(serializers.Serializer):
    capture_session_id = serializers.CharField(max_length=64, allow_blank=True, required=False, default='')
    purpose            = serializers.ChoiceField(choices=[c[0] for c in FaceCaptureTelemetry.PURPOSE_CHOICES])
    outcome            = serializers.ChoiceField(choices=[c[0] for c in FaceCaptureTelemetry.OUTCOME_CHOICES])
    duration_ms        = serializers.IntegerField(min_value=0, max_value=3_600_000, default=0)
    liveness_attempts  = serializers.IntegerField(min_value=0, max_value=200, default=0)
    quality_failures   = serializers.IntegerField(min_value=0, max_value=500, default=0)
    auto_resumes       = serializers.IntegerField(min_value=0, max_value=50, default=0)
    manual_retries     = serializers.IntegerField(min_value=0, max_value=50, default=0)
    tf_backend         = serializers.CharField(max_length=16, allow_blank=True, required=False, default='')
    avg_fps            = serializers.FloatField(min_value=0, max_value=240, required=False, allow_null=True)
    details            = serializers.DictField(required=False, default=dict)

    def validate_details(self, value: dict) -> dict:
        if len(value) > _MAX_DETAILS_KEYS:
            raise serializers.ValidationError('Too many detail fields.')
        if len(str(value)) > _MAX_DETAILS_CHARS:
            raise serializers.ValidationError('Details payload too large.')
        return value


class FaceCaptureTelemetryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = FaceCaptureTelemetrySerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), http_status=status.HTTP_400_BAD_REQUEST)

        FaceCaptureTelemetry.objects.create(
            employee=request.user,
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
            **serializer.validated_data,
        )
        return success('Recorded.', http_status=status.HTTP_201_CREATED)
