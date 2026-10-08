"""
Phase 6B Task E.3 — device punch push endpoint. Authenticated by the
device's own `api_key` (a bearer-style header), not by a logged-in user
session — a device has no user account. This is the documented
simplification versus a full Phase 4 scoped API-key object (see
PHASE6B_REPORT.md).
"""
from __future__ import annotations

from datetime import datetime

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.responses import error, success


class DevicePunchPushView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from apps.attendance.models_device import AttendanceDevice

        api_key = request.headers.get('X-Device-Api-Key', '')
        device = AttendanceDevice.objects.filter(api_key=api_key, is_active=True).first() if api_key else None
        if device is None:
            return error('Invalid or missing device API key.', http_status=status.HTTP_401_UNAUTHORIZED)

        rows = request.data.get('punches')
        if not isinstance(rows, list) or not rows:
            return error('punches must be a non-empty list.', http_status=status.HTTP_400_BAD_REQUEST)

        parsed_rows = []
        for i, row in enumerate(rows):
            missing = [f for f in ('device_punch_id', 'employee_code', 'punch_type', 'device_time') if not row.get(f)]
            if missing:
                return error(f'Row {i}: missing field(s) {missing}.', http_status=status.HTTP_400_BAD_REQUEST)
            if row['punch_type'] not in ('IN', 'OUT'):
                return error(f"Row {i}: punch_type must be IN or OUT.", http_status=status.HTTP_400_BAD_REQUEST)
            try:
                device_time = datetime.fromisoformat(row['device_time'])
            except ValueError:
                return error(f'Row {i}: device_time must be ISO-8601.', http_status=status.HTTP_400_BAD_REQUEST)
            parsed_rows.append({**row, 'device_time': device_time})

        from apps.attendance.services_device_push import push_punches
        results = push_punches(device, parsed_rows)
        return success('Punches processed.', data={'results': [r.as_dict() for r in results]})
