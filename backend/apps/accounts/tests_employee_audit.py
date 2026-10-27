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


class AuditLogNullActorAndTargetTests(TestCase):
    """UAT bug: GET /settings/audit/ and GET /employees/<id>/audit-trail/
    both 500'd. The real crash (AuditLogSerializer.get_actor_role doing
    obj.user.role.display_name -- Role has since been removed from the
    schema entirely, and even before that, obj.user.role could be None)
    is already fixed, but there was no test locking it in. These cover
    every shape of row these two endpoints must render without crashing:
    a null actor, an actor with no designation set, several different
    module/action event types in the same page, and a blank object_id
    (e.g. a login event with no "about" record at all)."""

    def setUp(self):
        self.client = APIClient()
        self.employee = make_user(
            'audit-target@test.com', employee_id='EMP-AUDIT-03', branch='Mumbai HQ',
        )
        # settings.edit too -- several seeded rows below are branch-less
        # (system/login events), which a branch-scoped viewer correctly
        # cannot see (AuditLogListView's own branch filter, working as
        # intended); org-wide visibility is what these tests need to
        # compare every seeded row shape against the same response.
        self.viewer_role = make_role(
            'audit_viewer_mixed',
            permission_codenames=['audit.view', 'employees.view_sensitive', 'settings.edit'],
        )
        self.viewer = make_user(
            'audit-viewer-mixed@test.com', role=self.viewer_role,
            employee_id='EMP-AUDIT-04', branch='Mumbai HQ',
        )

    def _seed_mixed_events(self):
        # Null actor -- a system-triggered event, or one whose user row was
        # later deleted (the FK is SET_NULL for exactly this reason).
        AuditLog.objects.create(
            user=None, action='scheduled_cleanup', module='platform_core',
            object_id='', branch='',
        )
        # A real actor with no designation set at all.
        actor_no_designation = make_user(
            'audit-no-designation@test.com', employee_id='EMP-AUDIT-05',
            branch='Mumbai HQ', designation='',
        )
        AuditLog.objects.create(
            user=actor_no_designation, action='login', module='accounts',
            object_id='', branch='',
        )
        # Blank object_id -- no "about" target at all (login/logout shape).
        AuditLog.objects.create(
            user=self.viewer, action='login', module='accounts',
            object_id='', branch='',
        )
        # A real "about this employee" event, different module/action.
        AuditLog.objects.create(
            user=self.viewer, action='sensitive_reveal', module='employees',
            object_id=str(self.employee.id), changes={'fields': ['pan_number']},
            branch='Mumbai HQ',
        )
        AuditLog.objects.create(
            user=self.viewer, action='employee_updated', module='employees',
            object_id=str(self.employee.id), branch='Mumbai HQ',
        )

    def test_audit_log_list_renders_every_row_shape_without_crashing(self):
        self._seed_mixed_events()
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(reverse('audit-log-list'))

        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['results']
        self.assertGreaterEqual(len(rows), 5)

        by_action = {row['action']: row for row in rows}
        self.assertEqual(by_action['scheduled_cleanup']['actor_name'], 'System')
        self.assertIsNone(by_action['scheduled_cleanup']['actor_email'])
        self.assertIsNone(by_action['scheduled_cleanup']['actor_role'])

        login_rows = [r for r in rows if r['action'] == 'login']
        no_designation_row = next(r for r in login_rows if r['actor_email'] == 'audit-no-designation@test.com')
        self.assertIsNone(no_designation_row['actor_role'])

        # Multiple distinct module/action combinations all render fine together.
        modules = {row['module'] for row in rows}
        self.assertIn('employees', modules)
        self.assertIn('accounts', modules)
        self.assertIn('platform_core', modules)

    def test_employee_audit_trail_renders_null_actor_rows_without_crashing(self):
        AuditLog.objects.create(
            user=None, action='bulk_import_created', module='employees',
            object_id=str(self.employee.id), branch='Mumbai HQ',
        )
        AuditLog.objects.create(
            user=self.viewer, action='sensitive_reveal', module='employees',
            object_id=str(self.employee.id), changes={'fields': ['pan_number']},
            branch='Mumbai HQ',
        )
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(
            reverse('employee-audit-trail', args=[self.employee.employee_id]),
        )

        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']
        actions = {row['action'] for row in rows}
        self.assertIn('bulk_import_created', actions)
        self.assertIn('sensitive_reveal', actions)
        null_actor_row = next(r for r in rows if r['action'] == 'bulk_import_created')
        self.assertEqual(null_actor_row['actor_name'], 'System')
        self.assertIsNone(null_actor_row['actor_email'])
        self.assertIsNone(null_actor_row['actor_role'])

    def test_sensitive_reveal_appears_in_employee_audit_trail(self):
        # UAT-038 knock-on: the reveal action must actually show up here,
        # which only requires the endpoint itself not crashing AND the
        # frontend refetching -- this covers the backend half.
        self.client.force_authenticate(user=self.viewer)
        reveal = self.client.post(
            reverse('employee-reveal-sensitive', args=[self.employee.employee_id]),
            {'fields': ['pan_number']}, format='json',
        )
        self.assertEqual(reveal.status_code, 200, reveal.data)

        trail = self.client.get(
            reverse('employee-audit-trail', args=[self.employee.employee_id]),
        )
        self.assertEqual(trail.status_code, 200, trail.data)
        actions = {row['action'] for row in trail.data['data']}
        self.assertIn('sensitive_reveal', actions)
