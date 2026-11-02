"""
Regression tests for the Project Budgeting integration (Work Status):
  * the employee.projects_changed push: auth, validation, idempotency, full-list semantics
  * history is NEVER deleted: vanished rows are closed, every change is an event, auto-close on project change
  * sync log, unmatched-employee reporting, retries (Celery reconcile), stale/out-of-order protection
  * Work Status API permissions (self / manager / HR / stranger) and the admin sync status endpoint
"""
from __future__ import annotations

import hashlib
from datetime import date
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ExternalAPIKey
from apps.hrms.models import ProjectAssignment, ProjectAssignmentEvent, ProjectSyncLog
from apps.hrms.services_project_sync import ProjectSyncError, reconcile_all_employees

RAW_KEY = 'eak_projectpush123'
PUSH_URL_NAME = 'external-project-assignments-push'


def _row(assignment_id: int, **overrides) -> dict:
    row = {
        'assignment_id': assignment_id, 'project_id': 12, 'project_name': 'Sample Client Website',
        'project_status': 'development', 'project_status_display': 'Development In Progress',
        'project_start_date': '2026-10-01', 'project_end_date': '2026-12-31',
        'assignment_start_date': '2026-10-05', 'assignment_end_date': '2026-11-30',
        'assignment_status': 'active', 'assignment_status_display': 'Active',
        'milestone_name': 'Phase 1', 'updated_at': '2026-10-28T09:30:00Z',
    }
    row.update(overrides)
    return row


class PushTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(raise_request_exception=False)
        self.url = reverse(PUSH_URL_NAME)
        ExternalAPIKey.objects.create(name='project_budget_tool', key_hash=hashlib.sha256(RAW_KEY.encode()).hexdigest())

    def push(self, code, rows, key=RAW_KEY, **extra_body):
        body = {'event': 'employee.projects_changed', 'employee_id': code, 'projects': rows, **extra_body}
        headers = {'HTTP_X_API_KEY': key} if key else {}
        return self.client.post(self.url, body, format='json', **headers)

    def rows_of(self, code):
        return ProjectAssignment.objects.filter(employee_code=code)


class PushAuthAndValidationTests(PushTestCase):
    def test_missing_or_wrong_key_is_rejected_and_stores_nothing(self):
        self.assertEqual(self.push('EMP00001', [_row(1)], key=None).status_code, 401)
        self.assertEqual(self.push('EMP00001', [_row(1)], key='nope').status_code, 401)
        self.assertEqual(ProjectAssignment.objects.count(), 0)

    def test_revoked_key_is_rejected(self):
        ExternalAPIKey.objects.update(is_active=False)
        self.assertEqual(self.push('EMP00001', [_row(1)]).status_code, 401)

    def test_other_event_is_ignored_with_200(self):
        resp = self.client.post(self.url, {'event': 'something.else', 'employee_id': 'EMP00001', 'projects': [_row(1)]},
                                format='json', HTTP_X_API_KEY=RAW_KEY)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProjectAssignment.objects.count(), 0)

    def test_malformed_body_is_400_and_logged(self):
        self.assertEqual(self.client.post(self.url, {'projects': []}, format='json', HTTP_X_API_KEY=RAW_KEY).status_code, 400)
        self.assertEqual(self.client.post(self.url, {'employee_id': 'EMP00001'}, format='json', HTTP_X_API_KEY=RAW_KEY).status_code, 400)
        bad = _row(1)
        del bad['project_name']
        self.assertEqual(self.push('EMP00001', [bad]).status_code, 400)
        self.assertEqual(ProjectAssignment.objects.count(), 0)
        self.assertEqual(ProjectSyncLog.objects.filter(status='failed', source='webhook').count(), 3)

    def test_start_date_is_required(self):
        row = _row(1)
        del row['assignment_start_date']
        self.assertEqual(self.push('EMP00001', [row]).status_code, 400)
        self.assertEqual(self.push('EMP00001', [_row(1, assignment_start_date=None)]).status_code, 400)

    def test_end_before_start_is_rejected(self):
        resp = self.push('EMP00001', [_row(1, assignment_start_date='2026-11-10', assignment_end_date='2026-11-01')])
        self.assertEqual(resp.status_code, 400)

    def test_unknown_enum_values_and_extra_fields_are_accepted(self):
        resp = self.push('EMP00001', [_row(1, assignment_status='paused', brand_new_field='x')])
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_optional_role_allocation_and_code_are_stored_when_sent(self):
        self.push('EMP00001', [_row(1, role='Backend Lead', allocation_percent='60', project_code='PRJ-12')])
        row = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual((row.role, str(row.allocation_percent), row.project_code), ('Backend Lead', '60.00', 'PRJ-12'))

    def test_null_milestone_is_stored_blank(self):
        self.push('EMP00001', [_row(1, milestone_name=None)])
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).milestone_name, '')


