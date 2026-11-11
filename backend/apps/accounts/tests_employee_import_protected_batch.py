"""
Protecting one invitation batch from every sending path (no code change needed: the existing 'skipped' status does it).

Used for the original 13-invitation UAT batch, which must never be sent, retried or recovered automatically, while a newer batch in
the same table stays eligible. The UPDATE below is exactly the one applied to UAT. No email is ever sent: sending is mocked.
"""
from __future__ import annotations

import datetime
import uuid
from unittest import mock

from django.utils import timezone

from apps.accounts import services_employee_import_invites as invites
from apps.accounts.models import EmployeeImportInvite
from apps.accounts.tests_employee_import_invites import DELAY, INVITE, _InviteCase

PROTECTED_REASON = 'protected_by_admin'
HOUR = datetime.timedelta(hours=1)


def protect_batch(batch_id: uuid.UUID, expected: int) -> int:
    """The exact change applied to UAT: only pending, never-attempted rows of ONE batch, and only if the count is what was verified."""
    rows = EmployeeImportInvite.objects.filter(batch_id=batch_id, status='pending', attempts=0)
    if rows.count() != expected:
        raise RuntimeError(f'expected {expected} rows, found {rows.count()}: nothing changed')
    return rows.update(status='skipped', reason_code=PROTECTED_REASON, updated_at=timezone.now())


class ProtectedBatchTests(_InviteCase):
    def setUp(self):
        super().setUp()
        self.protected_batch, self.new_batch = uuid.uuid4(), uuid.uuid4()
        self.old = [self.invite(self.employee(n), batch_id=self.protected_batch) for n in range(1, 4)]       # stands in for the 13
        self.new = [self.invite(self.employee(n), batch_id=self.new_batch) for n in range(4, 6)]             # stands in for the 3
        EmployeeImportInvite.objects.update(updated_at=timezone.now() - HOUR)                                 # old enough for the recovery sweep
        self.assertEqual(protect_batch(self.protected_batch, 3), 3)

    def statuses(self, batch):
        return sorted(EmployeeImportInvite.objects.filter(batch_id=batch).values_list('status', 'reason_code', 'attempts'))

    def test_the_sweep_queues_only_the_new_batch(self):
        with mock.patch(DELAY) as delay:
            result = invites.requeue_stale()
        self.assertEqual(result['queued'], 2)
        self.assertEqual({call.args[0] for call in delay.call_args_list}, {str(i.pk) for i in self.new})

    def test_queueing_the_protected_batch_directly_queues_nothing(self):
        with mock.patch(DELAY) as delay:
            self.assertEqual(invites.enqueue_batch(self.protected_batch), 0)
        delay.assert_not_called()

    def test_a_worker_handed_a_protected_invitation_sends_nothing_and_changes_nothing(self):
        before = self.statuses(self.protected_batch)
        with mock.patch(INVITE) as send:
            for invite in self.old:
                invites.process_invite(invite.pk)
        send.assert_not_called()
        self.assertEqual(self.statuses(self.protected_batch), before)

    def test_retry_never_revives_the_protected_invitations(self):
        with mock.patch(DELAY) as delay, mock.patch(INVITE) as send:
            self.assertEqual(invites.retry_batch(self.importer, self.protected_batch)['requeued'], 0)
        delay.assert_not_called()
        send.assert_not_called()
        self.assertEqual({row[0] for row in self.statuses(self.protected_batch)}, {'skipped'})

    def test_the_new_batch_is_still_pending_eligible_and_sends(self):
        self.assertEqual({row[0] for row in self.statuses(self.new_batch)}, {'pending'})
        with mock.patch(INVITE) as send:
            self.assertEqual([invites.process_invite(i.pk) for i in self.new], ['sent', 'sent'])
        self.assertEqual(send.call_count, 2)
        self.assertEqual({row[0] for row in self.statuses(self.protected_batch)}, {'skipped'})

    def test_records_and_history_are_preserved_and_the_change_is_reversible(self):
        self.assertEqual(EmployeeImportInvite.objects.filter(batch_id=self.protected_batch).count(), 3)
        self.assertEqual({row[1] for row in self.statuses(self.protected_batch)}, {PROTECTED_REASON})
        EmployeeImportInvite.objects.filter(batch_id=self.protected_batch, reason_code=PROTECTED_REASON).update(status='pending', reason_code='')
        self.assertEqual({row[0] for row in self.statuses(self.protected_batch)}, {'pending'})

    def test_the_protection_refuses_to_run_if_the_count_is_not_what_was_verified(self):
        with self.assertRaises(RuntimeError):
            protect_batch(self.new_batch, 3)                                  # the new batch has 2, not 3
        self.assertEqual({row[0] for row in self.statuses(self.new_batch)}, {'pending'})

    def test_it_does_not_touch_a_row_that_was_already_attempted(self):
        other = uuid.uuid4()
        attempted = self.invite(self.employee(9), batch_id=other, attempts=2)
        fresh = self.invite(self.employee(10), batch_id=other)
        with self.assertRaises(RuntimeError):
            protect_batch(other, 2)                                           # only 1 qualifies, so the guard stops the whole thing
        self.assertEqual((self.reload(attempted).status, self.reload(fresh).status), ('pending', 'pending'))
