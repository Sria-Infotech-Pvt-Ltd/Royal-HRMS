"""
Phase 2 Task J — mirrors the EXISTING onboarding configuration
(OnboardingFieldConfig/OnboardingSection) onto the new field/form engine,
behind feature flag `forms.v2` (default OFF). The old tables/endpoints
remain the source of truth while the flag is off; this module is a
write-through mirror, called from signal handlers on every save AND
available as a one-shot backfill command for data that already existed
before this phase.

Scope cut, stated plainly (see PHASE2_REPORT.md for the full reasoning):
only `OnboardingFieldConfig` (is_custom=True rows — core/locked fields
are already real model columns and don't need a FieldDefinition) and
`OnboardingSection` are mirrored. `EducationExperienceFieldConfig`-driven
repeating sections and the `DocumentTypeConfig`-driven documents section
are NOT mirrored in this pass — both would need a dedicated
EntityDefinition for education/experience/document records, which Task A
deliberately did not register (that's module-phase work, explicitly out
of this phase's registered-entity list: employee, branch, org_unit,
position, legal_entity, candidate). Building FormSection.repeats_for_entity
against a nonexistent entity would be worse than not building it.
"""
from __future__ import annotations

import re

from apps.platform_core.models import (
    EntityDefinition, FieldDefinition, FormFieldPlacement, FormLayout, FormSection, FormStep, LookupType, LookupValue,
)

ONBOARDING_LAYOUT_CODE = 'onboarding_v2_mirror'

_FIELD_TYPE_MAP = {
    'text': 'text', 'textarea': 'long_text', 'number': 'decimal', 'date': 'date',
    'dropdown': 'lookup', 'checkbox': 'boolean', 'file': 'file',
}

_STEP_LABELS = {0: 'Personal Information', 1: 'Education & Experience', 2: 'Bank Details', 3: 'Emergency Contact'}


def _employee_entity() -> EntityDefinition:
    return EntityDefinition.objects.get(code='employee')


def get_or_create_onboarding_layout() -> FormLayout:
    layout, _ = FormLayout.objects.get_or_create(
        code=ONBOARDING_LAYOUT_CODE, entity=_employee_entity(), context=FormLayout.CONTEXT_ONBOARDING,
        defaults={'name': 'Onboarding (mirrored from legacy config)', 'status': FormLayout.STATUS_PUBLISHED},
    )
    return layout


def _get_or_create_step(layout: FormLayout, step_number: int, label: str, icon: str = '') -> FormStep:
    step, created = FormStep.objects.get_or_create(
        layout=layout, order=step_number, defaults={'label': label, 'icon': icon},
    )
    if not created and step.label != label:
        step.label = label
        step.save(update_fields=['label'])
    return step


def _get_or_create_default_section(step: FormStep) -> FormSection:
    section, _ = FormSection.objects.get_or_create(step=step, order=0, defaults={'label': step.label})
    return section


def sync_section(section) -> FormStep:
    """`section` is an apps.accounts.models.OnboardingSection instance —
    HR-created steps 5+. Mirrors 1:1 as a FormStep."""
    layout = get_or_create_onboarding_layout()
    return _get_or_create_step(layout, section.step, section.label, section.icon)


def _auto_lookup_type_for_dropdown(field_key: str, options: list[str]) -> LookupType:
    """Task J.1's "inline dropdown options become auto-created lookup
    types" rule — one LookupType per legacy dropdown field, codes
    generated from the option text, with the ORIGINAL text preserved in
    `legacy_value` so values already stored in custom_field_values (which
    hold the raw option text, not a generated code) still resolve.
    Idempotent: re-running does not create duplicate values for options
    already seeded."""
    lookup_code = f'onboarding_{field_key}'
    lookup_type, _ = LookupType.objects.get_or_create(
        code=lookup_code, defaults={'name': f'Onboarding: {field_key}', 'is_system': False},
    )
    existing_legacy_values = set(
        LookupValue.objects.filter(lookup_type=lookup_type).values_list('attributes__legacy_value', flat=True)
    )
    for order, option_text in enumerate(options):
        if option_text in existing_legacy_values:
            continue
        code = re.sub(r'[^A-Z0-9]+', '_', option_text.upper()).strip('_') or f'OPTION_{order}'
        # Guard against two different option texts slugifying to the same
        # code (e.g. "N/A" and "NA") — append a numeric suffix rather than
        # silently colliding and losing one option.
        base_code, suffix = code, 1
        while LookupValue.objects.filter(lookup_type=lookup_type, code=code).exists():
            suffix += 1
            code = f'{base_code}_{suffix}'
        LookupValue.objects.create(
            lookup_type=lookup_type, code=code, label=option_text, sort_order=order,
            attributes={'legacy_value': option_text},
        )
    return lookup_type


