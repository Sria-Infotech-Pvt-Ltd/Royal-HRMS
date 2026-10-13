"""Phase 8B gap-closure — synonym resolution, generic custom-entity capabilities (list/create/status), provider config lookup."""
from django.conf import settings

from apps.voice_commands.models import GenericEntityVoiceCapability, VoiceSpeechProvider, VoiceSynonym


def resolve_synonym(domain: str, spoken_phrase: str, language_code: str = 'en') -> str:
    """Returns the real code a spoken phrase resolves to, or the original
    phrase unchanged if no synonym is registered (never guesses)."""
    match = VoiceSynonym.objects.filter(domain=domain, spoken_phrase__iexact=spoken_phrase, language_code=language_code).first()
    return match.resolves_to_code if match else spoken_phrase


def enable_entity_capability(entity, action: str) -> GenericEntityVoiceCapability:
    capability, _ = GenericEntityVoiceCapability.objects.update_or_create(
        entity=entity, action=action, defaults={'is_enabled': True},
    )
    return capability


def is_entity_capability_enabled(entity, action: str) -> bool:
    return GenericEntityVoiceCapability.objects.filter(entity=entity, action=action, is_enabled=True).exists()


def list_entity_records(entity, user, *, field_security_filter=None):
    """"Show my <custom entity> records" — scoped to `user`'s own records
    (the generic capability is always self-scoped, never another
    employee's data) and, if the caller supplies one, passed through a
    field-security filter before returning (never bypasses Phase 4
    masking) — matches the master prompt's own "with field security"
    requirement for this capability."""
    if not is_entity_capability_enabled(entity, GenericEntityVoiceCapability.ACTION_LIST):
        raise PermissionError(f'Voice listing is not enabled for entity {entity.code}.')
    from apps.platform_core.models.custom_objects import CustomRecord
    records = CustomRecord.objects.filter(entity=entity, owner=user, is_deleted=False)
    if field_security_filter is not None:
        records = [field_security_filter(r) for r in records]
    return records


def get_active_speech_provider() -> VoiceSpeechProvider | None:
    return VoiceSpeechProvider.objects.filter(is_active=True).first()


def seed_current_speech_provider() -> VoiceSpeechProvider:
    """Registers the CURRENT provider (Sarvam) as data — preserves it, no
    new provider is added."""
    provider, _ = VoiceSpeechProvider.objects.update_or_create(
        code='sarvam',
        defaults={
            'name': 'Sarvam AI', 'supported_language_codes': ['en', 'hi'],
            'config_key_reference': 'SARVAM_API_KEY', 'is_active': True,
        },
    )
    return provider
