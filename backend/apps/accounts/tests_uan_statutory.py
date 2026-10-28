"""UAT-031: UAN is optional but must be 12 digits wherever it is captured, is stored, comes back masked, and is revealed only through the audited action."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile, HireAction, OrgUnit, Position

FULL_UAN = '123456789012'


class HireDraftUanTests(TestCase):
    def setUp(self):
        role = make_role('hr_uan_hire_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-uan-hire@test.com', role=role)
        unit = OrgUnit.objects.create(name='Engineering')
        position = Position.objects.create(org_unit=unit, title='Software Engineer', grade='L2')
        self.action = HireAction.objects.create(
            reason=HireAction.REASON_NEW_POSITION, effective_from=datetime.date.today(),
            position=position, created_by=self.hr_user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)
        self.url = reverse('hire-action-detail', args=[self.action.pk])

    def test_short_uan_is_rejected_and_not_stored(self):
        response = self.client.patch(self.url, {'uan_number': '123'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'UAN must be 12 digits')
        self.assertEqual(response.json()['data']['uan_number'], 'UAN must be 12 digits')
        self.action.refresh_from_db()
        self.assertNotIn('uan_number', self.action.draft_data)

    def test_non_digit_uan_is_rejected(self):
        response = self.client.patch(self.url, {'uan_number': '12345678901A'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_valid_and_blank_uan_are_accepted(self):
        self.assertEqual(self.client.patch(self.url, {'uan_number': FULL_UAN}, format='json').status_code, 200)
        self.action.refresh_from_db()
        self.assertEqual(self.action.draft_data['uan_number'], FULL_UAN)
        self.assertEqual(self.client.patch(self.url, {'uan_number': ''}, format='json').status_code, 200)


class EmployeeUanTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('hr_uan_emp_test', permission_codenames=['employees.edit', 'employees.view', 'employees.view_sensitive'])
        self.hr_user = make_user('hr-uan-emp@test.com', role=role)
        self.employee = make_user('uan.employee@test.com', employee_id='EMPUAN0001')
        EmployeeProfile.objects.create(user=self.employee, uan_number=FULL_UAN)
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)
        self.url = reverse('employee-detail', args=[self.employee.employee_id])

    def test_employee_api_returns_the_uan_masked_never_in_full(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['profile']['uan_masked'], '••••••••9012')
        self.assertNotIn(FULL_UAN, response.content.decode())

    def test_edit_record_rejects_a_bad_uan(self):
        response = self.client.put(self.url, {'uan_number': '123'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('UAN must be 12 digits', response.json()['message'])
        self.assertEqual(response.json()['data']['uan_number'], ['UAN must be 12 digits'])

    def test_saving_without_a_uan_does_not_wipe_the_stored_one(self):
        # What Edit full record sends when HR leaves the write-only UAN box empty: no uan_number key at all.
        response = self.client.put(self.url, {'work_location': 'Hyderabad'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.profile.uan_number, FULL_UAN)

    def test_full_uan_comes_only_from_the_audited_reveal(self):
        response = self.client.post(
            reverse('employee-reveal-sensitive', args=[self.employee.employee_id]),
            {'fields': ['uan_number']}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['uan_number'], FULL_UAN)
        entry = AuditLog.objects.filter(action='sensitive_reveal', object_id=str(self.employee.id)).first()
        self.assertEqual(entry.changes['fields'], ['uan_number'])
        self.assertEqual(entry.user_id, self.hr_user.id)


class WipedStatutoryIdsReportTests(TestCase):
    """Read-only report of employees whose UAN/ESI is empty now but was entered in their hire draft."""

    def _hired(self, email, code, draft_data, profile_uan='', profile_esi=''):
        unit = OrgUnit.objects.get_or_create(name='Engineering')[0]
        position = Position.objects.create(org_unit=unit, title=f'Engineer {code}', grade='L2')
        employee = make_user(email, employee_id=code)
        EmployeeProfile.objects.create(user=employee, uan_number=profile_uan, esi_number=profile_esi)
        HireAction.objects.create(
            reason=HireAction.REASON_NEW_POSITION, effective_from=datetime.date.today(), position=position,
            status=HireAction.STATUS_COMPLETED, created_employee=employee, draft_data=draft_data,
        )
        return employee

    def test_lists_only_cases_with_evidence_and_masks_the_values(self):
        import csv
        import os
        import tempfile
        from io import StringIO
        from django.core.management import call_command

        wiped = self._hired('wiped@test.com', 'EMPWIPE01', {'uan_number': '123456789012', 'esi_number': '5566778899'})
        self._hired('intact@test.com', 'EMPWIPE02', {'uan_number': '210987654321'}, profile_uan='210987654321')
        self._hired('never@test.com', 'EMPWIPE03', {})  # nothing was ever entered: not a case
        before = EmployeeProfile.objects.filter(user=wiped).values_list('uan_number', 'esi_number').get()

        handle, path = tempfile.mkstemp(suffix='.csv')
        os.close(handle)
        out = StringIO()
        call_command('report_wiped_statutory_ids', csv=path, stdout=out)
        with open(path, encoding='utf-8') as csv_file:
            content = csv_file.read()
        os.remove(path)
        rows = list(csv.DictReader(content.splitlines()))

        self.assertEqual(sorted((row['employee_id'], row['field']) for row in rows), [('EMPWIPE01', 'esi_number'), ('EMPWIPE01', 'uan_number')])
        self.assertIn('2 case(s)', out.getvalue())
        self.assertNotIn('123456789012', content)  # last four digits only, never the full number
        self.assertNotIn('5566778899', content)
        self.assertIn('9012', content)
        # read-only: nothing restored
        self.assertEqual(EmployeeProfile.objects.filter(user=wiped).values_list('uan_number', 'esi_number').get(), before)
