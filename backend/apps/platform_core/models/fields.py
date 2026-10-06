"""
Phase 2 Tasks A/B/C — entity registry, field definitions, and the
uniqueness side-table for custom attribute values. See PHASE2_REPORT.md
for the full design rationale (especially the employee entity spanning
User + EmployeeProfile, and why attributes storage is NOT added here as
new JSONB columns on every core table sight-unseen).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .phase1 import LegalEntity, LookupType, TimestampedModel


class EntityDefinition(TimestampedModel):
    KIND_CORE = 'core'
    KIND_CUSTOM = 'custom'
    KIND_CHOICES = [(KIND_CORE, 'Core'), (KIND_CUSTOM, 'Custom')]

    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published'), (STATUS_ARCHIVED, 'Archived')]

    code = models.CharField(max_length=64, unique=True, help_text='lower_snake, immutable once published.')
    label = models.CharField(max_length=150)
    plural_label = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    module = models.CharField(max_length=50, blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)

    # Core entities only — which real Django model backs this entity, and
    # which of its fields already hold admin-added custom values.
    app_label = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    attributes_column = models.CharField(
        max_length=100, blank=True,
        help_text='Name of the JSONB column holding custom attribute values for this entity.',
    )

    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    has_attachments = models.BooleanField(default=True)
    history_enabled = models.BooleanField(default=True)

    number_series = models.ForeignKey('platform_core.NumberSeries', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    # Plain {token} substitution ONLY — never evaluated as code. See
    # services_custom_objects.render_title().
    title_template = models.CharField(max_length=255, blank=True)

    parent_entity = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_entities')
    owner_field = models.CharField(max_length=64, blank=True, default='owner')
    legal_entity_scoped = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'platform_entity_definitions'
        ordering = ['module', 'label']

    def __str__(self):
        return self.code


_DATA_TYPE_CHOICES = [
    ('text', 'Text'), ('long_text', 'Long text'), ('rich_text', 'Rich text'),
    ('integer', 'Integer'), ('decimal', 'Decimal'), ('currency_amount', 'Currency amount'), ('percentage', 'Percentage'),
    ('boolean', 'Boolean'), ('date', 'Date'), ('datetime', 'Date & time'), ('time', 'Time'), ('duration', 'Duration'),
    ('email', 'Email'), ('phone', 'Phone'), ('url', 'URL'),
    ('lookup', 'Lookup'), ('reference', 'Reference'), ('user_reference', 'User reference'),
    ('file', 'File'), ('image', 'Image'), ('geo_point', 'Geo point'), ('json', 'JSON (admin only)'),
]


class FieldDefinition(TimestampedModel):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published'), (STATUS_ARCHIVED, 'Archived')]

    UNIQUE_SCOPE_GLOBAL = 'global'
    UNIQUE_SCOPE_LEGAL_ENTITY = 'legal_entity'
    UNIQUE_SCOPE_PARENT = 'parent_record'
    UNIQUE_SCOPE_CHOICES = [
        (UNIQUE_SCOPE_GLOBAL, 'Global'), (UNIQUE_SCOPE_LEGAL_ENTITY, 'Per legal entity'), (UNIQUE_SCOPE_PARENT, 'Per parent record'),
    ]

    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='fields')
    code = models.CharField(max_length=64, help_text='lower_snake, unique per entity, immutable after publish.')
    label = models.CharField(max_length=150)
    help_text = models.CharField(max_length=255, blank=True)
    placeholder = models.CharField(max_length=150, blank=True)

    data_type = models.CharField(max_length=20, choices=_DATA_TYPE_CHOICES)
    is_core = models.BooleanField(default=False, help_text='Maps to a real model column — definition is auto-generated and type-locked.')
    is_system = models.BooleanField(default=False)

    required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    multiple = models.BooleanField(default=False)
    lookup_type = models.ForeignKey(LookupType, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    reference_entity = models.ForeignKey(EntityDefinition, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    validation = models.JSONField(default=dict, blank=True)

    is_sensitive = models.BooleanField(default=False)
    pii_category = models.CharField(max_length=64, blank=True)
    is_unique = models.BooleanField(default=False)
    unique_scope = models.CharField(max_length=20, choices=UNIQUE_SCOPE_CHOICES, default=UNIQUE_SCOPE_GLOBAL)
    is_searchable = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=False)
    is_sortable = models.BooleanField(default=False)
    is_exportable = models.BooleanField(default=True)
    is_importable = models.BooleanField(default=True)

    applicability = models.JSONField(default=dict, blank=True, help_text='{"countries": [...], "legal_entities": [...], "employment_types": [...]} — empty = all.')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    version = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'platform_field_definitions'
        ordering = ['entity', 'order']
        constraints = [
            models.UniqueConstraint(fields=['entity', 'code'], name='uniq_field_code_per_entity'),
        ]

    def __str__(self):
        return f'{self.entity_id}.{self.code}'

    def clean(self):
        from django.core.exceptions import ValidationError
        # Sensitive fields can't be filterable/sortable/searchable — a
        # filter/sort on an encrypted token is meaningless, and a sensitive
        # value appearing in a search-indexed column defeats the point of
        # marking it sensitive at all.
        if self.is_sensitive and (self.is_filterable or self.is_sortable or self.is_searchable):
            raise ValidationError('A sensitive field cannot be filterable, sortable, or searchable.')


class FieldValueUniqueness(models.Model):
    """Side table enforcing FieldDefinition.is_unique — no dynamic DB
    indexes (Master Prompt rule: no runtime DDL). `scope_key` encodes the
    uniqueness scope (empty string for global, a legal_entity id, or a
    parent record id) so the same (entity, field, scope_key, value_hash)
    triple can never collide."""
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='+')
    field = models.ForeignKey(FieldDefinition, on_delete=models.CASCADE, related_name='+')
    scope_key = models.CharField(max_length=100, blank=True)
    value_hash = models.CharField(max_length=64, db_index=True)
    record_id = models.CharField(max_length=64)

    class Meta:
        db_table = 'platform_field_value_uniqueness'
        constraints = [
            models.UniqueConstraint(fields=['entity', 'field', 'scope_key', 'value_hash'], name='uniq_field_value_per_scope'),
        ]

    def __str__(self):
        return f'{self.field_id}:{self.scope_key}:{self.value_hash[:8]}'
