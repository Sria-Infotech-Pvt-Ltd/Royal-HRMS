"""A work-from-home request must say why: the approver reads the reason to decide."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import WorkFromHomeRequest

TODAY = timezone.localdate()


class WfhReasonRequiredTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.employee = make_user(
            'wfh-reason@test.com', role=make_role('wfh_reason_emp', permission_codenames=[]),
            date_of_joining=TODAY - datetime.timedelta(days=200),
        )
        self.client.force_authenticate(user=self.employee)

    def _body(self, **extra):
        body = {
            'start_date': (TODAY + datetime.timedelta(days=3)).isoformat(), 'end_date': (TODAY + datetime.timedelta(days=4)).isoformat(),
            'location_label': 'Home', 'latitude': 17.385044, 'longitude': 78.486671,
        }
        body.update(extra)
        return body

    def _post(self, **extra):
        return self.client.post(reverse('wfh-request-list'), self._body(**extra), format='json')

    def test_a_request_with_a_reason_is_created_and_the_reason_is_kept_trimmed(self):
        response = self._post(reason='  Internet repair at home  ')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(WorkFromHomeRequest.objects.get(pk=response.data['data']['id']).reason, 'Internet repair at home')

    def test_a_request_without_a_reason_is_refused_and_nothing_is_saved(self):
        response = self._post()
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Reason is required.', str(response.data))
        self.assertFalse(WorkFromHomeRequest.objects.filter(employee=self.employee).exists())

    def test_an_empty_reason_is_refused(self):
        response = self._post(reason='')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Reason is required.', str(response.data))

    def test_a_reason_of_only_spaces_is_refused(self):
        response = self._post(reason='    ')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Reason is required.', str(response.data))

    def test_a_null_reason_is_refused(self):
        response = self._post(reason=None)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(WorkFromHomeRequest.objects.filter(employee=self.employee).exists())
