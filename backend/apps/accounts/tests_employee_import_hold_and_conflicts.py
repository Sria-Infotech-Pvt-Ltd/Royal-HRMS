"""
Two safety properties of the bulk employee import:

1. The invitation HOLD (EMPLOYEE_IMPORT_INVITES_ENABLED, off by default): while it is off nothing is queued, claimed, tokenised or
   emailed, whether the call comes from the pipeline, a Celery task, the Beat sweep or the sending function itself.
2. ROW-LEVEL CONFLICTS: a duplicate email, duplicate employee record or taken seat that appears AFTER a row was validated (a
   concurrent import, a manual hire) skips only that row; every other row of the batch is still imported and the job finishes.

No real email is ever sent: the mail function and the SMTP connection are mocked in every test.
"""
from __future__ import annotations

from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import override_settings
from django.utils import timezone

from apps.accounts import services_employee_import_invites as invites
from apps.accounts import services_employee_import_job as job_module
from apps.accounts import tasks_employee_import as tasks
from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, EmailLog, EmployeeImportInvite, EmployeeImportJobError, PasswordResetToken, User
from apps.accounts.services_employee_import_invite_policy import InviteSendingHeld, invites_enabled
from apps.accounts.tests_employee_bulk_import import INVITE
from apps.accounts.tests_employee_import_invites import DELAY, HOUR, _InviteCase
from apps.accounts.tests_employee_import_jobs import _JobCase
from apps.accounts.utils import send_activation_invite

SMTP = 'apps.accounts.utils._get_smtp_connection'


def _held():
    return override_settings(EMPLOYEE_IMPORT_INVITES_ENABLED=False)


class InvitationHoldTests(_InviteCase):
    def assert_untouched(self, invite):
        fresh = self.reload(invite)
        self.assertEqual((fresh.status, fresh.attempts, fresh.processing_started_at), ('pending', 0, None))
        self.assertFalse(PasswordResetToken.objects.exists())
        self.assertFalse(EmailLog.objects.exists())

    def test_the_hold_is_on_when_the_setting_is_missing(self):
        with override_settings():
            del settings.EMPLOYEE_IMPORT_INVITES_ENABLED
            self.assertFalse(invites_enabled())

    def test_a_held_invitation_is_left_exactly_as_it_was(self):
        invite = self.invite(self.employee(1))
        with _held(), mock.patch(INVITE) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'held')
        send.assert_not_called()
        self.assert_untouched(invite)

    def test_the_sending_function_itself_refuses_and_writes_nothing(self):
        user = self.employee(1)
        with _held(), mock.patch(SMTP) as smtp:
            with self.assertRaises(InviteSendingHeld):
                send_activation_invite(user, bulk_import=True)
        smtp.assert_not_called()
        self.assertFalse(PasswordResetToken.objects.filter(user=user).exists())          # no token: the current link is not invalidated
        self.assertFalse(EmailLog.objects.exists())

    def test_other_callers_of_the_sending_function_are_not_held(self):
        # Only the bulk-import pipeline asks for the hold; a deliberate single hire / Resend Invite is a different decision.
        with _held(), mock.patch(SMTP, side_effect=RuntimeError('reached the mail server')):
            with self.assertRaisesMessage(RuntimeError, 'reached the mail server'):
                send_activation_invite(self.employee(1))

    def test_switching_the_hold_on_after_the_claim_puts_the_invitation_back(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE, side_effect=InviteSendingHeld()) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'held')
        send.assert_called_once()
        self.assert_untouched(invite)

    def test_nothing_is_queued_or_swept_while_held_and_everything_resumes_when_lifted(self):
        invite = self.invite(self.employee(1))
        EmployeeImportInvite.objects.filter(pk=invite.pk).update(updated_at=timezone.now() - HOUR)      # old enough for the sweep
        with _held(), mock.patch(DELAY) as delay:
            self.assertEqual((invites.enqueue_batch(self.batch), invites.enqueue_ids([invite.pk]), invites.drain_batch(self.batch)), (0, 0, 0))
            self.assertEqual(invites.requeue_stale(), {'held': True, 'stale_processing': 0, 'pending_due': 0, 'queued': 0})
        delay.assert_not_called()
        self.assert_untouched(invite)
        with mock.patch(DELAY) as delay:                                                                  # control: the same sweep, hold lifted
            self.assertEqual(invites.requeue_stale()['queued'], 1)
        delay.assert_called_once_with(str(invite.pk))

    def test_the_celery_tasks_respect_the_hold(self):
        invite = self.invite(self.employee(1))
        EmployeeImportInvite.objects.filter(pk=invite.pk).update(updated_at=timezone.now() - HOUR)
        with _held(), mock.patch(INVITE) as send, mock.patch(DELAY) as delay:
            self.assertEqual(tasks.send_import_invite(str(invite.pk)), 'held')
            self.assertTrue(tasks.requeue_stale_import_invites()['held'])
        send.assert_not_called()
        delay.assert_not_called()
        self.assert_untouched(invite)

    def test_progress_says_the_invitations_are_held(self):
        self.invite(self.employee(1))
        with _held():
            self.assertTrue(invites.batch_progress(self.batch)['held'])
        self.assertFalse(invites.batch_progress(self.batch)['held'])

    def test_lifting_the_hold_lets_the_same_invitation_send_once(self):
        invite = self.invite(self.employee(1))
        with _held(), mock.patch(INVITE) as send:
            invites.process_invite(invite.pk)
        send.assert_not_called()
        with mock.patch(INVITE) as send:
            self.assertEqual((invites.process_invite(invite.pk), invites.process_invite(invite.pk)), ('sent', 'sent'))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.reload(invite).attempts, 1)


