"""
UAT-012 — the Employee Directory frontend showed the literal string "CEO
Office" for ANY employee with no reporting_manager, including ordinary
employees whose manager simply hadn't been resolved (53 such employees in
the reported case), not just actual top-of-hierarchy managers.

The fix lives entirely on the frontend (apps/dashboard/employees/_data.ts's
reportingManagerDisplay() + a new noManagerByDesign flag), but it depends on
a backend contract that already existed and must not silently regress:
_employee_dict() (apps/accounts/views/shared.py) OMITS the `reporting_manager`
key entirely for a manager/chief (can_manage_team) — who genuinely has none
by design — but always INCLUDES it (with name: None when unset) for an
ordinary employee. These tests lock in that key-presence distinction.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


class ReportingManagerKeyPresenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.viewer_role = make_role('directory_viewer', permission_codenames=['employees.view'])
        self.viewer = make_user('rm-viewer@test.com', role=self.viewer_role, employee_id='EMP-RMV-01', branch='Mumbai HQ')
        self.client.force_authenticate(user=self.viewer)

    def _row_for(self, response, employee_id):
        rows = response.data['data']['results']
        match = [r for r in rows if r['employee_id'] == employee_id]
        self.assertEqual(len(match), 1, f'expected exactly one row for {employee_id}')
        return match[0]

    def test_ordinary_employee_with_no_manager_includes_reporting_manager_with_null_name(self):
        employee = make_user('rm-ordinary@test.com', employee_id='EMP-RMV-02', branch='Mumbai HQ')
        self.assertIsNone(employee.reporting_manager_id)

        response = self.client.get(reverse('employee-list-create'))

        self.assertEqual(response.status_code, 200)
        row = self._row_for(response, employee.employee_id)
        self.assertIn('reporting_manager', row)
        self.assertIsNone(row['reporting_manager']['name'])

    def test_manager_role_employee_omits_reporting_manager_key_entirely(self):
        manager_role = make_role('team_manager', permission_codenames=[], can_manage_team=True)
        manager = make_user('rm-manager@test.com', role=manager_role, employee_id='EMP-RMV-03', branch='Mumbai HQ')

        response = self.client.get(reverse('employee-list-create'))

        self.assertEqual(response.status_code, 200)
        row = self._row_for(response, manager.employee_id)
        self.assertNotIn('reporting_manager', row)

    def test_employee_with_resolved_manager_includes_the_manager_name(self):
        manager_role = make_role('team_manager2', permission_codenames=[], can_manage_team=True)
        manager = make_user('rm-manager2@test.com', role=manager_role, employee_id='EMP-RMV-04', branch='Mumbai HQ')
        employee = make_user('rm-reports@test.com', employee_id='EMP-RMV-05', branch='Mumbai HQ')
        employee.reporting_manager = manager
        employee.save(update_fields=['reporting_manager'])

        response = self.client.get(reverse('employee-list-create'))

        self.assertEqual(response.status_code, 200)
        row = self._row_for(response, employee.employee_id)
        self.assertIn('reporting_manager', row)
        self.assertEqual(row['reporting_manager']['name'], manager.full_name)
