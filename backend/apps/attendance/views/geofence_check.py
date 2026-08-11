"""
Geofence pre-check for the web clock-in/out widget.

Split into its own file rather than added to my_attendance.py (already at
the 300-line split threshold — see CLAUDE.md Section 6) and rather than
face_registration.py (different domain — this is location, not face).

Endpoint:
  POST /api/attendance/geofence-check/ — validate GPS before face capture
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.serializers_my_attendance import GeofenceCheckSerializer

logger = logging.getLogger(__name__)


class AttendanceGeofenceCheckView(APIView):
    """
    POST /api/attendance/geofence-check/

    Body: { "attendance_mode": "office", "latitude": .., "longitude": .., "accuracy": .. }

    Runs the SAME GeofencingService.validate() that PunchService.record_punch
    uses, but purely as a read — no punch is written. This lets the web
    ClockWidget/ClockInButton reject an out-of-geofence attempt (or a missing
    GPS reading) BEFORE ever opening the face verification modal, matching
    the order the voice flow already enforces in
    conversation_clock_in_face.start_voice_clock_punch (location check, then
    facial proof). The final punch submission still re-validates geofence
    and face independently — this view changes nothing about that.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = GeofenceCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        from apps.attendance.services_geofencing import GeofencingService

        data = serializer.validated_data
        geo = GeofencingService.validate(
            employee=request.user,
            attendance_mode=data['attendance_mode'],
            employee_lat=data.get('latitude'),
            employee_lon=data.get('longitude'),
            employee_accuracy=data.get('accuracy'),
        )
        if not geo.is_allowed:
            return error(geo.rejection_message, http_status=status.HTTP_403_FORBIDDEN)

        return success('Location verified.', {'is_allowed': True})