class PushHistoryTests(PushTestCase):
    def test_push_stores_rows_and_a_created_event(self):
        resp = self.push('EMP00001', [_row(1), _row(2)])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.rows_of('EMP00001').count(), 2)
        self.assertEqual(ProjectAssignmentEvent.objects.filter(event_type='created').count(), 2)

    def test_duplicate_push_creates_no_duplicates_and_no_new_events(self):
        self.push('EMP00001', [_row(1), _row(2)])
        events_before = ProjectAssignmentEvent.objects.count()
        for _ in range(3):
            self.assertEqual(self.push('EMP00001', [_row(1), _row(2)]).status_code, 200)
        self.assertEqual(self.rows_of('EMP00001').count(), 2)
        self.assertEqual(ProjectAssignmentEvent.objects.count(), events_before)

    def test_vanished_row_is_closed_and_kept_not_deleted(self):
        self.push('EMP00001', [_row(1), _row(2)])
        self.push('EMP00001', [_row(2)])
        gone = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual(gone.assignment_status, 'removed')
        self.assertIsNotNone(gone.assignment_end_date)
        self.assertTrue(gone.events.filter(event_type='removed_in_source').exists())
        self.assertEqual(self.rows_of('EMP00001').count(), 2)

    def test_empty_list_closes_everything_but_keeps_history(self):
        self.push('EMP00001', [_row(1), _row(2)])
        self.push('EMP00001', [])
        self.assertEqual(self.rows_of('EMP00001').count(), 2)
        self.assertEqual(set(self.rows_of('EMP00001').values_list('assignment_status', flat=True)), {'removed'})

    def test_completed_row_missing_from_list_stays_completed(self):
        self.push('EMP00001', [_row(1, assignment_status='completed', assignment_status_display='Completed')])
        self.push('EMP00001', [_row(2)])
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).assignment_status, 'completed')

    def test_removed_row_that_reappears_is_restored_with_event(self):
        self.push('EMP00001', [_row(1)])
        self.push('EMP00001', [])
        self.push('EMP00001', [_row(1)])
        row = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual(row.assignment_status, 'active')
        self.assertTrue(row.events.filter(event_type='restored').exists())

    def test_end_date_extension_updates_row_and_keeps_the_old_value_in_the_event(self):
        self.push('EMP00001', [_row(1, assignment_end_date='2026-11-30', updated_at='2026-10-28T09:30:00Z')])
        self.push('EMP00001', [_row(1, assignment_end_date='2026-12-31', updated_at='2026-10-29T09:30:00Z')])
        row = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual(row.assignment_end_date, date(2026, 12, 31))
        event = row.events.filter(event_type='updated').first()
        self.assertEqual(event.changes['assignment_end_date'], ['2026-11-30', '2026-12-31'])

    def test_end_date_set_on_open_ended_row_is_an_ended_event(self):
        self.push('EMP00001', [_row(1, assignment_end_date=None, updated_at='2026-10-28T09:30:00Z')])
        self.push('EMP00001', [_row(1, assignment_end_date='2026-11-15', assignment_status='completed',
                                    assignment_status_display='Completed', updated_at='2026-10-29T09:30:00Z')])
        self.assertTrue(ProjectAssignment.objects.get(assignment_id=1).events.filter(event_type='ended').exists())

    def test_older_copy_of_a_row_does_not_overwrite_a_newer_one(self):
        self.push('EMP00001', [_row(1, project_name='Newer', updated_at='2026-10-29T10:00:00Z')])
        self.push('EMP00001', [_row(1, project_name='Older', updated_at='2026-10-28T10:00:00Z')])
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).project_name, 'Newer')

    def test_push_does_not_touch_other_employees(self):
        self.push('EMP00001', [_row(1)])
        self.push('EMP00002', [_row(2)])
        self.push('EMP00002', [])
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).assignment_status, 'active')

    def test_reassigned_assignment_moves_to_new_employee(self):
        self.push('EMP00001', [_row(1)])
        self.push('EMP00002', [_row(1)])
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).employee_code, 'EMP00002')

    def test_backdated_assignment_is_accepted(self):
        resp = self.push('EMP00001', [_row(1, assignment_start_date='2025-01-01', assignment_end_date='2025-06-30',
                                           assignment_status='completed', assignment_status_display='Completed')])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).assignment_start_date, date(2025, 1, 1))


