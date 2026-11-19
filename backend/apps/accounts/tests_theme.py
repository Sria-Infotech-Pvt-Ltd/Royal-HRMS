"""Each person's saved colour theme: private to them, validated, and empty until they choose."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import User


class MyThemeTests(TestCase):
    def setUp(self):
        self.user = make_user('theme-a@test.com', full_name='Theme A', employee_id='TH1')
        self.other = make_user('theme-b@test.com', full_name='Theme B', employee_id='TH2')
        self.client = APIClient()
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))
        self.url = reverse('my-theme')

    def test_nothing_saved_until_the_person_chooses(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data'], {'mode': None, 'accent': None})

    def test_saves_and_reads_back(self):
        saved = self.client.put(self.url, {'mode': 'dark', 'accent': 'ocean'}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(self.client.get(self.url).data['data'], {'mode': 'dark', 'accent': 'ocean'})

    def test_it_is_private_to_the_person(self):
        self.client.put(self.url, {'mode': 'dark', 'accent': 'forest'}, format='json')
        self.other.refresh_from_db()
        self.assertEqual((self.other.theme_mode, self.other.theme_accent), ('', ''))

    def test_rejects_unknown_values(self):
        for payload in ({'mode': 'neon', 'accent': 'ocean'}, {'mode': 'dark', 'accent': 'pink'}, {'mode': 'dark'}, {}):
            response = self.client.put(self.url, payload, format='json')
            self.assertEqual(response.status_code, 400, payload)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme_mode, '')

    def test_needs_a_signed_in_user(self):
        self.assertIn(APIClient().get(self.url).status_code, (401, 403))
