"""A profile-correction ticket raised before the new value was asked for (HR Help ticket with only the free-text message): HR types the new
value when approving, so an older request like "change my name" can still be applied."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.hrms.models import HRHelpRequest


class LegacyProfileCorrectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr = make_user('leg-hr@test.com', role=make_role('leg_hr', permission_codenames=['hr_help.respond']))
        self.employee = make_user(
            'leg-emp@test.com', role=make_role('leg_emp', permission_codenames=[]), full_name='G.Durga Prasad',
            onboarding_status=User.ONBOARDING_COMPLETE,
        )
        self.ticket = HRHelpRequest.objects.create(
            submitted_by=self.employee, topic='profile_correction', request_number=1,
            message='Section: Personal details. Field to change: Full name. Reason: changing the name from G.Durga Prasad to Gadde Durga Prasad',
        )

    def _decide(self, decision, note='', new_value=None):
        self.client.force_authenticate(user=self.hr)
        body = {'decision': decision, 'note': note, **({'new_value': new_value} if new_value is not None else {})}
        return self.client.post(reverse('hr-help-decide-change', args=[self.ticket.id]), body, format='json')

    def test_the_list_says_which_field_an_older_ticket_is_about(self):
        self.client.force_authenticate(user=self.hr)
        rows = self.client.get(reverse('hr-help-request-list')).data['data']['results']
        self.assertEqual(rows[0]['change_suggested_key'], 'full_name')
        self.assertEqual(rows[0]['change_field'], '')

    def test_hr_types_the_new_value_and_it_is_applied(self):
        response = self._decide('approve', 'Checked the ID', 'Gadde Durga Prasad')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'Gadde Durga Prasad')
        self.assertEqual((self.ticket.status, self.ticket.change_decision, self.ticket.change_field), ('resolved', 'applied', 'full_name'))
        self.assertEqual((self.ticket.change_old_value, self.ticket.change_new_value), ('G.Durga Prasad', 'Gadde Durga Prasad'))

    def test_a_value_is_required_and_validated(self):
        self.assertEqual(self._decide('approve').status_code, 400)
        self.assertEqual(self._decide('approve', new_value='G.Durga Prasad').status_code, 400)   # same as the current name
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'G.Durga Prasad')

    def test_it_can_be_declined_with_a_reason(self):
        self.assertEqual(self._decide('reject', 'Please attach proof').status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.change_decision, 'rejected')

    def test_a_decided_ticket_no_longer_suggests_a_field(self):
        self._decide('approve', new_value='Gadde Durga Prasad')
        self.client.force_authenticate(user=self.hr)
        rows = self.client.get(reverse('hr-help-request-list')).data['data']['results']
        self.assertEqual(rows[0]['change_suggested_key'], '')

    def test_an_older_ticket_about_an_unsupported_field_cannot_be_applied(self):
        other = HRHelpRequest.objects.create(
            submitted_by=self.employee, topic='profile_correction', request_number=2,
            message='Section: Bank details. Field to change: IFSC code. Reason: the branch merged',
        )
        self.client.force_authenticate(user=self.hr)
        response = self.client.post(reverse('hr-help-decide-change', args=[other.id]), {'decision': 'approve', 'new_value': 'X'}, format='json')
        self.assertEqual(response.status_code, 400)
