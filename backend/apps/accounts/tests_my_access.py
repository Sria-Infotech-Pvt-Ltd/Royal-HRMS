"""GET /api/employees/me/access/: a person's own permissions, and the viewed employee's while viewing as that employee."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User


class MyAccessTests(TestCase):
    def setUp(self):
        self.hr = make_user(
            'access-hr@test.com', role=make_role('access_hr', permission_codenames=[
                'employees.view', 'employees.view_workspace', 'documents.view', 'payroll.view',
            ]), employee_id='AC1', full_name='HR Viewer',
        )
        self.employee = make_user(
            'access-emp@test.com', role=make_role('access_emp', permission_codenames=['leave.view']),
            employee_id='AC2', full_name='Plain Employee',
        )
        self.url = reverse('my-access')

    def _client(self, user, **extra):
        client = APIClient()
        client.force_authenticate(user=User.objects.get(pk=user.pk))
        return client

    def test_returns_the_callers_own_permissions(self):
        data = self._client(self.hr).get(self.url).data['data']
        self.assertIn('documents.view', data['permissions'])
        self.assertIn('employees.view', data['permissions'])
        self.assertFalse(data['is_superuser'])

    def test_needs_a_signed_in_user(self):
        self.assertIn(APIClient().get(self.url).status_code, (401, 403))

    def test_a_superuser_has_every_permission_and_the_flag(self):
        admin = make_user('access-su@test.com', is_superuser=True, employee_id='AC3', full_name='Boss')
        data = self._client(admin).get(self.url).data['data']
        self.assertTrue(data['is_superuser'])
        self.assertIn('documents.view', data['permissions'])
