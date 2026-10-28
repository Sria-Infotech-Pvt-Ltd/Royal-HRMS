"""UAT-038: a "Reveal full values" is recorded, described in words, and shows in both the employee audit trail and Settings > Audit Log."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.audit_descriptions import describe_audit_event
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile


class RevealAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role(
            'hr_reveal_audit_test',
            permission_codenames=['employees.view', 'employees.view_sensitive', 'audit.view'],
        )
        # Branch-scoped HR (no settings.edit): sees only events whose target branch is theirs.
        self.hr_user = make_user('hr-reveal@test.com', role=role, full_name='Asha Admin', branch='Kondapur', employee_id='EMPREVEAL1')
        self.employee = make_user('reveal.employee@test.com', employee_id='EMPREVEAL2', branch='Kondapur')
        EmployeeProfile.objects.create(user=self.employee, pan_number='ABCDE1234F', account_number='123456789012')
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)

    def _reveal(self):
        return self.client.post(
            reverse('employee-reveal-sensitive', args=[self.employee.employee_id]),
            {'fields': ['pan_number', 'account_number']}, format='json', HTTP_USER_AGENT='unit-test-agent',
        )

    def test_reveal_writes_an_event_with_actor_fields_ip_and_agent(self):
        self.assertEqual(self._reveal().status_code, 200)
        event = AuditLog.objects.get(action='sensitive_reveal')
        self.assertEqual(event.user_id, self.hr_user.id)
        self.assertEqual(event.object_id, str(self.employee.id))
        self.assertEqual(event.changes['fields'], ['pan_number', 'account_number'])
        self.assertEqual(event.changes['user_agent'], 'unit-test-agent')
        self.assertEqual(event.branch, 'Kondapur')
        self.assertIsNotNone(event.created_at)

    def test_reveal_is_returned_by_the_employee_audit_trail_with_a_readable_description(self):
        self._reveal()
        rows = self.client.get(reverse('employee-audit-trail', args=[self.employee.employee_id])).json()['data']
        self.assertEqual(rows[0]['action'], 'sensitive_reveal')
        self.assertEqual(rows[0]['description'], 'Asha Admin revealed PAN, bank account')

    def test_reveal_is_returned_by_the_global_audit_log_for_branch_scoped_hr(self):
        self._reveal()
        body = self.client.get(reverse('audit-log-list'), {'module': 'employees'}).json()['data']
        reveals = [row for row in body['results'] if row['action'] == 'sensitive_reveal']
        self.assertEqual(len(reveals), 1)
        self.assertEqual(reveals[0]['description'], 'Asha Admin revealed PAN, bank account')

    def test_description_wording(self):
        self.assertEqual(
            describe_audit_event('Asha', 'employee_updated', {'employee_id': 'E1', 'full_name': 'Pat', 'phone': {'from': '1', 'to': '2'}}),
            'Asha updated mobile number',
        )
        self.assertEqual(describe_audit_event('Asha', 'login', {}), '')


class BranchScopedAuditTests(TestCase):
    """UAT-038 follow-up: branch HR sees audit events only for employees in their own branch (trail, reveal and global log)."""

    def setUp(self):
        cache.clear()
        role = make_role('hr_branch_audit_test', permission_codenames=['employees.view', 'employees.view_sensitive', 'audit.view'])
        self.hr_kondapur = make_user('hr-kondapur@test.com', role=role, full_name='Kondapur HR', branch='Kondapur', employee_id='EMPBA0001')
        self.here = make_user('here@test.com', employee_id='EMPBA0002', branch='Kondapur')
        self.there = make_user('there@test.com', employee_id='EMPBA0003', branch='Mulugu')
        for employee in (self.here, self.there):
            EmployeeProfile.objects.create(user=employee, pan_number='ABCDE1234F')
            AuditLog.objects.create(user=None, action='employee_updated', module='employees', object_id=str(employee.id), branch=employee.branch)
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_kondapur)

    def test_own_branch_employee_trail_is_visible(self):
        response = self.client.get(reverse('employee-audit-trail', args=[self.here.employee_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 1)

    def test_other_branch_employee_trail_is_not_found(self):
        response = self.client.get(reverse('employee-audit-trail', args=[self.there.employee_id]))
        self.assertEqual(response.status_code, 404)

    def test_other_branch_employee_cannot_be_revealed_so_no_event_leaks_either_way(self):
        response = self.client.post(
            reverse('employee-reveal-sensitive', args=[self.there.employee_id]), {'fields': ['pan_number']}, format='json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AuditLog.objects.filter(action='sensitive_reveal').exists())

    def test_global_audit_log_lists_only_own_branch_events(self):
        self.client.post(reverse('employee-reveal-sensitive', args=[self.here.employee_id]), {'fields': ['pan_number']}, format='json')
        rows = self.client.get(reverse('audit-log-list'), {'module': 'employees'}).json()['data']['results']
        object_ids = {row['object_id'] for row in rows}
        self.assertIn(str(self.here.id), object_ids)
        self.assertNotIn(str(self.there.id), object_ids)
        self.assertEqual({row['action'] for row in rows if row['object_id'] == str(self.here.id)}, {'employee_updated', 'sensitive_reveal'})