class RowConflictTests(_JobCase):
    ROWS = 3

    def run_with(self, failures: dict, rows=None):
        """Run a whole job. `failures` maps an email to the exception its row's creation hits AFTER some of its writes were made."""
        job = self.new_queued_job(rows or [self.row(n) for n in range(1, self.ROWS + 1)])
        real = job_module._create_one

        def create(importer, result, ip_address):
            failure = failures.get(result.values['email'])
            if failure is not None:
                make_user(result.values['email'], employee_id=f'PT{result.row:03}')      # a partial write that must be rolled back
                raise failure
            return real(importer, result, ip_address)
        with mock.patch.object(job_module, '_create_one', side_effect=create), mock.patch(INVITE):
            return self.drain(job.pk)

    def test_a_conflict_on_one_row_skips_only_that_row(self):
        job = self.run_with({'asha2@import.test': IntegrityError('duplicate')})
        self.assertEqual((job.status, job.created_count, job.failed_count, job.next_row, job.stalls), ('completed_with_errors', 2, 1, 3, 0))
        error = EmployeeImportJobError.objects.get()
        self.assertEqual((error.row_number, error.messages), (3, [job_module.CONFLICT_MESSAGE]))
        self.assertFalse(User.objects.filter(email='asha2@import.test').exists())               # the partial write was rolled back
        self.assertTrue(User.objects.filter(email='asha1@import.test').exists() and User.objects.filter(email='asha3@import.test').exists())
        self.assertEqual(EmployeeImportInvite.objects.filter(batch_id=job.pk).count(), 2)       # invitations only for who exists

    def test_an_email_created_after_validation_is_reported_as_taken(self):
        real_validate = job_module.validate_rows

        def validate_then_lose_the_race(importer, parsed):
            results = real_validate(importer, parsed)
            if not User.objects.filter(email='asha2@import.test').exists():
                make_user('asha2@import.test', employee_id='RACE01')                          # a concurrent hire commits in the gap
            return results
        job = self.new_queued_job([self.row(n) for n in range(1, 4)])
        with mock.patch.object(job_module, 'validate_rows', side_effect=validate_then_lose_the_race), mock.patch(INVITE):
            job = self.drain(job.pk)
        self.assertEqual((job.status, job.created_count, job.failed_count), ('completed_with_errors', 2, 1))
        self.assertEqual(EmployeeImportJobError.objects.get().messages, [job_module.EMAIL_TAKEN_MESSAGE])
        self.assertEqual(User.objects.filter(email='asha2@import.test').count(), 1)             # still only the concurrent hire

    def test_a_seat_taken_in_the_meantime_is_a_row_error(self):
        job = self.run_with({'asha1@import.test': DjangoValidationError('seat is held')})
        self.assertEqual((job.status, job.created_count, job.failed_count), ('completed_with_errors', 2, 1))
        error = EmployeeImportJobError.objects.get()
        self.assertEqual((error.row_number, error.messages), (2, [job_module.SEAT_TAKEN_MESSAGE]))

    def test_every_row_conflicting_still_finishes_the_job_without_stalling(self):
        everything = {f'asha{n}@import.test': IntegrityError('duplicate') for n in range(1, 4)}
        job = self.run_with(everything)
        self.assertEqual((job.status, job.created_count, job.failed_count, job.failure_code, job.stalls), ('completed_with_errors', 0, 3, '', 0))

    def test_an_unexpected_error_still_rolls_back_the_whole_batch_and_is_retried(self):
        # Row isolation is for database conflicts only; anything else is a fault of the worker or database, so the batch is retried.
        job = self.new_queued_job([self.row(n) for n in range(1, 4)])
        real = job_module._create_one

        def create(importer, result, ip_address):
            if result.values['email'] == 'asha2@import.test':
                raise RuntimeError('database went away')
            return real(importer, result, ip_address)
        with mock.patch.object(job_module, '_create_one', side_effect=create), mock.patch(INVITE):
            self.assertEqual(job_module.run_job(job.pk), 'retry_later')
        job.refresh_from_db()
        self.assertEqual((job.next_row, job.created_count, job.stalls), (0, 0, 1))
        self.assertFalse(User.objects.filter(email__endswith='@import.test').exists())

    def test_a_finished_job_cannot_be_finished_again(self):
        job = self.new_queued_job([self.row(1)])
        job_module.cancel_job(job)
        job_module._finish(job.pk, 'completed')                                                  # a late worker must not overwrite it
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')
        self.assertEqual(AuditLog.objects.filter(action='employee_bulk_import_job_finished', object_id=str(job.pk)).count(), 1)
