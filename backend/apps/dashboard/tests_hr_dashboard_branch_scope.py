"""
Regression test for _hr_dashboard_branch()'s company-wide vs. branch-scoped
decision — was a hardcoded `user.role.name == 'system_admin'` check, now
the dedicated 'dashboard.view_company_wide' permission (migration 0173).
Confirms the replacement preserves the exact same behavior.
"""
from __future__ import annotations

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.dashboard.views.overview import _hr_dashboard_branch


class HrDashboardBranchScopeTests(TestCase):
    def test_system_admin_sees_company_wide(self):
        role = make_role('system_admin_dash_test', permission_codenames=['dashboard.view_company_wide'])
        user = make_user('sysadmin-dash@test.com', role=role, branch='Mumbai')
        self.assertIsNone(_hr_dashboard_branch(user))

    def test_branch_hr_is_scoped_to_their_branch(self):
        role = make_role('branch_hr_dash_test', permission_codenames=['employees.view'])
        user = make_user('branchhr-dash@test.com', role=role, branch='Pune')
        self.assertEqual(_hr_dashboard_branch(user), 'Pune')

    def test_superuser_sees_company_wide_even_without_the_permission(self):
        role = make_role('no_perms_dash_test')
        user = make_user('superuser-dash@test.com', role=role, branch='Delhi', is_superuser=True)
        self.assertIsNone(_hr_dashboard_branch(user))

    def test_none_user_returns_none(self):
        self.assertIsNone(_hr_dashboard_branch(None))
