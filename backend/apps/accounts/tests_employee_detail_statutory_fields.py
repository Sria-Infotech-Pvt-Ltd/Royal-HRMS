"""
Regression test for the "Edit full record" modal's Statutory & accounts
section (Phase 6B frontend work) needing pan_number/aadhaar_number/
pf_covered/esi_covered/passport_number/passport_expiry writable through
PUT /api/employees/{id}/ — these are real EmployeeProfileSerializer
fields (already used by the Hire Wizard's pre-employee draft) but had no
post-hire write path at all until _PROFILE_FIELD_KEYS was extended to
include them. Same bug class as uan_number/esi_number before (see
tests_employee_detail_patch_partial_update.py's own docstring for that
precedent).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile


class EmployeeDetailStatutoryFieldsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_statutory_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-statutory@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_statutory_test', permission_codenames=[])
        self.employee = make_user(
            'employee-statutory@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Stat Utory', employee_id='EMPSTAT01',
        )
        self.client.force_authenticate(user=self.hr_user)

    def test_put_saves_pan_aadhaar_pf_esi_passport(self):
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {
                'pan_number': 'ABCDE1234F', 'aadhaar_number': '123456789012',
                'pf_covered': True, 'esi_covered': True,
                'passport_number': 'P1234567', 'passport_expiry': '2030-01-01',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.employee)
        self.assertEqual(profile.pan_number, 'ABCDE1234F')
        self.assertEqual(profile.aadhaar_number, '123456789012')
        self.assertTrue(profile.pf_covered)
        self.assertTrue(profile.esi_covered)
        self.assertEqual(profile.passport_number, 'P1234567')

    def test_put_saves_account_type_and_name_as_per_aadhar(self):
        """UAT-023: account_type/name_as_per_aadhar were already whitelisted
        in _PROFILE_FIELD_KEYS but the Edit-record modal never sent them, so
        they could be captured at hire yet never corrected afterward."""
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'account_type': 'current', 'name_as_per_aadhar': 'Stat Utory Kumar'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.employee)
        self.assertEqual(profile.account_type, 'current')
        self.assertEqual(profile.name_as_per_aadhar, 'Stat Utory Kumar')

    def test_omitting_statutory_fields_leaves_existing_values_unchanged(self):
        EmployeeProfile.objects.update_or_create(user=self.employee, defaults={'pan_number': 'ZZZZZ9999Z'})
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'uan_number': '999999999999'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.employee)
        self.assertEqual(profile.pan_number, 'ZZZZZ9999Z')
        self.assertEqual(profile.uan_number, '999999999999')

    def test_put_saves_core_skills_and_certifications(self):
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'core_skills': 'React, payroll operations', 'certifications': 'AWS SA, 2021'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = EmployeeProfile.objects.get(user=self.employee)
        self.assertEqual(profile.core_skills, 'React, payroll operations')
        self.assertEqual(profile.certifications, 'AWS SA, 2021')

    def test_put_and_get_support_edit_record_identity_fields(self):
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {
                'salutation': 'Ms.', 'display_name': 'Ms. Emp Test',
                'nationality': 'Indian', 'place_of_birth': 'Pune',
                'father_name': 'Test Father', 'mother_name': 'Test Mother',
                'languages_known': 'English, Hindi',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        profile = EmployeeProfile.objects.get(user=self.employee)
        self.assertEqual(profile.display_name, 'Ms. Emp Test')
        self.assertEqual(profile.nationality, 'Indian')
        self.assertEqual(profile.place_of_birth, 'Pune')
        self.assertEqual(profile.father_name, 'Test Father')
        self.assertEqual(profile.mother_name, 'Test Mother')
        self.assertEqual(profile.languages_known, 'English, Hindi')

        resp = self.client.get(reverse('employee-detail', args=[self.employee.employee_id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        details = resp.data['data']['profile']
        self.assertEqual(details['salutation'], 'Ms.')
        self.assertEqual(details['display_name'], 'Ms. Emp Test')
        self.assertEqual(details['nationality'], 'Indian')
        self.assertEqual(details['place_of_birth'], 'Pune')
        self.assertEqual(details['father_name'], 'Test Father')
        self.assertEqual(details['mother_name'], 'Test Mother')
        self.assertEqual(details['languages_known'], 'English, Hindi')


class EmployeeDetailBankEpfReadTests(TestCase):
    """UAT-023: GET /api/employees/{id}/ writes uan_number/esi_number/
    name_as_per_aadhar/account_type/bank_branch_name into the profile at
    hire (_apply_wizard_records -> _PROFILE_FIELDS already covers all of
    these) but _employee_dict()'s profile_data never included uan_number,
    esi_number, or name_as_per_aadhar in its read-side output at all -- so
    the Profile page's Bank/EPF card showed them blank no matter what was
    actually stored. account_number/ifsc_code must stay masked on this
    same endpoint; account_type/bank_branch_name were already correctly
    returned (not masked, not PII-tier) and must keep working."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_bank_epf_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-bank-epf@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_bank_epf_test', permission_codenames=[])
        self.employee = make_user(
            'employee-bank-epf@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Bank Epf', employee_id='EMPBANK01',
        )
        EmployeeProfile.objects.update_or_create(
            user=self.employee,
            defaults={
                'account_number': '1234567890123', 'ifsc_code': 'HDFC0001234',
                'account_type': 'current', 'bank_branch_name': 'Chennai',
                'uan_number': '100200300400', 'esi_number': '1122334455',
                'name_as_per_aadhar': 'Bank Epf',
            },
        )
        self.client.force_authenticate(user=self.hr_user)

    def test_get_returns_uan_esi_and_name_as_per_aadhar(self):
        resp = self.client.get(reverse('employee-detail', args=[self.employee.employee_id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = resp.data['data']['profile']
        self.assertEqual(profile['uan_number'], '100200300400')
        self.assertEqual(profile['esi_number'], '1122334455')
        self.assertEqual(profile['name_as_per_aadhar'], 'Bank Epf')
        self.assertEqual(profile['account_type'], 'current')
        self.assertEqual(profile['bank_branch_name'], 'Chennai')

    def test_account_number_and_ifsc_stay_masked_on_this_endpoint(self):
        resp = self.client.get(reverse('employee-detail', args=[self.employee.employee_id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        profile = resp.data['data']['profile']
        self.assertEqual(profile['account_number_masked'], '••••0123')
        self.assertNotIn('1234567890123', str(profile))
        self.assertEqual(profile['ifsc_code_masked'], '•' * len('HDFC0001234'))
        self.assertNotIn('HDFC0001234', str(profile))


class EmployeeDetailEmploymentFieldsTests(TestCase):
    """Regression test for the Edit-record modal's Employment section
    needing work_mode/probation_period_months/notice_period_days/
    dotted_line_manager_id writable through PUT /api/employees/{id}/ —
    real User columns (added for the Hire Wizard's Employment step) with
    no post-hire write path through this view until now."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_employment_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-employment@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_employment_test', permission_codenames=[])
        self.employee = make_user(
            'employee-employment@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Emp Loyment', employee_id='EMPEMPL01',
        )
        self.manager = make_user(
            'manager-employment@test.com', password='TestPass123!', full_name='Dotted Manager', employee_id='EMPMGR01',
        )
        self.client.force_authenticate(user=self.hr_user)

    def test_put_saves_work_mode_probation_notice_and_dotted_line_manager(self):
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {
                'work_mode': 'hybrid', 'probation_period_months': 6, 'notice_period_days': 60,
                'dotted_line_manager_id': str(self.manager.id),
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.work_mode, 'hybrid')
        self.assertEqual(self.employee.probation_period_months, 6)
        self.assertEqual(self.employee.notice_period_days, 60)
        self.assertEqual(self.employee.dotted_line_manager_id, self.manager.id)

    def test_dotted_line_manager_cannot_be_self(self):
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'dotted_line_manager_id': str(self.employee.id)},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_clearing_dotted_line_manager(self):
        self.employee.dotted_line_manager = self.manager
        self.employee.save(update_fields=['dotted_line_manager'])
        resp = self.client.put(
            reverse('employee-detail', args=[self.employee.employee_id]),
            {'dotted_line_manager_id': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.dotted_line_manager_id)
