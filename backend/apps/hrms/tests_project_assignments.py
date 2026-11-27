"""
Tests for admin-managed project assignments (Work Status):
  * assign / edit / extend / end through the API, with validation and the change history
  * who may view (self / manager / admin) and who may manage (admins with employees.edit only)
  * the daily job: completes finished assignments and sends one "ending soon" reminder per end date
  * running numbers never collide with ids old timesheet lines already use; one project name keeps one project_id
"""
from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import ProjectAssignment, ProjectAssignmentEvent
from apps.hrms.services_project_assignments import assign_project, project_id_for
from apps.hrms.services_project_notifications import run_daily_project_job
from apps.notifications.models import Notification

TODAY = timezone.localdate()


def _days(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


class AssignmentTestCase(TestCase):
    def setUp(self):
        cache.clear()
        plain = make_role('pa_plain')
        self.admin = make_user('pa-admin@test.com', role=make_role(
            'pa_admin', permission_codenames=['employees.view', 'employees.edit']), employee_id='EMP00030')
        self.manager = make_user('pa-mgr@test.com', role=make_role('pa_mgr', can_manage_team=True), employee_id='EMP00031')
        self.employee = make_user('pa-emp@test.com', role=plain, employee_id='EMP00032', reporting_manager=self.manager)
        self.stranger = make_user('pa-str@test.com', role=plain, employee_id='EMP00033')
        self.viewer = make_user('pa-view@test.com', role=make_role('pa_view', permission_codenames=['employees.view']),
                                employee_id='EMP00034')

    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user)
        return client

    def assign(self, user=None, code='EMP00032', **body):
        payload = {'project_name': 'Website Revamp', 'start_date': _days(-10), 'end_date': _days(30),
                   'work_mode': 'office', **body}
        return self.client_for(user or self.admin).post(reverse('work-status-assign', args=[code]), payload, format='json')

    def action(self, name, assignment_id, body, user=None, method='post'):
        url = reverse(f'work-status-assignment-{name}', args=['EMP00032', assignment_id])
        return getattr(self.client_for(user or self.admin), method)(url, body, format='json')

    def work_status(self, user, code=None):
        url = reverse('my-work-status') if code is None else reverse('employee-work-status', args=[code])
        return self.client_for(user).get(url)


class AssignTests(AssignmentTestCase):
    def test_admin_assigns_a_project_and_it_shows_as_current(self):
        response = self.assign(role='Developer')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data['data']['project_name'], response.data['data']['role']), ('Website Revamp', 'Developer'))
        data = self.work_status(self.admin, 'EMP00032').data['data']
        self.assertEqual([a['project_name'] for a in data['current']], ['Website Revamp'])
        self.assertTrue(data['can_manage'])
        self.assertEqual(data['current'][0]['last_change']['event_type'], 'created')

    def test_employee_and_manager_are_notified(self):
        self.assign()
        notified = set(Notification.objects.filter(notification_type='project_assigned').values_list('user_id', flat=True))
        self.assertEqual(notified, {self.employee.pk, self.manager.pk})

    def test_end_date_before_start_is_rejected(self):
        response = self.assign(start_date=_days(5), end_date=_days(1))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProjectAssignment.objects.exists())

    def test_work_mode_is_shown_with_its_proper_name(self):
        data = self.assign(work_mode='home').data['data']
        self.assertEqual((data['work_mode'], data['work_mode_display']), ('home', 'Work From Home (WFH)'))

    def test_client_location_needs_the_place(self):
        missing = self.assign(work_mode='client_site')
        self.assertEqual(missing.status_code, 400)
        self.assertIn('client location', missing.data['message'])
        ok = self.assign(work_mode='client_site', work_location='Client HQ, Hyderabad').data['data']
        self.assertEqual((ok['work_mode_display'], ok['work_location']), ('Client Location (On-site)', 'Client HQ, Hyderabad'))

    def test_unknown_work_mode_is_rejected(self):
        self.assertEqual(self.assign(work_mode='beach').status_code, 400)

    def test_both_dates_are_required(self):
        self.assertEqual(self.assign(end_date=None).status_code, 400)

    def test_several_projects_at_once_are_allowed_but_not_the_same_project_twice(self):
        self.assertEqual(self.assign().status_code, 201)
        self.assertEqual(self.assign(project_name='Mobile App').status_code, 201)
        duplicate = self.assign(project_name='website revamp', start_date=_days(0), end_date=_days(5))
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('already assigned', duplicate.data['message'])

    def test_non_admins_cannot_assign(self):
        for user in (self.manager, self.viewer, self.employee):
            self.assertEqual(self.assign(user=user).status_code, 404)
        self.assertFalse(ProjectAssignment.objects.exists())

    def test_cannot_assign_to_someone_who_has_left(self):
        type(self.employee).objects.filter(pk=self.employee.pk).update(is_active=False)
        self.assertEqual(self.assign().status_code, 400)

    def test_same_project_name_keeps_one_project_id(self):
        first = self.assign().data['data']
        other = self.assign(code='EMP00033', project_name='WEBSITE REVAMP').data['data']
        self.assertEqual(first['project_id'], other['project_id'])
        self.assertNotEqual(project_id_for('Something Else'), first['project_id'])


