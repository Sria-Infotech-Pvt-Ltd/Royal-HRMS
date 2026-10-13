"""
Regression tests for the Personal step's Identity header (migration 0187 +
views/shared.py's step-0 field-key allowlist): salutation/display_name are
hardcoded, non-configurable fields (no OnboardingFieldConfig row of their
own, same treatment as permanent_same_as_current) while nationality/
place_of_birth are real, seeded OnboardingFieldConfig rows — both groups
must actually round-trip through PATCH /onboarding/step/0/, not just exist
as EmployeeProfile columns with no save path reaching them (the exact gap
this migration closes — see apps.accounts.serializers.EmployeeProfileSerializer
and apps.accounts.views.shared._step_all_field_keys).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile, OnboardingFieldConfig


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


PERSONAL_STEP = 0


class IdentityFieldConfigSeedTests(TestCase):
    def test_nationality_and_place_of_birth_are_seeded_real_builtin_rows(self):
        nationality = OnboardingFieldConfig.objects.get(field_key='nationality', step=PERSONAL_STEP)
        place_of_birth = OnboardingFieldConfig.objects.get(field_key='place_of_birth', step=PERSONAL_STEP)
        self.assertFalse(nationality.is_custom)
        self.assertTrue(nationality.required)
        self.assertFalse(place_of_birth.is_custom)
        self.assertFalse(place_of_birth.required)

    def test_salutation_and_display_name_have_no_config_row(self):
        # Hardcoded Identity-header fields — deliberately NOT admin-
        # configurable via Settings > Onboarding Fields, same as Hire's own
        # Personal identity step.
        self.assertFalse(OnboardingFieldConfig.objects.filter(field_key='salutation').exists())
        self.assertFalse(OnboardingFieldConfig.objects.filter(field_key='display_name').exists())


class IdentityFieldSaveRoundTripTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = make_user(
            'identity-test@test.com',
            role=make_role('identity_test_role', permission_codenames=['employees.edit_own_profile']),
        )
        _login(self.client, 'identity-test@test.com')
        # Pre-fill every OTHER required step-0 field directly via the ORM —
        # the step-save required-field gate blocks the whole request if any
        # visible+required field would end up blank, and this test is only
        # exercising salutation/display_name/nationality/place_of_birth.
        profile, _ = EmployeeProfile.objects.get_or_create(user=self.user)
        profile.date_of_birth = '1990-01-01'
        profile.gender = 'male'
        profile.marital_status = 'single'
        profile.father_name = 'Test Father'
        profile.current_address = '123 Test Street'
        profile.current_district = 'Test District'
        profile.current_state = 'Test State'
        profile.current_pin_code = '500081'
        profile.save()

    def test_salutation_and_display_name_save_despite_no_field_config_row(self):
        resp = self.client.patch(
            reverse('onboarding-step', args=[PERSONAL_STEP]),
            {'salutation': 'Mr.', 'display_name': 'Mr. Test Employee'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.user)
        self.assertEqual(profile.salutation, 'Mr.')
        self.assertEqual(profile.display_name, 'Mr. Test Employee')

    def test_nationality_and_place_of_birth_save(self):
        resp = self.client.patch(
            reverse('onboarding-step', args=[PERSONAL_STEP]),
            {'nationality': 'American', 'place_of_birth': 'Chicago'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.user)
        self.assertEqual(profile.nationality, 'American')
        self.assertEqual(profile.place_of_birth, 'Chicago')

    def test_unconfigured_random_key_is_still_dropped(self):
        # Confirms the step-0 allowlist addition is scoped to exactly
        # salutation/display_name, not accidentally opened up wholesale.
        resp = self.client.patch(
            reverse('onboarding-step', args=[PERSONAL_STEP]),
            {'is_superuser': 'true', 'nationality': 'Indian'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)
