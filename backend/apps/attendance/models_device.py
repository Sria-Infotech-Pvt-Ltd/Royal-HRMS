"""
Phase 6B Task E — the device registry and push endpoint backing. No
`AttendanceDevice`-like model existed before this (Explore confirmed:
biometric support was limited to `AttendancePunch.source='biometric'`
and a free-text `device_id`, with no pairing/registration table).

API authentication for the push endpoint uses a per-device secret key
(`api_key`, a random token) checked by the view itself — a full Phase 4
scoped API-key object (with its own permission-scope model) was not
built in this pass; see PHASE6B_REPORT.md's Task E notes for this
simplification.
"""
from __future__ import annotations

import secrets
import uuid

from django.db import models


def _generate_api_key() -> str:
    return secrets.token_urlsafe(32)


class AttendanceDevice(models.Model):
    TYPE_BIOMETRIC = 'biometric'
    TYPE_KIOSK = 'kiosk'
    TYPE_MOBILE_APP = 'mobile_app'
    TYPE_CHOICES = [(TYPE_BIOMETRIC, 'Biometric'), (TYPE_KIOSK, 'Kiosk'), (TYPE_MOBILE_APP, 'Mobile app')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_BIOMETRIC)
    branch = models.ForeignKey('branch.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    serial = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    api_key = models.CharField(max_length=64, unique=True, default=_generate_api_key)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_devices'
        ordering = ['code']

    def __str__(self):
        return self.code


class DevicePunchLog(models.Model):
    """One row per (device, device_punch_id) pair pushed — the idempotency
    key (Task E.3: 'idempotency (device_id + device punch id)'). Points at
    the real `AttendancePunch` it resulted in, or null if the row was
    rejected (unknown employee, duplicate)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(AttendanceDevice, on_delete=models.CASCADE, related_name='punch_logs')
    device_punch_id = models.CharField(max_length=100)
    employee_code_raw = models.CharField(max_length=50, help_text='The employee code as sent by the device, before lookup.')
    punch = models.ForeignKey('attendance.AttendancePunch', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    status = models.CharField(max_length=20, choices=[('accepted', 'Accepted'), ('rejected', 'Rejected'), ('duplicate', 'Duplicate')])
    reject_reason = models.CharField(max_length=255, blank=True)
    device_time = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    clock_skew_seconds = models.IntegerField(null=True, blank=True, help_text='received_at - device_time, in seconds.')

    class Meta:
        db_table = 'attendance_device_punch_logs'
        constraints = [models.UniqueConstraint(fields=['device', 'device_punch_id'], name='uniq_device_punch_id')]
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.device_id}:{self.device_punch_id} ({self.status})'
