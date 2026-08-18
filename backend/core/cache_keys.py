"""
Tenant-aware cache key function — plugged in as CACHES['default']['KEY_FUNCTION']
in config/settings.py, for both the Redis and LocMemCache backends.

Without this, every cache key in core/cache_service.py and the dashboard
views (e.g. 'company:info', 'branches:all', 'leave_policy:all') is a plain,
tenant-agnostic string. apps.tenants.middleware.TenantSchemaMiddleware only
scopes the DATABASE connection per request — Django's separate cache
framework has no idea tenants exist, so with a shared Redis instance (or a
shared in-process LocMemCache) every company reads and writes the exact
same cache entries. Company A's request populates 'company:info'; Company
B's next request gets Company A's cached row back, without ever touching
the database or going through the correct schema at all.

Prepending the currently-active schema name here fixes this for every
existing and future cache key project-wide, without needing to touch each
individual cache.get/set call site.
"""
from django.db import connection


def tenant_aware_key_func(key, key_prefix, version) -> str:
    # connection.schema_name is None before any tenant is activated (e.g. a
    # bare `manage.py shell` with no request/task context) — fall back to a
    # fixed label so those rare cases still get a stable, non-crashing key
    # instead of mixing into the public/tenant keyspace unpredictably.
    schema_name = getattr(connection, "schema_name", None) or "__no_tenant__"
    return f"{schema_name}:{key_prefix}:{version}:{key}"
