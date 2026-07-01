"""
Attendance Settings service layer.

All database writes go through this module, wrapped in transaction.atomic()
so a validation failure in any section rolls back the entire save.

The view's responsibility is HTTP (validate input, return response).
This module's responsibility is persistence (create / update models).
"""
from __future__ import annotations

import logging

from django.db import transaction

from apps.attendance.models import (
    AttendanceAbsenceAlert,
    AttendanceLateMarkRules,
    AttendanceOvertimeRules,
    AttendancePunchRules,
    AttendanceSettings,
    AttendanceWeeklyOff,
    AttendanceWorkingHours,
)

logger = logging.getLogger(__name__)

# Passed to select_related() for all settings queries — avoids N+1 on reads.
_RELATED = (
    'working_hours',
    'weekly_off',
    'punch_rules',
    'overtime_rules',
    'late_mark_rules',
    'absence_alert',
    'updated_by',
)

# Returned by GET when no settings have been saved yet.
# Mirrors the frontend's default UI values.
DEFAULT_SETTINGS: dict = {
    'working_hours': {
        'shift_start':            '09:00:00',
        'shift_end':              '18:00:00',
        'grace_period_minutes':   15,
        'break_duration_minutes': 30,
    },
    'weekly_off': {
        'monday':    False,
        'tuesday':   False,
        'wednesday': False,
        'thursday':  False,
        'friday':    False,
        'saturday':  True,
        'sunday':    True,
    },
    'punch_rules': {
        'min_hours_full_day':       '8.00',
        'min_hours_half_day':       '4.00',
        'early_exit_grace_minutes': 30,
    },
    'overtime_rules': {
        'ot_threshold_hours':    '9.00',
        'ot_multiplier_regular': '1.50',
        'ot_multiplier_holiday': '2.00',
    },
    'late_mark_rules': {
        'late_marks_per_lop': 3,
        'lop_deduction_unit': 'full_day',
    },
    'absence_alert': {
        'is_enabled':      True,
        'alert_after_days': 3,
        'notify_whom':     'manager_and_hr',
    },
}


class AttendanceSettingsService:
    """
    All public methods are class methods.
    No instance state — this is a stateless service.
    """

    @classmethod
    def get_current(cls) -> AttendanceSettings | None:
        """Return the active settings record, or None if none configured yet."""
        return (
            AttendanceSettings.objects
            .select_related(*_RELATED)
            .filter(is_active=True)
            .order_by('-created_at')
            .first()
        )

    @classmethod
    def upsert(cls, validated_data: dict, user) -> AttendanceSettings:
        """
        Create or update attendance settings in one atomic transaction.

        validated_data must come from AttendanceSettingsWriteSerializer.validated_data.
        If no settings record exists, a new one is created with all six children.
        If one already exists, all six children are updated in place.
        """
        with transaction.atomic():
            existing = cls.get_current()
            if existing is None:
                instance = cls._create(validated_data, user)
            else:
                instance = cls._update(existing, validated_data, user)
        return instance

    # ── Private helpers ───────────────────────────────────────────────────────

    @classmethod
    def _create(cls, data: dict, user) -> AttendanceSettings:
        settings = AttendanceSettings.objects.create(
            created_by=user,
            updated_by=user,
        )
        AttendanceWorkingHours.objects.create(settings=settings, **data['working_hours'])
        AttendanceWeeklyOff.objects.create(settings=settings, **data['weekly_off'])
        AttendancePunchRules.objects.create(settings=settings, **data['punch_rules'])
        AttendanceOvertimeRules.objects.create(settings=settings, **data['overtime_rules'])
        AttendanceLateMarkRules.objects.create(settings=settings, **data['late_mark_rules'])
        AttendanceAbsenceAlert.objects.create(settings=settings, **data['absence_alert'])

        logger.info('AttendanceSettings created (pk=%s) by user %s', settings.pk, user.pk)
        return AttendanceSettings.objects.select_related(*_RELATED).get(pk=settings.pk)

    @classmethod
    def partial_update(cls, validated_data: dict, user) -> AttendanceSettings:
        """
        Update only the sections present in validated_data.
        If no settings record exists yet, fall back to a full create using defaults
        merged with the provided sections.
        """
        with transaction.atomic():
            existing = cls.get_current()
            if existing is None:
                merged = {**DEFAULT_SETTINGS, **validated_data}
                return cls._create(merged, user)
            return cls._update(existing, validated_data, user)

    @classmethod
    def _update(cls, instance: AttendanceSettings, data: dict, user) -> AttendanceSettings:
        _SECTION_MAP = {
            'working_hours':  'working_hours',
            'weekly_off':     'weekly_off',
            'punch_rules':    'punch_rules',
            'overtime_rules': 'overtime_rules',
            'late_mark_rules': 'late_mark_rules',
            'absence_alert':  'absence_alert',
        }
        for key, related_name in _SECTION_MAP.items():
            if key in data:
                cls._apply_fields(getattr(instance, related_name), data[key])

        instance.updated_by = user
        instance.save(update_fields=['updated_by', 'updated_at'])

        logger.info('AttendanceSettings updated (pk=%s) by user %s', instance.pk, user.pk)
        return AttendanceSettings.objects.select_related(*_RELATED).get(pk=instance.pk)

    @staticmethod
    def _apply_fields(obj, field_data: dict) -> None:
        """Set each field on obj and call save(). Reusable for all child models."""
        for field, value in field_data.items():
            setattr(obj, field, value)
        obj.save()
