"""
Bulk employee import as a durable background job: confirm returns a job id at once; workers create the employees in short
transactions with a database checkpoint; crashes, a missing broker and double execution cannot duplicate or skip anybody.

No real email is ever sent (the mail function is mocked). Three kinds of test live here, and the difference matters:
  - behaviour tests, with REAL employee creation, seat allocation, locking and database checkpoints (small files);
  - ENGINE tests at 500 and 2,500 rows that replace the per-employee creation with a minimal stub, to prove chunking, checkpoints
    and progress at those sizes. They say nothing about throughput;
  - the opt-in benchmark (RUN_IMPORT_BENCHMARK=1) and the opt-in real-thread race (RUN_DB_FLUSHING_TESTS=1), which measure and race
    the real thing and are meant for a throwaway database.
"""
from __future__ import annotations

import datetime
import io
import os
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import openpyxl
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts import services_employee_import_job as job_module
from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, EmployeeImportInvite, EmployeeImportJob, EmployeeImportJobError, OrgUnit, Placement, Position, User
from apps.accounts.services_employee_import import ParsedFile, RowResult, file_sha256
from apps.accounts.services_employee_import_job import create_job, requeue_stale_jobs, run_job
from apps.accounts.tests_employee_bulk_import import INVITE, _ImportCase, _workbook
from apps.accounts.tests_employee_scope import make_branch

JOBS = '/api/employees/bulk-import/jobs/'
DELAY = 'apps.accounts.tasks.run_employee_import_job.delay'


class _JobCase(_ImportCase):
    def add_seats(self, title: str, count: int) -> list[Position]:
        return [Position.objects.create(org_unit=self.unit, title=title, grade='') for _ in range(count)]

    def shared_rows(self, count: int, title: str = 'Developer', first: int = 1) -> list[dict]:
        return [self.row(n, position=title) for n in range(first, first + count)]

    def confirm(self, user, rows=None, *, batch=None, content=None):
        content = content if content is not None else _workbook(rows)
        return self.client_for(user).post(JOBS, {'file': _upload_file(content), 'batch_id': batch or str(uuid.uuid4()), 'file_hash': file_sha256(content)},
                                          format='multipart')

    def drain(self, job_id) -> EmployeeImportJob:
        while run_job(job_id) == 'running':
            pass
        return EmployeeImportJob.objects.get(pk=job_id)

    def new_queued_job(self, rows, **kw) -> EmployeeImportJob:
        content = _workbook(rows)
        job, created = create_job(self.hr, content, batch_id=kw.pop('batch', str(uuid.uuid4())), expected_hash=file_sha256(content))
        self.assertTrue(created)
        return job


def _upload_file(content: bytes):
    from apps.accounts.tests_employee_bulk_import import _upload
    return _upload(content)


