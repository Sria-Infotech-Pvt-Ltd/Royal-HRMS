"""
Company provisioning — the multi-step "create a new tenant" process shared
by manage.py create_company (terminal) and the platform-admin API
(apps.tenants.views), so there is exactly one place this is defined.
"""
import secrets
import string

from django.core.management import call_command

from apps.tenants.models import ALL_MODULES, Client, Domain


class CompanyCodeTaken(Exception):
    """Raised with the taken code as its message."""


class InvalidModules(Exception):
    def __init__(self, unknown: set[str]):
        self.unknown = unknown
        super().__init__(f'Unknown module(s): {", ".join(sorted(unknown))}')


def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def provision_company(*, company_code: str, company_name: str, admin_email: str, modules=None) -> dict:
    """
    Creates a new company end-to-end: schema + migrations, reference-data
    seed, and its first system_admin login.

    Returns {'client': Client, 'password': str}. Raises CompanyCodeTaken /
    InvalidModules for caller-fixable input errors — any other exception
    (e.g. a mid-provisioning failure) propagates as-is, same as the
    original manage.py command.
    """
    company_code = company_code.strip().upper()
    company_name = company_name.strip()
    admin_email  = admin_email.strip().lower()
    modules      = list(modules) if modules is not None else list(ALL_MODULES)

    unknown = set(modules) - set(ALL_MODULES)
    if unknown:
        raise InvalidModules(unknown)

    if Client.objects.filter(company_code__iexact=company_code).exists():
        raise CompanyCodeTaken(company_code)

    schema_name = f'tenant_{company_code.lower()}'

    client = Client(
        schema_name=schema_name,
        company_code=company_code,
        company_name=company_name,
        enabled_modules=modules,
        is_active=True,
    )
    client.save()  # auto_create_schema=True (default) creates + migrates the schema here

    Domain.objects.create(domain=f'{company_code.lower()}.internal', tenant=client, is_primary=True)

    password = generate_password()
    with client:
        from apps.accounts.models import Company, Role, User

        # Email templates, states/cities, employee code settings, etc. —
        # permissions/roles themselves are seeded by data migrations, so
        # they already exist from the schema migration above.
        call_command('seed_reference_data')

        Company.objects.create(company_name=company_name)

        admin_role, _ = Role.objects.get_or_create(
            name='system_admin',
            defaults={'display_name': 'System Admin', 'can_manage_team': True, 'can_manage_branch': True},
        )
        User.objects.create_superuser(
            email=admin_email, password=password,
            full_name=f'{company_name} Admin', role=admin_role,
            # create_superuser defaults this to False (unlike the normal
            # employee-creation flow, which always forces it) — a
            # randomly-generated password must be forced to change on
            # first login same as any other new account's temp password.
            must_change_password=True,
        )

    return {'client': client, 'password': password}
