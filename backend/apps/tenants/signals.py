"""
Invalidates core.cache_service.TenantClientCacheService's cached Client row
whenever the underlying row actually changes, so a deactivation/reactivation
is reflected on the very next request rather than left stale for up to
TENANT_CLIENT's TTL — see that service's own docstring.

Registered via apps/tenants/apps.py TenantsConfig.ready().
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.tenants.models import Client
from core.cache_service import TenantClientCacheService


@receiver(post_save, sender=Client)
def invalidate_client_cache_on_save(sender, instance, **kwargs):
    TenantClientCacheService.invalidate(instance.schema_name)


@receiver(post_delete, sender=Client)
def invalidate_client_cache_on_delete(sender, instance, **kwargs):
    TenantClientCacheService.invalidate(instance.schema_name)
