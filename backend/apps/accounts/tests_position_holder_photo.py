"""The positions list sends each holder's profile photo, so the org chart can show faces instead of initials."""
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Position, User
from apps.accounts.services_placement import assign_position


class PositionHolderPhotoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.viewer = make_user('chart-viewer@test.com', role=make_role('chart_viewer', permission_codenames=['org_chart.view', 'org_structure.view']))
        unit = OrgUnit.objects.create(name='Photo Unit')
        self.with_photo = Position.objects.create(org_unit=unit, title='Has Photo', grade='L3')
        self.without_photo = Position.objects.create(org_unit=unit, title='No Photo', grade='L3')
        self.vacant = Position.objects.create(org_unit=unit, title='Vacant', grade='L3')
        pictured = make_user('pictured@test.com', employee_id='40000001', full_name='Pictured Person')
        User.objects.filter(pk=pictured.pk).update(profile_photo='profile_photos/pictured.jpg')
        assign_position(User.objects.get(pk=pictured.pk), self.with_photo, effective_from=date(2026, 1, 1))
        assign_position(make_user('plain@test.com', employee_id='40000002'), self.without_photo, effective_from=date(2026, 1, 1))

    def _photo_of(self, client, position):
        response = client.get(reverse('position-detail', args=[position.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data']['holder_photo_url']

    def test_each_position_carries_its_holder_photo_or_null(self):
        client = APIClient()
        client.force_authenticate(self.viewer)
        self.assertIn('pictured.jpg', self._photo_of(client, self.with_photo) or '')
        self.assertIsNone(self._photo_of(client, self.without_photo))
        self.assertIsNone(self._photo_of(client, self.vacant))

    def test_the_list_sends_the_field_too(self):
        client = APIClient()
        client.force_authenticate(self.viewer)
        rows = client.get(reverse('position-list')).json()['data']['results']
        self.assertTrue(rows and all('holder_photo_url' in row for row in rows))
