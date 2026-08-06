"""
Serializers for the unified Attendance Settings endpoint.

Write serializers (Serializer, not ModelSerializer) handle validation and
produce clean validated_data that the service layer persists.

Read serializers (ModelSerializer) produce the full response payload.

Separation keeps validation rules in one place and response shaping in another.
"""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.attendance.models import (
    AttendanceAbsenceAlert,
    AttendanceFaceVerificationRules,
    AttendanceLateMarkRules,
    AttendanceOvertimeRules,
    AttendancePunchRules,
    AttendanceSettings,
    AttendanceWeeklyOff,
    AttendanceWorkingHours,
)

# ─── Constants ────────────────────────────────────────────────────────────────

_MAX_GRACE_PERIOD      = 120     # 2 h
_MAX_BREAK_DURATION    = 480     # 8 h
_MAX_EARLY_EXIT_GRACE  = 120     # 2 h
_MAX_HOURS             = Decimal('24')
_MIN_MULTIPLIER        = Decimal('1.00')
_MAX_MULTIPLIER        = Decimal('5.00')
_MAX_ALERT_DAYS        = 30
_MAX_LATE_MARKS        = 31


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE serializers  (validation only — service layer does the actual saves)
# ══════════════════════════════════════════════════════════════════════════════

class WorkingHoursWriteSerializer(serializers.Serializer):
    shift_start            = serializers.TimeField()
    shift_end              = serializers.TimeField()
    grace_period_minutes   = serializers.IntegerField(min_value=0, max_value=_MAX_GRACE_PERIOD)
    break_duration_minutes = serializers.IntegerField(min_value=0, max_value=_MAX_BREAK_DURATION)

    def validate(self, attrs: dict) -> dict:
        start  = attrs['shift_start']
        end    = attrs['shift_end']
        grace  = attrs.get('grace_period_minutes', 0)
        brk    = attrs.get('break_duration_minutes', 0)

        if start == end:
            raise serializers.ValidationError(
                {'shift_end': 'Shift end cannot equal shift start.'}
            )

        # Compute net shift hours (overnight-safe)
        from datetime import datetime, date, timedelta
        today    = date.today()
        start_dt = datetime.combine(today, start)
        end_dt   = datetime.combine(today, end)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        net_minutes = (end_dt - start_dt).total_seconds() / 60 - brk

        if net_minutes <= 0:
            raise serializers.ValidationError(
                'Net working hours (shift duration minus break) must be greater than zero.'
            )

        shift_minutes = (end_dt - start_dt).total_seconds() / 60
        if grace >= shift_minutes:
            raise serializers.ValidationError(
                {'grace_period_minutes': 'Grace period cannot equal or exceed the shift duration.'}
            )

        return attrs


class WeeklyOffWriteSerializer(serializers.Serializer):
    monday    = serializers.BooleanField(default=False)
    tuesday   = serializers.BooleanField(default=False)
    wednesday = serializers.BooleanField(default=False)
    thursday  = serializers.BooleanField(default=False)
    friday    = serializers.BooleanField(default=False)
    saturday  = serializers.BooleanField(default=True)
    sunday    = serializers.BooleanField(default=True)

    def validate(self, attrs: dict) -> dict:
        days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
        working = [d for d in days if not attrs.get(d, False)]
        if not working:
            raise serializers.ValidationError(
                'At least one day must be a working day. '
                'A week with zero working days is not a valid schedule.'
            )
        return attrs


class PunchRulesWriteSerializer(serializers.Serializer):
    min_hours_full_day       = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal('0.50'))
    min_hours_half_day       = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal('0.25'))
    early_exit_grace_minutes = serializers.IntegerField(min_value=0, max_value=_MAX_EARLY_EXIT_GRACE)

    def validate(self, attrs: dict) -> dict:
        full = attrs.get('min_hours_full_day')
        half = attrs.get('min_hours_half_day')

        if full is not None and half is not None and half >= full:
            raise serializers.ValidationError(
                {'min_hours_half_day': (
                    f'Half-day minimum hours ({half}h) must be less than '
                    f'full-day minimum hours ({full}h).'
                )}
            )
        return attrs


