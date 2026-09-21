"""
Tenant-aware Django test runner.

Plain `manage.py test` (django.test.runner.DiscoverRunner) only migrates
SHARED_APPS into the `public` schema (see config/settings.py's
SHARED_APPS/TENANT_APPS split) — every TENANT_APP table (accounts, hrms,
payroll, voice_commands, attendance, ...) never gets created in ANY schema
for the test database, so any test touching those models fails with
"relation ... does not exist".

TenantAwareTestRunner fixes this by provisioning one real, fully-migrated
test tenant schema right after Django's own setup_databases() finishes, and
then making sure every individual test's connection is actually pointed at
that schema before it runs — see _patch_transaction_test_case_pre_setup's
own docstring for why a single activation at start-of-run isn't enough —
AND immediately after every simulated APIClient request returns — see
_patch_api_client_request's own docstring for a SECOND, independent way the
connection ends up back on `public` mid-test that the first patch alone
does not cover (confirmed by actually running the full suite against a real
Postgres database: apps.accounts.tests_profile_photo's
test_any_role_including_system_admin_can_set_their_own_photo and every
other test whose test-method body calls make_role()/make_user() etc.
directly, AFTER setUp() has already logged in, failed with "relation ...
does not exist" — the connection was already back on `public` before the
test body's own first ORM query ever ran).
"""
import logging

from django.db import connection
from django.test.runner import DiscoverRunner
from django.test.testcases import TransactionTestCase

logger = logging.getLogger(__name__)

# Human-facing company code / derived schema for the one shared test tenant
# every test run provisions — mirrors apps.tenants.services.provision_company's
# own `schema_name = f'tenant_{company_code.lower()}'` derivation, so this
# stays a real, valid schema name rather than an invented convention.
TEST_COMPANY_CODE = 'TESTCO'
TEST_SCHEMA_NAME = f'tenant_{TEST_COMPANY_CODE.lower()}'

_pre_setup_patched = False


def _patch_transaction_test_case_pre_setup(client) -> None:
    """
    Monkeypatches TransactionTestCase._pre_setup (guarded to run exactly
    once per process) so `connection.set_tenant(client)` runs again
    immediately before EVERY individual test's own fixture/transaction setup.

    WHY a once-only activation right after setup_databases() isn't enough:
    apps.tenants.middleware.TenantSchemaMiddleware resets the connection to
    the public schema at the START of every real HTTP request — a deliberate
    fail-closed default (see that middleware's own docstring) — and only
    re-activates a tenant schema if the request carries a valid access-token
    cookie for one. Any test that makes an unauthenticated or failed-auth
    request (a bad-password login attempt, a permission-denied check, a
    plain APIClient.post() with no cookie at all, ...) leaves the shared DB
    connection sitting on `public` once that request returns. Since Django
    reuses the same connection across tests within a process, whatever runs
    next — a completely unrelated test's setUp(), or its own ORM queries —
    would then fail with "relation ... does not exist" against the public
    schema, because TENANT_APP tables (accounts, hrms, payroll,
    voice_commands, ...) only exist in tenant schemas, never in public.
    Re-activating the tenant right before each test's _pre_setup guarantees
    every test starts from a known-good tenant-active state regardless of
    what the previous test's requests did to the connection.
    """
    global _pre_setup_patched
    if _pre_setup_patched:
        return

    original_pre_setup = TransactionTestCase._pre_setup

    def _pre_setup_with_tenant(self, *args, **kwargs):
        connection.set_tenant(client)
        return original_pre_setup(self, *args, **kwargs)

    TransactionTestCase._pre_setup = _pre_setup_with_tenant
    _pre_setup_patched = True


_api_client_request_patched = False


