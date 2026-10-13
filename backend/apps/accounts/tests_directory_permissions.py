"""
Regression tests for the permission edges of the Employee Directory that the
persona work (Payroll Admin / Reporting Manager / Employee) depends on:

  * acting on ANOTHER person's login (reset password, resend invite, invite
    status) is an administrator action — a stray employees.reset_password on a
    plain role must not be enough;
  * the Export button's whole-list read is only available with employees.export;
  * everyone can read their OWN pay history, nobody else's without payroll.view.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import EmployeeSalaryConfig  # noqa: F401  (ensures the app's tables exist)

BRANCH = 'Test Branch'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class AccountAdministrationTests(TestCase):
    def setUp(self):
        cache.clear()
        # The historical bug: the plain employee role carried reset_password.
        self.stray_role = make_role('dp_employee_stray', permission_codenames=['employees.view', 'employees.reset_password'])
        self.admin_role = make_role(
            'dp_hr_admin', permission_codenames=['employees.view', 'employees.edit', 'employees.reset_password'],
        )
        self.plain_role = make_role('dp_plain')
        self.stray = make_user('dp_stray@test.com', role=self.stray_role, employee_id='DS1', branch=BRANCH)
        self.admin = make_user('dp_admin@test.com', role=self.admin_role, employee_id='DA1', branch=BRANCH)
        self.target = make_user('dp_target@test.com', role=self.plain_role, employee_id='DT1', branch=BRANCH)
        self.root = make_user('dp_root@test.com', role=self.plain_role, employee_id='DR1', branch=BRANCH, is_superuser=True)

    def _url(self, name, user):
        return f'/api/employees/{user.pk}/{name}/'

    def test_stray_reset_permission_is_not_enough(self):
        self.assertEqual(_api(self.stray).post(self._url('reset-password', self.target), {}, format='json').status_code, 403)
        self.assertEqual(_api(self.stray).post(self._url('resend-invite', self.target), {}, format='json').status_code, 403)
        self.assertEqual(_api(self.stray).get(self._url('invite-status', self.target)).status_code, 403)

    def test_plain_employee_is_denied(self):
        self.assertEqual(_api(self.target).post(self._url('reset-password', self.admin), {}, format='json').status_code, 403)

    def test_admin_with_both_permissions_is_allowed(self):
        self.assertEqual(_api(self.admin).post(self._url('reset-password', self.target), {}, format='json').status_code, 200)
        self.assertEqual(_api(self.admin).get(self._url('invite-status', self.target)).status_code, 200)

    def test_only_a_superuser_can_reset_a_superuser(self):
        self.assertEqual(_api(self.admin).post(self._url('reset-password', self.root), {}, format='json').status_code, 403)


class DirectoryExportCapTests(TestCase):
    def setUp(self):
        cache.clear()
        self.exporter_role = make_role('dp_exporter', permission_codenames=['employees.view', 'employees.export'])
        self.viewer_role = make_role('dp_viewer', permission_codenames=['employees.view'])
        self.exporter = make_user('dp_exp@test.com', role=self.exporter_role, employee_id='DX0', branch=BRANCH)
        self.viewer = make_user('dp_view@test.com', role=self.viewer_role, employee_id='DV0', branch=BRANCH)
        for index in range(60):
            make_user(f'dp_bulk{index}@test.com', role=self.viewer_role, employee_id=f'DB{index:03d}', branch=BRANCH)

    def _page_size(self, user):
        response = _api(user).get('/api/employees/', {'page_size': 1000})
        self.assertEqual(response.status_code, 200)
        return response.data['data']['page_size'], len(response.data['data']['results'])

    def test_viewer_without_export_stays_capped_at_50(self):
        self.assertEqual(self._page_size(self.viewer), (50, 50))

    def test_holder_of_export_can_pull_the_whole_list(self):
        size, returned = self._page_size(self.exporter)
        self.assertEqual(size, 1000)
        self.assertEqual(returned, 62)


class OwnPayHistoryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.role = make_role('dp_pay_plain')
        self.payroll_role = make_role('dp_pay_payroll', permission_codenames=['employees.view', 'payroll.view'])
        self.me = make_user('dp_me@test.com', role=self.role, employee_id='DM1', branch=BRANCH)
        self.colleague = make_user('dp_col@test.com', role=self.role, employee_id='DC1', branch=BRANCH)
        self.payroll = make_user('dp_pr@test.com', role=self.payroll_role, employee_id='DP1', branch=BRANCH)

    def _history(self, viewer, subject):
        return _api(viewer).get(f'/api/payroll/employee-salary/history/{subject.pk}/').status_code

    def test_employee_reads_own_pay_but_not_a_colleagues(self):
        self.assertEqual(self._history(self.me, self.me), 200)
        self.assertEqual(self._history(self.me, self.colleague), 403)

    def test_payroll_view_reads_anyone_in_scope(self):
        self.assertEqual(self._history(self.payroll, self.colleague), 200)
