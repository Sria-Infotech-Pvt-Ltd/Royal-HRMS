"""
Company provisioning — the multi-step "create a new tenant" process.

Two entry points share the core logic in _seed_company_data:
  - provision_company(): fully synchronous, start to finish — used by
    manage.py create_company (terminal). A terminal command's lifetime
    isn't tied to any web server process, so there's nothing to protect
    it from here.
  - create_pending_client() + finish_pending_provisioning(): the
    platform-admin API's async path (apps.tenants.views
    CompanyListCreateView.post), split across a web request (fast: just
    the registry row) and a Celery task (slow: schema + migrations +
    seed) — see apps.tenants.tasks.finish_provisioning_task. Running
    provisioning synchronously in the request used to let the web
    server process itself (Django's dev-server auto-reloader, a manual
    restart, a crash) kill it mid-migration, corrupting the new schema.
    A Celery worker's lifecycle is independent of the web server, so a
    restart there can no longer reach into an in-flight provisioning run.
"""
import secrets
import string

from django.core.management import call_command
from django.db import IntegrityError

from apps.tenants.models import ALL_MODULES, Client, Domain
from apps.tenants.utils import send_company_provisioned_email


class CompanyCodeTaken(Exception):
    """Raised with the taken code as its message."""


def _save_new_client(client: Client) -> None:
    """
    _validate_new_company's own uniqueness check (SELECT ... WHERE
    company_code) and this save race against each other under concurrent
    requests: two platform admins submitting the same code within the same
    instant can both pass that check before either has inserted, so the
    second .save() here hits company_code's DB-level unique constraint
    instead. Without this, that surfaces as a raw, unhandled IntegrityError
    (a 500) rather than the same clean CompanyCodeTaken error the earlier,
    far-more-common non-concurrent case already returns.
    """
    try:
        client.save()
    except IntegrityError:
        raise CompanyCodeTaken(client.company_code)


class InvalidModules(Exception):
    def __init__(self, unknown: set[str]):
        self.unknown = unknown
        super().__init__(f'Unknown module(s): {", ".join(sorted(unknown))}')


def generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _validate_new_company(company_code: str, modules) -> tuple[str, list[str]]:
    """Shared input validation for both provisioning paths. Returns
    (normalized_company_code, normalized_modules); raises CompanyCodeTaken /
    InvalidModules for caller-fixable errors."""
    company_code = company_code.strip().upper()
    modules = list(modules) if modules is not None else list(ALL_MODULES)

    unknown = set(modules) - set(ALL_MODULES)
    if unknown:
        raise InvalidModules(unknown)

    if Client.objects.filter(company_code__iexact=company_code).exists():
        raise CompanyCodeTaken(company_code)

    return company_code, modules


def _seed_company_data(client: Client, admin_email: str) -> str:
    """
    Assumes `client`'s schema already exists and is fully migrated. Seeds
    reference data, creates the Company row and first system_admin login,
    and emails the admin their credentials. Returns the generated password.
    """
    admin_email = admin_email.strip().lower()
    password = generate_password()

    with client:
        from apps.accounts.models import Company, Role, User

        # Email templates, states/cities, employee code settings, etc. —
        # permissions/roles themselves are seeded by data migrations, so
        # they already exist from the schema migration above.
        call_command('seed_reference_data')

        Company.objects.create(company_name=client.company_name)

        admin_role, _ = Role.objects.get_or_create(
            name='system_admin',
            defaults={'display_name': 'System Admin', 'can_manage_team': True, 'can_manage_branch': True},
        )
        User.objects.create_superuser(
            email=admin_email, password=password,
            full_name=f'{client.company_name} Admin', role=admin_role,
            # create_superuser defaults this to False (unlike the normal
            # employee-creation flow, which always forces it) — a
            # randomly-generated password must be forced to change on
            # first login same as any other new account's temp password.
            must_change_password=True,
        )

    send_company_provisioned_email(
        admin_email=admin_email, company_code=client.company_code,
        company_name=client.company_name, password=password,
    )

    return password


def provision_company(*, company_code: str, company_name: str, admin_email: str, modules=None) -> dict:
    """
    Creates a new company end-to-end, synchronously: schema + migrations,
    reference-data seed, and its first system_admin login.

    Returns {'client': Client, 'password': str}. Raises CompanyCodeTaken /
    InvalidModules for caller-fixable input errors — any other exception
    (e.g. a mid-provisioning failure) propagates as-is.
    """
    company_code, modules = _validate_new_company(company_code, modules)
    company_name = company_name.strip()
    schema_name = f'tenant_{company_code.lower()}'

    client = Client(
        schema_name=schema_name,
        company_code=company_code,
        company_name=company_name,
        enabled_modules=modules,
        is_active=True,
    )
    _save_new_client(client)  # auto_create_schema=True (default) creates + migrates the schema here

    Domain.objects.create(domain=f'{company_code.lower()}.internal', tenant=client, is_primary=True)

    password = _seed_company_data(client, admin_email)
    return {'client': client, 'password': password}


def create_pending_client(*, company_code: str, company_name: str, modules=None) -> Client:
    """
    Validates and creates only the registry row — schema creation and
    everything after it happen later, out-of-process (see
    finish_pending_provisioning + apps.tenants.tasks.finish_provisioning_task),
    so the web request calling this returns almost instantly.
    """
    company_code, modules = _validate_new_company(company_code, modules)
    company_name = company_name.strip()
    schema_name = f'tenant_{company_code.lower()}'

    client = Client(
        schema_name=schema_name,
        company_code=company_code,
        company_name=company_name,
        enabled_modules=modules,
        is_active=True,
        provisioning_status=Client.PROVISIONING_PENDING,
    )
    client.auto_create_schema = False  # deferred — finish_pending_provisioning creates it
    _save_new_client(client)
    return client


def finish_pending_provisioning(*, client: Client, admin_email: str, modules: list[str]) -> dict:
    """
    Runs in a Celery worker (see apps.tenants.tasks.finish_provisioning_task)
    for a Client row already created by create_pending_client. Creates the
    schema — synchronously from the worker's point of view, but
    independently of the web server process, which is the entire point —
    then the rest, then flips the row to 'active' and stashes the
    password for one-time viewing via CompanyRevealPasswordView.
    """
    client.create_schema(check_if_exists=True, verbosity=1)

    Domain.objects.get_or_create(
        tenant=client, defaults={'domain': f'{client.company_code.lower()}.internal', 'is_primary': True},
    )

    password = _seed_company_data(client, admin_email)

    client.provisioning_status    = Client.PROVISIONING_ACTIVE
    client.pending_admin_password = password
    client.save(update_fields=['provisioning_status', 'pending_admin_password', 'updated_at'])

    return {'client': client, 'password': password}
