"""
Joining notifications are safe to run from several workers at once: at most ONE notification per recipient per joining event
(an employee plus a joining date), however many tasks race. Uses real threads on real connections, so it is a TransactionTestCase.

OPT-IN: a TransactionTestCase empties EVERY table when it ends, including the rows the migrations seed (permissions, baseline
permissions, org seeds). On a kept test database (--keepdb) that breaks every later run. Django's serialized_rollback does not
help (it restores rows at the START of a test, never after the last one). So these tests are skipped unless you ask for them, and
you should only ask on a throwaway database, i.e. WITHOUT --keepdb, which destroys the test database afterwards:

    RUN_DB_FLUSHING_TESTS=1 python manage.py test apps.accounts.tests_joining_notification_concurrency --noinput
"""
from __future__ import annotations

import datetime
import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.accounts.services_joining_notifications import _notify, notify_joiners
from apps.accounts.tests_employee_scope import make_branch
from apps.notifications.models import Notification

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)
WORKERS = 6


@unittest.skipUnless(
    os.environ.get('RUN_DB_FLUSHING_TESTS') == '1',
    'Flushes the whole test database (including migration-seeded rows). Opt in with RUN_DB_FLUSHING_TESTS=1 on a throwaway '
    'test database (no --keepdb); see the module docstring.',
)
class JoiningNotificationConcurrencyTests(TransactionTestCase):
    """Real threads need COMMITTED rows, hence TransactionTestCase and the opt-in above."""

    def setUp(self):
        branch = make_branch('JC-A', 'Joining Concurrency Branch').branch_name
        self.manager = make_user('jc_mgr@test.com', role=make_role('jc_mgr', permission_codenames=['leave.approve'], can_manage_team=True),
                                 employee_id='JC001', branch=branch, date_of_joining=TODAY - 300 * DAY)
        self.hr = make_user('jc_hr@test.com', role=make_role('jc_hr', permission_codenames=['onboarding.approve', 'employees.view']),
                            employee_id='JC002', branch=branch, date_of_joining=TODAY - 300 * DAY)
        self.employee = make_user('jc_emp@test.com', employee_id='JC100', branch=branch, date_of_joining=TODAY, reporting_manager=self.manager)

    def _race(self, call, workers: int = WORKERS):
        """Run `call` in `workers` threads released at the same instant, each on its own database connection."""
        barrier = threading.Barrier(workers)

        def run():
            try:
                barrier.wait(timeout=30)
                return call()
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return [future.result() for future in [pool.submit(run) for _ in range(workers)]]

    def _count(self, user):
        return Notification.objects.filter(user=user, notification_type='system', module='system').count()

    def test_concurrent_workers_send_each_notification_once(self):
        original_create = Notification.objects.create

        def slow_create(*args, **kwargs):
            time.sleep(0.4)          # widen the window between "not sent yet" and "sent", where a race would double-send
            return original_create(*args, **kwargs)

        with mock.patch.object(Notification.objects, 'create', side_effect=slow_create):
            self._race(lambda: _notify(self.employee, self.manager, 'manager', TODAY))
        self.assertEqual(self._count(self.manager), 1)
        self.assertEqual(AuditLog.objects.filter(action='joining_notification_sent', changes__recipient=str(self.manager.pk)).count(), 1)

    def test_whole_task_run_by_several_workers_at_once(self):
        self._race(notify_joiners)
        for user in (self.employee, self.manager, self.hr):
            self.assertEqual(self._count(user), 1, user.email)
        self.assertEqual(AuditLog.objects.filter(action='joining_notification_sent').count(), 3)

    def test_running_again_later_sends_nothing_more(self):
        notify_joiners()
        self.assertEqual(notify_joiners()['sent'], 0)
        self.assertEqual(Notification.objects.filter(notification_type='system').count(), 3)

    def test_different_recipients_each_get_theirs(self):
        _notify(self.employee, self.manager, 'manager', TODAY)
        _notify(self.employee, self.hr, 'hr', TODAY)
        self.assertEqual((self._count(self.manager), self._count(self.hr)), (1, 1))

    def test_a_new_joining_date_is_a_new_event(self):
        # Rehire: the same person with a later joining date is notified again, once, even under a race.
        _notify(self.employee, self.manager, 'manager', TODAY - 400 * DAY)
        self._race(lambda: _notify(self.employee, self.manager, 'manager', TODAY))
        self.assertEqual(self._count(self.manager), 2)
        self._race(lambda: _notify(self.employee, self.manager, 'manager', TODAY))
        self.assertEqual(self._count(self.manager), 2)

    def test_a_switched_off_preference_is_still_recorded_exactly_once(self):
        from apps.notifications.models import NotificationSettings

        NotificationSettings.objects.create(user=self.hr, is_system_enabled=False)
        self._race(lambda: _notify(self.employee, self.hr, 'hr', TODAY))
        self.assertEqual(self._count(self.hr), 0)
        markers = AuditLog.objects.filter(action='joining_notification_sent', changes__recipient=str(self.hr.pk))
        self.assertEqual(markers.count(), 1)
        self.assertFalse(markers.get().changes['delivered'])
