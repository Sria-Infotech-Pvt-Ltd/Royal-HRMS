"""
Phase 6B Task B — the Shift master. Additive: nothing in
`AttendanceProcessorService` (services_attendance.py) reads from this
yet — the Explore pass that preceded this build confirmed daily
processing today reads the flat `AttendanceSettings` singleton, NOT
`WorkingHoursPolicy` (which exists but has no per-employee assignment and
is read only for display, by `MyShiftView`). `Shift` is a real, richer
superset of `WorkingHoursPolicy`'s fields (adds crosses_midnight,
core_hours/is_flexible, punch window, half/full-day minimums, overtime
start rule, is_night_shift) but is NOT wired into the processor or
`WorkingHoursPolicy` in this pass — see PHASE6B_REPORT.md Task B/D notes.
"""
from __future__ import annotations

import uuid

from django.db import models


class Shift(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    start_time = models.TimeField()
    end_time = models.TimeField()
    crosses_midnight = models.BooleanField(default=False, help_text='Derived from start_time > end_time on save() — see save() override.')

    break_minutes = models.PositiveIntegerField(default=0)
    is_break_paid = models.BooleanField(default=False)

    core_hours_start = models.TimeField(null=True, blank=True, help_text='For flexi shifts only.')
    core_hours_end = models.TimeField(null=True, blank=True)
    is_flexible = models.BooleanField(default=False, help_text='Total-hours-based rather than fixed start/end.')

    grace_in_minutes = models.PositiveIntegerField(default=0)
    grace_out_minutes = models.PositiveIntegerField(default=0)
    earliest_punch_in_minutes_before = models.PositiveIntegerField(default=60, help_text='Punch window: earliest IN relative to start_time.')
    latest_punch_out_minutes_after = models.PositiveIntegerField(default=120, help_text='Punch window: latest OUT relative to end_time.')

    half_day_minimum_minutes = models.PositiveIntegerField(default=240)
    full_day_minimum_minutes = models.PositiveIntegerField(default=480)

    OT_START_AFTER_SHIFT_END = 'after_shift_end'
    OT_START_AFTER_N_MINUTES = 'after_n_minutes'
    OVERTIME_START_RULE_CHOICES = [
        (OT_START_AFTER_SHIFT_END, 'After shift end'), (OT_START_AFTER_N_MINUTES, 'After N minutes worked'),
    ]
    overtime_start_rule = models.CharField(max_length=20, choices=OVERTIME_START_RULE_CHOICES, default=OT_START_AFTER_SHIFT_END)
    overtime_start_after_minutes = models.PositiveIntegerField(null=True, blank=True)

    color = models.CharField(max_length=20, blank=True)
    is_night_shift = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_shifts'
        ordering = ['start_time', 'code']

    def save(self, *args, **kwargs):
        self.crosses_midnight = self.end_time < self.start_time
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code
