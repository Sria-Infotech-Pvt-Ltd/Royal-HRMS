from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.platform_core import services_forms as forms
from apps.platform_core.models import EntityDefinition, FieldDefinition, FormFieldPlacement, FormLayout, FormSection, FormStep


class ResolveLayoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.get(code='branch')
        self.field = FieldDefinition.objects.create(
            entity=self.entity, code='fleet_tag', label='Fleet Tag', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, required=True,
        )

    def _build_layout(self, **kwargs):
        layout = FormLayout.objects.create(
            code='default', entity=self.entity, context=FormLayout.CONTEXT_CUSTOM_EDIT,
            name='Default', status=FormLayout.STATUS_PUBLISHED, **kwargs,
        )
        step = FormStep.objects.create(layout=layout, label='Details', order=0)
        section = FormSection.objects.create(step=step, label='Main', order=0)
        FormFieldPlacement.objects.create(section=section, field=self.field, order=0)
        return layout

    def test_resolve_layout_returns_none_when_no_published_layout(self):
        result = forms.resolve_layout(self.entity, FormLayout.CONTEXT_CUSTOM_EDIT)
        self.assertIsNone(result)

    def test_resolve_layout_returns_serialized_structure(self):
        self._build_layout()
        result = forms.resolve_layout(self.entity, FormLayout.CONTEXT_CUSTOM_EDIT)
        self.assertEqual(result['steps'][0]['sections'][0]['placements'][0]['field_code'], 'fleet_tag')

    def test_higher_priority_layout_wins(self):
        self._build_layout(priority=0)
        high = self._build_layout(priority=10)
        high.code = 'override'
        high.save()
        result = forms.resolve_layout(self.entity, FormLayout.CONTEXT_CUSTOM_EDIT)
        self.assertEqual(result['layout_code'], 'override')

    def test_validate_submission_flags_missing_required_field(self):
        self._build_layout()
        errors = forms.validate_submission(self.entity, FormLayout.CONTEXT_CUSTOM_EDIT, {})
        self.assertIn('fleet_tag', errors)

    def test_validate_submission_passes_with_value(self):
        self._build_layout()
        errors = forms.validate_submission(self.entity, FormLayout.CONTEXT_CUSTOM_EDIT, {'fleet_tag': 'ABC'})
        self.assertEqual(errors, {})
