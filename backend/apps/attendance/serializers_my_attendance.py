"""
Serializers for My Attendance APIs.

Write serializers validate incoming requests.
Read serializers shape outgoing responses.
All field names match exactly what the frontend components expect.
"""
from __future__ import annotations

import datetime

from rest_framework import serializers

from apps.attendance.models import AttendanceCorrection, AttendancePunch


# ══════════════════════════════════════════════════════════════════════════════
#  Write serializers
# ══════════════════════════════════════════════════════════════════════════════

class PunchWriteSerializer(serializers.Serializer):
    """
    POST /api/attendance/punch/

    The frontend should capture GPS via the browser Geolocation API and include
    latitude/longitude in every office punch.  All device and network fields are
    optional — omitting them is allowed but reduces the audit trail.
    """

    # ── Required ──────────────────────────────────────────────────────────────
    punch_type      = serializers.ChoiceField(choices=['IN', 'OUT'])

    # ── Source & mode ─────────────────────────────────────────────────────────
    source          = serializers.ChoiceField(
        choices=['web', 'mobile', 'biometric', 'manual', 'voice'],
        default='web',
    )
    attendance_mode = serializers.ChoiceField(
        choices=['office', 'wfh', 'field', 'client_location', 'remote_office'],
        default='office',
    )

    # ── GPS coordinates ───────────────────────────────────────────────────────
    latitude        = serializers.FloatField(required=False, allow_null=True, default=None)
    longitude       = serializers.FloatField(required=False, allow_null=True, default=None)
    accuracy        = serializers.FloatField(required=False, allow_null=True, default=None)

    # ── Face verification ─────────────────────────────────────────────────────
    # Only required when the employee has an approved FaceRegistrationRequest —
    # see FaceVerificationService.verify_for_punch. Never required otherwise.
    face_embedding  = serializers.ListField(
        child=serializers.FloatField(), required=False, allow_null=True, default=None,
    )
    # liveness_passed/liveness_score are the SAME capture-time liveness result
    # FaceRegistrationSubmitSerializer records at enrollment — carried here too
    # so FaceVerificationService's anti-replay check has something to compare
    # (see services_face_antispoofing.py). capture_session_id is a client-
    # generated UUID minted once per camera session (useFaceLivenessCapture.
    # start()) — used the same way, to tell a fresh capture apart from a
    # resubmitted one. None of the three are ever required on their own; they
    # only matter once face_embedding is present.
    liveness_passed = serializers.BooleanField(required=False, allow_null=True, default=None)
    liveness_score  = serializers.FloatField(required=False, allow_null=True, default=None)
    capture_session_id = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=64,
    )

    # ── Device info ───────────────────────────────────────────────────────────
    device_time     = serializers.DateTimeField(required=False, allow_null=True, default=None)
    device_name     = serializers.CharField(max_length=200,  required=False, allow_blank=True, default='')
    device_id       = serializers.CharField(max_length=255,  required=False, allow_blank=True, default='')
    browser         = serializers.CharField(max_length=500,  required=False, allow_blank=True, default='')
    operating_system = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')

    def validate(self, attrs: dict) -> dict:
        lat = attrs.get('latitude')
        lon = attrs.get('longitude')
        # Partial coordinates are worse than none — reject mismatched pairs
        if (lat is None) != (lon is None):
            raise serializers.ValidationError(
                'Both latitude and longitude must be provided together, or both omitted.'
            )
        return attrs


class CorrectionWriteSerializer(serializers.Serializer):
    """POST /api/attendance/correction/"""

    date               = serializers.DateField()
    punch_type         = serializers.ChoiceField(choices=['IN', 'OUT', 'BOTH'])
    correct_in_time    = serializers.TimeField(required=False, allow_null=True, default=None)
    correct_out_time   = serializers.TimeField(required=False, allow_null=True, default=None)
    reason             = serializers.ChoiceField(choices=[
        c[0] for c in AttendanceCorrection.REASON_CHOICES
    ])
    notes              = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default='',
    )

    def validate(self, attrs: dict) -> dict:
        punch_type = attrs['punch_type']
        in_time    = attrs.get('correct_in_time')
        out_time   = attrs.get('correct_out_time')

        if punch_type in ('IN', 'BOTH') and not in_time:
            raise serializers.ValidationError(
                {'correct_in_time': 'Correct In Time is required for this punch type.'}
            )
        if punch_type in ('OUT', 'BOTH') and not out_time:
            raise serializers.ValidationError(
                {'correct_out_time': 'Correct Out Time is required for this punch type.'}
            )
        if in_time and out_time and out_time <= in_time:
            raise serializers.ValidationError(
                {'correct_out_time': 'Out time must be after in time.'}
            )

        # Date cannot be in the future
        if attrs['date'] > datetime.date.today():
            raise serializers.ValidationError(
                {'date': 'Correction date cannot be in the future.'}
            )

        return attrs


