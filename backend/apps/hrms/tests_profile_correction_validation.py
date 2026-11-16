"""Profile-correction HR Help tickets must name a real section and one of that section's fields."""
from __future__ import annotations

import re
from pathlib import Path
from unittest import skipUnless

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import HRHelpRequest
from apps.hrms.profile_correction_fields import OTHER_FIELD, OTHER_SECTION, PROFILE_CORRECTION_FIELDS

REASON = 'Entered the wrong year at onboarding'
FRONTEND_FIELDS = Path(__file__).resolve().parents[3] / 'frontend' / 'app' / 'dashboard' / 'ess' / '_components' / 'profileCorrectionFields.ts'


def _message(section: str, field: str, reason: str = REASON) -> str:
    return f'Section: {section}. Field to change: {field}. Reason: {reason}'


class ProfileCorrectionValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(user=make_user('pc-valid@test.com', role=make_role('pc_valid_emp', permission_codenames=[])))
        self.url = reverse('hr-help-request-list')

    def _post(self, topic: str, message: str):
        return self.client.post(self.url, {'topic': topic, 'priority': 'normal', 'message': message}, format='json')

    def test_every_listed_pair_is_accepted(self):
        for section, fields in PROFILE_CORRECTION_FIELDS.items():
            for field in fields:
                response = self._post('profile_correction', _message(section, field))
                self.assertEqual(response.status_code, 201, (section, field, response.data))

    def test_a_field_from_another_section_is_rejected(self):
        response = self._post('profile_correction', _message('Bank details', 'Date of birth'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('belongs to the selected section', response.data['message'])

    def test_an_unknown_section_is_rejected(self):
        response = self._post('profile_correction', _message('Payroll', 'Date of birth'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('valid section', response.data['message'])

    def test_a_free_text_field_outside_the_list_is_rejected(self):
        self.assertEqual(self._post('profile_correction', _message('Personal details', 'Shoe size')).status_code, 400)

    def test_a_message_not_in_the_format_is_rejected(self):
        self.assertEqual(self._post('profile_correction', 'Please change my date of joining to 2025').status_code, 400)

    def test_a_short_reason_is_rejected(self):
        response = self._post('profile_correction', _message('Personal details', 'Date of birth', 'typo'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('at least 10 characters', response.data['message'])

    def test_other_topics_are_not_checked_against_the_list(self):
        response = self._post('payroll_query', 'Section: Nonsense. Field to change: Nothing. Reason: free text for a payroll query')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(HRHelpRequest.objects.count(), 1)

    def test_other_topics_keep_the_existing_minimum_length(self):
        self.assertEqual(self._post('payroll_query', 'short').status_code, 400)


class FrontendListsInSyncTests(SimpleTestCase):
    @skipUnless(FRONTEND_FIELDS.exists(), 'frontend source is not present next to the backend')
    def test_server_lists_match_the_frontend_file(self):
        source = FRONTEND_FIELDS.read_text(encoding='utf-8')
        block = source[source.index('export const CORRECTION_SECTIONS'):source.index('export function fieldsForSection')]
        parsed: dict[str, tuple[str, ...]] = {}
        for name, fields in re.findall(r'value: ("[^"]+"|OTHER_SECTION),\s*fields: \[(.*?)\]\s*,?\s*\}', block, re.S):
            section = OTHER_SECTION if name == 'OTHER_SECTION' else name.strip('"')
            names = re.findall(r'"([^"]+)"|(OTHER_FIELD)', re.sub(r'//[^\n]*', '', fields))
            parsed[section] = tuple(OTHER_FIELD if other else quoted for quoted, other in names)
        self.assertEqual(parsed, PROFILE_CORRECTION_FIELDS)
