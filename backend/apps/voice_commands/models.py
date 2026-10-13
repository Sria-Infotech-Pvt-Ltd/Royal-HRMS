"""
Phase 8B Task G — the voice capability registry. This app had NO models at
all before this pass (confirmed: no models.py, no migrations/ directory) —
every intent/executor was pure code. `VoiceCapability` is a real,
queryable catalogue of what the voice assistant can do, registered
alongside (not replacing) the existing executors — see
services_capability_registry.py for the registration call and the safety
invariant it enforces: a capability's `service_function_path` and
`required_permission_codename` are checked by that service, every single
call, exactly the way a real API endpoint would be — never a shortcut
around Phase 4 permissions.

Scoped down: no generic custom-entity capabilities (Task G.3), no
synonym-mapping lookups (Task G.2's last item), no provider-abstraction
model (Task G.5 — the current Sarvam integration is config/code, not data,
and stays that way this pass).
"""
import uuid

from django.db import models


class VoiceCapability(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intent_code = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=300)
    # {"en": ["mark my attendance", "clock me in"], "hi": [...]}
    example_phrases = models.JSONField(default=dict, blank=True)
    # [{"name": "leave_type", "type": "text", "required": True}, ...] — typed slots.
    required_slots = models.JSONField(default=list, blank=True)
    service_function_path = models.CharField(max_length=200, help_text='Dotted import path to the real service function this capability calls, e.g. "apps.hrms.services_leave.apply_leave".')
    required_permission_codename = models.CharField(max_length=100, blank=True, help_text='Checked via core.permissions.has_perm before the service function is ever called.')
    requires_confirmation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voice_commands_capabilities_v2'
        ordering = ['intent_code']

    def __str__(self):
        return self.intent_code


class VoiceSynonym(models.Model):
    """Phase 8B gap-closure — maps a spoken phrase to a real lookup value/
    leave type name/custom entity name, without touching the underlying
    data. e.g. spoken "PTO" -> real leave type code "ANNUAL_LEAVE"."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.CharField(max_length=40, help_text='e.g. "leave_type", "lookup:ATTENDANCE_STATUS", "custom_entity".')
    spoken_phrase = models.CharField(max_length=100)
    resolves_to_code = models.CharField(max_length=100)
    language_code = models.CharField(max_length=10, default='en')

    class Meta:
        db_table = 'voice_commands_synonyms_v2'
        unique_together = [('domain', 'spoken_phrase', 'language_code')]

    def __str__(self):
        return f'{self.spoken_phrase} -> {self.resolves_to_code}'


class VoiceSpeechProvider(models.Model):
    """Phase 8B gap-closure — the provider abstraction Task G.5 asks for.
    The CURRENT provider (Sarvam) is registered as data here; actual API
    keys stay in the secret manager / settings, never in this row (only a
    `config_key_reference` naming which setting/secret holds them)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    supported_language_codes = models.JSONField(default=list)
    config_key_reference = models.CharField(max_length=100, blank=True, help_text='e.g. "SARVAM_API_KEY" — the settings/env var name, never the secret value itself.')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'voice_commands_speech_providers_v2'

    def __str__(self):
        return self.code


class GenericEntityVoiceCapability(models.Model):
    """Phase 8B gap-closure — "show my <X> records" / "create a <X>
    record" / "what is the status of my <request>" for any registered
    platform_core.EntityDefinition, per Task G.3. Enabled per entity by an
    admin; slots are derived from the entity's own field list at
    invocation time (services_voice_generic_entity.py), not hardcoded."""
    ACTION_LIST   = 'list'
    ACTION_CREATE = 'create'
    ACTION_STATUS = 'status'
    ACTION_CHOICES = [(ACTION_LIST, 'List records'), (ACTION_CREATE, 'Create record'), (ACTION_STATUS, 'Check status')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.ForeignKey('platform_core.EntityDefinition', on_delete=models.CASCADE, related_name='voice_capabilities')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'voice_commands_generic_entity_capabilities_v2'
        unique_together = [('entity', 'action')]

    def __str__(self):
        return f'{self.entity_id}: {self.action}'


class VoiceCapabilityInvocation(models.Model):
    """Append-only audit row — real, per Task G.4's own safety rule ("every
    voice action uses... audit"). Written alongside, not instead of, the
    existing voice_commands/audit.py mechanism."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capability = models.ForeignKey(VoiceCapability, on_delete=models.PROTECT, related_name='invocations')
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='voice_capability_invocations')
    was_confirmed = models.BooleanField(default=False)
    was_permitted = models.BooleanField(help_text='False = blocked by a Phase 4 permission check, service function never called.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voice_commands_capability_invocations_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.capability_id} by {self.user_id} (permitted={self.was_permitted})'
