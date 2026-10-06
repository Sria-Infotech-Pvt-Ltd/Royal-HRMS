"""Phase 2 Task G — saved list views."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from .phase1 import TimestampedModel
from .fields import EntityDefinition


class ListViewDefinition(TimestampedModel):
    VISIBILITY_SYSTEM = 'system'
    VISIBILITY_ROLE = 'role'
    VISIBILITY_PERSONAL = 'personal'
    VISIBILITY_CHOICES = [
        (VISIBILITY_SYSTEM, 'System'), (VISIBILITY_ROLE, 'Role'), (VISIBILITY_PERSONAL, 'Personal'),
    ]

    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='list_views')
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=150)

    # [{"field": code, "order": n, "width": "120px"|None, "label": override|None}]
    columns = models.JSONField(default=list, blank=True)
    default_filters = models.JSONField(default=dict, blank=True)
    default_sort = models.CharField(max_length=100, blank=True, help_text='field code, optionally "-field" for descending.')

    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_SYSTEM)
    role = models.ForeignKey('accounts.Role', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_list_view_definitions'
        ordering = ['entity', 'name']

    def __str__(self):
        return f'{self.entity_id}:{self.code}'