class AutoCloseOnProjectChangeTests(PushTestCase):
    def _open_row(self, assignment_id, project_id, start, **extra):
        return _row(assignment_id, project_id=project_id, project_name=f'P{project_id}', assignment_start_date=start,
                    assignment_end_date=None, **extra)

    def test_new_project_closes_previous_open_assignment_the_day_before(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01')])
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01'), self._open_row(2, 20, '2026-11-01')])
        old = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual(old.assignment_end_date, date(2026, 10, 31))
        self.assertEqual(old.assignment_status, 'completed')
        self.assertTrue(old.events.filter(event_type='auto_closed').exists())
        self.assertIsNone(ProjectAssignment.objects.get(assignment_id=2).assignment_end_date)

    def test_auto_close_survives_later_syncs_that_still_show_the_old_row_open(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01')])
        both = [self._open_row(1, 10, '2026-10-01'), self._open_row(2, 20, '2026-11-01')]
        self.push('EMP00001', both)
        events_after_close = ProjectAssignmentEvent.objects.count()
        self.push('EMP00001', both)
        old = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual((old.assignment_end_date, old.assignment_status), (date(2026, 10, 31), 'completed'))
        self.assertEqual(ProjectAssignmentEvent.objects.count(), events_after_close)

    def test_budgeting_sending_its_own_end_date_wins_over_our_auto_close(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01')])
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01'), self._open_row(2, 20, '2026-11-01')])
        self.push('EMP00001', [_row(1, project_id=10, assignment_start_date='2026-10-01', assignment_end_date='2026-10-20',
                                    assignment_status='completed', assignment_status_display='Completed',
                                    updated_at='2026-11-02T00:00:00Z'), self._open_row(2, 20, '2026-11-01')])
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).assignment_end_date, date(2026, 10, 20))

    def test_first_ever_load_with_several_open_assignments_closes_none(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01'), self._open_row(2, 20, '2026-11-01')])
        self.assertEqual(self.rows_of('EMP00001').filter(assignment_end_date__isnull=True).count(), 2)

    def test_allocation_percent_means_concurrent_work_is_left_alone(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01', allocation_percent='50')])
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01', allocation_percent='50'),
                               self._open_row(2, 20, '2026-11-01', allocation_percent='50')])
        self.assertIsNone(ProjectAssignment.objects.get(assignment_id=1).assignment_end_date)

    def test_same_project_new_milestone_does_not_close_the_other_milestone(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01')])
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01'), self._open_row(2, 10, '2026-11-01')])
        self.assertIsNone(ProjectAssignment.objects.get(assignment_id=1).assignment_end_date)

    @override_settings(PROJECT_ASSIGNMENT_AUTO_CLOSE_OPEN_ENDED=False)
    def test_auto_close_can_be_switched_off(self):
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01')])
        self.push('EMP00001', [self._open_row(1, 10, '2026-10-01'), self._open_row(2, 20, '2026-11-01')])
        self.assertIsNone(ProjectAssignment.objects.get(assignment_id=1).assignment_end_date)


class SyncLogAndAlertTests(PushTestCase):
    def test_every_push_is_logged_with_counts(self):
        self.push('EMP00001', [_row(1), _row(2)])
        log = ProjectSyncLog.objects.get(employee_code='EMP00001')
        self.assertEqual((log.source, log.triggered_by, log.saved, log.changed), ('webhook', 'project_budget_tool', 2, 2))

    def test_unknown_employee_is_stored_logged_and_reported_not_dropped(self):
        with patch('apps.hrms.services_project_sync.alert_admins_unmatched') as alert:
            resp = self.push('EMP99999', [_row(5)])
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['data']['is_matched'])
        self.assertEqual(self.rows_of('EMP99999').count(), 1)
        self.assertEqual(ProjectSyncLog.objects.get(employee_code='EMP99999').status, 'unmatched')
        alert.assert_called_once_with('EMP99999')

    def test_known_employee_is_matched(self):
        make_user('known@test.com', role=make_role('known_role'), employee_id='EMP00050')
        resp = self.push('EMP00050', [_row(1)])
        self.assertTrue(resp.data['data']['is_matched'])
        self.assertEqual(ProjectSyncLog.objects.get(employee_code='EMP00050').status, 'success')

    def test_admins_are_notified_about_unmatched_employee_once_a_day(self):
        from apps.notifications.models import Notification
        admin = make_user('padmin@test.com', role=make_role('padmin_role', permission_codenames=['settings.edit']))
        self.push('EMP99998', [_row(1)])
        self.push('EMP99998', [_row(1)])
        notifications = Notification.objects.filter(user=admin, notification_type='project_sync_alert')
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(notifications.first().reference_id, 'EMP99998')

    def test_unexpected_failure_is_logged_and_surfaces_as_500_so_sender_retries(self):
        with patch('apps.hrms.services_project_sync.apply_employee_snapshot', side_effect=RuntimeError('db down')):
            resp = self.push('EMP00001', [_row(1)])
        self.assertEqual(resp.status_code, 500)
        log = ProjectSyncLog.objects.get(employee_code='EMP00001')
        self.assertEqual(log.status, 'failed')
        self.assertIn('db down', log.message)


@override_settings(PROJECT_BUDGET_API_BASE_URL='http://budget.invalid', PROJECT_BUDGET_API_KEY='k')
class ReconcileTests(TestCase):
    def setUp(self):
        cache.clear()

    def _pull(self, rows):
        return patch('apps.hrms.services_project_sync._get_all_pages', return_value=rows)

    def _resource_row(self, code, assignment_id, **overrides):
        return {**_row(assignment_id, **overrides), 'resource_type': 'employee', 'resource_code': code, 'resource_name': 'X'}

    def test_reconcile_creates_missing_assignments(self):
        with self._pull([self._resource_row('EMP00001', 1), self._resource_row('EMP00002', 2)]):
            summary = reconcile_all_employees()
        self.assertEqual(summary['failed'], 0)
        self.assertEqual(ProjectAssignment.objects.count(), 2)
        self.assertTrue(ProjectSyncLog.objects.filter(source='reconcile', status='success', employee_code='').exists())

    def test_reconcile_closes_employees_who_vanished_but_keeps_their_history(self):
        with self._pull([self._resource_row('EMP00001', 1)]):
            reconcile_all_employees()
        with self._pull([]):
            reconcile_all_employees()
        row = ProjectAssignment.objects.get(assignment_id=1)
        self.assertEqual(row.assignment_status, 'removed')

    def test_reconcile_is_idempotent(self):
        rows = [self._resource_row('EMP00001', 1)]
        with self._pull(rows):
            reconcile_all_employees()
        events = ProjectAssignmentEvent.objects.count()
        with self._pull(rows):
            reconcile_all_employees()
        self.assertEqual((ProjectAssignment.objects.count(), ProjectAssignmentEvent.objects.count()), (1, events))

    def test_failed_pull_changes_nothing_logs_and_raises_for_retry(self):
        with self._pull([self._resource_row('EMP00001', 1)]):
            reconcile_all_employees()
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=ProjectSyncError('page 2 failed')):
            with self.assertRaises(ProjectSyncError):
                reconcile_all_employees()
        self.assertEqual(ProjectAssignment.objects.get(assignment_id=1).assignment_status, 'active')
        self.assertTrue(ProjectSyncLog.objects.filter(source='reconcile', status='failed').exists())

    def test_rows_without_resource_code_are_skipped(self):
        with self._pull([{**self._resource_row('EMP00001', 1), 'resource_code': None}]):
            reconcile_all_employees()
        self.assertEqual(ProjectAssignment.objects.count(), 0)

    @override_settings(PROJECT_BUDGET_API_BASE_URL='', PROJECT_BUDGET_API_KEY='')
    def test_reconcile_is_a_noop_when_not_configured(self):
        self.assertEqual(reconcile_all_employees(), {'skipped': True})
        self.assertEqual(ProjectSyncLog.objects.count(), 0)


