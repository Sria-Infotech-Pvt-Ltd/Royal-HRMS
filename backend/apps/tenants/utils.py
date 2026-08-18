"""
Tenant-context helpers for code that runs OUTSIDE an HTTP request — Celery
tasks, chiefly. apps.tenants.middleware.TenantSchemaMiddleware only scopes
the database connection for the lifetime of one HTTP request; a Celery
worker process (or Celery Beat itself) never goes through that middleware,
so without deliberately activating a tenant, task code sees only the
public schema — no business tables live there at all (see SHARED_APPS /
TENANT_APPS in config/settings.py), so every query fails outright.
"""
import logging

from apps.tenants.models import Client

logger = logging.getLogger(__name__)


def run_for_all_tenants(fn, task_name: str = '') -> dict:
    """
    Runs fn() once per active company, with that company's schema
    activated. Used by scheduled (Celery Beat) tasks that have no single
    natural tenant — e.g. "check every company for missing clockouts today"
    rather than "check clockouts for company X".

    One tenant's exception is logged and does NOT stop the others — a bug
    or outage affecting one company's data must never silently skip the
    daily reminder/check for every other company.

    Returns {schema_name: result_or_None} for every active tenant.
    """
    results = {}
    for client in Client.objects.filter(is_active=True):
        try:
            with client:
                results[client.schema_name] = fn()
        except Exception:
            logger.error(
                '%s failed for tenant %s', task_name or fn.__name__, client.schema_name,
                exc_info=True,
            )
            results[client.schema_name] = None
    return results


def run_in_tenant(schema_name: str, fn):
    """
    Runs fn() with the given company's schema activated. Used by
    per-object tasks (e.g. "email this announcement") that already know
    exactly which company they belong to — the schema_name the caller
    captured at dispatch time, when a tenant WAS active (mid-request).

    Raises Client.DoesNotExist if the schema is unknown/inactive — callers
    let this propagate so Celery's normal retry/failure handling applies,
    same as any other exception in task body.
    """
    client = Client.objects.get(schema_name=schema_name, is_active=True)
    with client:
        return fn()


def get_current_company_code() -> str:
    """
    The human-facing Company ID (e.g. "DEMOCO") for whichever tenant schema
    is currently active — for anything shown to a user that needs to tell
    them which Company ID to log in with (e.g. the new-employee welcome
    email). Client itself lives in the public schema (see SHARED_APPS), so
    this briefly switches there to look it up and restores the caller's
    schema on the way out. Returns '' if no tenant is active (e.g. running
    against public directly) or the lookup fails, so a caller building an
    email/notification degrades gracefully instead of crashing.
    """
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, schema_context

    current_schema = connection.schema_name
    if not current_schema or current_schema == get_public_schema_name():
        return ''
    try:
        with schema_context(get_public_schema_name()):
            client = Client.objects.filter(schema_name=current_schema).first()
            return client.company_code if client else ''
    except Exception:
        logger.exception('get_current_company_code failed for schema %s', current_schema)
        return ''
