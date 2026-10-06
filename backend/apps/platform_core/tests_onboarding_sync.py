"""Phase 2 Task J — parity tests between the legacy onboarding config
(source of truth, unchanged) and its forms.v2 mirror. Confirms the
write-through signal fires on save, dropdown options become a lookup
type with legacy values preserved, and the resolved layout describes
the same fields/order/required-ness as the legacy config — not a
byte-for-byte JSON comparison (the shapes are deliberately different),
but the same facts about each field."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.models import OnboardingFieldConfig, OnboardingSection
from apps.platform_core import services_forms, services_onboarding_sync
from apps.platform_core.models import EntityDefinition, FieldDefinition, FormLayout


class OnboardingMirrorParityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.employee_entity = EntityDefinition.objects.get(code='employee')

    def test_custom_field_config_save_mirrors_a_field_definition(self):
        config = OnboardingFieldConfig.objects.create(
            field_key='favourite_color', label='Favourite Colour', field_type=OnboardingFieldConfig.TYPE_TEXT,
            step=OnboardingFieldConfig.STEP_PERSONAL, order=5, visible=True, required=True, is_custom=True,
        )
        field_def = FieldDefinition.objects.get(entity=self.employee_entity, code='favourite_color')
        self.assertEqual(field_def.label, 'Favourite Colour')
        self.assertTrue(field_def.required)
        self.assertEqual(field_def.data_type, 'text')

    def test_core_field_config_is_not_mirrored(self):
        OnboardingFieldConfig.objects.create(
            field_key='full_name', label='Full Name', field_type=OnboardingFieldConfig.TYPE_TEXT,
            step=OnboardingFieldConfig.STEP_PERSONAL, is_custom=False,
        )
        self.assertFalse(FieldDefinition.objects.filter(entity=self.employee_entity, code='full_name').exists())

    def test_dropdown_options_become_lookup_values_with_legacy_value_preserved(self):
        config = OnboardingFieldConfig.objects.create(
            field_key='t_shirt_size', label='T-Shirt Size', field_type=OnboardingFieldConfig.TYPE_DROPDOWN,
            options=['Small', 'Medium', 'Large'], step=OnboardingFieldConfig.STEP_PERSONAL, is_custom=True,
        )
        field_def = FieldDefinition.objects.get(entity=self.employee_entity, code='t_shirt_size')
        self.assertEqual(field_def.data_type, 'lookup')
        self.assertIsNotNone(field_def.lookup_type)

        values = list(field_def.lookup_type.values.all())
        self.assertEqual(len(values), 3)
        legacy_values = {v.attributes.get('legacy_value') for v in values}
        self.assertEqual(legacy_values, {'Small', 'Medium', 'Large'})

    def test_resync_is_idempotent_no_duplicate_lookup_values(self):
        config = OnboardingFieldConfig.objects.create(
            field_key='t_shirt_size', label='T-Shirt Size', field_type=OnboardingFieldConfig.TYPE_DROPDOWN,
            options=['Small', 'Medium'], step=OnboardingFieldConfig.STEP_PERSONAL, is_custom=True,
        )
        services_onboarding_sync.sync_field_config(config)
        services_onboarding_sync.sync_field_config(config)
        field_def = FieldDefinition.objects.get(entity=self.employee_entity, code='t_shirt_size')
        self.assertEqual(field_def.lookup_type.values.count(), 2)

    def test_hidden_field_has_no_placement_in_resolved_layout(self):
        OnboardingFieldConfig.objects.create(
            field_key='secret_note', label='Secret Note', field_type=OnboardingFieldConfig.TYPE_TEXT,
            step=OnboardingFieldConfig.STEP_PERSONAL, visible=False, is_custom=True,
        )
        layout = services_forms.resolve_layout(self.employee_entity, FormLayout.CONTEXT_ONBOARDING)
        placed_codes = {p['field_code'] for step in layout['steps'] for section in step['sections'] for p in section['placements']}
        self.assertNotIn('secret_note', placed_codes)

    def test_visible_required_field_appears_in_resolved_layout_matching_legacy_config(self):
        config = OnboardingFieldConfig.objects.create(
            field_key='emergency_note', label='Emergency Note', field_type=OnboardingFieldConfig.TYPE_TEXTAREA,
            step=OnboardingFieldConfig.STEP_EMERGENCY, order=2, visible=True, required=True, is_custom=True,
        )
        layout = services_forms.resolve_layout(self.employee_entity, FormLayout.CONTEXT_ONBOARDING)
        placements = [p for step in layout['steps'] for section in step['sections'] for p in section['placements'] if p['field_code'] == 'emergency_note']
        self.assertEqual(len(placements), 1)
        self.assertTrue(placements[0]['required'])
        self.assertEqual(placements[0]['data_type'], 'long_text')

    def test_hr_created_section_mirrors_as_a_form_step(self):
        section = OnboardingSection.objects.create(step=5, label='Custom HR Step', icon='ti-star', order=0)
        layout = services_onboarding_sync.get_or_create_onboarding_layout()
        step = layout.steps.filter(order=5).first()
        self.assertIsNotNone(step)
        self.assertEqual(step.label, 'Custom HR Step')

    def test_backfill_all_is_idempotent(self):
        OnboardingFieldConfig.objects.create(
            field_key='backfill_field', label='Backfill Field', field_type=OnboardingFieldConfig.TYPE_TEXT,
            step=OnboardingFieldConfig.STEP_PERSONAL, is_custom=True,
        )
        result1 = services_onboarding_sync.backfill_all()
        result2 = services_onboarding_sync.backfill_all()
        self.assertEqual(result1['fields_synced'], result2['fields_synced'])