class ChangeTests(AssignmentTestCase):
    def setUp(self):
        super().setUp()
        self.assignment_id = self.assign().data['data']['assignment_id']

    def row(self) -> ProjectAssignment:
        return ProjectAssignment.objects.get(assignment_id=self.assignment_id)

    def test_extend_moves_the_end_date_and_records_the_reason(self):
        response = self.action('extend', self.assignment_id, {'end_date': _days(90), 'reason': 'Phase 2'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.row().assignment_end_date.isoformat(), _days(90))
        event = self.row().events.first()
        self.assertEqual((event.event_type, event.reason), ('extended', 'Phase 2'))

    def test_extend_must_move_the_date_later(self):
        self.assertEqual(self.action('extend', self.assignment_id, {'end_date': _days(10)}).status_code, 400)

    def test_extend_reopens_a_completed_assignment(self):
        self.action('end', self.assignment_id, {})
        self.assertEqual(self.row().assignment_status, 'completed')
        self.action('extend', self.assignment_id, {'end_date': _days(20)})
        self.assertEqual(self.row().assignment_status, 'active')

    def test_end_today_completes_it_and_it_leaves_current(self):
        response = self.action('end', self.assignment_id, {'reason': 'Client paused'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.row().assignment_status, self.row().assignment_end_date), ('completed', TODAY))
        data = self.work_status(self.admin, 'EMP00032').data['data']
        self.assertEqual((data['current'], data['history']['count']), ([], 1))

    def test_end_cannot_move_the_date_later(self):
        self.assertEqual(self.action('end', self.assignment_id, {'end_date': _days(60)}).status_code, 400)

    def test_switching_to_client_location_on_edit_needs_the_place(self):
        response = self.action('edit', self.assignment_id, {'work_mode': 'client_site'}, method='patch')
        self.assertEqual(response.status_code, 400)
        response = self.action('edit', self.assignment_id, {'work_mode': 'client_site', 'work_location': 'Pune'}, method='patch')
        self.assertEqual(response.status_code, 200, response.data)

    def test_edit_changes_fields_and_logs_the_diff(self):
        response = self.action('edit', self.assignment_id, {'role': 'Lead'}, method='patch')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.row().events.first().changes, {'role': ['', 'Lead']})

    def test_completed_assignment_cannot_be_edited(self):
        self.action('end', self.assignment_id, {})
        self.assertEqual(self.action('edit', self.assignment_id, {'role': 'Lead'}, method='patch').status_code, 400)

    def test_unknown_assignment_is_404(self):
        self.assertEqual(self.action('extend', 999999, {'end_date': _days(90)}).status_code, 404)

    def test_manager_cannot_change(self):
        self.assertEqual(self.action('end', self.assignment_id, {}, user=self.manager).status_code, 404)


class ViewPermissionTests(AssignmentTestCase):
    def setUp(self):
        super().setUp()
        self.assign()

    def test_employee_sees_own_projects_read_only(self):
        data = self.work_status(self.employee).data['data']
        self.assertEqual(len(data['current']), 1)
        self.assertFalse(data['can_manage'])

    def test_manager_and_viewer_can_see_but_not_manage(self):
        for user in (self.manager, self.viewer):
            response = self.work_status(user, 'EMP00032')
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.data['data']['can_manage'])

    def test_stranger_cannot_view_and_cannot_tell_if_the_employee_exists(self):
        denied, missing = self.work_status(self.stranger, 'EMP00032'), self.work_status(self.stranger, 'EMP12345')
        self.assertEqual((denied.status_code, missing.status_code), (404, 404))
        self.assertEqual(denied.data['message'], missing.data['message'])


