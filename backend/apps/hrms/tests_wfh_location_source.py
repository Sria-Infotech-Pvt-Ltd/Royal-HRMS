"""WFH location_source: how a work-from-home point was obtained (gps captured on the device, or address looked up)."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import WFHSavedLocation, WorkFromHomeRequest

TODAY = timezone.localdate()


class WfhLocationSourceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.employee = make_user(
            'wfh-src@test.com', role=make_role('wfh_src_emp', permission_codenames=[]),
            date_of_joining=TODAY - datetime.timedelta(days=200),
        )
        self.client.force_authenticate(user=self.employee)
        self.start = (TODAY + datetime.timedelta(days=3)).isoformat()
        self.end = (TODAY + datetime.timedelta(days=4)).isoformat()

    def _request_body(self, **extra):
        return {'start_date': self.start, 'end_date': self.end, 'reason': 'x', 'location_label': 'Home',
                'latitude': 17.385044, 'longitude': 78.486671, **extra}

    def _post_request(self, **extra):
        return self.client.post(reverse('wfh-request-list'), self._request_body(**extra), format='json')

    def test_request_is_created_with_each_source(self):
        for source, offset in (('gps', 0), ('address', 10)):
            self.start = (TODAY + datetime.timedelta(days=3 + offset)).isoformat()
            self.end = (TODAY + datetime.timedelta(days=4 + offset)).isoformat()
            response = self._post_request(location_source=source)
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['data']['location_source'], source)
            self.assertEqual(WorkFromHomeRequest.objects.get(pk=response.data['data']['id']).location_source, source)

    def test_source_defaults_to_gps_when_omitted(self):
        response = self._post_request()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['location_source'], 'gps')

    def test_invalid_source_is_rejected(self):
        response = self._post_request(location_source='satellite')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(WorkFromHomeRequest.objects.exists())

    def test_saved_location_stores_and_returns_its_source(self):
        created = self.client.post(reverse('wfh-saved-location-list-create'),
                                   {'label': 'Flat', 'latitude': 17.4, 'longitude': 78.4, 'location_source': 'address'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        listed = self.client.get(reverse('wfh-saved-location-list-create'))
        self.assertEqual([row['location_source'] for row in listed.data['data']], ['address'])

    def test_saved_location_source_defaults_to_gps_and_rejects_invalid(self):
        default = self.client.post(reverse('wfh-saved-location-list-create'),
                                   {'label': 'Home', 'latitude': 17.4, 'longitude': 78.4}, format='json')
        self.assertEqual(default.data['data']['location_source'], 'gps')
        bad = self.client.post(reverse('wfh-saved-location-list-create'),
                               {'label': 'Bad', 'latitude': 17.4, 'longitude': 78.4, 'location_source': 'x'}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_request_from_a_saved_location_copies_that_locations_source(self):
        saved = WFHSavedLocation.objects.create(employee=self.employee, label='Flat', latitude=17.4, longitude=78.4, location_source='address')
        response = self._post_request(saved_location_id=str(saved.id), location_source='gps')   # the saved record wins
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['data']['location_source'], 'address')

    def test_someone_elses_saved_location_cannot_be_used(self):
        other = make_user('wfh-other@test.com', role=make_role('wfh_src_other', permission_codenames=[]))
        saved = WFHSavedLocation.objects.create(employee=other, label='Theirs', latitude=17.4, longitude=78.4, location_source='address')
        response = self._post_request(saved_location_id=str(saved.id))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(WorkFromHomeRequest.objects.exists())
