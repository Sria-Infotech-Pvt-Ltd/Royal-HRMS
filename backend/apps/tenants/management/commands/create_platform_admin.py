"""
manage.py create_platform_admin — creates a platform-admin login (the
operator account that can create/manage companies through the
platform-admin API and frontend). There is no one "above" this tier to
create it through a UI, so — like Django's own createsuperuser — the very
first one is always created from the terminal.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import PlatformAdmin
from apps.tenants.services import generate_password


class Command(BaseCommand):
    help = 'Create a platform admin — the operator account that can create/manage companies.'

    def add_arguments(self, parser):
        parser.add_argument('email', help='Login email for this platform admin')
        parser.add_argument('full_name', help='Display name, e.g. "Jane Doe"')

    def handle(self, *args, **options):
        email     = options['email'].strip().lower()
        full_name = options['full_name'].strip()

        if PlatformAdmin.objects.filter(email__iexact=email).exists():
            raise CommandError(f'A platform admin with email "{email}" already exists.')

        password = generate_password()
        admin = PlatformAdmin(email=email, full_name=full_name)
        admin.set_password(password)
        admin.save()

        self.stdout.write(self.style.SUCCESS(
            f'\nPlatform admin created.\n'
            f'  Email:    {email}\n'
            f'  Password: {password}\n'
            f'\nShare this directly — it is not stored anywhere else.'
        ))
