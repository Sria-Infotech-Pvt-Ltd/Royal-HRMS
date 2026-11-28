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
        self.assertEqual(_client_for(self.superuser, 'NO-SUCH-CODE').get(ME_URL).status_code, 403)
        self.assertEqual(_client_for(self.superuser, '00000000-0000-0000-0000-000000000000').get(ME_URL).status_code, 403)
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])
        self.assertEqual(_client_for(self.superuser, self.other.pk).get(ME_URL).status_code, 403)

    def test_an_employee_code_works_like_the_id(self):
        resp = _client_for(self.superuser, 'VAE001').get(ME_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['full_name'], 'Target Employee')

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


class ViewAsCannotReadMoreThanTheViewerTests(TestCase):
    """Viewing as someone reads with all of THEIR access, so a viewer who is not a superuser may only open the workspace
    of an employee holding no sensitive access the viewer lacks, inside the viewer's own branch."""

    def setUp(self):
        cache.clear()
        permission, _ = Permission.objects.get_or_create(
            codename='employees.view_workspace', defaults={'module': 'employees', 'action': 'view_workspace'},
        )
        self.viewer = make_user('va-hr@test.com', role=make_role('va_hr'), full_name='Branch HR', employee_id='VAH001', branch='North')
        EmployeePermission.objects.create(employee=self.viewer, permission=permission)
        self.colleague = make_user('va-colleague@test.com', role=make_role('va_colleague'), full_name='Colleague', employee_id='VAH002',
                                   branch='North')

    def test_an_everyday_employee_in_the_same_branch_can_be_viewed(self):
        self.assertEqual(_client_for(self.viewer, self.colleague.pk).get(ME_URL).status_code, 200)

    def test_a_superuser_cannot_be_viewed(self):
        admin = make_user('va-super@test.com', is_superuser=True, employee_id='VAH003', branch='North')
        self.assertEqual(_client_for(self.viewer, admin.pk).get(ME_URL).status_code, 403)

    def test_someone_with_sensitive_access_the_viewer_lacks_cannot_be_viewed(self):
        payroll, _ = Permission.objects.get_or_create(codename='payroll.view', defaults={'module': 'payroll', 'action': 'view'})
        EmployeePermission.objects.create(employee=self.colleague, permission=payroll)
        self.assertEqual(_client_for(self.viewer, self.colleague.pk).get(ME_URL).status_code, 403)

    def test_an_employee_in_another_branch_cannot_be_viewed(self):
        self.colleague.branch = 'South'
        self.colleague.save(update_fields=['branch'])
        self.assertEqual(_client_for(self.viewer, self.colleague.pk).get(ME_URL).status_code, 403)

