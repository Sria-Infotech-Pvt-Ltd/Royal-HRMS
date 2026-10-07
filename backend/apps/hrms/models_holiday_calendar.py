"""
Phase 6A Task H — holiday calendars, additive alongside the existing
`Holiday` model (branch-scoped, no year/calendar concept). Nothing reads
from these new models yet except `services_holiday_calendar.py`'s own
functions, which are opt-in — the existing `HolidayCacheService` (used by
leave validation's working-days calculation) is completely untouched.
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.hrms.models import HOLIDAY_TYPE_CHOICES


class HolidayCalendar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    year = models.PositiveIntegerField()
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    country = models.ForeignKey('platform_core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    description = models.TextField(blank=True)
    optional_holiday_quota = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_holiday_calendars'
        constraints = [models.UniqueConstraint(fields=['code', 'year'], name='uniq_holiday_calendar_code_per_year')]
        ordering = ['-year', 'code']

    def __str__(self):
        return f'{self.code} ({self.year})'


class HolidayCalendarEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=200)
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPE_CHOICES, default='national')
    is_optional = models.BooleanField(default=False)
    is_half_day = models.BooleanField(default=False)
    region = models.CharField(max_length=100, blank=True, help_text='State/region text — Phase 1 State FK not wired in this pass.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_holiday_calendar_entries'
        ordering = ['date']
        constraints = [models.UniqueConstraint(fields=['calendar', 'date', 'name'], name='uniq_holiday_calendar_entry')]

    def __str__(self):
        return f'{self.calendar_id}:{self.date} {self.name}'


class HolidayCalendarAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar = models.ForeignKey(HolidayCalendar, on_delete=models.CASCADE, related_name='assignments')
    branch = models.ForeignKey('branch.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='+', help_text='null = company-wide, mirroring Holiday.branch\'s own null-means-company-wide convention.')
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_holiday_calendar_assignments'
        ordering = ['-effective_from']

    def __str__(self):
        return f'{self.calendar_id} -> {self.branch_id or "company-wide"}'