class JobFlowTests(_JobCase):
    def test_a_three_employee_import_runs_as_a_job(self):
        self.add_seats('Developer', 3)
        with mock.patch(INVITE):
            response = self.confirm(self.hr, self.shared_rows(3))
        self.assertEqual(response.status_code, 202, response.content)
        progress = self.client_for(self.hr).get(f"{JOBS}{response.json()['data']['job_id']}/").json()['data']
        self.assertEqual((progress['status'], progress['total_rows'], progress['processed_rows'], progress['created'], progress['failed_rows']),
                         ('completed', 3, 3, 3, 0))
        self.assertEqual((progress['invitations']['total'], progress['invitations']['sent']), (3, 3))
        self.assertEqual(len({p.position_id for p in Placement.objects.filter(employee__email__endswith='@import.test')}), 3)   # one seat each

    def test_a_thirteen_employee_import_with_shared_designation(self):
        self.add_seats('Developer', 13)
        with mock.patch(INVITE):
            job_id = self.confirm(self.hr, self.shared_rows(13)).json()['data']['job_id']
        job = EmployeeImportJob.objects.get(pk=job_id)
        self.assertEqual((job.status, job.created_count, job.next_row), ('completed', 13, 13))
        self.assertEqual(bytes(job.content), b'')                                       # the uploaded file is not kept once the job is finished
        self.assertEqual(Placement.objects.filter(employee__email__endswith='@import.test', effective_to__isnull=True).values('position').distinct().count(), 13)

    def test_confirm_returns_before_any_employee_exists_and_the_worker_finishes_it_later(self):
        self.add_seats('Developer', 3)
        with override_settings(RUNNING_TESTS=False), mock.patch(DELAY) as delay:        # the browser got its answer; no worker has run yet
            response = self.confirm(self.hr, self.shared_rows(3))
        self.assertEqual((response.status_code, response.json()['data']['status']), (202, 'queued'))
        delay.assert_called_once()
        self.assertFalse(User.objects.filter(email__endswith='@import.test').exists())
        with mock.patch(INVITE):
            self.assertEqual(self.drain(response.json()['data']['job_id']).status, 'completed')
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 3)

    def test_duplicate_confirm_returns_the_same_job_and_creates_nobody_twice(self):
        self.add_seats('Developer', 3)
        content, batch = _workbook(self.shared_rows(3)), str(uuid.uuid4())
        with mock.patch(INVITE):
            first = self.confirm(self.hr, None, batch=batch, content=content).json()['data']
            second = self.confirm(self.hr, None, batch=batch, content=content).json()['data']
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertEqual((User.objects.filter(email__endswith='@import.test').count(), EmployeeImportJob.objects.count()), (3, 1))

    def test_the_same_file_cannot_be_queued_twice_at_once(self):
        self.add_seats('Developer', 3)
        content = _workbook(self.shared_rows(3))
        with override_settings(RUNNING_TESTS=False), mock.patch(DELAY):
            self.assertEqual(self.confirm(self.hr, None, content=content).status_code, 202)
            again = self.confirm(self.hr, None, content=content)                        # a different batch id, the same file, still queued
        self.assertEqual(again.status_code, 400)
        self.assertEqual(EmployeeImportJob.objects.count(), 1)

    def test_files_that_would_fail_are_refused_at_confirm_and_no_job_is_created(self):
        self.add_seats('Developer', 2)
        cases = {
            'insufficient seats': self.shared_rows(3),                                            # 3 people, 2 seats
            'duplicate rows': [self.row(1, position='Developer'), self.row(2, position='Developer', email='asha1@import.test')],
            'existing employee': [self.row(1, position='Developer', email=self.plain.email)],
        }
        for label, rows in cases.items():
            response = self.confirm(self.hr, rows)
            self.assertEqual(response.status_code, 400, label)
        self.assertFalse(EmployeeImportJob.objects.exists())

    def test_a_row_that_stops_validating_becomes_a_row_error_and_the_others_still_import(self):
        job = self.new_queued_job([self.row(1), self.row(2), self.row(3)])               # Analyst 1..3, all valid right now
        taker = make_user('taker_job@test.com', employee_id='TJ001', branch=self.hyd.branch_name)
        Placement.objects.create(position=self.seats[2], employee=taker, effective_from='2020-01-01')     # someone fills seat 2 before the worker runs
        with mock.patch(INVITE):
            job = self.drain(job.pk)
        self.assertEqual((job.status, job.created_count, job.failed_count), ('completed_with_errors', 2, 1))
        error = EmployeeImportJobError.objects.get()
        self.assertEqual(error.row_number, 3)
        self.assertIn('occupied', ' '.join(error.messages))
        self.assertFalse(User.objects.filter(email='asha2@import.test').exists())
        report = self.client_for(self.hr).get(f'{JOBS}{job.pk}/errors/')
        sheet = openpyxl.load_workbook(io.BytesIO(report.content))['Import Errors']
        self.assertEqual(sheet.max_row, 2)                                                 # header + the one failed row

    def test_only_the_importer_can_see_a_job(self):
        self.add_seats('Developer', 1)
        with mock.patch(INVITE):
            job_id = self.confirm(self.hr, self.shared_rows(1)).json()['data']['job_id']
        self.assertEqual(self.client_for(self.admin).get(f'{JOBS}{job_id}/').status_code, 404)
        self.assertEqual(self.client_for(self.plain).get(f'{JOBS}{job_id}/').status_code, 403)
        self.assertEqual(len(self.client_for(self.hr).get(JOBS).json()['data']['jobs']), 1)


