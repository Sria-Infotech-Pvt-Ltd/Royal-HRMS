"""
My Profile (/employees/me/) shows the signed-in user's own Reporting Manager,
Reporting Approver and HR — including for Manager roles, whose reporting
manager used to be hidden by MyProfileSerializer. Also re-checks the Manager
reporting hierarchy that decides who may be assigned.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from apps.accounts.views import COO_ROLE_NAME, _manager_reporting_candidates


class MyProfileReportingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.coo = make_user('mp.coo@test.com', role=make_role(COO_ROLE_NAME, can_manage_team=False),
                             employee_id='MPCOO', full_name='Chief Ops', branch='Delhi HQ')
        self.hr = make_user('mp.hr@test.com', role=make_role('hr_admin'), employee_id='MPHR',
                            full_name='Branch HR', branch='Suryapet')
        self.manager_role = make_role('mp_manager', can_manage_team=True)
        self.manager = make_user('mp.mgr@test.com', role=self.manager_role, employee_id='MPMGR',
                                 full_name='Branch Manager', branch='Suryapet')
        self.employee = make_user('mp.emp@test.com', role=make_role('mp_employee'), employee_id='MPEMP',
                                  full_name='Staff One', branch='Suryapet')

    def _me(self, user):
        api = APIClient()
        _login(api, user.email)
        resp = api.get(reverse('my-profile'))
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['data']

    def test_manager_sees_own_reporting_manager_and_approver(self):
        self.manager.reporting_manager = self.coo
        self.manager.reporting_approver = self.hr
        self.manager.hr = self.hr
        self.manager.save(update_fields=['reporting_manager', 'reporting_approver', 'hr'])
        data = self._me(self.manager)
        # Before the fix reporting_manager came back null for every Manager role.
        self.assertEqual(data['reporting_manager'], {'id': 'MPCOO', 'name': 'Chief Ops'})
        self.assertEqual(data['reporting_approver'], {'id': 'MPHR', 'name': 'Branch HR'})
        self.assertEqual(data['hr'], {'id': 'MPHR', 'name': 'Branch HR'})

    def test_employee_reporting_fields_unchanged(self):
        self.employee.reporting_manager = self.manager
        self.employee.reporting_approver = self.hr
        self.employee.save(update_fields=['reporting_manager', 'reporting_approver'])
        data = self._me(self.employee)
        self.assertEqual(data['reporting_manager'], {'id': 'MPMGR', 'name': 'Branch Manager'})
        self.assertEqual(data['reporting_approver'], {'id': 'MPHR', 'name': 'Branch HR'})

    def test_unassigned_relationships_are_null(self):
        for user in (self.manager, self.employee):
            data = self._me(user)
            self.assertEqual((data['reporting_manager'], data['reporting_approver'], data['hr']), (None, None, None))

    def test_profile_read_does_not_change_assignments(self):
        self.manager.reporting_manager = self.coo
        self.manager.save(update_fields=['reporting_manager'])
        self._me(self.manager)
        self.manager.refresh_from_db()
        self.assertEqual((self.manager.reporting_manager_id, self.manager.reporting_approver_id), (self.coo.pk, None))


class ManagerReportingHierarchyTests(TestCase):
    """Who may be a Manager's Reporting Manager / Approver — unchanged by the profile fix."""

    def setUp(self):
        cache.clear()
        mk = lambda email, role, branch: make_user(email, role=role, employee_id=email.split('@')[0][:20],
                                                    full_name=email.split('@')[0], branch=branch)
        self.coo = mk('h.coo@test.com', make_role(COO_ROLE_NAME, can_manage_team=False), 'Delhi HQ')
        self.admin_head = mk('h.adminhead@test.com', make_role('admin_head'), 'Delhi HQ')
        self.hr_same = mk('h.hr.same@test.com', make_role('hr_admin'), 'Suryapet')
        self.hr_other = mk('h.hr.other@test.com', make_role('hr'), 'Hyderabad')
        self.ba_same = mk('h.ba.same@test.com', make_role('branch_admin'), 'Suryapet')
        self.ba_other = mk('h.ba.other@test.com', make_role('branch_admin'), 'Hyderabad')
        self.sysadmin = mk('h.sys@test.com', make_role('system_admin', permission_codenames=['settings.edit']), 'Suryapet')
        manager_role = make_role('h_manager', can_manage_team=True)
        self.manager = mk('h.mgr@test.com', manager_role, 'Suryapet')
        self.peer_manager = mk('h.peer@test.com', manager_role, 'Suryapet')

    def test_eligible_candidates_follow_the_approved_hierarchy(self):
        ids = set(_manager_reporting_candidates('Suryapet').values_list('pk', flat=True))
        self.assertTrue({self.coo.pk, self.admin_head.pk, self.hr_same.pk, self.ba_same.pk} <= ids)
        for not_eligible in (self.hr_other, self.ba_other, self.sysadmin, self.peer_manager, self.manager):
            self.assertNotIn(not_eligible.pk, ids)

    def _assign(self, **fields):
        api = APIClient()
        _login(api, self.sysadmin.email)
        return api.put(reverse('employee-detail', kwargs={'employee_id': self.manager.employee_id}),
                       {k: str(v.pk) for k, v in fields.items()}, format='json')

    def test_assignment_rejects_self_system_admin_and_other_branch(self):
        self.assertEqual(self._assign(reporting_manager_id=self.manager).status_code, 400)
        self.assertEqual(self._assign(reporting_manager_id=self.sysadmin).status_code, 400)
        self.assertEqual(self._assign(reporting_approver_id=self.hr_other).status_code, 400)
        self.assertEqual(self._assign(reporting_approver_id=self.peer_manager).status_code, 400)
        self.manager.refresh_from_db()
        self.assertEqual((self.manager.reporting_manager_id, self.manager.reporting_approver_id), (None, None))

    def test_assignment_accepts_coo_and_same_branch_hr(self):
        resp = self._assign(reporting_manager_id=self.coo, reporting_approver_id=self.hr_same)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual((self.manager.reporting_manager_id, self.manager.reporting_approver_id),
                         (self.coo.pk, self.hr_same.pk))