class OvertimeRulesWriteSerializer(serializers.Serializer):
    ot_threshold_hours    = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal('1.00'))
    ot_multiplier_regular = serializers.DecimalField(max_digits=3, decimal_places=2,
                                                     min_value=_MIN_MULTIPLIER, max_value=_MAX_MULTIPLIER)
    ot_multiplier_holiday = serializers.DecimalField(max_digits=3, decimal_places=2,
                                                     min_value=_MIN_MULTIPLIER, max_value=_MAX_MULTIPLIER)


class LateMarkRulesWriteSerializer(serializers.Serializer):
    _VALID_LOP_UNITS = {c[0] for c in AttendanceLateMarkRules.LOP_UNIT_CHOICES}

    late_marks_per_lop = serializers.IntegerField(min_value=0, max_value=_MAX_LATE_MARKS)
    lop_deduction_unit = serializers.ChoiceField(choices=AttendanceLateMarkRules.LOP_UNIT_CHOICES)


class AbsenceAlertWriteSerializer(serializers.Serializer):
    is_enabled       = serializers.BooleanField(default=True)
    alert_after_days = serializers.IntegerField(min_value=1, max_value=_MAX_ALERT_DAYS)
    notify_whom      = serializers.ChoiceField(choices=AttendanceAbsenceAlert.NOTIFY_CHOICES)


class FaceVerificationRulesWriteSerializer(serializers.Serializer):
    is_mandatory = serializers.BooleanField(default=False)


class AttendanceSettingsWriteSerializer(serializers.Serializer):
    """
    Top-level write serializer.
    Nests the seven section serializers; performs cross-section validation
    (e.g. OT threshold must exceed full-day minimum hours).
    """

    working_hours     = WorkingHoursWriteSerializer()
    weekly_off        = WeeklyOffWriteSerializer()
    punch_rules       = PunchRulesWriteSerializer()
    overtime_rules    = OvertimeRulesWriteSerializer()
    late_mark_rules   = LateMarkRulesWriteSerializer()
    absence_alert     = AbsenceAlertWriteSerializer()
    face_verification = FaceVerificationRulesWriteSerializer()

    def validate(self, attrs: dict) -> dict:
        pr = attrs.get('punch_rules', {})
        or_ = attrs.get('overtime_rules', {})

        full_day_min = pr.get('min_hours_full_day')
        ot_threshold = or_.get('ot_threshold_hours')

        if full_day_min is not None and ot_threshold is not None:
            if ot_threshold <= full_day_min:
                raise serializers.ValidationError({
                    'overtime_rules': {
                        'ot_threshold_hours': (
                            f'OT threshold ({ot_threshold}h) must be greater than the '
                            f'full-day minimum hours ({full_day_min}h). Overtime can only '
                            'start after an employee has completed a full working day.'
                        )
                    }
                })

        return attrs


class AttendanceSettingsPatchSerializer(serializers.Serializer):
    """
    Partial update serializer — all six sections are optional.
    Send only the section(s) you want to change; the rest stay untouched.
    At least one section must be provided.
    """

    working_hours     = WorkingHoursWriteSerializer(required=False)
    weekly_off        = WeeklyOffWriteSerializer(required=False)
    punch_rules       = PunchRulesWriteSerializer(required=False)
    overtime_rules    = OvertimeRulesWriteSerializer(required=False)
    late_mark_rules   = LateMarkRulesWriteSerializer(required=False)
    absence_alert     = AbsenceAlertWriteSerializer(required=False)
    face_verification = FaceVerificationRulesWriteSerializer(required=False)

    def validate(self, attrs: dict) -> dict:
        if not attrs:
            raise serializers.ValidationError(
                'At least one section must be provided for a partial update.'
            )

        pr = attrs.get('punch_rules', {})
        or_ = attrs.get('overtime_rules', {})
        full_day_min = pr.get('min_hours_full_day')
        ot_threshold = or_.get('ot_threshold_hours')

        if full_day_min is not None and ot_threshold is not None:
            if ot_threshold <= full_day_min:
                raise serializers.ValidationError({
                    'overtime_rules': {
                        'ot_threshold_hours': (
                            f'OT threshold ({ot_threshold}h) must be greater than the '
                            f'full-day minimum hours ({full_day_min}h).'
                        )
                    }
                })

        return attrs