def _patch_api_client_request(client) -> None:
    """
    Monkeypatches rest_framework.test.APIClient.request (guarded to run
    exactly once per process) so `connection.set_tenant(client)` runs again
    immediately after EVERY simulated request an APIClient instance makes —
    every .get()/.post()/.put()/.patch()/.delete() call funnels through this
    one method (APIClient.request is the most-derived override in its MRO —
    APIRequestFactory.generic()/DjangoClient's own verb helpers all end by
    calling self.request(**kwargs)), so patching it here covers every real
    HTTP-shaped test call site in this project uniformly.

    WHY the _pre_setup patch above (reactivating once at the START of each
    test) isn't enough on its own: apps.accounts.views.LoginView.post()
    activates the target company's schema only for the DURATION of its own
    `with client:` block, then restores whatever was active before entering
    it — which is `public`, since TenantSchemaMiddleware.process_request()
    unconditionally defaults every request to `public` first (see that
    middleware's own docstring) and a login request carries no access-token
    cookie yet for it to reactivate a tenant from. So even a fully
    SUCCESSFUL login leaves the connection on `public` the instant it
    returns — not just a failed/unauthenticated request, as the _pre_setup
    patch's own docstring describes. Since this project's own `_login()`
    test helper (used in nearly every test file's setUp()) is exactly such
    a call, any test that logs in during setUp() and then touches the ORM
    directly afterward — rather than through another AUTHENTICATED request,
    which the middleware WOULD reactivate the tenant from via the response's
    own cookie — hits "relation ... does not exist" on that direct query,
    even though _pre_setup already correctly activated the tenant at the
    start of that very same test. Re-activating again after every request
    closes this gap regardless of which endpoint was called or whether it
    succeeded, failed, or never carried a token at all.
    """
    global _api_client_request_patched
    if _api_client_request_patched:
        return

    from rest_framework.test import APIClient

    original_request = APIClient.request

    def _request_with_tenant(self, *args, **kwargs):
        try:
            return original_request(self, *args, **kwargs)
        finally:
            connection.set_tenant(client)

    APIClient.request = _request_with_tenant
    _api_client_request_patched = True


class TenantAwareTestRunner(DiscoverRunner):
    """See module docstring."""

    def setup_databases(self, **kwargs):
        result = super().setup_databases(**kwargs)
        client = self._provision_test_tenant()
        connection.set_tenant(client)
        _patch_transaction_test_case_pre_setup(client)
        _patch_api_client_request(client)
        return result

    def _provision_test_tenant(self):
        """
        Provisions ONE test tenant schema, mirroring
        apps.tenants.services.provision_company's own
        Client(...).save() / Domain.objects.create(...) pattern —
        auto_create_schema (Client's class-level default) does the actual
        CREATE SCHEMA + migrate work as part of .save() below, which is what
        actually brings every TENANT_APP table into existence.

        Reuses an existing Client row for TEST_COMPANY_CODE if one is
        already there (supports `manage.py test --keepdb`: a previous run's
        schema is already created and fully migrated, and
        auto_create_schema's CREATE SCHEMA is not idempotent, so attempting
        it again would fail/be wasted work for no benefit).

        enabled_modules is every known module (ALL_MODULES) rather than an
        empty default — TenantSchemaMiddleware's own module gate
        (tenant.has_module()) would otherwise 403 any test hitting a
        module-gated endpoint (payroll, voice_commands, attendance, ...)
        regardless of what that test is actually trying to check.
        """
        from apps.tenants.models import ALL_MODULES, Client, Domain

        client = Client.objects.filter(company_code=TEST_COMPANY_CODE).first()
        if client is not None:
            return client

        client = Client(
            schema_name=TEST_SCHEMA_NAME,
            company_code=TEST_COMPANY_CODE,
            company_name='Test Company',
            enabled_modules=list(ALL_MODULES),
            is_active=True,
        )
        client.save()  # auto_create_schema=True creates + migrates the schema here

        Domain.objects.create(
            domain=f'{TEST_COMPANY_CODE.lower()}.internal', tenant=client, is_primary=True,
        )

        logger.info('TenantAwareTestRunner: provisioned test tenant %s (%s)', TEST_COMPANY_CODE, TEST_SCHEMA_NAME)
        return client
