"""
Management command: cleanup_failed_tenants

apps.tenants.tasks.sweep_stale_provisioning already flips a Client row to
provisioning_status='failed' after it's been stuck 'pending' too long — but
it only ever updates that one column. The company's PostgreSQL schema
(created synchronously the moment the Client row was inserted, via
auto_create_schema) is never dropped, so a failed provisioning attempt
leaves an orphaned schema in the database forever, unrecoverable through
the app.

This command is the missing other half: it (1) runs the existing stale
sweep first so any long-pending row still waiting to be marked 'failed'
is caught in the same pass, then (2) for every provisioning_status='failed'
Client, drops its schema and deletes the Client/Domain rows using
django-tenants' own Client.delete(force_drop=True) — never hand-rolled SQL.

Deliberately NOT wired into the Celery beat schedule alongside
sweep_stale_provisioning: dropping a schema is irreversible, so this stays
a manual, on-demand action a platform admin runs (and reviews via
--dry-run first), rather than something that fires unattended on a timer.

Usage:
    python manage.py cleanup_failed_tenants --dry-run
    python manage.py cleanup_failed_tenants --yes
    python manage.py cleanup_failed_tenants --yes --stale-minutes 60
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import Client
from apps.tenants.tasks import sweep_stale_provisioning


class Command(BaseCommand):
    help = (
        "Drop the PostgreSQL schema and delete the Client row for every company stuck at "
        "provisioning_status='failed' (running the stale-pending sweep first)."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                             help='List what would be dropped without changing anything.')
        parser.add_argument('--yes', action='store_true',
                             help='Actually drop schemas and delete rows (required unless --dry-run).')
        parser.add_argument('--stale-minutes', type=int, default=15,
                             help='Passed through to sweep_stale_provisioning (default 15, matches the Celery beat schedule).')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if not dry_run and not options['yes']:
            raise CommandError('Refusing to drop schemas without --yes (or use --dry-run to preview first).')

        newly_failed = sweep_stale_provisioning(stale_minutes=options['stale_minutes'])
        if newly_failed:
            self.stdout.write(f'Marked {newly_failed} stale pending compan(y/ies) as failed.')

        failed = list(Client.objects.filter(provisioning_status=Client.PROVISIONING_FAILED))
        if not failed:
            self.stdout.write(self.style.SUCCESS('No failed tenants to clean up.'))
            return

        self.stdout.write(f'{"[DRY RUN] " if dry_run else ""}{len(failed)} failed tenant(s) found:')
        for client in failed:
            self.stdout.write(
                f'  {client.company_code:20} {client.schema_name:25} '
                f'"{client.company_name}"  created {client.created_at:%Y-%m-%d %H:%M}'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — nothing was dropped.'))
            return

        dropped = 0
        for client in failed:
            company_code = client.company_code
            try:
                client.delete(force_drop=True)
                dropped += 1
                self.stdout.write(self.style.SUCCESS(f'  Dropped {company_code}'))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'  FAILED to drop {company_code}: {exc}'))

        self.stdout.write(self.style.SUCCESS(f'Done. {dropped}/{len(failed)} tenant(s) cleaned up.'))
