"""
Activation invitations of a bulk employee import: durable queue, bounded retries, no duplicates, recovery.

No real email is ever sent: the mail-sending function is mocked in every test. Celery's broker is also mocked (`.delay`), because
what is under test is the database-driven pipeline, which must work when the broker or a worker is missing.
"""
from __future__ import annotations

import datetime
import smtplib
import uuid
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts import services_employee_import_commit as commit_module
from apps.accounts import services_employee_import_invites as invites
from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, EmailLog, EmployeeImportInvite, PasswordResetToken, Placement, User
from apps.accounts.tests_employee_bulk_import import INVITE, _ImportCase, _workbook

HOUR = datetime.timedelta(hours=1)
DELAY = 'apps.accounts.tasks.send_import_invite.delay'


class _InviteCase(TestCase):
    def setUp(self):
        self.importer = make_user('inv_importer@test.com', employee_id='IV000', is_superuser=True)
        self.batch = uuid.uuid4()
        self.row = 1

    def employee(self, n: int) -> User:
        return make_user(f'inv{n}@test.com', employee_id=f'IV{n:03}', account_activated_at=None)

    def invite(self, user: User, **fields) -> EmployeeImportInvite:
        self.row += 1
        fields.setdefault('batch_id', self.batch)
        return EmployeeImportInvite.objects.create(user=user, created_by=self.importer, row_number=self.row, **fields)

    def reload(self, invite: EmployeeImportInvite) -> EmployeeImportInvite:
        invite.refresh_from_db()
        return invite

    def log_sent_mail(self, user: User, when=None) -> EmailLog:
        log = EmailLog.objects.create(recipient_email=user.email, subject='Welcome', body_html='x', template_name=invites.INVITE_TEMPLATE,
                                      module='accounts', status=EmailLog.STATUS_SENT, error_message='')
        if when:
            EmailLog.objects.filter(pk=log.pk).update(created_at=when)
        return log