class WorkStatusPermissionTests(PushTestCase):
    def setUp(self):
        super().setUp()
        plain = make_role('ws_plain')
        self.manager = make_user('ws-mgr@test.com', role=make_role('ws_mgr', can_manage_team=True), employee_id='EMP00020')
        self.employee = make_user('ws-emp@test.com', role=plain, employee_id='EMP00021', reporting_manager=self.manager)
        self.stranger = make_user('ws-str@test.com', role=plain, employee_id='EMP00022')
        self.other_manager = make_user('ws-mgr2@test.com', role=make_role('ws_mgr2', can_manage_team=True), employee_id='EMP00023')
        self.hr = make_user('ws-hr@test.com', role=make_role('ws_hr', permission_codenames=['employees.view']), employee_id='EMP00024')
        self.push('EMP00021', [_row(1, assignment_start_date='2026-01-01', assignment_end_date='2026-03-01',
                                    assignment_status='completed', assignment_status_display='Completed'),
                               _row(2, project_id=99, project_name='Current One', assignment_start_date='2026-04-01',
                                    assignment_end_date=None)])

    def get(self, user, code=None):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(reverse('my-work-status') if code is None else reverse('employee-work-status', args=[code]))

    def test_employee_sees_own_current_and_history_newest_first_and_read_only(self):
        data = self.get(self.employee).data['data']
        self.assertEqual([a['project_name'] for a in data['current']], ['Current One'])
        self.assertTrue(data['current'][0]['is_ongoing'])
        self.assertIsNone(data['current'][0]['end_date'])
        self.assertEqual([a['assignment_id'] for a in data['history']['results']], [2, 1])
        self.assertEqual((data['managed_in'], data['is_read_only']), ('Project Budgeting', True))
        self.assertIsNotNone(data['last_synced_at'])

    def test_history_rows_say_what_triggered_the_change(self):
        row = self.get(self.employee).data['data']['history']['results'][0]
        self.assertEqual((row['last_change']['source'], row['last_change']['triggered_by']), ('webhook', 'project_budget_tool'))

    def test_manager_of_the_employee_can_view(self):
        self.assertEqual(self.get(self.manager, 'EMP00021').status_code, 200)

    def test_hr_can_view(self):
        self.assertEqual(self.get(self.hr, 'EMP00021').status_code, 200)

    def test_someone_elses_manager_cannot_view(self):
        self.assertEqual(self.get(self.other_manager, 'EMP00021').status_code, 404)

    def test_stranger_employee_cannot_view_and_cannot_tell_if_the_employee_exists(self):
        denied = self.get(self.stranger, 'EMP00021')
        missing = self.get(self.stranger, 'EMP12345')
        self.assertEqual((denied.status_code, missing.status_code), (404, 404))
        self.assertEqual(denied.data['message'], missing.data['message'])

    def test_unauthenticated_is_rejected(self):
        self.assertIn(APIClient().get(reverse('employee-work-status', args=['EMP00021'])).status_code, (401, 403))

    def test_employee_without_projects_gets_an_empty_but_valid_response(self):
        data = self.get(self.stranger).data['data']
        self.assertEqual((data['current'], data['history']['count']), ([], 0))

    @override_settings(PROJECT_BUDGET_API_BASE_URL='http://budget.invalid', PROJECT_BUDGET_API_KEY='k')
    def test_own_work_status_asks_budgeting_once_when_nothing_is_stored(self):
        with patch('apps.hrms.services_project_sync._get_all_pages', return_value=[_row(77, assignment_end_date=None)]) as pull:
            first = self.get(self.stranger).data['data']
            self.get(self.stranger)
        self.assertEqual([a['assignment_id'] for a in first['current']], [77])
        self.assertEqual(pull.call_count, 1)

    def test_removed_and_ended_assignments_are_not_current(self):
        self.push('EMP00021', [])
        data = self.get(self.employee).data['data']
        self.assertEqual(data['current'], [])
        self.assertEqual(data['history']['count'], 2)

    def test_allocation_over_100_is_flagged(self):
        self.push('EMP00021', [_row(2, project_id=99, assignment_end_date=None, allocation_percent='70'),
                               _row(3, project_id=100, assignment_end_date=None, allocation_percent='60')])
        types = [c['type'] for c in self.get(self.employee).data['data']['conflicts']]
        self.assertIn('allocation_over_100', types)

    def test_terminated_employee_keeps_history_and_is_flagged(self):
        User = type(self.employee)
        User.objects.filter(pk=self.employee.pk).update(is_active=False)
        self.employee.refresh_from_db()
        data = self.get(self.hr, 'EMP00021').data['data']
        self.assertFalse(data['employee_is_active'])
        self.assertEqual(data['history']['count'], 2)


