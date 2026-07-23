"""
HR Attendance Management serializers.

Read serializers shape API responses.
Write serializers validate incoming HR actions.
All computation happens in services — never here.
"""
from __future__ import annotations

import datetime

from rest_framework import serializers

from apps.attendance.models import AttendanceOvertime


# ── Query param validators ────────────────────────────────────────────────────

class AttendanceListFilterSerializer(serializers.Serializer):
    date       = serializers.DateField(required=False)
    branch     = serializers.CharField(required=False, allow_blank=True, default='')
    department = serializers.CharField(required=False, allow_blank=True, default='')
    status     = serializers.ChoiceField(
        choices=['', 'present', 'late', 'absent', 'half_day', 'weekly_off', 'holiday', 'on_leave', 'incomplete'],
        required=False, allow_blank=True, default='',
    )
    search     = serializers.CharField(required=False, allow_blank=True, default='')
    sort_by    = serializers.ChoiceField(
        choices=['name', 'employee_id', 'department', 'branch', 'clock_in', 'status'],
        required=False, default='name',
    )
    sort_dir   = serializers.ChoiceField(
        choices=['asc', 'desc'], required=False, default='asc',
    )

    def validate(self, attrs: dict) -> dict:
        if not attrs.get('date'):
            attrs['date'] = datetime.date.today()
        return attrs


class DateFilterSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get('date'):
            attrs['date'] = datetime.date.today()
        return attrs


# ── Read serializers ──────────────────────────────────────────────────────────

class StatCardSerializer(serializers.Serializer):
    present_today    = serializers.IntegerField()
    absent           = serializers.IntegerField()
    late_arrivals    = serializers.IntegerField()
    on_leave         = serializers.IntegerField()
    total_employees  = serializers.IntegerField()


class SummaryChipsSerializer(serializers.Serializer):
    present    = serializers.IntegerField()
    late       = serializers.IntegerField()
    absent     = serializers.IntegerField()
    on_leave   = serializers.IntegerField()
    half_day   = serializers.IntegerField()
    weekly_off = serializers.IntegerField()
    holiday    = serializers.IntegerField()


class TabBadgeSerializer(serializers.Serializer):
    invalid_punches = serializers.IntegerField()
    un_punches      = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    stat_cards    = StatCardSerializer()
    summary_chips = SummaryChipsSerializer()
    tab_badges    = TabBadgeSerializer()


class AttendanceRowSerializer(serializers.Serializer):
    """One row in the HR attendance grid — matches AttendanceTab.tsx columns."""
    record_id    = serializers.UUIDField(allow_null=True)
    employee_id  = serializers.CharField()
    name         = serializers.CharField()
    initials     = serializers.CharField()
    department   = serializers.CharField()
    branch       = serializers.CharField()
    clock_in     = serializers.CharField()   # "09:05" or "—"
    clock_out    = serializers.CharField()   # "18:15" or "—"
    total_hours  = serializers.CharField()   # "9h 10m" or "—"
    ot           = serializers.CharField()   # "10m" or "—"
    status       = serializers.CharField()   # "Present", "Late", …
    status_key   = serializers.CharField()   # "present", "late", …
    is_late      = serializers.BooleanField()


class PunchEntrySerializer(serializers.Serializer):
    punch_type  = serializers.CharField()
    time        = serializers.CharField()
    source      = serializers.CharField()
    mode        = serializers.CharField()
    is_geofence = serializers.BooleanField(allow_null=True)
    distance_m  = serializers.FloatField(allow_null=True)


class AttendanceDetailSerializer(serializers.Serializer):
    """Full detail for one employee on a date — shown in 'View' modal."""
    record_id    = serializers.UUIDField(allow_null=True)
    employee_id  = serializers.CharField()
    name         = serializers.CharField()
    department   = serializers.CharField()
    branch       = serializers.CharField()
    date         = serializers.DateField()
    status       = serializers.CharField()
    status_key   = serializers.CharField()
    clock_in     = serializers.CharField()
    clock_out    = serializers.CharField()
    total_hours  = serializers.CharField()
    overtime     = serializers.CharField()
    is_late      = serializers.BooleanField()
    is_early_exit = serializers.BooleanField()
    note         = serializers.CharField()
    punches      = PunchEntrySerializer(many=True)