class SendingTests(_InviteCase):
    def test_successful_invitation(self):
        user = self.employee(1)
        invite = self.invite(user)
        with mock.patch(INVITE) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'sent')
        invite = self.reload(invite)
        self.assertEqual((invite.status, invite.attempts, invite.reason_code), ('sent', 1, ''))
        self.assertIsNotNone(invite.sent_at)
        send.assert_called_once()
        self.assertEqual(invites.batch_progress(self.batch)['state'], 'done')

    def test_smtp_failure_that_cannot_succeed_fails_with_a_reason_and_is_not_retried(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE, side_effect=smtplib.SMTPRecipientsRefused({})) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'failed')
            self.assertEqual(invites.process_invite(invite.pk), 'failed')           # running again changes nothing
        self.assertEqual((self.reload(invite).reason_code, self.reload(invite).attempts), ('recipient_refused', 1))
        self.assertEqual(send.call_count, 1)
        failed = invites.batch_progress(self.batch)['failed']
        self.assertEqual((failed[0]['employee_id'], '@' in failed[0]['reason']), ('IV001', False))     # a reason, never an address

    def test_smtp_login_rejection_is_permanent_and_stores_no_server_text(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE, side_effect=smtplib.SMTPAuthenticationError(535, b'secret-looking server text')):
            invites.process_invite(invite.pk)
        invite = self.reload(invite)
        self.assertEqual((invite.status, invite.reason_code), ('failed', 'smtp_auth'))
        self.assertNotIn('secret', ' '.join(str(v) for v in EmployeeImportInvite.objects.values().first().values()))

    def test_temporary_failure_is_retried_later_and_then_succeeds(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE, side_effect=[smtplib.SMTPServerDisconnected(), None]) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'retry')
            waiting = self.reload(invite)
            self.assertEqual((waiting.status, waiting.reason_code, waiting.attempts), ('pending', 'smtp_connection', 1))
            self.assertGreater(waiting.next_attempt_at, timezone.now())
            self.assertEqual(invites.process_invite(invite.pk), 'not_due')            # not before its time
            EmployeeImportInvite.objects.filter(pk=invite.pk).update(next_attempt_at=timezone.now() - HOUR)
            self.assertEqual(invites.process_invite(invite.pk), 'sent')
        done = self.reload(invite)
        self.assertEqual((done.status, done.attempts, done.reason_code), ('sent', 2, ''))
        self.assertEqual(send.call_count, 2)

    def test_retries_are_bounded(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE, side_effect=smtplib.SMTPServerDisconnected()) as send:
            for _ in range(invites.max_attempts() + 3):
                EmployeeImportInvite.objects.filter(pk=invite.pk, status='pending').update(next_attempt_at=timezone.now() - HOUR)
                invites.process_invite(invite.pk)
        final = self.reload(invite)
        self.assertEqual((final.status, final.attempts, final.reason_code), ('failed', invites.max_attempts(), 'smtp_connection'))
        self.assertEqual(send.call_count, invites.max_attempts())

    def test_an_unrecognised_error_fails_at_once_and_keeps_no_error_text(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE, side_effect=RuntimeError('boom with someone@example.com inside')):
            invites.process_invite(invite.pk)
        invite = self.reload(invite)
        self.assertEqual((invite.status, invite.reason_code, invite.attempts), ('failed', 'unexpected', 1))

    def test_running_the_same_task_twice_sends_once(self):
        invite = self.invite(self.employee(1))
        with mock.patch(INVITE) as send:
            self.assertEqual((invites.process_invite(invite.pk), invites.process_invite(invite.pk)), ('sent', 'sent'))
        self.assertEqual(send.call_count, 1)

    def test_an_invitation_another_worker_is_sending_is_left_alone(self):
        invite = self.invite(self.employee(1), status='processing', attempts=1, processing_started_at=timezone.now())
        with mock.patch(INVITE) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'in_progress')
        send.assert_not_called()

    def test_an_employee_who_already_activated_or_left_is_skipped(self):
        activated, inactive = self.employee(1), self.employee(2)
        User.objects.filter(pk=activated.pk).update(account_activated_at=timezone.now())
        User.objects.filter(pk=inactive.pk).update(is_active=False)
        first, second = self.invite(activated), self.invite(inactive)
        with mock.patch(INVITE) as send:
            self.assertEqual((invites.process_invite(first.pk), invites.process_invite(second.pk)), ('skipped', 'skipped'))
        send.assert_not_called()
        self.assertEqual((self.reload(first).reason_code, self.reload(second).reason_code), ('already_activated', 'employee_inactive'))


class DuplicateAndTokenTests(_InviteCase):
    def test_an_expired_activation_link_does_not_block_a_new_invitation(self):
        user = self.employee(1)
        token = PasswordResetToken.objects.create(user=user, purpose=PasswordResetToken.PURPOSE_INVITE, expires_at=timezone.now() - HOUR)
        self.log_sent_mail(user, when=token.created_at + datetime.timedelta(seconds=5))
        invites.create_invites(self.importer, self.batch, [(2, str(user.pk), user.employee_id)])
        invite = EmployeeImportInvite.objects.get(user=user)
        self.assertEqual(invite.status, 'pending')                                  # the old link is dead: a new one is needed

    def test_a_valid_unused_delivered_invitation_is_not_duplicated(self):
        user = self.employee(1)
        token = PasswordResetToken.objects.create(user=user, purpose=PasswordResetToken.PURPOSE_INVITE, expires_at=timezone.now() + HOUR)
        self.log_sent_mail(user, when=token.created_at + datetime.timedelta(seconds=5))
        invites.create_invites(self.importer, self.batch, [(2, str(user.pk), user.employee_id)])
        invite = EmployeeImportInvite.objects.get(user=user)
        self.assertEqual((invite.status, invite.reason_code), ('skipped', 'already_invited'))

    def test_two_batches_cannot_both_have_an_open_invitation_for_one_employee(self):
        user = self.employee(1)
        self.invite(user)                                                           # open invitation from batch A
        invites.create_invites(self.importer, uuid.uuid4(), [(2, str(user.pk), user.employee_id)])
        other = EmployeeImportInvite.objects.exclude(batch_id=self.batch).get()
        self.assertEqual((other.status, other.reason_code), ('skipped', 'duplicate_open_invite'))
        with self.assertRaises(IntegrityError), transaction.atomic():               # and the database itself refuses a second open row
            EmployeeImportInvite.objects.create(batch_id=uuid.uuid4(), user=user, status='pending')

    def test_a_finished_failed_invitation_does_not_block_a_later_batch(self):
        user = self.employee(1)
        self.invite(user, status='failed', reason_code='smtp_connection')
        invites.create_invites(self.importer, uuid.uuid4(), [(2, str(user.pk), user.employee_id)])
        self.assertEqual(EmployeeImportInvite.objects.exclude(batch_id=self.batch).get().status, 'pending')

    def test_creating_the_invitations_twice_for_a_batch_adds_nothing(self):
        user = self.employee(1)
        for _ in range(2):
            invites.create_invites(self.importer, self.batch, [(2, str(user.pk), user.employee_id)])
        self.assertEqual(EmployeeImportInvite.objects.filter(user=user).count(), 1)


