"""Phase 2 Task D — form layouts (generalises OnboardingFieldConfig's
step/order/visible/required shape into a reusable, versioned structure).

Stored as normalised tables (Step -> Section -> FieldPlacement), not one
big JSON blob, per the Master Prompt's own instruction — so ordering and
field references are real FKs the database validates, not strings that
can silently point at nothing.
"""
from __future__ import annotations

from django.db import models

from .phase1 import LegalEntity, TimestampedModel
from .fields import EntityDefinition, FieldDefinition


class FormLayout(TimestampedModel):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published')]

    # Extensible by design (Task D.1) — new contexts just need a new
    # string here and whatever frontend route consumes resolve_layout()
    # for it; nothing else in this model needs to change.
    CONTEXT_ONBOARDING = 'onboarding'
    CONTEXT_HIRE_WIZARD = 'hire_wizard'
    CONTEXT_PROFILE_SELF = 'profile_self'
    CONTEXT_PROFILE_HR = 'profile_hr'
    CONTEXT_EMPLOYEE_DETAIL = 'employee_detail'
    CONTEXT_CANDIDATE_FORM = 'candidate_form'
    CONTEXT_CUSTOM_CREATE = 'custom_create'
    CONTEXT_CUSTOM_EDIT = 'custom_edit'
    CONTEXT_CUSTOM_VIEW = 'custom_view'
    CONTEXT_CHOICES = [
        (CONTEXT_ONBOARDING, 'Onboarding'), (CONTEXT_HIRE_WIZARD, 'Hire wizard'),
        (CONTEXT_PROFILE_SELF, 'Profile (self)'), (CONTEXT_PROFILE_HR, 'Profile (HR)'),
        (CONTEXT_EMPLOYEE_DETAIL, 'Employee detail'), (CONTEXT_CANDIDATE_FORM, 'Candidate form'),
        (CONTEXT_CUSTOM_CREATE, 'Custom — create'), (CONTEXT_CUSTOM_EDIT, 'Custom — edit'), (CONTEXT_CUSTOM_VIEW, 'Custom — view'),
    ]

    code = models.CharField(max_length=100)
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='layouts')
    context = models.CharField(max_length=30, choices=CONTEXT_CHOICES)
    name = models.CharField(max_length=150)

    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    country = models.ForeignKey('platform_core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    employment_type = models.CharField(max_length=50, blank=True)

    # Highest priority wins when more than one published layout matches
    # the same (entity, context) for a given record — see
    # services_forms.resolve_layout().
    priority = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'platform_form_layouts'
        ordering = ['entity', 'context', '-priority']

    def __str__(self):
        return f'{self.entity_id}/{self.context}/{self.code} v{self.version}'


class FormStep(TimestampedModel):
    layout = models.ForeignKey(FormLayout, on_delete=models.CASCADE, related_name='steps')
    label = models.CharField(max_length=150)
    icon = models.CharField(max_length=50, blank=True)
    order = models.PositiveIntegerField(default=0)
    # Declarative condition JSON — see services_conditions.py. Never code.
    visible_when = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'platform_form_steps'
        ordering = ['layout', 'order']

    def __str__(self):
        return f'{self.layout_id}:{self.label}'


class FormSection(TimestampedModel):
    step = models.ForeignKey(FormStep, on_delete=models.CASCADE, related_name='sections')
    label = models.CharField(max_length=150)
    order = models.PositiveIntegerField(default=0)
    columns = models.PositiveSmallIntegerField(default=1)
    collapsible = models.BooleanField(default=False)
    visible_when = models.JSONField(default=dict, blank=True)

    # Repeating sections (education/experience/family/documents-style
    # lists) are bound to a CHILD entity, not inline JSON — reuses the
    # same custom-object child-relationship machinery Task E already
    # provides, rather than inventing a second repeating-list concept.
    repeats_for_entity = models.ForeignKey(EntityDefinition, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'platform_form_sections'
        ordering = ['step', 'order']

    def __str__(self):
        return f'{self.step_id}:{self.label}'


class FormFieldPlacement(TimestampedModel):
    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name='placements')
    field = models.ForeignKey(FieldDefinition, on_delete=models.CASCADE, related_name='placements')
    order = models.PositiveIntegerField(default=0)
    column_span = models.PositiveSmallIntegerField(default=1)
    read_only = models.BooleanField(default=False)
    visible_when = models.JSONField(default=dict, blank=True)
    required_when = models.JSONField(default=dict, blank=True)
    label_override = models.CharField(max_length=150, blank=True)
    help_override = models.CharField(max_length=255, blank=True)

    # Presentation only — NOT security. The server still enforces the
    # existing permission system on every read/write regardless of what
    # this restricts to in the UI. See FieldPlacementRoleRestriction and
    # PHASE2_REPORT.md's "Risks" section.
    restricted_to_roles = models.ManyToManyField('accounts.Role', blank=True, related_name='+')

    class Meta:
        db_table = 'platform_form_field_placements'
        ordering = ['section', 'order']
        constraints = [
            models.UniqueConstraint(fields=['section', 'field'], name='uniq_field_per_section'),
        ]

    def __str__(self):
        return f'{self.section_id}:{self.field_id}'