class ProjectSyncStatusTests(PushTestCase):
    def get(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(reverse('project-sync-status'))

    def test_admin_sees_health_failures_and_unmatched_ids(self):
        admin = make_user('sync-admin@test.com', role=make_role('sync_admin', permission_codenames=['settings.view']))
        self.push('EMP99997', [_row(1)])
        self.client.post(self.url, {'projects': []}, format='json', HTTP_X_API_KEY=RAW_KEY)
        data = self.get(admin).data['data']
        self.assertIn('EMP99997', data['unmatched_employee_ids'])
        self.assertEqual(data['failed_last_24h'], 1)
        self.assertIsNotNone(data['last_synced_at'])
        self.assertGreaterEqual(data['logs']['count'], 2)

    def test_non_admin_is_forbidden(self):
        employee = make_user('sync-emp@test.com', role=make_role('sync_plain'))
        self.assertEqual(self.get(employee).status_code, 403)


class EmployeeProjectsDashboardTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('project_dash_role')
        self.employee = make_user('proj1@test.com', role=role, employee_id='EMP00010')
        self.other = make_user('proj2@test.com', role=role, employee_id='EMP00011')
        self.client = APIClient()
        self.client.force_authenticate(self.employee)
        self.url = '/api/dashboard/employee/projects/'

    def _make(self, code, assignment_id, status='active'):
        ProjectAssignment.objects.create(
            assignment_id=assignment_id, employee_code=code, project_id=1, project_name=f'P{assignment_id}',
            assignment_status=status,
        )

    def test_shows_only_own_non_removed_rows(self):
        self._make('EMP00010', 1)
        self._make('EMP00010', 2, status='removed')
        self._make('EMP00011', 3)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([r['assignment_id'] for r in resp.data['data']['results']], [1])

    def test_query_param_cannot_read_someone_elses_rows(self):
        self._make('EMP00011', 3)
        resp = self.client.get(self.url, {'employee_id': 'EMP00011'})
        self.assertEqual(resp.data['data']['count'], 0)

    def test_unauthenticated_is_rejected(self):
        self.assertIn(APIClient().get(self.url).status_code, (401, 403))

    @override_settings(PROJECT_BUDGET_API_BASE_URL='http://budget.invalid', PROJECT_BUDGET_API_KEY='k')
    def test_fallback_pull_fills_empty_employee_once(self):
        with patch('apps.hrms.services_project_sync._get_all_pages', return_value=[_row(7)]) as pull:
            resp = self.client.get(self.url)
            self.client.get(self.url)
        self.assertEqual(resp.data['data']['count'], 1)
        self.assertEqual(pull.call_count, 1)

    @override_settings(PROJECT_BUDGET_API_BASE_URL='http://budget.invalid', PROJECT_BUDGET_API_KEY='k')
    def test_failed_fallback_pull_does_not_break_the_dashboard_and_is_logged(self):
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=ProjectSyncError('boom')):
            resp = self.client.get(self.url)
        self.assertEqual((resp.status_code, resp.data['data']['count']), (200, 0))
        self.assertTrue(ProjectSyncLog.objects.filter(source='pull', status='failed').exists())

    @override_settings(PROJECT_BUDGET_API_BASE_URL='', PROJECT_BUDGET_API_KEY='')
    def test_fallback_is_off_when_not_configured(self):
        with patch('apps.hrms.services_project_sync.requests.get') as http:
            self.client.get(self.url)
        http.assert_not_called()