class RecoveryTests(_InviteCase):
    def test_worker_restart_an_abandoned_invitation_is_recovered_and_sent(self):
        invite = self.invite(self.employee(1), status='processing', attempts=1, processing_started_at=timezone.now() - HOUR)
        with mock.patch(DELAY) as delay:
            self.assertEqual(invites.requeue_stale()['stale_processing'], 1)
        delay.assert_called_once_with(str(invite.pk))
        with mock.patch(INVITE) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'sent')
        recovered = self.reload(invite)
        self.assertEqual((recovered.status, recovered.attempts, recovered.ambiguous_attempts), ('sent', 2, 1))   # honest: this attempt was uncertain
        send.assert_called_once()

    def test_a_crash_after_the_mail_was_accepted_and_logged_is_recognised_not_resent(self):
        user, started = self.employee(1), timezone.now() - HOUR
        invite = self.invite(user, status='processing', attempts=1, processing_started_at=started)
        self.log_sent_mail(user, when=started + datetime.timedelta(seconds=30))
        with mock.patch(INVITE) as send:
            self.assertEqual(invites.process_invite(invite.pk), 'sent')
        send.assert_not_called()
        self.assertEqual(self.reload(invite).ambiguous_attempts, 0)

    def test_an_invitation_nobody_queued_is_picked_up_by_the_sweep_after_a_grace_period(self):
        old, fresh = self.invite(self.employee(1)), self.invite(self.employee(2))
        EmployeeImportInvite.objects.filter(pk=old.pk).update(updated_at=timezone.now() - HOUR)
        with mock.patch(DELAY) as delay:
            result = invites.requeue_stale()
        self.assertEqual(result['queued'], 1)
        delay.assert_called_once_with(str(old.pk))                                  # the brand-new one is left alone for now

    def test_when_the_broker_is_down_the_sweep_reports_nothing_queued_and_loses_nothing(self):
        invite = self.invite(self.employee(1))
        EmployeeImportInvite.objects.filter(pk=invite.pk).update(updated_at=timezone.now() - HOUR)
        with mock.patch(DELAY, side_effect=ConnectionError('redis down')):
            self.assertEqual(invites.requeue_stale()['queued'], 0)
        self.assertEqual(self.reload(invite).status, 'pending')                      # still owed; a later sweep will queue it

    def test_partial_failure_is_reported_and_retry_only_touches_the_failed_one(self):
        users = [self.employee(n) for n in (1, 2, 3)]
        made = [self.invite(u) for u in users]
        outcomes = [None, smtplib.SMTPRecipientsRefused({}), None]
        with mock.patch(INVITE, side_effect=outcomes):
            for invite in made:
                invites.process_invite(invite.pk)
        progress = invites.batch_progress(self.batch)
        self.assertEqual((progress['sent'], len(progress['failed']), progress['state']), (2, 1, 'done'))
        with mock.patch(INVITE) as send:
            first = invites.retry_batch(self.importer, self.batch, inline=True)
            second = invites.retry_batch(self.importer, self.batch, inline=True)       # idempotent: nothing left to retry
        self.assertEqual((first['requeued'], second['requeued'], send.call_count), (1, 0, 1))
        self.assertEqual(invites.batch_progress(self.batch)['sent'], 3)