class OvertimeRowSerializer(serializers.Serializer):
    id          = serializers.UUIDField()
    employee_id = serializers.CharField()
    name        = serializers.CharField()
    initials    = serializers.CharField()
    date        = serializers.CharField()
    ot_hours    = serializers.CharField()
    ot_type     = serializers.CharField()
    ot_amount   = serializers.CharField()
    approved_by = serializers.CharField()
    status      = serializers.CharField()


class InvalidPunchSerializer(serializers.Serializer):
    id              = serializers.UUIDField()
    device_id       = serializers.CharField()
    raw_time        = serializers.CharField()
    biometric_id    = serializers.CharField()
    issue           = serializers.CharField()
    issue_type      = serializers.CharField()
    suggested_match = serializers.CharField()
    branch          = serializers.CharField()


class UnpunchRowSerializer(serializers.Serializer):
    employee_id        = serializers.CharField()
    name               = serializers.CharField()
    initials           = serializers.CharField()
    date               = serializers.CharField()
    clock_in           = serializers.CharField()
    expected_out       = serializers.CharField()
    branch             = serializers.CharField()
    correction_pending = serializers.BooleanField()
    correction_id      = serializers.UUIDField(allow_null=True)


class CorrectionRowSerializer(serializers.Serializer):
    """One row in the HR corrections list."""
    id                 = serializers.UUIDField()
    employee_id        = serializers.CharField()
    name               = serializers.CharField()
    department         = serializers.CharField()
    branch             = serializers.CharField()
    date               = serializers.CharField()
    punch_type         = serializers.CharField()
    requested_in       = serializers.CharField(allow_null=True)
    requested_out      = serializers.CharField(allow_null=True)
    reason             = serializers.CharField()
    notes              = serializers.CharField()
    status             = serializers.CharField()
    l1_approver_name   = serializers.CharField(allow_null=True)
    l1_status          = serializers.CharField(allow_null=True)
    l1_remarks         = serializers.CharField()
    l2_approver_name   = serializers.CharField(allow_null=True)
    l2_status          = serializers.CharField(allow_null=True)
    l2_remarks         = serializers.CharField()
    can_action         = serializers.BooleanField()
    reviewed_by        = serializers.CharField(allow_null=True)
    reviewed_at        = serializers.CharField(allow_null=True)
    created_at         = serializers.CharField()


class CorrectionListFilterSerializer(serializers.Serializer):
    branch     = serializers.CharField(required=False, allow_blank=True, default='')
    department = serializers.CharField(required=False, allow_blank=True, default='')
    status     = serializers.ChoiceField(
        choices=['', 'pending', 'l2_pending', 'approved', 'rejected'],
        required=False, allow_blank=True, default='',
    )


class CorrectionReviewSerializer(serializers.Serializer):
    action  = serializers.ChoiceField(choices=['approve', 'reject'])
    remarks = serializers.CharField(required=False, allow_blank=True, default='')


# ── Write serializers ─────────────────────────────────────────────────────────

class OvertimeWriteSerializer(serializers.Serializer):
    employee_id = serializers.CharField()
    date        = serializers.DateField()
    ot_type     = serializers.ChoiceField(
        choices=[c[0] for c in AttendanceOvertime.OT_TYPE_CHOICES],
    )
    ot_start    = serializers.TimeField()
    ot_end      = serializers.TimeField()
    approved_by = serializers.CharField(required=False, allow_blank=True, default='')
    reason      = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')

    def validate(self, attrs: dict) -> dict:
        if attrs['ot_end'] <= attrs['ot_start']:
            raise serializers.ValidationError({'ot_end': 'OT end time must be after OT start time.'})
        if attrs['date'] > datetime.date.today():
            raise serializers.ValidationError({'date': 'OT date cannot be in the future.'})
        return attrs


