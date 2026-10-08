"""
Phase 6B Task F — multiple geofences per branch/legal entity. Additive:
`GeofencingService` (services_geofencing.py) is completely untouched —
still reads `Branch.latitude`/`longitude`/`allowed_radius_meters`/
`geofencing_enabled` directly, exactly as before. `services_geofence_v2.py`
proves the new `Geofence` model's circle validation produces IDENTICAL
results to the existing branch-based check (parity test), but nothing
calls it from the real punch-validation path yet.
"""
from __future__ import annotations

import uuid

from django.db import models


class Geofence(models.Model):
    TYPE_CIRCLE = 'circle'
    TYPE_POLYGON = 'polygon'
    TYPE_CHOICES = [(TYPE_CIRCLE, 'Circle'), (TYPE_POLYGON, 'Polygon')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_CIRCLE)

    branch = models.ForeignKey('branch.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='geofences')
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    center_latitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    center_longitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    radius_meters = models.PositiveIntegerField(null=True, blank=True)
    polygon_points = models.JSONField(null=True, blank=True, help_text='[[lat, lng], ...] — only for type=polygon.')

    allowed_modes = models.JSONField(default=list, blank=True, help_text='Attendance modes this geofence is valid for; [] = all.')
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_geofences'
        ordering = ['code']

    def __str__(self):
        return self.code