class DailyJobTests(AssignmentTestCase):
    def make(self, start: int, end: int, name='Project X') -> ProjectAssignment:
        return assign_project(self.employee, {'project_name': name, 'start_date': TODAY + timedelta(days=start),
                                              'end_date': TODAY + timedelta(days=end), 'work_mode': 'office'}, self.admin)

    def test_finished_assignments_are_completed_and_admins_told(self):
        assignment = self.make(-30, -1)
        self.assertEqual(assignment.assignment_status, 'completed')   # already past at creation
        ProjectAssignment.objects.filter(pk=assignment.pk).update(assignment_status='active')
        result = run_daily_project_job(TODAY)
        self.assertEqual(result['completed'], 1)
        assignment.refresh_from_db()
        self.assertEqual(assignment.assignment_status, 'completed')
        self.assertEqual(assignment.events.first().source, ProjectAssignmentEvent.SOURCE_SYSTEM)
        recipients = set(Notification.objects.filter(notification_type='project_completed').values_list('user_id', flat=True))
        self.assertTrue({self.employee.pk, self.manager.pk, self.admin.pk} <= recipients)

    def test_ending_soon_reminder_is_sent_once_and_again_after_an_extend(self):
        assignment = self.make(-5, 3)
        self.assertEqual(run_daily_project_job(TODAY)['reminded'], 1)
        self.assertEqual(run_daily_project_job(TODAY)['reminded'], 0)
        self.action('extend', assignment.assignment_id, {'end_date': _days(5)})
        self.assertEqual(run_daily_project_job(TODAY)['reminded'], 1)

    def test_far_off_end_dates_get_no_reminder(self):
        self.make(-5, 60)
        self.assertEqual(run_daily_project_job(TODAY)['reminded'], 0)

    def test_ending_soon_is_flagged_in_work_status(self):
        self.make(-5, 2)
        current = self.work_status(self.admin, 'EMP00032').data['data']['current'][0]
        self.assertEqual((current['is_ending_soon'], current['days_left']), (True, 2))


class RunningNumberTests(AssignmentTestCase):
    def test_new_ids_stay_above_ids_used_by_old_timesheet_lines(self):
        from apps.attendance.models_timesheet import Timesheet, TimesheetLine
        sheet = Timesheet.objects.create(employee=self.employee, week_start=TODAY - timedelta(days=TODAY.weekday()))
        TimesheetLine.objects.create(timesheet=sheet, assignment_id=5000, project_id=700, project_name='Old Project')
        created = self.assign().data['data']
        self.assertGreater(created['assignment_id'], 5000)
        self.assertGreater(created['project_id'], 700)
        self.assertEqual(project_id_for('old project'), 700)


class EmployeeProjectsDashboardTests(AssignmentTestCase):
    def test_my_projects_card_lists_own_assignments(self):
        self.assign()
        response = self.client_for(self.employee).get('/api/dashboard/employee/projects/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['project_name'] for r in response.data['data']['results']], ['Website Revamp'])


class UnassignedFilterTests(AssignmentTestCase):
    def test_directory_lists_only_employees_without_a_current_project(self):
        User = type(self.employee)
        User.objects.update(onboarding_status=User.ONBOARDING_COMPLETE, activation_pending=False)   # fully onboarded
        self.assign()
        response = self.client_for(self.admin).get('/api/employees/?status=unassigned&page_size=50')
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['data']['results']
        codes = {row.get('id') or row.get('employee_id') for row in rows}
        self.assertNotIn('EMP00032', codes)
        self.assertIn('EMP00033', codes)


class ViewAsWorkspaceTests(AssignmentTestCase):
    """Opening an employee shows their workspace ("view as"): request.user is the employee, `viewed_by` the viewer."""

    def own_status_as_seen_by(self, viewer):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.hrms.views.work_status import MyWorkStatusView
        employee = type(self.employee).objects.get(pk=self.employee.pk)
        employee.viewed_by = viewer
        request = APIRequestFactory().get(reverse('my-work-status'))
        force_authenticate(request, user=employee)
        return MyWorkStatusView.as_view()(request).data['data']

    def test_admin_viewing_the_workspace_can_manage(self):
        self.assertTrue(self.own_status_as_seen_by(self.admin)['can_manage'])

    def test_manager_viewing_the_workspace_cannot(self):
        self.assertFalse(self.own_status_as_seen_by(self.manager)['can_manage'])

    def test_the_employee_on_their_own_page_cannot(self):
        self.assertFalse(self.own_status_as_seen_by(None)['can_manage'])
