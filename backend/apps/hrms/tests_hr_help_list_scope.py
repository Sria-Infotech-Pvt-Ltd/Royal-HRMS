"""HR Help list scope: staff (hr_help.respond or full access) see every ticket; mine=1 narrows anyone to their own."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import HRHelpRequest


class HrHelpListScopeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('hr-help-request-list')
        self.staff = make_user('scope-staff@test.com', role=make_role('hr_scope_staff', permission_codenames=['hr_help.respond']))
        self.employee = make_user('scope-emp@test.com', role=make_role('hr_scope_emp', permission_codenames=[]))
        self.own = HRHelpRequest.objects.create(submitted_by=self.staff, topic='other', message='My own question to HR')
        self.theirs = HRHelpRequest.objects.create(submitted_by=self.employee, topic='profile_correction', message='Their correction request')

    def _ids(self, user, query=''):
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url + query)
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id'] for row in response.data['data']['results']}

    def test_staff_see_every_ticket_by_default(self):
        self.assertEqual(self._ids(self.staff), {str(self.own.id), str(self.theirs.id)})

    def test_staff_can_ask_for_only_their_own(self):
        self.assertEqual(self._ids(self.staff, '?mine=1'), {str(self.own.id)})

    def test_an_employee_only_ever_sees_their_own(self):
        self.assertEqual(self._ids(self.employee), {str(self.theirs.id)})
        self.assertEqual(self._ids(self.employee, '?mine=1'), {str(self.theirs.id)})

    def test_staff_can_still_filter_the_queue_by_status(self):
        self.assertEqual(self._ids(self.staff, '?status=open'), {str(self.own.id), str(self.theirs.id)})
        self.assertEqual(self._ids(self.staff, '?status=resolved'), set())
