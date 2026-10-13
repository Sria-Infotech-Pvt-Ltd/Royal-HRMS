"""Phase 8B gap-closure tests — synonym resolution, generic entity capabilities (self-scoped), speech provider registration."""
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.voice_commands.models import GenericEntityVoiceCapability, VoiceSynonym
from apps.voice_commands.services_voice_gaps import (
    enable_entity_capability, get_active_speech_provider, is_entity_capability_enabled,
    list_entity_records, resolve_synonym, seed_current_speech_provider,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class SynonymResolutionTests(TestCase):
    def test_registered_synonym_resolves(self):
        VoiceSynonym.objects.create(domain='leave_type', spoken_phrase='PTO', resolves_to_code='ANNUAL_LEAVE')
        self.assertEqual(resolve_synonym('leave_type', 'PTO'), 'ANNUAL_LEAVE')
        self.assertEqual(resolve_synonym('leave_type', 'pto'), 'ANNUAL_LEAVE')  # case-insensitive

    def test_unregistered_phrase_passes_through_unchanged(self):
        self.assertEqual(resolve_synonym('leave_type', 'Sick Leave'), 'Sick Leave')


class GenericEntityCapabilityTests(TestCase):
    def _make_entity(self):
        from apps.platform_core.models.fields import EntityDefinition
        return EntityDefinition.objects.create(code=_unique('entity'), label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM)

    def test_disabled_capability_blocks_listing(self):
        entity = self._make_entity()
        employee = _make_employee()
        with self.assertRaises(PermissionError):
            list_entity_records(entity, employee)

    def test_enabled_capability_lists_only_own_records(self):
        entity = self._make_entity()
        employee = _make_employee()
        other = _make_employee()
        enable_entity_capability(entity, GenericEntityVoiceCapability.ACTION_LIST)
        self.assertTrue(is_entity_capability_enabled(entity, GenericEntityVoiceCapability.ACTION_LIST))

        from apps.platform_core.models.custom_objects import CustomRecord
        CustomRecord.objects.create(entity=entity, owner=employee, data={'reg': 'KA01AB1234'})
        CustomRecord.objects.create(entity=entity, owner=other, data={'reg': 'KA02XY5678'})

        records = list_entity_records(entity, employee)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].owner_id, employee.id)


class SpeechProviderTests(TestCase):
    def test_seed_registers_sarvam_as_active(self):
        seed_current_speech_provider()
        provider = get_active_speech_provider()
        self.assertEqual(provider.code, 'sarvam')
        self.assertIn('en', provider.supported_language_codes)