@override_settings(EMPLOYEE_IMPORT_COMMIT_BATCH=2, EMPLOYEE_IMPORT_CHUNK_SIZE=4)
class CheckpointAndRecoveryTests(_JobCase):
    def test_chunks_and_commit_batches_advance_a_checkpoint(self):
        self.add_seats('Developer', 7)
        job = self.new_queued_job(self.shared_rows(7))
        with mock.patch(INVITE):
            self.assertEqual(run_job(job.pk), 'running')                                  # the first run handles one chunk (4 rows) and stops
            mid = EmployeeImportJob.objects.get(pk=job.pk)
            self.assertEqual((mid.next_row, mid.created_count, mid.lease_until), (4, 4, None))     # checkpoint saved, lease released
            self.assertEqual(run_job(job.pk), 'completed')
        self.assertEqual(EmployeeImportJob.objects.get(pk=job.pk).created_count, 7)

    def test_worker_crash_midway_resumes_at_the_checkpoint_without_duplicates(self):
        self.add_seats('Developer', 6)
        job = self.new_queued_job(self.shared_rows(6))
        original, calls = job_module._create_one, {'n': 0}

        def crash(importer, result, ip):
            calls['n'] += 1
            if calls['n'] == 4:                                  # the 4th employee: the middle of the second commit batch
                raise RuntimeError('worker died')
            return original(importer, result, ip)
        with mock.patch.object(job_module, '_create_one', crash), mock.patch(INVITE):
            self.assertEqual(run_job(job.pk), 'retry_later')
        crashed = EmployeeImportJob.objects.get(pk=job.pk)
        self.assertEqual((crashed.next_row, crashed.created_count), (2, 2))                  # batch 1 committed; batch 2 rolled back as a whole
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 2)      # no half-created employee from batch 2
        with mock.patch(INVITE):
            self.assertEqual(run_job(job.pk), 'completed')                                   # the retry resumes at row 3
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 6)
        self.assertEqual(EmployeeImportInvite.objects.filter(batch_id=job.pk).count(), 6)
        self.assertEqual(Placement.objects.filter(employee__email__endswith='@import.test').values('position').distinct().count(), 6)

    def test_a_batch_that_keeps_failing_fails_the_job_and_keeps_what_was_committed(self):
        self.add_seats('Developer', 4)
        job = self.new_queued_job(self.shared_rows(4))
        original, calls = job_module._create_one, {'n': 0}

        def always_crash_from_the_third(importer, result, ip):
            calls['n'] += 1
            if calls['n'] > 2:
                raise RuntimeError('boom')
            return original(importer, result, ip)
        with mock.patch.object(job_module, '_create_one', always_crash_from_the_third), mock.patch(INVITE):
            outcomes = [run_job(job.pk) for _ in range(job_module.MAX_STALLS)]
        failed = EmployeeImportJob.objects.get(pk=job.pk)
        self.assertEqual((outcomes[-1], failed.status, failed.failure_code, failed.created_count), ('failed', 'failed', 'batch_failed', 2))
        self.assertEqual(bytes(failed.content), b'')

    def test_a_live_lease_blocks_a_second_worker_and_a_finished_job_cannot_run_again(self):
        self.add_seats('Developer', 2)
        job = self.new_queued_job(self.shared_rows(2))
        EmployeeImportJob.objects.filter(pk=job.pk).update(status='running', lease_until=timezone.now() + datetime.timedelta(minutes=5))
        self.assertEqual(run_job(job.pk), 'not_runnable')                                  # duplicate execution while a worker is alive
        EmployeeImportJob.objects.filter(pk=job.pk).update(lease_until=timezone.now() - datetime.timedelta(minutes=1))
        with mock.patch(INVITE):
            self.assertEqual(run_job(job.pk), 'completed')                                 # the worker died: its lease expired
            self.assertEqual(run_job(job.pk), 'not_runnable')                              # and a task run twice does nothing more
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 2)

    def test_redis_down_at_dispatch_leaves_the_job_queued_and_the_sweep_recovers_it(self):
        self.add_seats('Developer', 3)
        with override_settings(RUNNING_TESTS=False), mock.patch(DELAY, side_effect=ConnectionError('redis down')):
            response = self.confirm(self.hr, self.shared_rows(3))
        self.assertEqual((response.status_code, response.json()['data']['status']), (202, 'queued'))   # the user is not shown an error
        job_id = response.json()['data']['job_id']
        EmployeeImportJob.objects.filter(pk=job_id).update(updated_at=timezone.now() - datetime.timedelta(hours=1))
        with mock.patch(DELAY, side_effect=lambda jid: run_job(jid)), mock.patch(INVITE):
            result = requeue_stale_jobs()
        self.assertEqual((result['queued_waiting'], result['dispatched']), (1, 1))
        self.assertEqual(EmployeeImportJob.objects.get(pk=job_id).status, 'completed')

    def test_a_dead_workers_job_is_found_by_the_sweep_after_its_lease_expires(self):
        self.add_seats('Developer', 3)
        job = self.new_queued_job(self.shared_rows(3))
        EmployeeImportJob.objects.filter(pk=job.pk).update(
            status='running', lease_until=timezone.now() - datetime.timedelta(minutes=1), updated_at=timezone.now() - datetime.timedelta(hours=1))
        with mock.patch(DELAY) as delay:
            self.assertEqual(requeue_stale_jobs()['lease_expired'], 1)
        delay.assert_called_once_with(str(job.pk))

    def test_cancelling_a_queued_job_and_a_running_job(self):
        self.add_seats('Developer', 6)
        queued = self.new_queued_job(self.shared_rows(2, first=1))
        self.assertEqual(self.client_for(self.hr).post(f'{JOBS}{queued.pk}/cancel/').json()['data']['status'], 'cancelled')
        self.assertFalse(User.objects.filter(email__endswith='@import.test').exists())
        running = self.new_queued_job(self.shared_rows(4, first=10))
        with mock.patch(INVITE):
            self.assertEqual(run_job(running.pk, max_rows=2), 'running')                  # two employees committed
        self.client_for(self.hr).post(f'{JOBS}{running.pk}/cancel/')
        with mock.patch(INVITE):
            self.assertEqual(run_job(running.pk), 'cancelled')                             # stops at the next batch boundary
        done = EmployeeImportJob.objects.get(pk=running.pk)
        self.assertEqual((done.created_count, done.next_row, bytes(done.content)), (2, 2, b''))   # committed employees stay; nobody else is created

    def test_invitation_progress_is_part_of_the_job_and_failed_invitations_can_be_retried(self):
        self.add_seats('Developer', 2)
        import smtplib
        with mock.patch(INVITE, side_effect=[smtplib.SMTPRecipientsRefused({}), None]):
            job_id = self.confirm(self.hr, self.shared_rows(2)).json()['data']['job_id']
        progress = self.client_for(self.hr).get(f'{JOBS}{job_id}/').json()['data']
        self.assertEqual((progress['invitations']['sent'], progress['invitations']['failed'], len(progress['invitation_failures'])), (1, 1, 1))
        with mock.patch(INVITE), mock.patch('apps.accounts.tasks.send_import_invite.delay'):
            retried = self.client_for(self.hr).post(f'/api/employees/bulk-import/invites/{job_id}/retry/').json()['data']
        self.assertEqual(retried['requeued'], 1)


