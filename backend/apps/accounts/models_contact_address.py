"""
Phase 5A Tasks B+C — structured names/contact methods and country-aware
addresses. Additive: `User.phone`/`EmployeeProfile.personal_email`/the
current+permanent address columns are kept and kept in sync (Task L) —
NOT executed in this pass, see PHASE5A_REPORT.md.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ContactMethod(models.Model):
    TYPE_WORK_PHONE = 'work_phone'
    TYPE_PERSONAL_MOBILE = 'personal_mobile'
    TYPE_HOME_PHONE = 'home_phone'
    TYPE_PERSONAL_EMAIL = 'personal_email'
    TYPE_WORK_EMAIL = 'work_email'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_WORK_PHONE, 'Work phone'), (TYPE_PERSONAL_MOBILE, 'Personal mobile'),
        (TYPE_HOME_PHONE, 'Home phone'), (TYPE_PERSONAL_EMAIL, 'Personal email'),
        (TYPE_WORK_EMAIL, 'Work email'), (TYPE_OTHER, 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_methods')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    value = models.CharField(max_length=255, help_text='E.164 for phone types; lowercased for email types.')
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    effective_from = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_contact_methods'
        ordering = ['employee', 'type', '-is_primary']

    def __str__(self):
        return f'{self.employee_id}:{self.type}={self.value}'


class Address(models.Model):
    """`owner` is generic — Task C.1 explicitly lists employee, family
    member, emergency contact, and legal entity as possible owners."""
    TYPE_CURRENT = 'current'
    TYPE_PERMANENT = 'permanent'
    TYPE_MAILING = 'mailing'
    TYPE_WORK = 'work'
    TYPE_EMERGENCY = 'emergency'
    TYPE_CHOICES = [
        (TYPE_CURRENT, 'Current'), (TYPE_PERMANENT, 'Permanent'), (TYPE_MAILING, 'Mailing'),
        (TYPE_WORK, 'Work'), (TYPE_EMERGENCY, 'Emergency'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    object_id = models.CharField(max_length=64)

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    country = models.ForeignKey('platform_core.Country', on_delete=models.PROTECT, related_name='+')
    line1 = models.CharField(max_length=255, blank=True)
    line2 = models.CharField(max_length=255, blank=True)
    line3 = models.CharField(max_length=255, blank=True)
    locality = models.CharField(max_length=150, blank=True)
    village = models.CharField(max_length=150, blank=True)
    district = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=150, blank=True)
    state = models.ForeignKey('branch.State', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    state_text = models.CharField(max_length=150, blank=True, help_text='Task C.3 — kept when the stored state text does not match any Phase 1 State row (reported, never silently dropped).')
    postal_code = models.CharField(max_length=20, blank=True)
    geo = models.JSONField(null=True, blank=True, help_text='{"lat": ..., "lng": ...}, optional.')

    is_primary = models.BooleanField(default=False)
    is_same_as_current = models.BooleanField(default=False, help_text='Task C.3 — preserves permanent_same_as_current\'s "copy of current" meaning.')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_addresses'
        ordering = ['content_type', 'object_id', 'type', '-effective_from']
        indexes = [models.Index(fields=['content_type', 'object_id', 'type'], name='addr_owner_type_idx')]

    def __str__(self):
        return f'{self.content_type_id}:{self.object_id} {self.type}'