# ══════════════════════════════════════════════════════════════════════════════
#  READ serializers  (response shaping only)
# ══════════════════════════════════════════════════════════════════════════════

class WorkingHoursReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AttendanceWorkingHours
        fields = ('shift_start', 'shift_end', 'grace_period_minutes', 'break_duration_minutes')
        read_only_fields = fields


class WeeklyOffReadSerializer(serializers.ModelSerializer):
    off_days           = serializers.ListField(child=serializers.CharField(), read_only=True)
    working_days_count = serializers.IntegerField(read_only=True)

    class Meta:
        model  = AttendanceWeeklyOff
        fields = (
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'off_days', 'working_days_count',
        )
        read_only_fields = fields


class PunchRulesReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AttendancePunchRules
        fields = ('min_hours_full_day', 'min_hours_half_day', 'early_exit_grace_minutes')
        read_only_fields = fields


class OvertimeRulesReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AttendanceOvertimeRules
        fields = ('ot_threshold_hours', 'ot_multiplier_regular', 'ot_multiplier_holiday')
        read_only_fields = fields


class LateMarkRulesReadSerializer(serializers.ModelSerializer):
    lop_deduction_unit_display = serializers.CharField(
        source='get_lop_deduction_unit_display', read_only=True,
    )
    is_lop_enabled = serializers.SerializerMethodField()

    class Meta:
        model  = AttendanceLateMarkRules
        fields = ('late_marks_per_lop', 'lop_deduction_unit', 'lop_deduction_unit_display', 'is_lop_enabled')
        read_only_fields = fields

    def get_is_lop_enabled(self, obj: AttendanceLateMarkRules) -> bool:
        return obj.late_marks_per_lop > 0


class AbsenceAlertReadSerializer(serializers.ModelSerializer):
    notify_whom_display = serializers.CharField(
        source='get_notify_whom_display', read_only=True,
    )

    class Meta:
        model  = AttendanceAbsenceAlert
        fields = ('is_enabled', 'alert_after_days', 'notify_whom', 'notify_whom_display')
        read_only_fields = fields


class FaceVerificationRulesReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AttendanceFaceVerificationRules
        fields = ('is_mandatory',)
        read_only_fields = fields


class AttendanceSettingsReadSerializer(serializers.ModelSerializer):
    working_hours     = WorkingHoursReadSerializer(read_only=True)
    weekly_off        = WeeklyOffReadSerializer(read_only=True)
    punch_rules       = PunchRulesReadSerializer(read_only=True)
    overtime_rules    = OvertimeRulesReadSerializer(read_only=True)
    late_mark_rules   = LateMarkRulesReadSerializer(read_only=True)
    absence_alert     = AbsenceAlertReadSerializer(read_only=True)
    face_verification = FaceVerificationRulesReadSerializer(read_only=True)
    updated_by_name   = serializers.SerializerMethodField()

    class Meta:
        model  = AttendanceSettings
        fields = (
            'id',
            'working_hours',
            'weekly_off',
            'punch_rules',
            'overtime_rules',
            'late_mark_rules',
            'absence_alert',
            'face_verification',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_updated_by_name(self, obj: AttendanceSettings) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None
