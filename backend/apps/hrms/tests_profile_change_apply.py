"""Profile-change requests: an employee asks for a new value, HR / the System Admin approves and it is applied in one step."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile, User
from apps.hrms.models import HRHelpRequest
from apps.hrms.profile_change_fields import CHANGE_FIELDS, KIND_CHOICE, KIND_DATE, KIND_PHONE, KIND_PIN
from apps.notifications.models import Notification

REASON = 'The name on my documents is different'


def sample_value(spec) -> str:
    """A value that is valid for the field and different from a fresh record's."""
    if spec.kind == KIND_DATE:
        return '1990-05-17'
    if spec.kind == KIND_PHONE:
        return '9123456789'
    if spec.kind == KIND_PIN:
        return '500081'
    if spec.kind == KIND_CHOICE:
        return spec.choices[0][0]
    return 'Sample value'


def message(section: str, field: str, reason: str = REASON) -> str:
    return f'Section: {section}. Field to change: {field}. Reason: {reason}'


class ProfileChangeApplyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr = make_user('pcg-hr@test.com', role=make_role('pcg_hr', permission_codenames=['hr_help.respond']))
        self.admin = make_user('pcg-admin@test.com', role=make_role('pcg_admin', permission_codenames=['settings.edit']))
        self.employee = make_user(
            'pcg-emp@test.com', role=make_role('pcg_emp', permission_codenames=[]), full_name='Old Name', phone='9000000001',
            onboarding_status=User.ONBOARDING_COMPLETE, date_of_joining=datetime.date(2026, 3, 2),
        )
        self.create_url = reverse('hr-help-request-list')

    def _ask(self, section='Personal details', field='Full name', value='New Name', user=None, **extra):
        self.client.force_authenticate(user=user or self.employee)
        body = {'topic': 'profile_correction', 'priority': 'normal', 'message': message(section, field), **extra}
        if value is not None:
            body['change_new_value'] = value
        return self.client.post(self.create_url, body, format='json')

    def _ticket(self, **kwargs) -> HRHelpRequest:
        response = self._ask(**kwargs)
        self.assertEqual(response.status_code, 201, response.data)
        return HRHelpRequest.objects.get(pk=response.data['data']['id'])

    def _decide(self, user, ticket, decision, note=''):
        self.client.force_authenticate(user=user)
        return self.client.post(reverse('hr-help-decide-change', args=[ticket.id]), {'decision': decision, 'note': note}, format='json')

    # ── asking ────────────────────────────────────────────────────────────────────────────────────────
    def test_the_request_keeps_the_field_and_the_current_and_new_values(self):
        ticket = self._ticket()
        self.assertEqual((ticket.change_field, ticket.change_old_value, ticket.change_new_value), ('full_name', 'Old Name', 'New Name'))
        self.assertEqual(ticket.change_decision, '')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'Old Name')   # nothing is written until HR approves

    def test_every_field_with_a_new_value_is_accepted_when_the_value_is_valid(self):
        for spec in CHANGE_FIELDS:
            response = self._ask(section=spec.section, field=spec.label, value=sample_value(spec))
            self.assertEqual(response.status_code, 201, (spec.key, response.data))
            self.assertEqual(HRHelpRequest.objects.get(pk=response.data['data']['id']).change_field, spec.key)

    def test_a_field_that_needs_a_value_is_refused_without_one(self):
        self.assertEqual(self._ask(value=None).status_code, 400)
        self.assertEqual(self._ask(value='   ').status_code, 400)

    def test_bad_values_are_refused(self):
        self.assertEqual(self._ask(field='Date of birth', value='17-05-1990').status_code, 400)
        self.assertEqual(self._ask(field='Date of birth', value=(datetime.date.today() + datetime.timedelta(days=3)).isoformat()).status_code, 400)
        self.assertEqual(self._ask(section='Contact & address', field='Current PIN code', value='5000').status_code, 400)
        self.assertEqual(self._ask(section='Contact & address', field='Mobile number', value='12345').status_code, 400)
        self.assertEqual(self._ask(field='Gender', value='robot').status_code, 400)

    def test_a_value_equal_to_the_current_one_is_refused(self):
        self.assertEqual(self._ask(value='Old Name').status_code, 400)

    def test_a_mobile_number_used_by_someone_else_is_refused(self):
        make_user('pcg-other@test.com', role=make_role('pcg_other', permission_codenames=[]), phone='9111111111')
        self.assertEqual(self._ask(section='Contact & address', field='Mobile number', value='9111111111').status_code, 400)

    def test_fields_without_a_structured_flow_stay_plain_tickets(self):
        ticket = self._ticket(section='Bank details', field='IFSC code', value=None)
        self.assertEqual((ticket.change_field, ticket.change_new_value), ('', ''))
        ticket = self._ticket(section='Other', field='Other (describe in the reason)', value='ignored')
        self.assertEqual((ticket.change_field, ticket.change_new_value), ('', ''))

    # ── deciding ──────────────────────────────────────────────────────────────────────────────────────
    def test_hr_approves_and_the_name_changes_even_though_onboarding_is_complete(self):
        ticket = self._ticket()
        response = self._decide(self.hr, ticket, 'approve', 'Checked the ID card')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'New Name')
        self.assertEqual((ticket.status, ticket.change_decision, ticket.response), ('resolved', 'applied', 'Checked the ID card'))
        self.assertIsNotNone(ticket.change_applied_at)

    def test_approval_is_audited_with_before_and_after_and_the_employee_is_told(self):
        ticket = self._ticket()
        self._decide(self.hr, ticket, 'approve')
        entry = AuditLog.objects.get(action='employee_profile_corrected', object_id=str(self.employee.id))
        self.assertEqual(entry.changes['full_name'], {'from': 'Old Name', 'to': 'New Name'})
        note = Notification.objects.get(user=self.employee, reference_id='profile-change')
        self.assertIn('updated', note.title)

    def test_a_profile_field_is_written_to_the_profile(self):
        ticket = self._ticket(field='Date of birth', value='1990-05-17')
        self.assertEqual(self._decide(self.hr, ticket, 'approve').status_code, 200)
        self.assertEqual(EmployeeProfile.objects.get(user=self.employee).date_of_birth, datetime.date(1990, 5, 17))

    def test_a_mobile_number_is_stored_normalised(self):
        ticket = self._ticket(section='Contact & address', field='Mobile number', value='+91 98765 43210')
        self.assertEqual(self._decide(self.hr, ticket, 'approve').status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9876543210')

    def test_declining_needs_a_reason_and_changes_nothing(self):
        ticket = self._ticket()
        self.assertEqual(self._decide(self.hr, ticket, 'reject').status_code, 400)
        response = self._decide(self.hr, ticket, 'reject', 'No proof attached')
        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(self.employee.full_name, 'Old Name')
        self.assertEqual((ticket.status, ticket.change_decision), ('resolved', 'rejected'))
        self.assertIn('declined', Notification.objects.get(user=self.employee, reference_id='profile-change').title)

    def test_a_plain_employee_cannot_decide(self):
        ticket = self._ticket()
        self.assertEqual(self._decide(self.employee, ticket, 'approve').status_code, 403)

    def test_a_request_is_decided_only_once(self):
        ticket = self._ticket()
        self._decide(self.hr, ticket, 'approve')
        self.assertEqual(self._decide(self.hr, ticket, 'approve').status_code, 400)

    def test_the_joining_date_needs_a_system_admin(self):
        ticket = self._ticket(field='Date of joining', value='2025-03-02')
        refused = self._decide(self.hr, ticket, 'approve')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('System Admin', refused.data['message'])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.date_of_joining, datetime.date(2026, 3, 2))
        self.assertEqual(self._decide(self.admin, ticket, 'approve').status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.date_of_joining, datetime.date(2025, 3, 2))

    def test_a_ticket_without_a_value_cannot_be_applied(self):
        ticket = self._ticket(section='Bank details', field='IFSC code', value=None)
        self.assertEqual(self._decide(self.hr, ticket, 'approve').status_code, 400)

    def test_the_change_fields_list_describes_each_input(self):
        self.client.force_authenticate(user=self.employee)
        rows = self.client.get(reverse('hr-help-change-fields')).data['data']
        gender = next(row for row in rows if row['key'] == 'gender')
        self.assertEqual(gender['kind'], 'choice')
        self.assertIn('male', [choice['value'] for choice in gender['choices']])
        self.assertTrue(next(row for row in rows if row['key'] == 'date_of_joining')['full_access_only'])