class CommitIntegrationTests(_ImportCase):
    def rows(self, count):
        return [self.row(n) for n in range(1, count + 1)]

    def test_browser_gone_and_redis_down_after_commit_the_employees_and_their_invitations_still_exist(self):
        with override_settings(RUNNING_TESTS=False), mock.patch(DELAY, side_effect=ConnectionError('redis down')), mock.patch(INVITE) as send:
            response = self.commit(self.hr, self.rows(2))                              # nothing is ever queued, nobody polls, nobody retries
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 2)
        self.assertEqual(list(EmployeeImportInvite.objects.values_list('status', flat=True)), ['pending', 'pending'])
        send.assert_not_called()
        # Redis and a worker come back: the sweep queues them and a worker sends them.
        EmployeeImportInvite.objects.update(updated_at=timezone.now() - HOUR)
        queued = []
        with mock.patch(DELAY, side_effect=lambda pk: queued.append(pk)):
            invites.requeue_stale()
        with mock.patch(INVITE) as send:
            for pk in queued:
                invites.process_invite(pk)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(set(EmployeeImportInvite.objects.values_list('status', flat=True)), {'sent'})

    def test_a_rolled_back_import_leaves_no_invitations_behind(self):
        content = _workbook(self.rows(3))
        original, calls = commit_module._save_profile, {'n': 0}

        def explode(user, result):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('boom')
            original(user, result)
        with mock.patch.object(commit_module, '_save_profile', explode), self.assertRaises(RuntimeError):
            commit_module.commit_import(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=commit_module.file_sha256(content))
        self.assertFalse(EmployeeImportInvite.objects.exists())
        self.assertFalse(User.objects.filter(email__endswith='@import.test').exists())

    def test_committing_the_same_batch_again_creates_no_employees_and_no_second_invitations(self):
        content, batch = _workbook(self.rows(2)), str(uuid.uuid4())
        with mock.patch(INVITE):
            first = self.commit(self.hr, None, batch=batch, content=content)
            again = self.commit(self.hr, None, batch=batch, content=content)
        self.assertEqual((first.status_code, again.status_code), (201, 200))
        self.assertEqual((User.objects.filter(email__endswith='@import.test').count(), EmployeeImportInvite.objects.count()), (2, 2))

    def test_a_failure_while_queueing_does_not_undo_the_import(self):
        with mock.patch.object(commit_module, 'dispatch_invites', side_effect=RuntimeError('queue exploded')), mock.patch(INVITE):
            response = self.commit(self.hr, self.rows(2))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(EmployeeImportInvite.objects.filter(status='pending').count(), 2)

    def test_progress_and_retry_endpoints(self):
        with mock.patch(INVITE, side_effect=[smtplib.SMTPRecipientsRefused({}), None]):
            batch = self.commit(self.hr, self.rows(2)).json()['data']['batch_id']
        client = self.client_for(self.hr)
        progress = client.get(f'/api/employees/bulk-import/invites/{batch}/').json()['data']
        self.assertEqual((progress['sent'], len(progress['failed']), progress['state']), (1, 1, 'done'))
        with mock.patch(INVITE), mock.patch(DELAY):
            retried = client.post(f'/api/employees/bulk-import/invites/{batch}/retry/').json()['data']
        self.assertEqual(retried['requeued'], 1)
        self.assertEqual(self.client_for(self.plain).post(f'/api/employees/bulk-import/invites/{batch}/retry/').status_code, 403)


