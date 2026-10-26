from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog


class EmployeeAuditTrailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employee = make_user(
            'audit-employee@test.com',
            employee_id='EMP-AUDIT-01',
            branch='Mumbai HQ',
        )
        self.client.force_authenticate(user=self.employee)

    def test_self_audit_trail_returns_actor_details(self):
        response = self.client.get(
            reverse('employee-audit-trail', args=[self.employee.employee_id]),
        )

        self.assertEqual(response.status_code, 200)
        rows = response.data['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actor_name'], self.employee.full_name)
        self.assertEqual(rows[0]['actor_email'], self.employee.email)
        self.assertEqual(AuditLog.objects.filter(
            user=self.employee,
            action='profile_viewed_self',
            object_id=str(self.employee.id),
        ).count(), 1)

    def test_audit_log_list_returns_actor_details(self):
        role = make_role('audit_viewer', permission_codenames=['audit.view'])
        viewer = make_user(
            'audit-viewer@test.com',
            role=role,
            employee_id='EMP-AUDIT-02',
            branch='Mumbai HQ',
        )
        AuditLog.objects.create(
            user=self.employee,
            action='employee_updated',
            module='employees',
            object_id=str(self.employee.id),
            branch='Mumbai HQ',
        )
        self.client.force_authenticate(user=viewer)

        response = self.client.get(reverse('audit-log-list'))

        self.assertEqual(response.status_code, 200)
        rows = response.data['data']['results']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actor_name'], self.employee.full_name)
        self.assertEqual(rows[0]['actor_role'], self.employee.designation or None)
