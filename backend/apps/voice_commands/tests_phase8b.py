"""Phase 8B Task G — the voice capability registry's safety invariant: permission check and confirmation gate always run before the real service function."""
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.voice_commands.models import VoiceCapability, VoiceCapabilityInvocation
from apps.voice_commands.services_capability_registry import (
    CapabilityConfirmationRequiredError, CapabilityNotFoundError, CapabilityPermissionDeniedError,
    invoke_capability, register_capability,
)

_seq = [0]
_calls = []


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _fake_service_function(user, **slots):
    _calls.append((user.id, slots))
    return 'ok'


# Registered under a real importable dotted path for invoke_capability to resolve.
fake_service_function = _fake_service_function


def _make_employee(permission_codenames=None):
    role = make_role(_unique('role'), permission_codenames=permission_codenames or [])
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class VoiceCapabilityRegistryTests(TestCase):
    def setUp(self):
        _calls.clear()

    def test_register_is_idempotent(self):
        first = register_capability('TEST_INTENT', 'desc', 'apps.voice_commands.tests_phase8b.fake_service_function')
        second = register_capability('TEST_INTENT', 'desc updated', 'apps.voice_commands.tests_phase8b.fake_service_function')
        self.assertEqual(first.id, second.id)
        second.refresh_from_db()
        self.assertEqual(second.description, 'desc updated')

    def test_unknown_intent_raises(self):
        employee = _make_employee()
        with self.assertRaises(CapabilityNotFoundError):
            invoke_capability('NOT_REGISTERED', employee, {})

    def test_missing_permission_blocks_and_never_calls_service(self):
        register_capability(
            'LEAVE_APPLY_TEST', 'Apply leave', 'apps.voice_commands.tests_phase8b.fake_service_function',
            required_permission_codename='leave.apply',
        )
        employee = _make_employee(permission_codenames=[])  # no leave.apply permission
        with self.assertRaises(CapabilityPermissionDeniedError):
            invoke_capability('LEAVE_APPLY_TEST', employee, {})
        self.assertEqual(_calls, [])  # service function never reached

        invocation = VoiceCapabilityInvocation.objects.get(user=employee)
        self.assertFalse(invocation.was_permitted)

    def test_permitted_call_without_confirmation_requirement_reaches_service(self):
        register_capability(
            'GREETING_TEST', 'Greeting', 'apps.voice_commands.tests_phase8b.fake_service_function',
        )
        employee = _make_employee()
        result = invoke_capability('GREETING_TEST', employee, {'foo': 'bar'})
        self.assertEqual(result, 'ok')
        self.assertEqual(_calls, [(employee.id, {'foo': 'bar'})])

    def test_confirmation_required_blocks_until_confirmed(self):
        register_capability(
            'PAYOUT_TEST', 'Pay bonus', 'apps.voice_commands.tests_phase8b.fake_service_function',
            requires_confirmation=True,
        )
        employee = _make_employee()
        with self.assertRaises(CapabilityConfirmationRequiredError):
            invoke_capability('PAYOUT_TEST', employee, {})
        self.assertEqual(_calls, [])

        result = invoke_capability('PAYOUT_TEST', employee, {}, confirmed=True)
        self.assertEqual(result, 'ok')
        self.assertEqual(len(_calls), 1)

    def test_disabled_capability_is_not_invocable(self):
        capability = register_capability('DISABLE_TEST', 'x', 'apps.voice_commands.tests_phase8b.fake_service_function')
        capability.is_active = False
        capability.save()
        employee = _make_employee()
        with self.assertRaises(CapabilityNotFoundError):
            invoke_capability('DISABLE_TEST', employee, {})
