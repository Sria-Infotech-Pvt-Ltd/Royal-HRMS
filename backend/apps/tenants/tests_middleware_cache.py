"""
Tests for TenantSchemaMiddleware's cached Client lookup
(core.cache_service.TenantClientCacheService) and its invalidation signals
(apps/tenants/signals.py). See both modules' own docstrings for the
caching/invalidation design this verifies.

Covers: query-count behavior on cache hit/miss, unknown/inactive schema
handling unchanged, signal-driven invalidation (save/delete — NOT assumed
merely because apps/tenants/apps.py imports the signals module; verified
behaviorally by saving a Client and confirming the cache actually clears,
plus a direct receiver-registration check), cache-outage fallback, and
two-tenant isolation through the cache.

Uses RequestFactory + a hand-minted AccessToken (company_schema claim only —
TenantSchemaMiddleware.process_request never resolves a user from this
token, only reads that one claim) to exercise the middleware directly,
narrower and faster than a full login round-trip for what is purely an
apps.tenants.middleware behavior test.
"""
from __future__ import annotations

from unittest.mock import patch

from django.db import connection
from django.test import RequestFactory, TestCase
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.middleware import TenantSchemaMiddleware
from apps.tenants.models import ALL_MODULES, MODULE_LEAVE, MODULE_PAYROLL, Client, Domain
from apps.tenants.signals import invalidate_client_cache_on_save
from config.test_runner import TEST_COMPANY_CODE
from core.cache_service import TenantClientCacheService


def _token_for_schema(schema_name: str) -> str:
    token = AccessToken()
    token['company_schema'] = schema_name
    return str(token)


def _request_for_schema(schema_name: str, path: str = '/api/employees/'):
    req = RequestFactory().get(path)
    req.COOKIES['royal_access_token'] = _token_for_schema(schema_name)
    return req


class TenantClientCacheServiceTests(TestCase):
    """Direct tests of the cache service — query counts, TTL-independent
    correctness. Uses the one tenant schema TenantAwareTestRunner already
    provisions (TEST_COMPANY_CODE); all lookups run explicitly on public,
    mirroring exactly how the real middleware calls this (after its own
    connection.set_schema_to_public())."""

    def setUp(self):
        self.client_obj = Client.objects.get(company_code=TEST_COMPANY_CODE)
        TenantClientCacheService.invalidate(self.client_obj.schema_name)
        self.addCleanup(lambda: connection.set_tenant(self.client_obj))

    def test_first_lookup_hits_db(self):
        with schema_context(get_public_schema_name()):
            with self.assertNumQueries(1):
                result = TenantClientCacheService.get(self.client_obj.schema_name)
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_name, self.client_obj.schema_name)

    def test_second_lookup_uses_cache_no_db_query(self):
        with schema_context(get_public_schema_name()):
            TenantClientCacheService.get(self.client_obj.schema_name)  # populate
            with self.assertNumQueries(0):
                result = TenantClientCacheService.get(self.client_obj.schema_name)
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_name, self.client_obj.schema_name)

    def test_cache_hit_returns_real_client_instance_with_working_has_module(self):
        with schema_context(get_public_schema_name()):
            TenantClientCacheService.get(self.client_obj.schema_name)  # populate
            result = TenantClientCacheService.get(self.client_obj.schema_name)  # cache hit
        self.assertIsInstance(result, Client)
        # TEST_COMPANY_CODE's fixture has every module enabled (see test_runner.py)
        self.assertTrue(result.has_module(ALL_MODULES[0]))

    def test_unknown_schema_returns_none_and_is_never_cached(self):
        with schema_context(get_public_schema_name()):
            with self.assertNumQueries(1):
                self.assertIsNone(TenantClientCacheService.get('no_such_schema_xyz'))
            # Not cached — a repeat lookup hits the DB again too, same as today.
            with self.assertNumQueries(1):
                self.assertIsNone(TenantClientCacheService.get('no_such_schema_xyz'))

    def test_inactive_client_not_returned(self):
        self.client_obj.is_active = False
        self.client_obj.save(update_fields=['is_active'])
        try:
            with schema_context(get_public_schema_name()):
                self.assertIsNone(TenantClientCacheService.get(self.client_obj.schema_name))
        finally:
            self.client_obj.is_active = True
            self.client_obj.save(update_fields=['is_active'])

    def test_cache_read_failure_falls_back_to_db_safely(self):
        with schema_context(get_public_schema_name()):
            with patch('core.cache_service.cache.get', side_effect=Exception('redis down')):
                result = TenantClientCacheService.get(self.client_obj.schema_name)
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_name, self.client_obj.schema_name)

    def test_cache_write_failure_does_not_raise(self):
        with schema_context(get_public_schema_name()):
            with patch('core.cache_service.cache.set', side_effect=Exception('redis down')):
                result = TenantClientCacheService.get(self.client_obj.schema_name)
        self.assertIsNotNone(result)


