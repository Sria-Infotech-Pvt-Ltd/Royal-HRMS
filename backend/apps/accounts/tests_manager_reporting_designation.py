"""
Manager Reporting Manager / Reporting Approver eligibility by approved
designation (in addition to the existing role rules): exact normalized
match, company-wide vs own-branch scope, leave.approve required for
designation-only candidates, and a COO / CMD Manager not offered their
branch's designation-based HR candidates.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from apps.accounts.views import _manager_reporting_candidates, _normalize_designation, _resolve_rule_approver


class DesignationEligibilityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.approver_mgr_role = make_role('d_manager', can_manage_team=True, permission_codenames=['leave.approve'])
        self.approver_emp_role = make_role('d_emp_approve', permission_codenames=['leave.approve'])
        self.plain_role = make_role('d_employee')
        self.n = 0

        # Role-based candidate with no designation (unchanged behaviour).
        self.ba = self.mk(make_role('branch_admin'), 'Surat', '')
        # Designation-only candidates.
        self.coo = self.mk(self.approver_mgr_role, 'Surat', 'COO')
        self.cmd = self.mk(self.approver_emp_role, 'Surat', 'CMD')
        self.chairman = self.mk(self.approver_emp_role, 'Delhi', 'Chairman & Managing Director (CMD)')
        self.hr_mgr = self.mk(self.approver_mgr_role, 'Surat', 'Hr. Manager')
        self.hr_head = self.mk(self.approver_emp_role, 'Surat', ' hr   HEAD ')
        self.hr_mgr_other = self.mk(self.approver_mgr_role, 'Hyderabad', 'HR Manager')
        # Never eligible.
        self.coordinator = self.mk(self.approver_mgr_role, 'Surat', 'Hr. Coordinator')
        self.partial = self.mk(self.approver_mgr_role, 'Surat', 'HR Manager Assistant')
        self.ta_mgr = self.mk(self.approver_mgr_role, 'Surat', 'Talent Acquisition Manager')
        self.coo_no_perm = self.mk(self.plain_role, 'Surat', 'COO')
        self.coo_inactive = self.mk(self.approver_mgr_role, 'Surat', 'COO', is_active=False)
        self.sysadmin = self.mk(make_role('system_admin', permission_codenames=['settings.edit']), 'Surat', 'COO')
        # Role and designation both match: listed once.
        self.hr_admin_both = self.mk(make_role('hr_admin'), 'Surat', 'HR Admin Manager')

        self.manager = self.mk(self.approver_mgr_role, 'Surat', 'Team Lead')
        self.coo_manager = self.coo  # a Manager whose own designation is company-wide

    def mk(self, role, branch, designation, **extra):
        self.n += 1
        return make_user(f'd{self.n}@test.com', role=role, employee_id=f'D{self.n:03d}',
                         full_name=f'Person {self.n}', branch=branch, designation=designation, **extra)

    def ids(self, branch, designation=''):
        return list(_manager_reporting_candidates(branch, designation).values_list('pk', flat=True))

    def test_normalization(self):
        self.assertEqual(_normalize_designation(' Hr.  MANAGER '), 'hr manager')
        self.assertEqual(_normalize_designation('Chairman & Managing Director (CMD)'), 'chairman & managing director (cmd)')
        self.assertEqual(_normalize_designation(None), '')

    def test_role_and_designation_rules_combined(self):
        ids = self.ids('Surat', 'Team Lead')
        for eligible in (self.ba, self.coo, self.cmd, self.chairman, self.hr_mgr, self.hr_head, self.hr_admin_both):
            self.assertIn(eligible.pk, ids)
        for excluded in (self.hr_mgr_other, self.coordinator, self.partial, self.ta_mgr,
                         self.coo_no_perm, self.coo_inactive, self.sysadmin):
            self.assertNotIn(excluded.pk, ids)
        self.assertEqual(len(ids), len(set(ids)))  # duplicates removed

    def test_company_wide_designations_cross_branches(self):
        ids = self.ids('Hyderabad')
        self.assertTrue({self.coo.pk, self.cmd.pk, self.chairman.pk, self.hr_mgr_other.pk} <= set(ids))
        for other_branch in (self.hr_mgr, self.hr_head, self.ba):
            self.assertNotIn(other_branch.pk, ids)

    def test_company_wide_manager_not_offered_branch_designation_candidates(self):
        ids = self.ids('Surat', ' Coo ')
        self.assertNotIn(self.hr_mgr.pk, ids)
        self.assertNotIn(self.hr_head.pk, ids)
        # Role-based and company-wide candidates are unaffected.
        self.assertTrue({self.ba.pk, self.hr_admin_both.pk, self.cmd.pk} <= set(ids))

    def test_dropdown_endpoint_matches_rule(self):
        api = APIClient()
        _login(api, self.sysadmin.email)
        url = reverse('employee-manager-list')
        resp = api.get(url, {'manager_approvers': '1', 'branch': 'Surat', 'designation': 'Team Lead'})
        self.assertEqual(resp.status_code, 200, resp.data)
        returned = {row['id'] for row in resp.data['data']}
        self.assertEqual(returned, {str(pk) for pk in self.ids('Surat', 'Team Lead')})
        resp = api.get(url, {'manager_approvers': '1', 'branch': 'Surat', 'designation': 'COO'})
        self.assertNotIn(str(self.hr_mgr.pk), {row['id'] for row in resp.data['data']})

    def _put(self, employee, **fields):
        api = APIClient()
        _login(api, self.sysadmin.email)
        return api.put(reverse('employee-detail', kwargs={'employee_id': employee.employee_id}),
                       {k: str(v.pk) for k, v in fields.items()}, format='json')

    def test_save_accepts_designation_candidates(self):
        resp = self._put(self.manager, reporting_manager_id=self.hr_mgr, reporting_approver_id=self.cmd)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.manager.refresh_from_db()
        self.assertEqual((self.manager.reporting_manager_id, self.manager.reporting_approver_id),
                         (self.hr_mgr.pk, self.cmd.pk))

    def test_save_rejects_ineligible(self):
        for field, person in (('reporting_manager_id', self.hr_mgr_other),
                              ('reporting_approver_id', self.coo_no_perm),
                              ('reporting_manager_id', self.partial),
                              ('reporting_approver_id', self.coordinator)):
            self.assertEqual(self._put(self.manager, **{field: person}).status_code, 400, (field, person.designation))
        # COO Manager: own-branch HR Manager hidden and rejected; self rejected.
        self.assertEqual(self._put(self.coo_manager, reporting_manager_id=self.hr_mgr).status_code, 400)
        self.assertEqual(self._put(self.coo_manager, reporting_approver_id=self.coo_manager).status_code, 400)
        self.assertEqual(self._put(self.coo_manager, reporting_manager_id=self.cmd).status_code, 200)

    def test_reporting_manager_patch_endpoint_uses_same_rule(self):
        api = APIClient()
        _login(api, self.sysadmin.email)
        url = reverse('employee-reporting-manager', kwargs={'employee_id': self.manager.employee_id})
        self.assertEqual(api.patch(url, {'reporting_manager_id': str(self.hr_mgr_other.pk)}, format='json').status_code, 400)
        self.assertEqual(api.patch(url, {'reporting_manager_id': str(self.hr_head.pk)}, format='json').status_code, 200)

    def test_approval_matrix_accepts_designation_reporting_manager(self):
        self.manager.reporting_manager = self.cmd  # employee role, eligible by designation
        self.assertEqual(_resolve_rule_approver(self.approver_mgr_role, self.manager), self.cmd)
        self.manager.reporting_manager = self.coordinator  # Manager role: accepted as before
        self.assertEqual(_resolve_rule_approver(self.approver_mgr_role, self.manager), self.coordinator)
        plain = self.mk(self.plain_role, 'Surat', 'Hr. Recruiter')
        self.manager.reporting_manager = plain
        self.assertIsNone(_resolve_rule_approver(self.approver_mgr_role, self.manager))

    def test_no_permissions_granted(self):
        self.assertFalse(self.plain_role.role_permissions.exists())
        self.coo_no_perm.refresh_from_db()
        self.assertNotIn(self.coo_no_perm.pk, self.ids('Surat'))
