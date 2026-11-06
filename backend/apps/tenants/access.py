"""
Which modules the active company may use — one answer for the API gate, the
login / token `modules` claim, the dashboards and the notification list.

Rules (on top of Client.enabled_modules, which the subscription writes):
  * the original modules (attendance, leave, payroll, …) — exactly
    enabled_modules, always;
  * the modules added with SaaS plans (documents, assets, wfh) — exactly
    enabled_modules once the company's subscription has been applied, or
    when SUBSCRIPTION_ENFORCEMENT == 'on'. A company still without an
    applied subscription (legacy, not yet backfilled) keeps them, as before.
"""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context

from apps.tenants.modules import LATE_GATED_MODULES

_STATE_KEY = 'tenant:subscription_applied:{schema}'
_STATE_TTL = 300


def subscription_applied(client) -> bool:
    """True when the company's subscription modules are in effect
    (provisioning Success, or a new company being set up with them)."""
    if client is None or getattr(client, 'pk', None) is None or getattr(client, 'schema_name', 'public') == 'public':
        return False
    key = _STATE_KEY.format(schema=client.schema_name)
    # Cache keys are prefixed with the active schema (core.cache_keys) — read
    # and write this one in the public schema so the Platform Admin side
    # (public) can invalidate what a company request (tenant) cached.
    with schema_context(get_public_schema_name()):
        applied = cache.get(key)
        if applied is None:
            from apps.tenants.models import CompanySubscription as Sub
            status = Sub.objects.filter(client_id=client.pk).values_list('provisioning_status', flat=True).first()
            applied = status in (Sub.PROVISION_SUCCESS, Sub.PROVISION_PENDING)
            cache.set(key, applied, _STATE_TTL)
    return applied


def invalidate_subscription_state(schema_name: str) -> None:
    with schema_context(get_public_schema_name()):
        cache.delete(_STATE_KEY.format(schema=schema_name))


def strict(client) -> bool:
    """Late-gated modules follow enabled_modules exactly for this company."""
    return getattr(settings, 'SUBSCRIPTION_ENFORCEMENT', 'off') == 'on' or subscription_applied(client)


def visible_modules(client, enabled=None) -> list[str]:
    """The modules this company's users may see and use."""
    out = set(enabled if enabled is not None else (getattr(client, 'enabled_modules', None) or []))
    if not strict(client):
        out |= set(LATE_GATED_MODULES)
    return sorted(out)


def current_tenant():
    tenant = getattr(connection, 'tenant', None)
    return None if getattr(tenant, 'schema_name', 'public') == 'public' else tenant


def module_enabled(key: str, client=None) -> bool:
    """Whether the active (or given) company may use module `key`. Outside a
    company (public schema, scripts) everything counts as enabled."""
    client = client if client is not None else current_tenant()
    if client is None or getattr(client, 'enabled_modules', None) is None:
        return True
    return key in visible_modules(client)


# Notification.module / AuditLog.module values that belong to a sellable
# module; anything else (birthdays, security, settings, …) is core.
NOTIFICATION_MODULES = {
    'leave': 'leave', 'holiday': 'leave', 'attendance': 'attendance', 'regularization': 'attendance',
    'permission': 'attendance', 'facial_recognition': 'face_attendance', 'expense': 'expenses',
    'separation': 'separation', 'documents': 'documents', 'payroll': 'payroll', 'announcement': 'announcements',
}
AUDIT_MODULES = {
    'leave': 'leave', 'attendance': 'attendance', 'payroll': 'payroll', 'recruitment': 'recruitment',
    'assets': 'assets', 'documents': 'documents', 'announcement': 'announcements', 'wfh': 'wfh',
    'assessments': 'assessments', 'expenses': 'expenses', 'separation': 'separation',
}


def hidden_names(mapping: dict[str, str], client=None) -> list[str]:
    """The source names (e.g. Notification.module values) whose module is off."""
    return [name for name, module in mapping.items() if not module_enabled(module, client)]
