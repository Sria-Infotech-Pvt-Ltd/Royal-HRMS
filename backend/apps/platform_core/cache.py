"""
Phase 1 Task I — versioned metadata cache namespaces. Any write to a model
in a namespace bumps that namespace's version (via transaction.on_commit,
so a rolled-back transaction never invalidates anything), which makes
every previously-cached key for that namespace unreachable without
needing to explicitly track/delete each one — the same effect as
"invalidate everything in this namespace" but without an unbounded
cache.delete_many() call.

Works identically against Redis and the local-memory fallback (both are
just django.core.cache.cache) — same try/except-and-log-and-fall-back-to-
the-database philosophy already used throughout core/cache_service.py.
"""
from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

NAMESPACES = ('lookups', 'geo', 'flags', 'numbering', 'entities')

_DEFAULT_TTL = 300  # generous base TTL — the version bump is what actually
                    # invalidates on change, this is just a cap so a
                    # namespace that's never written to doesn't cache forever


def _version_key(namespace: str) -> str:
    return f'platform_meta_version:{namespace}'


def get_version(namespace: str) -> int:
    try:
        version = cache.get(_version_key(namespace))
    except Exception:
        logger.warning('MetadataCache: version read failed for namespace=%s', namespace)
        return 0  # version 0 never matches a real cached key — safe "always miss"
    return version or 1


def bump_version(namespace: str) -> None:
    """Call from a model's post_save/post_delete signal, wrapped in
    transaction.on_commit() — see signals.py."""
    def _bump():
        try:
            try:
                cache.incr(_version_key(namespace))
            except ValueError:
                # Key didn't exist yet (incr requires an existing key).
                cache.set(_version_key(namespace), 2)
        except Exception:
            logger.warning('MetadataCache: version bump failed for namespace=%s', namespace)
    transaction.on_commit(_bump)


def cache_key(namespace: str, suffix: str) -> str:
    return f'platform_meta:{namespace}:v{get_version(namespace)}:{suffix}'


def get(namespace: str, suffix: str):
    try:
        return cache.get(cache_key(namespace, suffix))
    except Exception:
        logger.warning('MetadataCache: read failed for %s/%s', namespace, suffix)
        return None


def set(namespace: str, suffix: str, value, ttl: int = _DEFAULT_TTL) -> None:
    try:
        cache.set(cache_key(namespace, suffix), value, ttl)
    except Exception:
        logger.warning('MetadataCache: write failed for %s/%s', namespace, suffix)


def cached(namespace: str, suffix: str, loader, ttl: int = _DEFAULT_TTL):
    """get-or-compute-and-set in one call."""
    value = get(namespace, suffix)
    if value is not None:
        return value
    value = loader()
    set(namespace, suffix, value, ttl)
    return value