class ImportRowSerializer(serializers.Serializer):
    """Validates a single row from the uploaded CSV."""
    employee_id = serializers.CharField()
    date        = serializers.DateField()
    punch_in    = serializers.TimeField(required=False, allow_null=True, default=None)
    punch_out   = serializers.TimeField(required=False, allow_null=True, default=None)

    def validate(self, attrs: dict) -> dict:
        punch_in  = attrs.get('punch_in')
        punch_out = attrs.get('punch_out')
        if punch_in and punch_out and punch_out <= punch_in:
            raise serializers.ValidationError({
                'punch_out': (
                    f'Punch out ({punch_out.strftime("%H:%M")}) must be after '
                    f'punch in ({punch_in.strftime("%H:%M")}). '
                    'Use 24-hour format — e.g. 14:00 for 2 PM.'
                )
            })
        return attrs


# ── Audit log serializers ─────────────────────────────────────────────────────

class AuditLogEntrySerializer(serializers.Serializer):
    """One row in the attendance record audit history."""
    event        = serializers.CharField()
    performed_by = serializers.CharField()
    performed_at = serializers.CharField()
    old_value    = serializers.CharField(allow_null=True)
    new_value    = serializers.CharField(allow_null=True)
    action       = serializers.CharField()
    remarks      = serializers.CharField()


# ── Invalid punch action serializers ─────────────────────────────────────────

class InvalidPunchAssignSerializer(serializers.Serializer):
    assigned_to = serializers.UUIDField(
        help_text='UUID of the HR user to assign this punch to.',
    )


class InvalidPunchDiscardSerializer(serializers.Serializer):
    remarks = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default='',
        help_text='Optional reason for discarding.',
    )


class InvalidPunchConvertSerializer(serializers.Serializer):
    target_punch_type = serializers.ChoiceField(
        choices=['IN', 'OUT'],
        help_text='The correct punch type to create.',
    )
    target_time = serializers.TimeField(
        help_text='The correct punch time in HH:MM format.',
    )


# ── HR Attendance Edit / Manual Create ───────────────────────────────────────

_EDITABLE_STATUSES = [
    'present', 'late', 'half_day', 'on_leave',
    'weekly_off', 'holiday', 'absent', 'incomplete',
]


class HRAttendanceEditSerializer(serializers.Serializer):
    """Validates a PATCH body for HR editing an existing attendance record."""
    status    = serializers.ChoiceField(choices=_EDITABLE_STATUSES, required=False)
    clock_in  = serializers.TimeField(required=False, allow_null=True)
    clock_out = serializers.TimeField(required=False, allow_null=True)
    note      = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    reason    = serializers.CharField(max_length=500, help_text='Required — logged in the audit trail.')

    def validate(self, attrs: dict) -> dict:
        clock_in  = attrs.get('clock_in')
        clock_out = attrs.get('clock_out')
        if clock_in and clock_out and clock_out <= clock_in:
            raise serializers.ValidationError({'clock_out': 'Clock out must be after clock in.'})
        return attrs


class HRAttendanceManualCreateSerializer(serializers.Serializer):
    """Validates a POST body for HR manually creating an attendance record."""
    employee_id = serializers.CharField()
    date        = serializers.DateField()
    status      = serializers.ChoiceField(choices=_EDITABLE_STATUSES)
    clock_in    = serializers.TimeField(required=False, allow_null=True, default=None)
    clock_out   = serializers.TimeField(required=False, allow_null=True, default=None)
    note        = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    reason      = serializers.CharField(max_length=500, help_text='Required — logged in the audit trail.')

    def validate(self, attrs: dict) -> dict:
        clock_in  = attrs.get('clock_in')
        clock_out = attrs.get('clock_out')
        if clock_in and clock_out and clock_out <= clock_in:
            raise serializers.ValidationError({'clock_out': 'Clock out must be after clock in.'})
        if attrs['date'] > datetime.date.today():
            raise serializers.ValidationError({'date': 'Cannot create attendance for a future date.'})
        return attrs