class MonthYearQuerySerializer(serializers.Serializer):
    """Query-param validator for ?month=&year= on summary, calendar, stats."""
    month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    year  = serializers.IntegerField(min_value=2000, max_value=2100, required=False)

    def validate(self, attrs: dict) -> dict:
        today = datetime.date.today()
        attrs.setdefault('month', today.month)
        attrs.setdefault('year',  today.year)
        return attrs


# ══════════════════════════════════════════════════════════════════════════════
#  Read serializers  (response shaping)
# ══════════════════════════════════════════════════════════════════════════════

class PunchEntrySerializer(serializers.Serializer):
    """Single punch entry for the ClockWidget punch list."""
    type                = serializers.CharField()
    time                = serializers.CharField()
    location            = serializers.CharField()
    attendance_mode     = serializers.CharField()
    is_inside_geofence  = serializers.BooleanField(allow_null=True)
    calculated_distance = serializers.FloatField(allow_null=True)


class TodayAttendanceSerializer(serializers.Serializer):
    """
    Full payload for the ClockWidget.
    Fields match ClockWidget's state variables exactly.
    """
    is_clocked_in   = serializers.BooleanField()
    punches         = PunchEntrySerializer(many=True)
    total_seconds   = serializers.IntegerField()
    session_seconds = serializers.IntegerField()
    date_display    = serializers.CharField()


class StatsSerializer(serializers.Serializer):
    """Four stat cards on the My Attendance page."""
    days_present          = serializers.IntegerField()
    late_arrivals         = serializers.IntegerField()
    lop_pending           = serializers.IntegerField()
    avg_hours_per_day     = serializers.FloatField()
    attendance_percentage = serializers.IntegerField()
    working_days          = serializers.IntegerField()


class MonthlySummarySerializer(serializers.Serializer):
    """6-cell Monthly Summary grid."""
    working_days = serializers.IntegerField()
    days_present = serializers.IntegerField()
    days_absent  = serializers.IntegerField()
    leave_days   = serializers.IntegerField()
    half_days    = serializers.IntegerField()
    ot_hours     = serializers.CharField()


class DayRecordSerializer(serializers.Serializer):
    """
    One day's data for the CalendarGrid.
    Field names match DayRecord interface in CalendarGrid.tsx exactly.
    """
    date                    = serializers.CharField()
    status                  = serializers.CharField()
    color                   = serializers.CharField()
    clockIn                 = serializers.CharField(allow_null=True)
    clockOut                = serializers.CharField(allow_null=True)
    hours                   = serializers.CharField(allow_null=True)
    note                    = serializers.CharField(allow_null=True)
    holiday_name            = serializers.CharField(allow_null=True, required=False)
    canRegularize           = serializers.BooleanField()
    regularization_required = serializers.BooleanField()


class CalendarSerializer(serializers.Serializer):
    """Calendar response — days keyed by integer day number."""
    days = serializers.DictField(child=DayRecordSerializer())


class HistoryRowSerializer(serializers.Serializer):
    """One row in the AttendanceHistory table."""
    date          = serializers.CharField()
    day           = serializers.CharField()
    clockIn       = serializers.CharField()
    clockOut      = serializers.CharField()
    hours         = serializers.CharField()
    status        = serializers.CharField()
    canRegularize = serializers.BooleanField()


class CorrectionReadSerializer(serializers.Serializer):
    """Confirmation payload returned after a correction is submitted."""
    id         = serializers.UUIDField()
    date       = serializers.DateField()
    punch_type = serializers.CharField()
    reason     = serializers.CharField()
    status     = serializers.CharField()
    created_at = serializers.DateTimeField()


class MyCorrectionsFilterSerializer(serializers.Serializer):
    """Query params for GET /api/attendance/corrections/my/."""
    status    = serializers.ChoiceField(
        choices=['', 'pending', 'l2_pending', 'approved', 'rejected'],
        required=False, allow_blank=True, default='',
    )
    date_from = serializers.DateField(required=False, allow_null=True, default=None)
    date_to   = serializers.DateField(required=False, allow_null=True, default=None)

    def validate(self, attrs: dict) -> dict:
        if attrs.get('date_from') and attrs.get('date_to') and attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError({'date_to': 'date_to must be on or after date_from.'})
        return attrs
