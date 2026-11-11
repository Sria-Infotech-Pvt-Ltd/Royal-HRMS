"""
Real-thread races for the import invitation pipeline: two imports for one employee, and two workers on one invitation.

Real threads need COMMITTED rows on separate connections, hence TransactionTestCase, and that empties every table (including the
rows migrations seed) when each test ends. So these are OPT-IN and must only run on a throwaway test database (never --keepdb on a
database you intend to reuse):

    RUN_DB_FLUSHING_TESTS=1 python manage.py test apps.accounts.tests_employee_import_invites_concurrency --noinput

No email is ever sent: the mail-sending function is mocked.
"""
from __future__ import annotations

import os
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.db import connection, transaction
from django.test import TransactionTestCase

from apps.accounts import services_employee_import_invites as invites
from apps.accounts.factories import make_user
from apps.accounts.models import EmployeeImportInvite

SEND = 'apps.accounts.services_employee_import_invites.send_activation_invite'


@unittest.skipUnless(
    os.environ.get('RUN_DB_FLUSHING_TESTS') == '1',
    'Flushes the whole test database (including migration-seeded rows). Opt in with RUN_DB_FLUSHING_TESTS=1 on a throwaway test '
    'database; see the module docstring.',
)
class ConcurrentInviteTests(TransactionTestCase):
    def setUp(self):
        self.importer = make_user('cc_importer@test.com', employee_id='CC000', is_superuser=True)
        self.employee = make_user('cc_employee@test.com', employee_id='CC001', account_activated_at=None)

    def _race(self, calls):
        """Run the callables at the same instant, each on its own database connection."""
        barrier = threading.Barrier(len(calls))

        def run(call):
            try:
                barrier.wait(timeout=60)
                return call()
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            return [future.result() for future in [pool.submit(run, call) for call in calls]]

    def test_two_imports_racing_for_one_employee_leave_exactly_one_open_invitation(self):
        def import_batch():
            with transaction.atomic():
                invites.create_invites(self.importer, uuid.uuid4(), [(2, str(self.employee.pk), self.employee.employee_id)])
                time.sleep(1.5)                       # keep this transaction open so the other import overlaps it
        self._race([import_batch, import_batch])
        rows = list(EmployeeImportInvite.objects.filter(user=self.employee).values_list('status', 'reason_code'))
        self.assertEqual(sorted(status for status, _reason in rows), ['pending', 'skipped'])
        self.assertEqual([reason for status, reason in rows if status == 'skipped'], ['duplicate_open_invite'])

    def test_two_workers_taking_one_invitation_send_it_once(self):
        invite = EmployeeImportInvite.objects.create(batch_id=uuid.uuid4(), user=self.employee, created_by=self.importer, row_number=2)
        sent = []

        def slow_send(user, **_kwargs):
            sent.append(user.pk)
            time.sleep(1.5)                           # the other worker arrives while this send is still in progress
        with mock.patch(SEND, side_effect=slow_send):
            outcomes = self._race([lambda: invites.process_invite(invite.pk), lambda: invites.process_invite(invite.pk)])
        self.assertEqual(len(sent), 1)
        self.assertIn('sent', outcomes)
        self.assertTrue(set(outcomes) <= {'sent', 'in_progress', 'busy_or_missing'}, outcomes)
        invite.refresh_from_db()
        self.assertEqual((invite.status, invite.attempts), ('sent', 1))

    def test_a_sweep_racing_a_worker_does_not_double_send(self):
        invite = EmployeeImportInvite.objects.create(batch_id=uuid.uuid4(), user=self.employee, created_by=self.importer, row_number=2)
        EmployeeImportInvite.objects.filter(pk=invite.pk).update(updated_at='2000-01-01T00:00:00Z')   # looks "never queued"
        sent = []
        with mock.patch(SEND, side_effect=lambda user, **_kw: (sent.append(user.pk), time.sleep(1.0))), \
                mock.patch('apps.accounts.tasks.send_import_invite.delay', side_effect=lambda pk: invites.process_invite(pk)):
            self._race([lambda: invites.process_invite(invite.pk), invites.requeue_stale])
        self.assertEqual(len(sent), 1)