class TenantClientCacheInvalidationTests(TestCase):
    """Signal-driven invalidation — NOT assumed from the import in
    apps/tenants/apps.py alone; each test proves the observable effect."""

    def setUp(self):
        self.client_obj = Client.objects.get(company_code=TEST_COMPANY_CODE)
        self.addCleanup(lambda: connection.set_tenant(self.client_obj))

    def test_receiver_actually_registered_on_client_model(self):
        """Direct proof the signal is connected — not just that the module
        imports without error. _live_receivers returns
        (sync_receivers, async_receivers) in Django 5.2."""
        from django.db.models.signals import post_save
        sync_receivers, _async_receivers = post_save._live_receivers(sender=Client)
        self.assertIn(invalidate_client_cache_on_save, sync_receivers)

    def test_save_invalidates_cache_without_calling_invalidate_directly(self):
        with schema_context(get_public_schema_name()):
            TenantClientCacheService.get(self.client_obj.schema_name)  # populate
            key = TenantClientCacheService._key(self.client_obj.schema_name)
            from django.core.cache import cache
            self.assertIsNotNone(cache.get(key))

            # Deliberately NOT calling TenantClientCacheService.invalidate()
            # ourselves — this must happen purely via the post_save signal.
            self.client_obj.save(update_fields=['updated_at'])

            self.assertIsNone(cache.get(key))

    def test_deactivation_is_reflected_on_next_request_not_stale(self):
        with schema_context(get_public_schema_name()):
            TenantClientCacheService.get(self.client_obj.schema_name)  # populate while active
        try:
            self.client_obj.is_active = False
            self.client_obj.save(update_fields=['is_active'])
            with schema_context(get_public_schema_name()):
                self.assertIsNone(TenantClientCacheService.get(self.client_obj.schema_name))
        finally:
            self.client_obj.is_active = True
            self.client_obj.save(update_fields=['is_active'])

    def test_reactivation_is_reflected_on_next_request(self):
        self.client_obj.is_active = False
        self.client_obj.save(update_fields=['is_active'])
        with schema_context(get_public_schema_name()):
            self.assertIsNone(TenantClientCacheService.get(self.client_obj.schema_name))

        self.client_obj.is_active = True
        self.client_obj.save(update_fields=['is_active'])
        with schema_context(get_public_schema_name()):
            result = TenantClientCacheService.get(self.client_obj.schema_name)
        self.assertIsNotNone(result)

    def test_delete_invalidates_cache(self):
        with schema_context(get_public_schema_name()):
            throwaway = Client.objects.create(
                schema_name='tenant_throwaway_delete_test',
                company_code='THROWAWAYDEL',
                company_name='Throwaway Delete Test Co',
                enabled_modules=[], is_active=True,
            )
            Domain.objects.create(domain='throwawaydel.internal', tenant=throwaway, is_primary=True)
            TenantClientCacheService.get(throwaway.schema_name)  # populate
            key = TenantClientCacheService._key(throwaway.schema_name)
            from django.core.cache import cache
            self.assertIsNotNone(cache.get(key))

            throwaway.delete()

            self.assertIsNone(cache.get(key))