@override_settings(EMPLOYEE_IMPORT_JOB_MAX_ROWS=5000, EMPLOYEE_IMPORT_CHUNK_SIZE=2000, EMPLOYEE_IMPORT_COMMIT_BATCH=500)
class EngineAtScaleTests(_ImportCase):
    """ENGINE tests: the per-employee creation is replaced by a minimal stub, so these prove chunking, checkpoints and progress at 500
    and 2,500 rows, NOT how fast real employees can be created (see the benchmark for that)."""

    def run_engine(self, count: int):
        rows = [self.row(n) for n in range(1, count + 1)]
        content = _workbook(rows)

        def fake_validate(importer, parsed: ParsedFile):
            return [RowResult(row=row, values=values) for row, values in parsed.rows]

        def fake_create(importer, result, ip):
            return User.objects.create_user(email=result.values['email'], password=None, full_name='Stub', employee_id=f'ST{result.row:06}', account_activated_at=None)
        with mock.patch.object(job_module, 'validate_rows', fake_validate), mock.patch.object(job_module, '_create_one', fake_create), \
                mock.patch.object(job_module, 'enqueue_ids', return_value=0):
            job, _ = create_job(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))
            runs, started = 0, time.perf_counter()
            while True:
                runs += 1
                if run_job(job.pk) != 'running':
                    break
        job = EmployeeImportJob.objects.get(pk=job.pk)
        print(f'ENGINE n={count}: {runs} task runs, {time.perf_counter() - started:.1f}s (stubbed employee creation)')
        return job, runs

    def test_five_hundred_rows_one_chunk(self):
        job, runs = self.run_engine(500)
        self.assertEqual((job.status, job.created_count, job.next_row, runs), ('completed', 500, 500, 1))
        self.assertEqual(EmployeeImportInvite.objects.filter(batch_id=job.pk).count(), 500)

    def test_twenty_five_hundred_rows_cross_the_two_thousand_row_chunk_boundary(self):
        job, runs = self.run_engine(2500)
        self.assertEqual((job.status, job.created_count, job.next_row, runs), ('completed', 2500, 2500, 2))     # 2,000 + 500
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 2500)


