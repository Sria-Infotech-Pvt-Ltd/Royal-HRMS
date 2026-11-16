"""Branch Admin (role.can_manage_branch) keeps settings.edit and its abilities, but
only ever sees its own branch's employees. System Admin and HR Admin are unchanged."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from core.permissions import can_edit_settings, has_perm, is_branch_restricted

BRANCH_ADMIN_PERMS = ['settings.edit', 'settings.view', 'employees.view', 'employees.edit', 'org_chart.view',
                      'onboarding.approve']


class BranchAdminScopeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ba_role = make_role('ba_scope_test', permission_codenames=BRANCH_ADMIN_PERMS)
        self.ba_role.can_manage_branch = True
        self.ba_role.save()
        sys_role = make_role('sys_scope_test', permission_codenames=['settings.edit', 'employees.view', 'org_chart.view'])
        hr_role = make_role('hr_scope_test', permission_codenames=['employees.view', 'onboarding.approve'])
        mgr_role = make_role('mgr_scope_test', can_manage_team=True)
        emp_role = make_role('emp_scope_test')
        kw = {'onboarding_status': 'complete'}
        self.ba = make_user('ba.scope@test.com', role=self.ba_role, branch='Alpha', employee_id='BAS1', **kw)
        self.ba_blank = make_user('ba.blank@test.com', role=self.ba_role, branch='', employee_id='BAS2', **kw)
        self.sys = make_user('sys.scope@test.com', role=sys_role, branch='Alpha', employee_id='SYS1', **kw)
        self.hr_any = make_user('hr.scope@test.com', role=hr_role, branch='', employee_id='HRS1', **kw)
        self.emp_a = make_user('a.scope@test.com', role=emp_role, branch='Alpha', employee_id='EA1',
                               department='Ops', **kw)
        self.emp_b = make_user('b.scope@test.com', role=emp_role, branch='Beta', employee_id='EB1',
                               department='Ops', **kw)
        self.mgr_a = make_user('ma.scope@test.com', role=mgr_role, branch='Alpha', employee_id='MA1',
                               department='Ops', **kw)
        self.mgr_b = make_user('mb.scope@test.com', role=mgr_role, branch='Beta', employee_id='MB1',
                               department='Ops', **kw)

    def client_for(self, email):
        c = APIClient()
        _login(c, email)
        return c

    def ids(self, email, **params):
        resp = self.client_for(email).get(reverse('employee-list-create'), {'page_size': 50, **params})
        self.assertEqual(resp.status_code, 200, resp.data)
        return {r['employee_id'] for r in resp.data['data']['results']}

    # Permissions: keeps everything, but not company-wide data
    def test_branch_admin_keeps_permissions_and_settings(self):
        self.assertTrue(is_branch_restricted(self.ba))
        self.assertFalse(has_perm(self.ba, 'settings.edit'))              # not "sees every branch"
        self.assertTrue(has_perm(self.ba, 'payroll.process'))             # settings.edit still grants the rest
        self.assertTrue(can_edit_settings(self.ba))                        # still edits settings
        self.assertTrue(has_perm(self.sys, 'settings.edit'))              # System Admin unchanged
        resp = self.client_for('ba.scope@test.com').get(reverse('role-list-create'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(self.client_for('ba.scope@test.com').put(reverse('company'), {}, format='json').status_code, 403)

    # Employees list / detail
    def test_branch_admin_sees_only_own_branch(self):
        seen = self.ids('ba.scope@test.com')
        self.assertIn('EA1', seen)
        self.assertNotIn('EB1', seen)
        self.assertNotIn('EB1', self.ids('ba.scope@test.com', branch='Beta'))   # parameter can't widen
        c = self.client_for('ba.scope@test.com')
        self.assertEqual(c.get(reverse('employee-detail', args=['EB1'])).status_code, 404)
        self.assertEqual(c.get(reverse('employee-detail', args=['EA1'])).status_code, 200)

    def test_branch_admin_without_branch_sees_nobody(self):
        self.assertEqual(self.ids('ba.blank@test.com'), set())
        c = self.client_for('ba.blank@test.com')
        self.assertEqual(c.get(reverse('employee-detail', args=['EA1'])).status_code, 404)

    def test_system_admin_and_hr_admin_unchanged(self):
        self.assertTrue({'EA1', 'EB1'} <= self.ids('sys.scope@test.com'))
        self.assertTrue({'EA1', 'EB1'} <= self.ids('hr.scope@test.com'))      # HR with no branch: company-wide, as before

    # Org chart
    def test_org_chart_own_branch_only(self):
        data = self.client_for('ba.scope@test.com').get(reverse('org-chart'), {'branch': 'Beta'}).data['data']
        self.assertNotIn('EB1', str(data))
        self.assertNotIn('MB1', str(data))

    # Manager / HR dropdowns
    def test_manager_and_hr_dropdowns_respect_branch(self):
        c = self.client_for('ba.scope@test.com')
        by_branch = {m['employee_id'] for m in c.get(reverse('employee-manager-list'), {'branch': 'Beta'}).data['data']}
        self.assertNotIn('MB1', by_branch)
        by_dept = {m['employee_id'] for m in c.get(reverse('employee-manager-list'), {'department': 'Ops'}).data['data']}
        self.assertIn('MA1', by_dept)
        self.assertNotIn('MB1', by_dept)
        self.assertEqual(c.get(reverse('employee-hr-list'), {'branch': 'Beta'}).data['data'], [])
        sys_dept = {m['employee_id'] for m in self.client_for('sys.scope@test.com').get(
            reverse('employee-manager-list'), {'department': 'Ops'}).data['data']}
        self.assertTrue({'MA1', 'MB1'} <= sys_dept)                         # System Admin unchanged


class BranchAdminDashboardTests(BranchAdminScopeTests):
    """The Admin dashboard stays available to a Branch Admin, with every card
    limited to its own branch; System Admin still sees the whole company."""

    def get(self, email, path, **params):
        resp = self.client_for(email).get(f'/api/dashboard/system-admin/{path}', params)
        self.assertEqual(resp.status_code, 200, (path, resp.data))
        return resp.data['data']

    def test_admin_dashboard_cards_are_branch_scoped(self):
        ba_kpis = self.get('ba.scope@test.com', 'kpis/')
        sys_kpis = self.get('sys.scope@test.com', 'kpis/')
        self.assertLess(ba_kpis['total_employees'], sys_kpis['total_employees'])
        heads = {r['department']: r['count'] for r in self.get('ba.scope@test.com', 'department-headcount/')}
        self.assertEqual(heads.get('Ops'), 2)                                 # EA1 + MA1 (Alpha only)
        self.get('ba.scope@test.com', 'pending-approvals/')
        life = self.get('ba.scope@test.com', 'employee-lifecycle/')
        self.assertNotIn('EB1', str(life))
        self.get('ba.scope@test.com', 'birthdays/today/')
        self.get('ba.scope@test.com', 'birthdays/upcoming/')
        self.get('ba.scope@test.com', 'audit-logs/', limit=10, offset=0)
        self.get('ba.scope@test.com', 'announcement/')

    def test_employee_without_settings_cannot_open_admin_dashboard(self):
        resp = self.client_for('a.scope@test.com').get('/api/dashboard/system-admin/kpis/')
        self.assertEqual(resp.status_code, 403)


class BranchAdminActionQueueTests(BranchAdminScopeTests):
    """Action Queue on a Branch Admin's dashboard counts its own branch only."""

    def queue(self, email):
        cache.clear()
        resp = self.client_for(email).get('/api/dashboard/hr/action-queue/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['data']

    def test_action_queue_counts_own_branch_only(self):
        from apps.accounts.models import User
        User.objects.filter(pk=self.emp_b.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)   # Beta
        self.assertEqual(self.queue('ba.scope@test.com')['onboarding_reviews'], 0)
        User.objects.filter(pk=self.emp_a.pk).update(onboarding_status=User.ONBOARDING_SUBMITTED)   # Alpha
        self.assertEqual(self.queue('ba.scope@test.com')['onboarding_reviews'], 1)
        self.assertEqual(self.queue('ba.blank@test.com')['onboarding_reviews'], 0)                 # no branch: nothing
