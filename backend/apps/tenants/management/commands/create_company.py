"""
manage.py create_company — provisions a brand-new company: creates its
PostgreSQL schema, runs every TENANT_APP migration into it, registers it in
the shared tenant registry, and creates its first login (a system_admin).

A thin CLI wrapper around apps.tenants.services.provision_company, which is
also called by the platform-admin API (apps.tenants.views) so a company can
be created either from the terminal or, now, from the frontend by a
platform admin.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import ALL_MODULES
from apps.tenants.services import CompanyCodeTaken, InvalidModules, provision_company


class Command(BaseCommand):
    help = 'Provision a new company: creates its schema, registers it, and creates its first admin login.'

    def add_arguments(self, parser):
        parser.add_argument('company_code', help='Short code the company logs in with, e.g. ACME2026')
        parser.add_argument('company_name', help='Full display name, e.g. "Acme Corp"')
        parser.add_argument('admin_email', help='Email for the first system_admin login')
        parser.add_argument(
            '--modules', nargs='*', default=None,
            help=f'Space-separated module keys to enable. Omit for all: {", ".join(ALL_MODULES)}',
        )

    def handle(self, *args, **options):
        admin_email = options['admin_email'].strip().lower()

        self.stdout.write('Creating schema and running migrations — this may take a minute...')
        try:
            result = provision_company(
                company_code=options['company_code'],
                company_name=options['company_name'],
                admin_email=admin_email,
                modules=options['modules'],
            )
        except InvalidModules as exc:
            raise CommandError(f'{exc} Valid: {", ".join(ALL_MODULES)}')
        except CompanyCodeTaken as exc:
            raise CommandError(f'Company code "{exc}" is already in use.')

        client = result['client']
        self.stdout.write(self.style.SUCCESS(
            f'\nCompany "{client.company_name}" created.\n'
            f'  Company code: {client.company_code}\n'
            f'  Admin login:  {admin_email}\n'
            f'  Password:     {result["password"]}\n'
            f'  Modules:      {", ".join(client.enabled_modules)}\n'
            f'\nShare the company code, email, and password with them directly — this password is not stored anywhere else.'
        ))
