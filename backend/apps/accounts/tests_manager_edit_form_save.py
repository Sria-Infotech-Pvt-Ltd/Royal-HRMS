"""Saving the Edit form for a manager: the form sends reporting_manager_id blank, which must not be refused as "managers have no reporting manager"."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


class ManagerEditFormSaveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('admin-mgr-edit@test.com', role=make_role('admin_mgr_edit', permission_codenames=['employees.edit', 'employees.view']))
        self.other = make_user('other-mgr-edit@test.com', employee_id='20000002')
        self.subject = make_user('subject-mgr-edit@test.com', employee_id='20000001', full_name='Manager Subject')
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.url = reverse('employee-detail', args=[self.subject.employee_id])

    def _as_manager(self):
        from unittest import mock
        return mock.patch('apps.accounts.views.employees_detail.can_manage_team', return_value=True)

    def test_a_blank_reporting_manager_in_a_manager_save_is_accepted(self):
        with self._as_manager():
            for blank in (None, ''):
                response = self.client.put(self.url, {'full_name': 'Manager Subject', 'reporting_manager_id': blank}, format='json')
                self.assertNotEqual(response.json().get('message'), 'Managers do not have a reporting manager.', blank)

    def test_choosing_a_reporting_manager_for_a_manager_is_still_refused(self):
        with self._as_manager():
            response = self.client.put(self.url, {'reporting_manager_id': str(self.other.pk)}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Managers do not have a reporting manager.')