class TenantSchemaMiddlewareBehaviorTests(TestCase):
    """External middleware behavior must be identical to before caching was
    introduced — unknown schema, inactive schema, missing/invalid token,
    and successful activation."""

    def setUp(self):
        self.client_obj = Client.objects.get(company_code=TEST_COMPANY_CODE)
        TenantClientCacheService.invalidate(self.client_obj.schema_name)
        self.addCleanup(lambda: connection.set_tenant(self.client_obj))

    def test_no_cookie_leaves_connection_on_public(self):
        req = RequestFactory().get('/api/employees/')
        TenantSchemaMiddleware().process_request(req)
        self.assertEqual(connection.schema_name, get_public_schema_name())

    def test_unknown_schema_leaves_connection_on_public(self):
        req = _request_for_schema('no_such_schema_xyz')
        resp = TenantSchemaMiddleware().process_request(req)
        self.assertIsNone(resp)
        self.assertEqual(connection.schema_name, get_public_schema_name())

    def test_inactive_schema_leaves_connection_on_public(self):
        self.client_obj.is_active = False
        self.client_obj.save(update_fields=['is_active'])
        try:
            req = _request_for_schema(self.client_obj.schema_name)
            resp = TenantSchemaMiddleware().process_request(req)
            self.assertIsNone(resp)
            self.assertEqual(connection.schema_name, get_public_schema_name())
        finally:
            self.client_obj.is_active = True
            self.client_obj.save(update_fields=['is_active'])

    def test_valid_active_schema_activates_tenant(self):
        req = _request_for_schema(self.client_obj.schema_name)
        resp = TenantSchemaMiddleware().process_request(req)
        self.assertIsNone(resp)
        self.assertEqual(connection.schema_name, self.client_obj.schema_name)

    def test_second_request_same_schema_still_activates_correctly_from_cache(self):
        req1 = _request_for_schema(self.client_obj.schema_name)
        TenantSchemaMiddleware().process_request(req1)
        self.assertEqual(connection.schema_name, self.client_obj.schema_name)

        req2 = _request_for_schema(self.client_obj.schema_name)
        TenantSchemaMiddleware().process_request(req2)
        self.assertEqual(connection.schema_name, self.client_obj.schema_name)

    def test_module_gated_path_still_enforced_off_a_cached_client(self):
        # TEST_COMPANY_CODE has every module enabled (test_runner.py), so a
        # module-gated path must still pass through cleanly on both the
        # first (DB) and second (cache) lookup.
        for _ in range(2):
            req = _request_for_schema(self.client_obj.schema_name, path='/api/payroll/cycles/')
            resp = TenantSchemaMiddleware().process_request(req)
            self.assertIsNone(resp)


class TenantClientCacheIsolationTests(TestCase):
    """Two real tenant schemas — proves the cache can never resolve tenant B
    from a lookup keyed by tenant A's schema_name, or vice versa. Mirrors
    config.test_runner's own provisioning pattern (auto_create_schema=True
    does the real CREATE SCHEMA + migrate work in .save()) rather than
    inventing a lighter-weight fixture that wouldn't prove real isolation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant_a = Client.objects.get(company_code=TEST_COMPANY_CODE)
        with schema_context(get_public_schema_name()):
            cls.tenant_b, created = Client.objects.get_or_create(
                company_code='ISOTEST',
                defaults=dict(
                    schema_name='tenant_isotest',
                    company_name='Isolation Test Co',
                    enabled_modules=[MODULE_PAYROLL],
                    is_active=True,
                ),
            )
            if created:
                Domain.objects.create(domain='isotest.internal', tenant=cls.tenant_b, is_primary=True)

    def setUp(self):
        TenantClientCacheService.invalidate(self.tenant_a.schema_name)
        TenantClientCacheService.invalidate(self.tenant_b.schema_name)
        self.addCleanup(lambda: connection.set_tenant(self.tenant_a))

    def test_each_schema_resolves_only_its_own_client_via_cache(self):
        with schema_context(get_public_schema_name()):
            result_a = TenantClientCacheService.get(self.tenant_a.schema_name)
            result_b = TenantClientCacheService.get(self.tenant_b.schema_name)
            # Repeat, now from cache — same isolation must hold on a hit too.
            result_a_cached = TenantClientCacheService.get(self.tenant_a.schema_name)
            result_b_cached = TenantClientCacheService.get(self.tenant_b.schema_name)

        self.assertEqual(result_a.schema_name, self.tenant_a.schema_name)
        self.assertEqual(result_b.schema_name, self.tenant_b.schema_name)
        self.assertEqual(result_a_cached.schema_name, self.tenant_a.schema_name)
        self.assertEqual(result_b_cached.schema_name, self.tenant_b.schema_name)

        # tenant_b only has payroll enabled — proves module data isn't mixed.
        self.assertTrue(result_b_cached.has_module(MODULE_PAYROLL))
        self.assertFalse(result_b_cached.has_module(MODULE_LEAVE))

    def test_full_middleware_request_activates_correct_tenant_only(self):
        req_a = _request_for_schema(self.tenant_a.schema_name)
        TenantSchemaMiddleware().process_request(req_a)
        self.assertEqual(connection.schema_name, self.tenant_a.schema_name)

        req_b = _request_for_schema(self.tenant_b.schema_name)
        TenantSchemaMiddleware().process_request(req_b)
        self.assertEqual(connection.schema_name, self.tenant_b.schema_name)
        # And back again, both now served from cache.
        req_a2 = _request_for_schema(self.tenant_a.schema_name)
        TenantSchemaMiddleware().process_request(req_a2)
        self.assertEqual(connection.schema_name, self.tenant_a.schema_name)