@unittest.skipUnless(os.environ.get('RUN_IMPORT_BENCHMARK') == '1', 'Measures real timing; slow against a remote database. Opt in with RUN_IMPORT_BENCHMARK=1.')
class BenchmarkTests(_JobCase):
    """REAL employee creation, real seat allocation, real database. Prints elapsed time and the number of database queries."""

    def measure(self, count: int):
        self.add_seats('Bench', count)
        content = _workbook([self.row(n, position='Bench') for n in range(1, count + 1)])
        began = time.perf_counter()
        job, _ = create_job(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))
        confirm_seconds = time.perf_counter() - began
        with mock.patch.object(job_module, 'enqueue_ids', return_value=0), CaptureQueriesContext(connection) as queries:
            began = time.perf_counter()
            job = self.drain(job.pk)
            run_seconds = time.perf_counter() - began
        print(f'BENCHMARK n={count}: confirm {confirm_seconds:.1f}s | creation {run_seconds:.1f}s = {run_seconds / count:.2f}s per employee | '
              f'{len(queries)} queries = {len(queries) / count:.0f} per employee')
        self.assertEqual((job.status, job.created_count), ('completed', count))

    def test_benchmark_3(self):
        self.measure(3)

    def test_benchmark_13(self):
        self.measure(13)

    def test_benchmark_100(self):
        self.measure(100)


@unittest.skipUnless(os.environ.get('RUN_DB_FLUSHING_TESTS') == '1', 'Flushes the whole test database. Opt in with RUN_DB_FLUSHING_TESTS=1 on a throwaway database.')
class ConcurrentJobTests(TransactionTestCase):
    """Two imports racing for the last seats on real threads and real connections: nobody gets a seat that is already taken."""

    def test_two_jobs_racing_for_three_seats_never_double_book(self):
        branch = make_branch('JB-HYD', 'Job Hyderabad')
        unit = OrgUnit.objects.create(name='Job Unit')
        seats = [Position.objects.create(org_unit=unit, title='Dev', grade='') for _ in range(3)]
        importer = make_user('job_race@test.com', employee_id='JR001', is_superuser=True, branch=branch.branch_name)

        def file_of(tag):
            return _workbook([{'first_name': f'Racer{tag}{n}', 'last_name': 'T', 'email': f'racer{tag}{n}@race.test', 'date_of_joining': '2026-11-10',
                               'branch': 'JB-HYD', 'org_unit': 'Job Unit', 'position': 'Dev'} for n in (1, 2)])
        jobs = []
        for tag in ('a', 'b'):
            content = file_of(tag)
            jobs.append(create_job(importer, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))[0])     # both valid: 3 free seats
        barrier = threading.Barrier(2)

        def work(job):
            try:
                barrier.wait(timeout=60)
                while run_job(job.pk) == 'running':
                    pass
            finally:
                connection.close()
        with mock.patch(INVITE), mock.patch.object(job_module, 'enqueue_ids', return_value=0):      # patched once, outside the threads
            with ThreadPoolExecutor(max_workers=2) as pool:
                for future in [pool.submit(work, job) for job in jobs]:
                    future.result()
        held = list(Placement.objects.filter(position__in=seats).values_list('position_id', flat=True))
        self.assertEqual((len(held), len(set(held))), (3, 3))                                 # every seat held once, three employees in all
        finished = sorted(EmployeeImportJob.objects.values_list('created_count', 'failed_count'))
        self.assertEqual(finished, [(1, 1), (2, 0)])                                          # one job got both of its seats, the other lost one
        self.assertEqual(AuditLog.objects.filter(action='employee_bulk_import_job_finished').count(), 2)