class ConfigurationTests(TestCase):
    def test_the_table_holds_no_token_no_email_and_no_personal_data(self):
        names = {f.name for f in EmployeeImportInvite._meta.get_fields()}
        self.assertTrue({'token', 'email', 'address', 'name', 'phone', 'password'}.isdisjoint(names), names)
        self.assertFalse(any(f.is_relation and f.related_model is PasswordResetToken for f in EmployeeImportInvite._meta.get_fields()))

    def test_mail_connections_have_a_timeout(self):
        fake = SimpleNamespace(host='smtp.example.com', port=587, username='u', password='p', use_tls=True, sender_name='S', from_email='a@example.com')
        from apps.accounts.models import SMTPSettings
        from apps.accounts.utils import _get_smtp_connection
        with mock.patch.object(SMTPSettings, 'get_active', return_value=fake):
            connection, _from, _smtp = _get_smtp_connection()
        self.assertEqual(connection.timeout, settings.EMAIL_TIMEOUT)
        self.assertGreater(connection.timeout, 0)

    def test_the_recovery_sweep_is_scheduled_and_the_tasks_are_registered(self):
        from apps.accounts import tasks

        self.assertIn('requeue-stale-import-invites', settings.CELERY_BEAT_SCHEDULE)
        self.assertTrue(tasks.send_import_invite.acks_late)
        self.assertTrue(tasks.send_import_invite.reject_on_worker_lost)
        self.assertEqual(tasks.requeue_stale_import_invites.name, 'apps.accounts.tasks.requeue_stale_import_invites')


class ResendCommandTests(_ImportCase):
    """Reproduces the real incident: employees exist but the invitations were never queued (no invitation rows at all)."""

    def setUp(self):
        super().setUp()
        with mock.patch(INVITE):
            self.batch = self.commit(self.hr, [self.row(1), self.row(2), self.row(3)]).json()['data']['batch_id']
        EmployeeImportInvite.objects.all().delete()                                   # as if they were never created

    def run_command(self, *args):
        out = StringIO()
        call_command('resend_import_invites', '--batch', self.batch, *args, stdout=out)
        return out.getvalue()

    def test_default_is_a_masked_dry_run_that_creates_and_sends_nothing(self):
        with mock.patch(INVITE) as send:
            text = self.run_command()
        self.assertIn('DRY RUN', text)
        self.assertIn('as***@import.test', text)                                      # masked
        self.assertNotIn('asha1@import.test', text)
        self.assertEqual((EmployeeImportInvite.objects.count(), send.call_count), (0, 0))

    def test_sending_needs_the_exact_confirmation_count(self):
        for args in (('--send',), ('--send', '--confirm-count', '2'), ('--send', '--confirm-count', '4')):
            with mock.patch(INVITE) as send, self.assertRaises(CommandError):
                self.run_command(*args)
            self.assertEqual((EmployeeImportInvite.objects.count(), send.call_count), (0, 0))

    def test_send_is_idempotent_and_reuses_the_existing_accounts(self):
        users_before = list(User.objects.filter(email__endswith='@import.test').values_list('pk', flat=True))
        with mock.patch(INVITE) as send:
            self.run_command('--send', '--confirm-count', '3', '--inline')
            self.run_command('--send', '--confirm-count', '3', '--inline')            # the second run finds nothing to do
        self.assertEqual(send.call_count, 3)
        self.assertEqual(set(EmployeeImportInvite.objects.values_list('status', flat=True)), {'sent'})
        self.assertEqual(sorted(User.objects.filter(email__endswith='@import.test').values_list('pk', flat=True)), sorted(users_before))
        self.assertEqual(Placement.objects.filter(employee__email__endswith='@import.test').count(), 3)

    def test_it_refuses_when_it_cannot_identify_the_employees_exactly(self):
        entry = AuditLog.objects.get(action=commit_module.AUDIT_ACTION, changes__batch_id=self.batch)
        entry.changes = {**entry.changes, 'created': 99}
        entry.save()
        with self.assertRaises(CommandError):
            self.run_command()
