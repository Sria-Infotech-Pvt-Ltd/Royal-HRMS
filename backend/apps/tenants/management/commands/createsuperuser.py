"""
manage.py createsuperuser — deliberately overrides Django's built-in command.

AUTH_USER_MODEL (accounts.User) is a TENANT app, so Django's own
createsuperuser would create a superuser inside whichever single company's
schema happened to be active — not a platform-wide account, and easy to
mistake for one. This project's actual "top of the system" account is the
PlatformAdmin (creates/manages companies, has no visibility into any one
company's data), so createsuperuser is repointed to create that instead.
Overriding is safe here: apps.tenants is listed ahead of django.contrib.auth
in INSTALLED_APPS, and Django resolves same-named commands in favor of
whichever app appears earliest, so this always wins without any other
settings change.

A company's own first admin is still created automatically during
provisioning (apps.tenants.services._seed_company_data), and
`manage.py create_tenant_superuser --schema=<company>` (shipped by
django_tenants) remains available to manually create/recover a tenant's own
admin account by hand if that's ever needed.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenants.models import PlatformAdmin
from apps.tenants.services import generate_password


class Command(BaseCommand):
    help = 'Create a platform admin — the operator account that creates and manages companies.'

    def add_arguments(self, parser):
        parser.add_argument('email', nargs='?', help='Login email for this platform admin')
        parser.add_argument('full_name', nargs='?', help='Display name, e.g. "Jane Doe"')

    def handle(self, *args, **options):
        email = options['email'] or input('Email: ')
        email = email.strip().lower()
        full_name = options['full_name'] or input('Full name: ')
        full_name = full_name.strip()

        if not email or not full_name:
            raise CommandError('Both an email and a full name are required.')
        if PlatformAdmin.objects.filter(email__iexact=email).exists():
            raise CommandError(f'A platform admin with email "{email}" already exists.')

        # Generated, not typed — this account, like every other PlatformAdmin
        # created via the invite flow, is always given a one-time generated
        # password rather than a human-chosen one at creation time.
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
