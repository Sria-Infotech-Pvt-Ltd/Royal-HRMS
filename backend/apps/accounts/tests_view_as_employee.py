"""Read-only "view as employee": a permitted person can open an employee's workspace data exactly as the employee
sees it (X-View-As-Employee header); nobody else can, and nothing can be written through it."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeePermission, Permission

ME_URL = '/api/employees/me/'
HEADER = 'HTTP_X_VIEW_AS_EMPLOYEE'


def _client_for(user, view_as=None):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    if view_as is not None:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}', **{HEADER: str(view_as)})
    return client


class ViewAsEmployeeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.superuser = make_user('va-admin@test.com', is_superuser=True, full_name='Admin Person')
        self.employee = make_user('va-employee@test.com', role=make_role('va_employee'), full_name='Target Employee', employee_id='VAE001')
        self.other = make_user('va-other@test.com', role=make_role('va_other'), full_name='Other Person', employee_id='VAE002')
        self.permission, _ = Permission.objects.get_or_create(
            codename='employees.view_workspace', defaults={'module': 'employees', 'action': 'view_workspace'},
        )

    def test_without_the_header_a_request_is_the_signed_in_person(self):
        resp = _client_for(self.superuser).get(ME_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['full_name'], 'Admin Person')

    def test_a_superuser_sees_the_employees_own_data(self):
        resp = _client_for(self.superuser, self.employee.pk).get(ME_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['full_name'], 'Target Employee')

    def test_a_person_granted_the_permission_can_view_as_an_employee(self):
        EmployeePermission.objects.create(employee=self.other, permission=self.permission)
        resp = _client_for(self.other, self.employee.pk).get(ME_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['full_name'], 'Target Employee')

    def test_without_the_permission_the_header_is_refused_not_ignored(self):
        resp = _client_for(self.other, self.employee.pk).get(ME_URL)
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_nothing_can_be_written_while_viewing_as_someone(self):
        client = _client_for(self.superuser, self.employee.pk)
        for method in ('post', 'put', 'patch', 'delete'):
            resp = getattr(client, method)(ME_URL, {}, format='json')
            self.assertEqual(resp.status_code, 403, f'{method} should be refused: {resp.data}')

    def test_an_unknown_or_inactive_employee_is_refused(self):
        self.assertEqual(_client_for(self.superuser, 'not-a-uuid').get(ME_URL).status_code, 403)
        self.assertEqual(_client_for(self.superuser, '00000000-0000-0000-0000-000000000000').get(ME_URL).status_code, 403)
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])
        self.assertEqual(_client_for(self.superuser, self.other.pk).get(ME_URL).status_code, 403)

    def test_viewing_as_yourself_is_just_your_own_data(self):
        resp = _client_for(self.superuser, self.superuser.pk).get(ME_URL)
        self.assertEqual(resp.data['data']['full_name'], 'Admin Person')

    def test_each_viewer_and_employee_pair_is_audited_once(self):
        client = _client_for(self.superuser, self.employee.pk)
        client.get(ME_URL)
        client.get(ME_URL)
        entries = AuditLog.objects.filter(action='view_employee_workspace', object_id=str(self.employee.pk))
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().user, self.superuser)
        self.assertEqual(entries.first().changes['employee_id'], 'VAE001')

    def test_an_anonymous_request_with_the_header_is_still_unauthenticated(self):
        client = APIClient()
        client.credentials(**{HEADER: str(self.employee.pk)})
        self.assertEqual(client.get(ME_URL).status_code, 401)
