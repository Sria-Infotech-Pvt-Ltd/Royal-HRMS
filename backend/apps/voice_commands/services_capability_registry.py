"""
Phase 8B Task G — invoke a registered VoiceCapability through the EXACT
same permission check a real API endpoint would use, then the real
service function — never a shortcut. This is the safety invariant Task
G.4 requires, enforced in code here (not just documented): a disabled or
unpermitted capability NEVER reaches its service function.
"""
import importlib

from core.permissions import has_perm

from apps.voice_commands.models import VoiceCapability, VoiceCapabilityInvocation


class CapabilityNotFoundError(Exception):
    pass


class CapabilityPermissionDeniedError(Exception):
    pass


class CapabilityConfirmationRequiredError(Exception):
    """Raised when requires_confirmation=True and the caller didn't pass confirmed=True — caller must re-prompt the user."""


def _resolve_service_function(dotted_path: str):
    module_path, function_name = dotted_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, function_name)


def register_capability(
    intent_code: str, description: str, service_function_path: str, *,
    required_permission_codename: str = '', requires_confirmation: bool = False,
    example_phrases: dict | None = None, required_slots: list | None = None,
) -> VoiceCapability:
    """Idempotent. Registers an EXISTING intent/executor as a capability —
    does not change what that executor does."""
    capability, _ = VoiceCapability.objects.update_or_create(
        intent_code=intent_code,
        defaults={
            'description': description, 'service_function_path': service_function_path,
            'required_permission_codename': required_permission_codename,
            'requires_confirmation': requires_confirmation,
            'example_phrases': example_phrases or {}, 'required_slots': required_slots or [],
        },
    )
    return capability


def invoke_capability(intent_code: str, user, slots: dict, *, confirmed: bool = False):
    """The one real entry point every voice-driven action must go through.
    Audits EVERY call, including denied/unconfirmed ones (was_permitted
    False, or never reaching the service function at all)."""
    try:
        capability = VoiceCapability.objects.get(intent_code=intent_code, is_active=True)
    except VoiceCapability.DoesNotExist:
        raise CapabilityNotFoundError(f'No active capability registered for intent {intent_code!r}.')

    permitted = True
    if capability.required_permission_codename:
        permitted = has_perm(user, capability.required_permission_codename)

    if not permitted:
        VoiceCapabilityInvocation.objects.create(capability=capability, user=user, was_confirmed=confirmed, was_permitted=False)
        raise CapabilityPermissionDeniedError(
            f'{user} lacks permission {capability.required_permission_codename!r} for {intent_code!r}.'
        )

    if capability.requires_confirmation and not confirmed:
        raise CapabilityConfirmationRequiredError(f'{intent_code!r} requires explicit confirmation before executing.')

    VoiceCapabilityInvocation.objects.create(capability=capability, user=user, was_confirmed=confirmed, was_permitted=True)

    service_function = _resolve_service_function(capability.service_function_path)
    return service_function(user=user, **slots)
