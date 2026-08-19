"""
Base class for one-off management commands that touch tenant-scoped data.

A bare `manage.py <command>` invocation defaults the DB connection to the
`public` schema, which holds no company data at all — a command built
directly on BaseCommand that queries tenant models (User, Document,
LeaveRequest, etc.) will either crash outright (relation does not exist,
for TENANT_APPS models never migrated to public) or, worse, silently run
against whichever tenant schema a previous operation in the same process
happened to leave active. Several one-off scripts in this codebase had
exactly this gap (gen_hyderabad_test_data, seed_dummy_onboarding,
seed_reference_data, sync_leave_attendance, migrate_files_to_cloudinary).

Subclass TenantCommand and implement handle_tenant(self, client, *args,
**options) instead of handle() — it runs once per selected company, inside
`with client:` (which activates that tenant's schema for the duration of
the block), after --schema/--company-code/--all has been resolved to a
concrete list of Client rows. Nothing runs against more than one company
unless --all is passed explicitly — this is a fail-closed default, not a
convenience default, on purpose.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.tenants.models import Client


class TenantCommand(BaseCommand):
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--schema', default=None,
                            help='Run only against this tenant schema name (e.g. tenant_royalhrms).')
        group.add_argument('--company-code', default=None,
                            help='Run only against this tenant company code (e.g. ROYALHRMS).')
        group.add_argument('--all', action='store_true',
                            help='Run against every active tenant.')
        self.add_tenant_arguments(parser)

    def add_tenant_arguments(self, parser):
        """Override to add command-specific arguments alongside --schema/--company-code/--all."""

    def handle(self, *args, **options):
        clients = self._resolve_clients(options)
        multi = len(clients) > 1
        failed = []
        for client in clients:
            self.stdout.write(self.style.NOTICE(f'--- {client.company_code} ({client.schema_name}) ---'))
            try:
                with client:
                    self.handle_tenant(client, *args, **options)
            except Exception as exc:
                # A tenant whose schema was never fully provisioned (see the
                # tenancy leakage punch list, item #7 — orphaned schemas from
                # failed/incomplete provisioning) will fail here with a bare
                # DB error rather than anything command-specific. Under --all
                # this must not abort every other, healthy tenant's run —
                # report it and keep going; a single --schema run still
                # raises normally via re-raise below.
                if not multi:
                    raise
                # A failed query.iterator() call raises a second, unrelated
                # InvalidCursorName from cursor cleanup on top of the real
                # error — walk back to __context__ so the report says what
                # actually went wrong (e.g. "relation ... does not exist"
                # for a tenant whose schema was never fully migrated),
                # instead of the confusing cursor-cleanup artifact.
                root_cause = exc
                while root_cause.__context__ is not None:
                    root_cause = root_cause.__context__
                self.stderr.write(self.style.ERROR(f'    FAILED: {root_cause}'))
                failed.append(client.company_code)
            finally:
                # Server-side cursors (queryset.iterator()) are tied to the
                # connection's transaction state — a subsequent tenant's
                # schema switch on the SAME connection can invalidate a
                # cursor still considered "open" from this tenant's work,
                # surfacing as psycopg2.errors.InvalidCursorName on the next
                # --all iteration. Forcing a fresh connection per tenant
                # sidesteps that entirely.
                connection.close()

        if failed:
            raise CommandError(f'{len(failed)} of {len(clients)} tenant(s) failed: {", ".join(failed)}')

    def _resolve_clients(self, options):
        if options.get('all'):
            clients = list(Client.objects.filter(is_active=True))
            if not clients:
                raise CommandError('No active tenants found.')
            return clients
        if options.get('schema'):
            try:
                return [Client.objects.get(schema_name=options['schema'], is_active=True)]
            except Client.DoesNotExist:
                raise CommandError(f'No active tenant with schema_name={options["schema"]!r}.')
        try:
            return [Client.objects.get(company_code__iexact=options['company_code'], is_active=True)]
        except Client.DoesNotExist:
            raise CommandError(f'No active tenant with company_code={options["company_code"]!r}.')

    def handle_tenant(self, client, *args, **options):
        raise NotImplementedError
