"""
Regression test for QA #68 — PATCH /api/employees/{id}/ used to support
ONLY the is_active activate/deactivate toggle: any other partial update
(e.g. correcting phone/email/address/DOB) hit `if 'is_active' not in
request.data: return error('is_active field is required.')` and 400'd
immediately, even though PUT already had full field-by-field validation
for exactly these fields. PATCH now delegates to that same
EmployeeDetailView._update_fields() logic whenever the body doesn't carry
`is_active`, while the is_active toggle itself keeps working unchanged.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


class EmployeeDetailPatchPartialUpdateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_patch_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-patch@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_patch_test', permission_codenames=[])
        self.employee = make_user(
            'employee-patch@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Pat Chester', phone='9876543210', employee_id='EMPPATCH01',
        )
        self.client.force_authenticate(user=self.hr_user)

    def test_patch_without_is_active_updates_other_fields_instead_of_erroring(self):
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'phone': '9123456780'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9123456780')

    def test_patch_is_active_still_toggles_status_as_before(self):
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'is_active': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)

    def test_patch_with_no_recognised_fields_still_errors_same_as_put(self):
        resp = self.client.patch(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


class EmployeeDetailPatchRoleLookupTests(TestCase):
    """UAT: Edit full record > Employment sent the Role's numeric id and failed with 'Role "4" does not exist'."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_admin_role_lookup', permission_codenames=['employees.edit', 'employees.view'])
        self.client.force_authenticate(user=make_user('hr-role@test.com', role=hr_role, password='TestPass123!'))
        self.target_role = make_role('employee_role_lookup', permission_codenames=[])
        self.employee = make_user(
            'employee-role@test.com', role=make_role('old_role_lookup', permission_codenames=[]),
            password='TestPass123!', full_name='Role Tester', phone='9876543211', employee_id='EMPROLE01',
        )

    def _patch_role(self, value):
        return self.client.patch(reverse('employee-detail', args=[self.employee.employee_id]), {'role': value}, format='json')

    def test_role_accepted_by_numeric_id(self):
        resp = self._patch_role(str(self.target_role.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, self.target_role)

    def test_role_accepted_by_name(self):
        resp = self._patch_role(self.target_role.name)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, self.target_role)

    def test_unknown_role_id_still_rejected(self):
        resp = self._patch_role('999999')
        self.assertEqual(resp.status_code, 400)


class EmployeeDetailPutEmploymentRoleTests(TestCase):
    """UAT (Deepak EMP00055 / Arjun EMP00006): Edit full record > Employment PUT with the existing Employee role
    rejected as 'Role "4" does not exist' and nothing persisted."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_put_role', permission_codenames=['employees.edit', 'employees.view'])
        self.client.force_authenticate(user=make_user('hr-put@test.com', role=hr_role, password='TestPass123!'))
        self.employee_role = make_role('employee_put_role', permission_codenames=[])
        self.manager = make_user('mgr-put@test.com', role=make_role('mgr_put_role', permission_codenames=[]),
                                 full_name='Rakesh Manager', employee_id='EMPMGR01')
        # An imported employee: onboarding not complete, no role yet.
        self.employee = make_user(
            'imported-put@test.com', role=make_role('imported_put_role', permission_codenames=[]),
            full_name='Imported Person', phone='9876500001', employee_id='EMPIMP01',
            onboarding_status='draft',
        )

    def _put(self, role):
        payload = {
            'employee_type': 'Permanent', 'role': role, 'reporting_manager_id': str(self.manager.pk),
            'dotted_line_manager_id': '', 'work_location': 'Hyderabad', 'work_mode': 'office',
            'probation_period_months': '6', 'notice_period_days': '30',
        }
        return self.client.put(reverse('employee-detail', args=[self.employee.employee_id]), payload, format='json')

    def test_put_full_employment_payload_with_role_id_string_persists(self):
        resp = self._put(str(self.employee_role.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, self.employee_role)
        self.assertEqual(self.employee.reporting_manager_id, self.manager.pk)
        self.assertEqual(self.employee.employee_type, 'Permanent')
        self.assertEqual(self.employee.work_location, 'Hyderabad')
        self.assertEqual(self.employee.notice_period_days, 30)

    def test_put_role_sent_as_json_number_persists(self):
        resp = self._put(self.employee_role.pk)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, self.employee_role)

    def test_put_unknown_role_rejected_and_nothing_persisted(self):
        old_role = self.employee.role
        resp = self._put('999999')
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, old_role)

    def test_put_privileged_role_still_blocked(self):
        privileged = make_role('privileged_put_role', permission_codenames=['settings.edit'])
        resp = self._put(str(privileged.pk))
        self.assertEqual(resp.status_code, 400)
        self.employee.refresh_from_db()
        self.assertNotEqual(self.employee.role, privileged)
