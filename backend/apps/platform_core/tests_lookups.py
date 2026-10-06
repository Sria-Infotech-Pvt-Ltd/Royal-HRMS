"""Phase 1 Task D — lookup engine service tests."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.platform_core import services_lookups as lookups
from apps.platform_core.models import LookupType, LookupValue


class LookupServiceTests(TestCase):
    def setUp(self):
        # Same reason every other test file in this codebase clears the
        # cache in setUp: the metadata cache is a real process-wide cache
        # backend (not DB-transaction-scoped), so a previous test's cached
        # result for the same lookup-type code can otherwise leak into
        # this test even though the DB itself was rolled back.
        cache.clear()
        self.lt = LookupType.objects.create(code='TEST_TYPE', name='Test Type')
        self.active = LookupValue.objects.create(lookup_type=self.lt, code='ACTIVE_ONE', label='Active One', sort_order=1)
        self.inactive = LookupValue.objects.create(lookup_type=self.lt, code='INACTIVE_ONE', label='Inactive One', sort_order=2, is_active=False)

    def test_get_values_excludes_inactive_by_default(self):
        values = lookups.get_values('TEST_TYPE')
        codes = {v.code for v in values}
        self.assertIn('ACTIVE_ONE', codes)
        self.assertNotIn('INACTIVE_ONE', codes)

    def test_get_values_includes_inactive_when_requested(self):
        values = lookups.get_values('TEST_TYPE', include_inactive=True)
        codes = {v.code for v in values}
        self.assertIn('INACTIVE_ONE', codes)

    def test_is_valid(self):
        self.assertTrue(lookups.is_valid('TEST_TYPE', 'ACTIVE_ONE'))
        self.assertFalse(lookups.is_valid('TEST_TYPE', 'NOT_A_REAL_CODE'))

    def test_deactivated_value_still_valid_for_is_valid_check(self):
        # Task D rule: a deactivated value must still be accepted for
        # EXISTING records (is_valid uses include_inactive=True
        # internally) — only NEW selections should reject it, which is
        # the caller's job to enforce (e.g. a serializer using
        # get_values() without include_inactive for its choice list).
        self.assertTrue(lookups.is_valid('TEST_TYPE', 'INACTIVE_ONE'))

    def test_get_label_falls_back_to_code_for_unknown_value(self):
        self.assertEqual(lookups.get_label('TEST_TYPE', 'TOTALLY_UNKNOWN'), 'TOTALLY_UNKNOWN')

    def test_get_label_returns_stored_label(self):
        self.assertEqual(lookups.get_label('TEST_TYPE', 'ACTIVE_ONE'), 'Active One')

    def test_legacy_value_lookup(self):
        # get_values() is cache-backed (Task I) — a plain .create() here
        # doesn't bump the 'lookups' namespace version until its
        # transaction.on_commit fires, which TestCase's own wrap-and-
        # rollback never does on its own. Same reasoning as
        # tests_cache.py's MetadataCacheInvalidationTests.
        with self.captureOnCommitCallbacks(execute=True):
            LookupValue.objects.create(lookup_type=self.lt, code='MAPPED', label='Mapped', attributes={'legacy_value': 'old_value'})
        self.assertEqual(lookups.legacy_value_to_code('TEST_TYPE', 'old_value'), 'MAPPED')
        self.assertIsNone(lookups.legacy_value_to_code('TEST_TYPE', 'never_seen'))

    def test_gender_pilot_values_match_existing_stored_values(self):
        # Confirms the core_lookups seed pack's legacy_value attributes
        # exactly match what EmployeeProfile.GENDER_CHOICES/FamilyMember.
        # GENDER_CHOICES already store today — the whole point of the
        # pilot conversion's backward-compatibility requirement. The test
        # DB is isolated from whatever's been seeded in dev/prod, so this
        # loads the real pack here rather than assuming it's present.
        from django.core.management import call_command
        call_command('load_seed_pack', 'core_lookups')
        self.assertEqual(lookups.legacy_value_to_code('GENDER', 'male'), 'MALE')
        self.assertEqual(lookups.legacy_value_to_code('GENDER', 'female'), 'FEMALE')
        self.assertEqual(lookups.legacy_value_to_code('GENDER', 'other'), 'OTHER')