def sync_field_config(config) -> FieldDefinition | None:
    """`config` is an apps.accounts.models.OnboardingFieldConfig instance.
    Returns None for non-custom (core/locked) rows — those map to real
    model columns already and get no FieldDefinition in this phase."""
    if not config.is_custom:
        return None

    entity = _employee_entity()
    data_type = _FIELD_TYPE_MAP.get(config.field_type, 'text')
    lookup_type = None
    if config.field_type == OnboardingFieldConfigLike.TYPE_DROPDOWN and config.options:
        lookup_type = _auto_lookup_type_for_dropdown(config.field_key, config.options)

    field_def, _ = FieldDefinition.objects.get_or_create(
        entity=entity, code=config.field_key,
        defaults={
            'label': config.label, 'data_type': data_type, 'required': config.required,
            'multiple': config.allow_multiple, 'lookup_type': lookup_type,
            'status': FieldDefinition.STATUS_PUBLISHED, 'order': config.order,
        },
    )
    # Update mutable presentation attributes every sync (write-through) —
    # code/data_type are NOT changed after creation (Task B.5: immutable
    # after publish), only label/required/order/lookup_type track the
    # live config.
    changed = []
    if field_def.label != config.label:
        field_def.label = config.label
        changed.append('label')
    if field_def.required != config.required:
        field_def.required = config.required
        changed.append('required')
    if field_def.order != config.order:
        field_def.order = config.order
        changed.append('order')
    if lookup_type is not None and field_def.lookup_type_id != lookup_type.pk:
        field_def.lookup_type = lookup_type
        changed.append('lookup_type')
    if changed:
        field_def.save(update_fields=changed)

    layout = get_or_create_onboarding_layout()
    step_label = _STEP_LABELS.get(config.step)
    if step_label is None:
        from apps.accounts.models import OnboardingSection
        section_row = OnboardingSection.objects.filter(step=config.step).first()
        step_label = section_row.label if section_row else f'Step {config.step}'
    step = _get_or_create_step(layout, config.step, step_label)
    section = _get_or_create_default_section(step)

    if config.visible:
        FormFieldPlacement.objects.get_or_create(section=section, field=field_def, defaults={'order': config.order})
    else:
        # Mirrors "hidden" by absence rather than a placement with a
        # permanently-false visible_when — matches what the old system
        # actually does (the field is not shown at all), and keeps
        # FormFieldPlacement's visible_when reserved for genuine
        # conditional visibility, not a static on/off flag.
        FormFieldPlacement.objects.filter(section=section, field=field_def).delete()

    return field_def


class OnboardingFieldConfigLike:
    """Avoids a hard import-time dependency from platform_core on
    apps.accounts at module load (apps.accounts imports platform_core
    indirectly via the entity registry) — only TYPE_DROPDOWN's string
    value is needed here, and it's a stable constant."""
    TYPE_DROPDOWN = 'dropdown'


def backfill_all() -> dict:
    """One-shot sync of every existing OnboardingFieldConfig/OnboardingSection
    row — for data that already existed before this phase. Safe to
    re-run (every operation above is get_or_create/idempotent update)."""
    from apps.accounts.models import OnboardingFieldConfig, OnboardingSection

    for section in OnboardingSection.objects.filter(is_active=True):
        sync_section(section)

    synced = 0
    for config in OnboardingFieldConfig.objects.all():
        if sync_field_config(config) is not None:
            synced += 1

    return {'sections_synced': OnboardingSection.objects.filter(is_active=True).count(), 'fields_synced': synced}
