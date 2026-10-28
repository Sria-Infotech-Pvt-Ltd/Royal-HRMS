"""UAT-010: the same email or mobile as an existing employee (or another open draft) is caught at hire, with a clear message."""
import datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import HireAction, OrgUnit, Position
from apps.accounts.services_hire_duplicates import employee_status_label
from apps.hrms.models import SEP_APPROVED, SeparationRequest


class HireDuplicateTests(TestCase):
    def setUp(self):
        role = make_role('hr_dup_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-dup@test.com', role=role)
        unit = OrgUnit.objects.create(name='Engineering')
        self.position = Position.objects.create(org_unit=unit, title='Engineer', grade='L2')
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)
        self.existing = make_user(
            'already.here@test.com', employee_id='EMPDUP001', phone='+91 98765 43210', onboarding_status='complete',
        )

    def _draft(self):
        return HireAction.objects.create(
            reason=HireAction.REASON_NEW_POSITION, effective_from=datetime.date.today(), position=self.position, created_by=self.hr_user,
        )

    def _patch(self, action, body):
        return self.client.patch(reverse('hire-action-detail', args=[action.pk]), body, format='json')

    def test_same_email_is_refused_inline_naming_the_employee_and_status(self):
        response = self._patch(self._draft(), {'email': 'Already.Here@test.com'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['data']['email'], 'This email already belongs to EMPDUP001 (active).')

    def test_same_mobile_in_any_format_is_refused(self):
        response = self._patch(self._draft(), {'phone': '9876543210'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['data']['phone'], 'This mobile number already belongs to EMPDUP001 (active).')

    def test_a_clean_email_and_mobile_pass(self):
        response = self._patch(self._draft(), {'email': 'new.person@test.com', 'phone': '9123456789'})
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()['data']['warnings'], [])

    def test_an_exited_employee_is_a_warning_not_a_block(self):
        make_user('gone@test.com', employee_id='EMPDUP002', is_active=False)
        response = self._patch(self._draft(), {'email': 'gone@test.com'})
        self.assertEqual(response.status_code, 200, response.json())
        warning = response.json()['data']['warnings'][0]
        self.assertEqual((warning['field'], warning['severity']), ('email', 'warning'))
        self.assertIn('EMPDUP002', warning['message'])
        self.assertIn('rehire', warning['message'])

    def test_another_open_draft_with_the_same_email_is_refused_but_your_own_resave_is_fine(self):
        mine, other = self._draft(), self._draft()
        self.assertEqual(self._patch(mine, {'email': 'twice@test.com'}).status_code, 200)
        self.assertEqual(self._patch(mine, {'email': 'twice@test.com'}).status_code, 200)  # saving the same draft again
        refused = self._patch(other, {'email': 'twice@test.com'})
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.json()['data']['email'], 'Another open hire draft already uses this email.')

    def test_completion_checks_again_on_the_server(self):
        draft = self._draft()
        HireAction.objects.filter(pk=draft.pk).update(
            employment_type='Permanent', reserved_employee_id='EMPDUPR1',
            draft_data={'first_name': 'A', 'last_name': 'B', 'email': 'already.here@test.com', 'branch': 'Kondapur'},
        )
        response = self.client.post(reverse('hire-action-complete', args=[draft.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('EMPDUP001', response.json()['message'])

    def test_status_labels(self):
        self.assertEqual(employee_status_label(self.existing), 'active')
        SeparationRequest.objects.create(
            employee=self.existing, separation_type='resignation', request_date=datetime.date.today(),
            proposed_last_working_day=datetime.date.today() + datetime.timedelta(days=10), status=SEP_APPROVED,
        )
        self.assertEqual(employee_status_label(self.existing), 'notice period')


class DuplicateLoginEmailReportTests(TestCase):
    def test_reports_case_only_duplicates_without_printing_emails(self):
        make_user('Same.Person@test.com', employee_id='EMPCASE01')
        make_user('same.person@test.com', employee_id='EMPCASE02')
        make_user('different@test.com', employee_id='EMPCASE03')
        out = StringIO()
        call_command('report_duplicate_login_emails', stdout=out)
        text = out.getvalue()
        self.assertIn('1 duplicate group(s)', text)
        self.assertIn('EMPCASE01', text)
        self.assertNotIn('@', text)
