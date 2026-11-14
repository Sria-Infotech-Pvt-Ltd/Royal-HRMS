"""
Timesheets are safe when several requests arrive at the same instant (a double click, two tabs, two approvers): one submit, one
decision, one sheet per week. Uses real threads on real connections, so it is a TransactionTestCase.

OPT-IN, for the same reason as apps.accounts.tests_joining_notification_concurrency: a TransactionTestCase empties EVERY table when
it ends, including the rows the migrations seed. Run it only on a throwaway test database, i.e. WITHOUT --keepdb:

    RUN_DB_FLUSHING_TESTS=1 TEST_DB_SUFFIX=tsc python manage.py test apps.attendance.tests_timesheet_concurrency --noinput
"""
from __future__ import annotations

import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase

from apps.accounts.factories import make_user
from apps.accounts.models import ApprovalWorkflowRule, AuditLog
from apps.attendance.models_timesheet import Timesheet, TimesheetEvent
from apps.attendance.services_timesheet import save_draft, submit
from apps.attendance.services_timesheet_common import TimesheetConflict, TimesheetError
from apps.attendance.services_timesheet_decisions import approve, return_to_employee
from apps.attendance.tests_timesheet_support import MONDAY, cell, internal_line, pinned_today
from apps.notifications.models import Notification

WORKERS = 6
EMAIL_TASK = 'apps.notifications.tasks.send_lifecycle_email_task.apply_async'


@unittest.skipUnless(
    os.environ.get('RUN_DB_FLUSHING_TESTS') == '1',
    'Flushes the whole test database (including migration-seeded rows). Opt in with RUN_DB_FLUSHING_TESTS=1 on a throwaway '
    'test database (no --keepdb); see the module docstring.',
)
class TimesheetConcurrencyTests(TransactionTestCase):
    def setUp(self):
        ApprovalWorkflowRule.objects.get_or_create(workflow_type='timesheet', defaults={'l1_approver_kind': 'reporting_manager', 'l2_approver_kind': 'hr'})
        self.manager = make_user('tc_mgr@test.com', employee_id='TCM001', branch='TC-Branch')
        self.employee = make_user('tc_emp@test.com', employee_id='TCE001', branch='TC-Branch', reporting_manager=self.manager)
        patcher = mock.patch(EMAIL_TASK)
        patcher.start()
        self.addCleanup(patcher.stop)

    def race(self, calls):
        """Run each callable in its own thread and connection, all released at the same instant. Returns outcomes: result or exception."""
        barrier = threading.Barrier(len(calls))

        def run(call):
            try:
                barrier.wait(timeout=30)
                return call()
            except TimesheetError as exc:
                return exc
            finally:
                connection.close()

        with pinned_today(), ThreadPoolExecutor(max_workers=len(calls)) as pool:
            return [future.result() for future in [pool.submit(run, call) for call in calls]]

    def draft(self):
        with pinned_today():
            save_draft(self.employee, MONDAY, {'lines': [internal_line(cell(0, '8'))]})
        return Timesheet.objects.get(employee=self.employee)

    def submitted(self):
        self.draft()
        with pinned_today():
            submit(self.employee, MONDAY)
        return Timesheet.objects.get(employee=self.employee)

    @staticmethod
    def slowly(original):
        """Pause between 'the state was checked' and 'the decision is recorded', where an unprotected race would double-act."""
        def wrapper(*args, **kwargs):
            time.sleep(0.3)
            return original(*args, **kwargs)
        return wrapper

    def test_simultaneous_first_saves_make_one_sheet_and_no_error(self):
        outcomes = self.race([lambda: save_draft(self.employee, MONDAY, {'lines': [internal_line(cell(0, '8'))]}) for _ in range(WORKERS)])
        self.assertEqual([o for o in outcomes if isinstance(o, Exception)], [])
        self.assertEqual(Timesheet.objects.filter(employee=self.employee, week_start=MONDAY).count(), 1)

    def test_simultaneous_submits_submit_exactly_once(self):
        self.draft()
        import apps.attendance.services_timesheet as service
        with mock.patch.object(service, 'record_event', self.slowly(service.record_event)):
            outcomes = self.race([lambda: submit(self.employee, MONDAY) for _ in range(WORKERS)])
        successes = [o for o in outcomes if not isinstance(o, Exception)]
        conflicts = [o for o in outcomes if isinstance(o, TimesheetConflict)]
        self.assertEqual((len(successes), len(conflicts)), (1, WORKERS - 1))
        sheet = Timesheet.objects.get(employee=self.employee)
        self.assertEqual((sheet.status, sheet.submit_count), ('submitted', 1))
        self.assertEqual(TimesheetEvent.objects.filter(timesheet=sheet, event_type='submitted').count(), 1)
        self.assertEqual(AuditLog.objects.filter(action='timesheet_submitted').count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.manager, notification_type='timesheet_submitted').count(), 1)

    def test_simultaneous_approvals_approve_exactly_once(self):
        sheet = self.submitted()
        import apps.attendance.services_timesheet_decisions as decisions
        with mock.patch.object(decisions, 'record_event', self.slowly(decisions.record_event)):
            outcomes = self.race([lambda: approve(sheet.pk, self.manager) for _ in range(WORKERS)])
        self.assertEqual(len([o for o in outcomes if not isinstance(o, Exception)]), 1)
        self.assertEqual(len([o for o in outcomes if isinstance(o, TimesheetConflict)]), WORKERS - 1)
        self.assertEqual(TimesheetEvent.objects.filter(timesheet=sheet, event_type='approved').count(), 1)
        self.assertEqual(AuditLog.objects.filter(action='timesheet_approved').count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.employee, notification_type='timesheet_approved').count(), 1)

    def test_an_approve_racing_a_send_back_ends_with_exactly_one_decision(self):
        sheet = self.submitted()
        import apps.attendance.services_timesheet_decisions as decisions
        calls = [lambda: approve(sheet.pk, self.manager) for _ in range(3)] + [lambda: return_to_employee(sheet.pk, self.manager, 'Fix it') for _ in range(3)]
        with mock.patch.object(decisions, 'record_event', self.slowly(decisions.record_event)):
            outcomes = self.race(calls)
        self.assertEqual(len([o for o in outcomes if not isinstance(o, Exception)]), 1)
        sheet.refresh_from_db()
        decided = list(TimesheetEvent.objects.filter(timesheet=sheet, event_type__in=['approved', 'returned']))
        self.assertEqual(len(decided), 1)
        self.assertEqual(sheet.status, decided[0].event_type)           # the status and the one recorded decision agree

    def test_a_submit_racing_a_save_never_leaves_a_half_written_sheet(self):
        self.draft()
        calls = [lambda: submit(self.employee, MONDAY)] + [lambda: save_draft(self.employee, MONDAY, {'lines': [internal_line(cell(0, '6'))]}) for _ in range(3)]
        outcomes = self.race(calls)
        self.assertEqual([o for o in outcomes if isinstance(o, Exception) and not isinstance(o, TimesheetConflict)], [])
        sheet = Timesheet.objects.get(employee=self.employee)
        self.assertEqual(sheet.total_hours, sum(entry.hours for line in sheet.lines.all() for entry in line.entries.all()))
