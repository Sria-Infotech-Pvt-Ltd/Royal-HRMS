"""
Resend the activation invitations of one bulk import whose emails were never attempted (e.g. the web server dropped the request
before the invitations were queued).

  python manage.py resend_import_invites --batch <batch id>                              DRY RUN: prints who would be invited
  python manage.py resend_import_invites --batch <id> --send --confirm-count 13          queues them (Celery + Redis)
  python manage.py resend_import_invites --batch <id> --send --confirm-count 13 --inline sends them right here, without Redis

Safe by construction:
  - dry run unless --send AND an exact --confirm-count are given, so nothing is emailed by accident;
  - reuses the existing employee accounts (nobody is created, changed or placed) and the normal invitation pipeline, so every
    attempt is recorded in EmailLog and in the batch progress, activation links come from the existing PasswordResetToken
    mechanism, and an employee who already has a valid unused invitation, or who has already activated, is skipped;
  - idempotent: running it again never creates a second invitation for the same employee;
  - the output masks email addresses.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AuditLog, EmployeeImportInvite, PasswordResetToken, Placement
from apps.accounts.services_employee_import_commit import AUDIT_ACTION
from apps.accounts.services_employee_import_invites import batch_progress, create_invites, drain_batch, enqueue_batch

LOOKBACK = timedelta(minutes=10)       # an import creates all its employees within one request, shortly before its audit entry


def _mask(email: str) -> str:
    local, _, domain = (email or '').partition('@')
    return f'{local[:2]}***@{domain}' if domain else '<none>'


def _token_state(user) -> str:
    token = PasswordResetToken.objects.filter(user=user, purpose=PasswordResetToken.PURPOSE_INVITE).order_by('-created_at').first()
    return token.status if token else 'none'


class Command(BaseCommand):
    help = 'Preview (default) or send the activation invitations of one bulk import. Dry run unless --send and --confirm-count are given.'

    def add_arguments(self, parser):
        parser.add_argument('--batch', required=True, help='The full batch id of the import.')
        parser.add_argument('--send', action='store_true', help='Actually queue the invitations.')
        parser.add_argument('--confirm-count', type=int, default=None, help='Must equal the number of employees shown in the preview.')
        parser.add_argument('--inline', action='store_true', help='Send in this process instead of through Celery (works without Redis).')

    def _commit_entry(self, batch: str) -> AuditLog:
        entry = AuditLog.objects.filter(action=AUDIT_ACTION, changes__batch_id=batch).first()
        if entry is None:
            raise CommandError('No committed import with that batch id was found. Nothing was done.')
        return entry

    def _employees(self, entry: AuditLog) -> list:
        placements = (Placement.objects.filter(created_by=entry.user, created_at__lte=entry.created_at, created_at__gte=entry.created_at - LOOKBACK)
                      .select_related('employee', 'position__org_unit').order_by('created_at'))
        found = list(placements)
        expected = int(entry.changes.get('created', -1))
        if len(found) != expected:
            raise CommandError(f'Could not identify the import\'s employees safely: expected {expected}, found {len(found)}. Nothing was done.')
        return found

    def handle(self, *args, **options):
        batch = str(uuid.UUID(options['batch']))
        entry = self._commit_entry(batch)
        placements = self._employees(entry)
        invites = {i.user_id: i for i in EmployeeImportInvite.objects.filter(batch_id=batch)}
        self.stdout.write(f'Batch {batch}: {len(placements)} employees. Preview (emails masked):')
        self.stdout.write('  # | employee id | email           | activation link | existing invitation | designation')
        for number, placement in enumerate(placements, start=1):
            user, invite = placement.employee, invites.get(placement.employee_id)
            self.stdout.write(f'{number:3} | {user.employee_id:11} | {_mask(user.email):15} | {_token_state(user):15} | '
                              f'{invite.status if invite else "none":19} | {placement.position.org_unit.name} / {placement.position.title}')
        if not options['send']:
            self.stdout.write('DRY RUN: nothing was created or sent. Add --send --confirm-count <number> to send.')
            return
        if options['confirm_count'] != len(placements):
            raise CommandError(f'--confirm-count must equal {len(placements)} (the number shown above). Nothing was sent.')
        with transaction.atomic():
            create_invites(entry.user, batch, [(n, str(p.employee_id), p.employee.employee_id) for n, p in enumerate(placements, start=1)])
        started = timezone.now()
        handled = drain_batch(batch) if options['inline'] else enqueue_batch(batch)
        progress = batch_progress(batch)
        self.stdout.write(self.style.SUCCESS(
            f'{"Sent inline" if options["inline"] else "Queued"}: {handled} invitations at {started:%H:%M:%S}. Progress: sent={progress["sent"]} '
            f'pending={progress["pending"]} skipped={progress["skipped"]} failed={len(progress["failed"])}.'))
