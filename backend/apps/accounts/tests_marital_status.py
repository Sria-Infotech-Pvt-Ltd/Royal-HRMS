"""UAT-034: all five marital statuses are accepted and stored; anything else is refused with the valid list."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile


class MaritalStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('hr_marital_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-marital@test.com', role=role)
        self.employee = make_user('marital.employee@test.com', employee_id='EMPMARITAL1')
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)
        self.url = reverse('employee-detail', args=[self.employee.employee_id])

    def test_choices_are_the_five_expected(self):
        values = [value for value, _label in EmployeeProfile.MARITAL_CHOICES]
        self.assertEqual(values, ['single', 'married', 'divorced', 'widowed', 'separated'])

    def test_every_status_saves_and_comes_back(self):
        for status_value in ('single', 'married', 'divorced', 'widowed', 'separated'):
            response = self.client.patch(self.url, {'marital_status': status_value}, format='json')
            self.assertEqual(response.status_code, 200, (status_value, response.json()))
            self.assertEqual(response.json()['data']['profile']['marital_status'], status_value)

    def test_unknown_status_is_rejected(self):
        response = self.client.patch(self.url, {'marital_status': 'complicated'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('marital_status', response.json()['data'])
