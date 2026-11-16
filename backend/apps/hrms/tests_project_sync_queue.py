"""
The Project Budgeting fallback pull no longer runs inside the dashboard / Work Status request.

What these tests pin down:
  * the two views answer at once from what is stored, report `sync_pending`, and queue exactly ONE background pull
  * an unreachable or slow Project Budgeting changes nothing that is stored and never breaks the page
  * a pull that works eventually stores the assignments, and the page then stops reporting `sync_pending`
  * no duplicate jobs (including under a race), a failed enqueue is retried soon (not after the full cooldown)
  * the pull never overwrites assignments that are already stored
  * eager mode (no broker) is reported honestly as NOT asynchronous

Safety: an in-memory cache stands in for Redis and the Celery enqueue is a mock, so nothing here touches the shared Redis
or the broker the developer's own worker listens to.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms import services_project_sync as sync
from apps.hrms.models import ProjectAssignment, ProjectSyncLog
from apps.hrms.services_project_sync import ProjectSyncError, queue_employee_assignments_sync, run_employee_assignments_pull
from apps.hrms.tests_project_assignments import _row

CODE = 'EMP00110'
ASYNC_TARGET = 'apps.hrms.tasks.pull_employee_assignments.apply_async'
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
CONFIGURED = dict(PROJECT_BUDGET_API_BASE_URL='http://budget.invalid', PROJECT_BUDGET_API_KEY='k')

PROJECTS_URL = '/api/dashboard/employee/projects/'
WORK_STATUS_URL = '/api/work-status/me/'


def _http_response(rows: list[dict], total_pages: int = 1) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {'data': {'results': rows, 'total_pages': total_pages}}
    return response


@override_settings(CACHES=LOCMEM, **CONFIGURED)
class QueuedPullTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.employee = make_user('queue1@test.com', role=make_role('queue_role'), employee_id=CODE)
        self.client = APIClient()
        self.client.force_authenticate(self.employee)
        # Not eager (the default whenever REDIS_URL is set); eager mode has its own tests below.
        eager = patch('apps.hrms.services_project_sync._tasks_run_eagerly', return_value=False)
        eager.start()
        self.addCleanup(eager.stop)
        queue = patch(ASYNC_TARGET)
        self.apply_async = queue.start()
        self.addCleanup(queue.stop)

    def get(self, url=PROJECTS_URL):
        return self.client.get(url)

    @staticmethod
    def data(response) -> dict:
        return response.data['data']

    def store(self, code=CODE, assignment_id=1):
        return ProjectAssignment.objects.create(
            assignment_id=assignment_id, employee_code=code, project_id=1, project_name='Stored', assignment_status='active',
        )


class RequestPathTests(QueuedPullTestCase):
    def test_dashboard_answers_at_once_and_queues_one_pull_without_calling_project_budgeting(self):
        def never_in_a_request(*args, **kwargs):
            raise AssertionError('Project Budgeting must not be called inside the request')

        started = time.monotonic()
        with patch('apps.hrms.services_project_sync.requests.get', side_effect=never_in_a_request), \
                patch('apps.hrms.services_project_sync._get_all_pages', side_effect=lambda *a, **k: time.sleep(5)) as slow_pull:
            response = self.get()
        self.assertLess(time.monotonic() - started, 3, 'the page waited for a slow Project Budgeting')
        slow_pull.assert_not_called()
        self.assertEqual((response.status_code, self.data(response)['count'], self.data(response)['results']), (200, 0, []))
        self.assertTrue(self.data(response)['sync_pending'])
        self.apply_async.assert_called_once_with(args=[CODE], retry=False)

    def test_work_status_me_does_the_same(self):
        response = self.get(WORK_STATUS_URL)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.data(response)['sync_pending'])
        self.assertEqual(self.data(response)['current'], [])
        self.apply_async.assert_called_once_with(args=[CODE], retry=False)

    def test_both_pages_loading_together_queue_only_one_pull(self):
        first, second = self.get(PROJECTS_URL), self.get(WORK_STATUS_URL)
        self.apply_async.assert_called_once()
        self.assertTrue(self.data(first)['sync_pending'])
        self.assertTrue(self.data(second)['sync_pending'])   # the same job is still expected to finish

    def test_stored_assignments_are_shown_immediately_with_nothing_pending_or_queued(self):
        self.store()
        response = self.get()
        self.assertEqual([r['assignment_id'] for r in self.data(response)['results']], [1])
        self.assertFalse(self.data(response)['sync_pending'])
        self.apply_async.assert_not_called()

    def test_viewing_someone_elses_work_status_never_queues_or_reports_pending(self):
        manager = make_user('queue-mgr@test.com', role=make_role('queue_mgr', can_manage_team=True), employee_id='EMP00111')
        self.employee.reporting_manager = manager
        self.employee.save(update_fields=['reporting_manager'])
        client = APIClient()
        client.force_authenticate(manager)
        response = client.get(f'/api/work-status/{CODE}/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(self.data(response)['sync_pending'])
        self.apply_async.assert_not_called()

    @override_settings(PROJECT_BUDGET_API_BASE_URL='', PROJECT_BUDGET_API_KEY='')
    def test_nothing_is_queued_when_project_budgeting_is_not_configured(self):
        response = self.get()
        self.assertFalse(self.data(response)['sync_pending'])
        self.apply_async.assert_not_called()


class BackgroundPullTests(QueuedPullTestCase):
    def test_a_pull_that_succeeds_stores_the_assignments_and_the_page_stops_reporting_pending(self):
        self.assertTrue(self.data(self.get())['sync_pending'])
        with patch('apps.hrms.services_project_sync._get_all_pages', return_value=[_row(7)]):
            run_employee_assignments_pull(CODE)
        after = self.get()
        self.assertEqual([r['assignment_id'] for r in self.data(after)['results']], [7])
        self.assertFalse(self.data(after)['sync_pending'])
        self.assertTrue(ProjectSyncLog.objects.filter(source='pull', status='success', employee_code=CODE).exists())
        self.apply_async.assert_called_once()   # still just the one queued job

    def test_a_slow_but_valid_response_still_synchronizes(self):
        def slow(*args, **kwargs):
            time.sleep(0.3)
            return _http_response([_row(8)])

        with patch('apps.hrms.services_project_sync.requests.get', side_effect=slow):
            run_employee_assignments_pull(CODE)
        self.assertEqual(list(ProjectAssignment.objects.filter(employee_code=CODE).values_list('assignment_id', flat=True)), [8])

    def test_requests_carry_a_connect_and_a_read_timeout(self):
        with patch('apps.hrms.services_project_sync.requests.get', return_value=_http_response([_row(9)])) as http:
            run_employee_assignments_pull(CODE)
        self.assertEqual(http.call_args.kwargs['timeout'], (sync.PULL_CONNECT_TIMEOUT_SECONDS, sync.PULL_READ_TIMEOUT_SECONDS))
        self.assertEqual((sync.PULL_CONNECT_TIMEOUT_SECONDS, sync.PULL_READ_TIMEOUT_SECONDS), (3, 10))

    def test_an_unreachable_or_timed_out_project_budgeting_changes_nothing_and_is_logged(self):
        for failure in (requests.ConnectTimeout('connect timed out'), requests.ReadTimeout('read timed out'),
                        requests.ConnectionError('refused')):
            with self.subTest(failure=type(failure).__name__):
                with patch('apps.hrms.services_project_sync.requests.get', side_effect=failure):
                    run_employee_assignments_pull(CODE)    # must not raise
                self.assertFalse(ProjectAssignment.objects.filter(employee_code=CODE).exists())
        self.assertEqual(ProjectSyncLog.objects.filter(source='pull', status='failed', employee_code=CODE).count(), 3)

    def test_the_page_stays_usable_and_the_failure_does_not_pile_up_retries(self):
        self.assertTrue(self.data(self.get())['sync_pending'])
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=ProjectSyncError('service down')):
            run_employee_assignments_pull(CODE)
        after = self.get()
        self.assertEqual((after.status_code, self.data(after)['count'], self.data(after)['sync_pending']), (200, 0, False))
        self.get(WORK_STATUS_URL)
        self.apply_async.assert_called_once()   # the cooldown holds: no new job for the next ten minutes

    def test_the_overall_time_budget_stops_a_pull_that_keeps_going_page_after_page(self):
        clock = {'now': 0.0}
        pages = {'asked': 0}

        def page(*args, **kwargs):
            pages['asked'] += 1
            clock['now'] += 31.0                       # every page takes longer than the whole budget
            return _http_response([_row(pages['asked'])], total_pages=5)

        with patch('apps.hrms.services_project_sync.time.monotonic', side_effect=lambda: clock['now']), \
                patch('apps.hrms.services_project_sync.requests.get', side_effect=page):
            run_employee_assignments_pull(CODE)
        self.assertEqual(pages['asked'], 1)            # it stopped before asking for page 2
        self.assertFalse(ProjectAssignment.objects.filter(employee_code=CODE).exists())   # partial data is never applied
        failure = ProjectSyncLog.objects.get(source='pull', status='failed', employee_code=CODE)
        self.assertIn('time budget', failure.message)

    def test_it_never_overwrites_assignments_that_arrived_in_the_meantime(self):
        self.store(assignment_id=5)                    # a webhook push got there first
        with patch('apps.hrms.services_project_sync._get_all_pages', return_value=[_row(99)]) as pull:
            run_employee_assignments_pull(CODE)
        pull.assert_not_called()
        self.assertEqual(list(ProjectAssignment.objects.filter(employee_code=CODE).values_list('assignment_id', flat=True)), [5])

    def test_existing_assignments_survive_a_failed_pull_for_other_data(self):
        self.store(assignment_id=5)
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=ProjectSyncError('down')):
            run_employee_assignments_pull(CODE)
        self.assertEqual(list(ProjectAssignment.objects.filter(employee_code=CODE).values_list('assignment_id', flat=True)), [5])
        self.assertEqual([r['assignment_id'] for r in self.data(self.get())['results']], [5])

    def test_the_pending_state_is_cleared_even_when_the_pull_crashes(self):
        self.get()
        self.assertGreater(cache.get(sync._state_key(CODE)), time.time())   # pending: "may be running until <future time>"
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=RuntimeError('unexpected')):
            run_employee_assignments_pull(CODE)         # must not raise either
        self.assertEqual(cache.get(sync._state_key(CODE)), 0)
        self.assertFalse(self.data(self.get())['sync_pending'])

    def test_a_soft_time_limit_is_logged_like_any_other_failure(self):
        from celery.exceptions import SoftTimeLimitExceeded
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=SoftTimeLimitExceeded()):
            run_employee_assignments_pull(CODE)
        self.assertTrue(ProjectSyncLog.objects.filter(source='pull', status='failed', message__contains='SoftTimeLimitExceeded').exists())


class DuplicateAndEnqueueFailureTests(QueuedPullTestCase):
    def test_many_simultaneous_requests_queue_exactly_one_job(self):
        threads_total = 8
        barrier = threading.Barrier(threads_total)
        results: list[bool] = []
        errors: list[BaseException] = []

        def request():
            try:
                barrier.wait(timeout=10)
                results.append(queue_employee_assignments_sync(CODE))
            except BaseException as exc:  # noqa: BLE001 — surfaced by the assertion below
                errors.append(exc)
            finally:
                connection.close()

        workers = [threading.Thread(target=request) for _ in range(threads_total)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=30)
        self.assertEqual(errors, [])
        self.assertEqual(self.apply_async.call_count, 1)
        # The winner queued it and every other request sees it still pending: the claim and the pending state are one
        # atomic write, so there is no moment in which a request can see the claim without the pending state.
        self.assertEqual(results, [True] * threads_total)

    def test_a_job_nobody_picks_up_stops_being_reported_pending(self):
        self.assertTrue(self.data(self.get())['sync_pending'])
        with patch('time.time', return_value=time.time() + sync.FALLBACK_RUNNING_SECONDS + 1):
            response = self.get()
        self.assertFalse(self.data(response)['sync_pending'])    # the page is not told to wait for ever
        self.assertEqual(self.apply_async.call_count, 1)         # and no second job is queued during the cooldown

    def test_a_leftover_value_from_the_old_synchronous_version_reads_as_not_pending(self):
        cache.set(sync._state_key(CODE), True, 600)              # what the previous version stored under this key
        self.assertFalse(self.data(self.get())['sync_pending'])
        self.apply_async.assert_not_called()

    def test_a_broker_failure_is_swallowed_and_nothing_is_reported_pending(self):
        self.apply_async.side_effect = ConnectionError('broker down')
        response = self.get()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(self.data(response)['sync_pending'])
        self.assertEqual(cache.get(sync._state_key(CODE)), 0)       # nothing is running

    def test_after_a_failed_enqueue_the_next_try_comes_soon_not_after_ten_minutes(self):
        self.apply_async.side_effect = ConnectionError('broker down')
        self.get()
        self.get()
        self.assertEqual(self.apply_async.call_count, 1)    # a short pause: the broker is not hammered on every page load

        self.apply_async.side_effect = None                  # the broker is back
        real_time = time.time()
        later = real_time + sync.ENQUEUE_FAILURE_RETRY_SECONDS + 1   # nowhere near the ten-minute cooldown
        with patch('time.time', return_value=later):
            response = self.get()
        self.assertEqual(self.apply_async.call_count, 2)    # queued again
        self.assertTrue(self.data(response)['sync_pending'])

    def test_the_cooldown_is_not_extended_by_a_failed_enqueue(self):
        self.apply_async.side_effect = ConnectionError('broker down')
        self.get()
        self.apply_async.side_effect = None
        with patch('time.time', return_value=time.time() + sync.FALLBACK_COOLDOWN_SECONDS - 1):
            self.get()
        self.assertEqual(self.apply_async.call_count, 2)    # long before ten minutes were up


class EagerModeTests(QueuedPullTestCase):
    def setUp(self):
        super().setUp()
        eager = patch('apps.hrms.services_project_sync._tasks_run_eagerly', return_value=True)   # stacks on the base patch
        eager.start()
        self.addCleanup(eager.stop)

    def test_eager_mode_runs_the_pull_inline_and_does_not_claim_to_be_asynchronous(self):
        with patch('apps.hrms.services_project_sync._get_all_pages', return_value=[_row(7)]):
            response = self.get()
        self.assertEqual([r['assignment_id'] for r in self.data(response)['results']], [7])   # already synchronized
        self.assertFalse(self.data(response)['sync_pending'])                                  # nothing is "pending"
        self.apply_async.assert_not_called()                                                   # nothing was queued

    def test_eager_mode_does_not_go_through_celery_so_the_requests_database_connection_stays_open(self):
        """config/celery.py runs close_old_connections() around every task, eager ones included. Run as a task, an inline
        pull would close the connection the request is still using (always, when CONN_MAX_AGE is 0)."""
        with patch('apps.hrms.tasks.pull_employee_assignments.apply') as task_apply, \
                patch('apps.hrms.services_project_sync.run_employee_assignments_pull') as inline_pull, \
                patch('django.db.close_old_connections') as close_connections:
            response = self.get()
        inline_pull.assert_called_once_with(CODE)       # the plain function ran, once
        task_apply.assert_not_called()                  # Celery's task machinery (and its connection-closing signals) did not
        close_connections.assert_not_called()
        self.assertEqual(response.status_code, 200, response.data)

    def test_a_failing_inline_pull_still_lets_the_page_load(self):
        with patch('apps.hrms.services_project_sync._get_all_pages', side_effect=ProjectSyncError('down')):
            response = self.get()
        self.assertEqual((response.status_code, self.data(response)['count'], self.data(response)['sync_pending']), (200, 0, False))
        self.assertTrue(ProjectSyncLog.objects.filter(source='pull', status='failed').exists())


class TaskDefinitionTests(TestCase):
    def test_the_eager_check_reads_the_live_celery_setting(self):
        self.assertEqual(sync._tasks_run_eagerly(), bool(settings.CELERY_TASK_ALWAYS_EAGER))

    def test_the_task_is_bounded_and_does_not_retry(self):
        from apps.hrms.tasks import pull_employee_assignments
        self.assertEqual(
            (pull_employee_assignments.soft_time_limit, pull_employee_assignments.time_limit,
             pull_employee_assignments.max_retries, pull_employee_assignments.ignore_result),
            (40, 60, 0, True),
        )
        self.assertLess(sync.FALLBACK_PULL_BUDGET_SECONDS, pull_employee_assignments.soft_time_limit)   # the budget bites first

    def test_the_scheduled_reconcile_is_still_registered(self):
        entry = settings.CELERY_BEAT_SCHEDULE['reconcile-project-assignments']
        self.assertEqual((entry['task'], entry['schedule']), ('apps.hrms.tasks.reconcile_project_assignments', 1800.0))
