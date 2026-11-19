"""Each person's saved interface language: private to them, validated, and empty until they choose."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import User


class MyLanguageTests(TestCase):
    def setUp(self):
        self.user = make_user('lang-a@test.com', full_name='Lang A', employee_id='LG1')
        self.other = make_user('lang-b@test.com', full_name='Lang B', employee_id='LG2')
        self.client = APIClient()
        self.client.force_authenticate(user=User.objects.get(pk=self.user.pk))
        self.url = reverse('my-language')

    def test_nothing_saved_until_the_person_chooses(self):
        self.assertEqual(self.client.get(self.url).data['data'], {'language': None})

    def test_saves_and_reads_back(self):
        saved = self.client.put(self.url, {'language': 'te'}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(self.client.get(self.url).data['data'], {'language': 'te'})

    def test_it_is_private_to_the_person(self):
        self.client.put(self.url, {'language': 'hi'}, format='json')
        self.other.refresh_from_db()
        self.assertEqual(self.other.language, '')

    def test_rejects_unknown_languages(self):
        for payload in ({'language': 'fr'}, {'language': ''}, {}):
            self.assertEqual(self.client.put(self.url, payload, format='json').status_code, 400, payload)
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, '')

    def test_needs_a_signed_in_user(self):
        self.assertIn(APIClient().get(self.url).status_code, (401, 403))
