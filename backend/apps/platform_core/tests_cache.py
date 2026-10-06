"""Phase 1 Task I — metadata cache invalidation tests."""
from __future__ import annotations

from django.core.cache import cache as django_cache
from django.test import TestCase

from apps.platform_core import cache as metadata_cache
from apps.platform_core.models import LookupType, LookupValue


class MetadataCacheInvalidationTests(TestCase):
    def setUp(self):
        django_cache.clear()

    # bump_version() fires via transaction.on_commit — Django's TestCase
    # wraps each test in a transaction that's rolled back, not committed,
    # so on_commit callbacks never fire on their own here. Every test in
    # this class must wrap its write(s) in captureOnCommitCallbacks to
    # actually exercise the invalidation path, rather than silently
    # testing nothing.

    def test_version_bumps_on_create(self):
        v1 = metadata_cache.get_version('lookups')
        with self.captureOnCommitCallbacks(execute=True):
            LookupType.objects.create(code='CACHE_TEST_TYPE', name='Cache Test')
        v2 = metadata_cache.get_version('lookups')
        self.assertGreater(v2, v1)

    def test_version_bumps_on_update(self):
        lt = LookupType.objects.create(code='CACHE_TEST_TYPE_2', name='Original')
        v1 = metadata_cache.get_version('lookups')
        with self.captureOnCommitCallbacks(execute=True):
            lt.name = 'Changed'
            lt.save()
        v2 = metadata_cache.get_version('lookups')
        self.assertGreater(v2, v1)

    def test_version_bumps_on_delete(self):
        lt = LookupType.objects.create(code='CACHE_TEST_TYPE_3', name='To Delete')
        v1 = metadata_cache.get_version('lookups')
        with self.captureOnCommitCallbacks(execute=True):
            lt.delete()
        v2 = metadata_cache.get_version('lookups')
        self.assertGreater(v2, v1)

    def test_no_stale_read_after_write(self):
        """A value cached before a write must never be returned after it —
        this is the whole point of the version-bump scheme, proven
        end-to-end through services_lookups.get_values(), not just by
        checking the version counter in isolation."""
        from apps.platform_core import services_lookups as lookups

        lt = LookupType.objects.create(code='CACHE_TEST_TYPE_4', name='Stale Read Test')
        LookupValue.objects.create(lookup_type=lt, code='ONE', label='One')
        values_before = lookups.get_values('CACHE_TEST_TYPE_4')
        self.assertEqual(len(values_before), 1)

        with self.captureOnCommitCallbacks(execute=True):
            LookupValue.objects.create(lookup_type=lt, code='TWO', label='Two')
        values_after = lookups.get_values('CACHE_TEST_TYPE_4')
        self.assertEqual(len(values_after), 2, 'Stale cached result returned after a write.')

    def test_cache_unavailable_falls_back_to_database_without_crashing(self):
        """Simulates a cache backend failure — get()/set() must log and
        return None/no-op, never raise, and the caller (services_lookups)
        must still work by falling through to the database."""
        from unittest import mock
        from apps.platform_core import services_lookups as lookups

        lt = LookupType.objects.create(code='CACHE_TEST_TYPE_5', name='Cache Down Test')
        LookupValue.objects.create(lookup_type=lt, code='ONE', label='One')

        with mock.patch('apps.platform_core.cache.cache.get', side_effect=Exception('cache down')), \
             mock.patch('apps.platform_core.cache.cache.set', side_effect=Exception('cache down')):
            values = lookups.get_values('CACHE_TEST_TYPE_5')
            self.assertEqual(len(values), 1)
