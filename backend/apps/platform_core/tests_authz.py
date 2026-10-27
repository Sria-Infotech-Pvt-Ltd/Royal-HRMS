"""Phase 4 — authorization engine tests. Proven against the Phase 2
"Vehicle Allocation" custom entity, same strategy used for the Phase 3A
policy engine and Phase 3B workflow engine, since the engine is not
wired into any existing core-entity view in this pass."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Permission, Placement, Position, PositionPermission
from core.access import current_seat
from apps.platform_core import services_authz as authz
from apps.platform_core import services_authz_admin as authz_admin
from apps.platform_core import services_field_security as field_security
from apps.platform_core import services_sod as sod
from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import EntityDefinition, FieldDefinition, FieldPermission, PositionAssignment, SoDRule


def _seat_held_by(user, title='Test Seat'):
    """A new position held by `user` from the start of 2020."""
    unit, _ = OrgUnit.objects.get_or_create(name='Authz Test Unit')
    seat = Position.objects.create(org_unit=unit, title=title, grade='L1')
    Placement.objects.create(position=seat, employee=user, effective_from=datetime.date(2020, 1, 1))
    return seat


class ScopeQuerysetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(
            code='vehicle_allocation', label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM,
            attributes_column='data',
        )
        FieldDefinition.objects.create(
            entity=self.entity, code='vehicle_number', label='Vehicle Number', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED,
        )
        self.role = make_role('authz_role')
        self.owner = make_user('authz-owner@test.com', role=self.role)
        self.other_user = make_user('authz-other@test.com', role=self.role)
        self.seat = _seat_held_by(self.owner, 'Authz Seat')

        self.own_record = custom_objects.create_record(self.entity, {'vehicle_number': 'OWN123'}, actor=self.owner)
        self.own_record.owner = self.owner
        self.own_record.save()
        self.other_record = custom_objects.create_record(self.entity, {'vehicle_number': 'OTHER456'}, actor=self.other_user)
        self.other_record.owner = self.other_user
        self.other_record.save()

    def test_own_scope_sees_only_own_records(self):
        PositionAssignment.objects.create(user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_OWN, effective_from=datetime.date(2020, 1, 1))
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity))
        ids = set(qs.values_list('pk', flat=True))
        self.assertEqual(ids, {self.own_record.pk})

    def test_all_scope_sees_everything(self):
        PositionAssignment.objects.create(user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_ALL, effective_from=datetime.date(2020, 1, 1))
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity))
        ids = set(qs.values_list('pk', flat=True))
        self.assertEqual(ids, {self.own_record.pk, self.other_record.pk})

    def test_no_assignment_sees_nothing(self):
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity))
        self.assertEqual(qs.count(), 0)

    def test_expired_assignment_does_not_grant_access(self):
        PositionAssignment.objects.create(
            user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_ALL,
            effective_from=datetime.date(2020, 1, 1), effective_to=datetime.date(2020, 12, 31),
        )
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity), as_of=datetime.date(2026, 1, 1))
        self.assertEqual(qs.count(), 0)

    def test_future_assignment_does_not_grant_access_yet(self):
        PositionAssignment.objects.create(user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_ALL, effective_from=datetime.date(2030, 1, 1))
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity), as_of=datetime.date(2026, 1, 1))
        self.assertEqual(qs.count(), 0)

    def test_superuser_sees_everything_without_any_assignment(self):
        admin_user = make_user('authz-admin@test.com', is_superuser=True)
        qs = authz.scope_queryset(admin_user, self.entity, 'view', custom_objects.list_records(self.entity))
        self.assertEqual(qs.count(), 2)

    def test_can_single_record_check_matches_scope_queryset(self):
        PositionAssignment.objects.create(user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_OWN, effective_from=datetime.date(2020, 1, 1))
        self.assertTrue(authz.can(self.owner, self.entity, 'view', self.own_record))
        self.assertFalse(authz.can(self.owner, self.entity, 'view', self.other_record))

    def test_union_of_multiple_assignments(self):
        """Task B.1 — effective rights are the union of all assignments."""
        PositionAssignment.objects.create(user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_OWN, effective_from=datetime.date(2020, 1, 1))
        from apps.platform_core.models import Country, Currency, LegalEntity, Timezone
        inr, _ = Currency.objects.get_or_create(code='INR', defaults={'name': 'Indian Rupee', 'symbol': '₹', 'minor_units': 2})
        tz, _ = Timezone.objects.get_or_create(name='Asia/Kolkata')
        india, _ = Country.objects.get_or_create(iso2='IN', defaults={'iso3': 'IND', 'name': 'India', 'default_currency': inr, 'default_timezone': tz})
        legal_entity = LegalEntity.objects.create(code='LE1', legal_name='Entity 1', base_currency=inr, country=india, timezone=tz)
        self.other_record.legal_entity_id = legal_entity.pk
        self.other_record.save()
        PositionAssignment.objects.create(
            user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_LEGAL_ENTITY,
            scope_values=[str(legal_entity.pk)], effective_from=datetime.date(2020, 1, 1),
        )
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity))
        self.assertEqual(set(qs.values_list('pk', flat=True)), {self.own_record.pk, self.other_record.pk})

    def test_unmapped_scope_type_raises_not_silently_matches_everything(self):
        """Task C.5 — "where behaviour cannot be expressed exactly, stop"
        — an org_unit scope has no declared mapping for a generic
        CustomRecord, so it must contribute nothing, not accidentally
        match everything."""
        PositionAssignment.objects.create(user=self.owner, position=self.seat, scope_type=PositionAssignment.SCOPE_ORG_UNIT, scope_values=['unit-1'], effective_from=datetime.date(2020, 1, 1))
        qs = authz.scope_queryset(self.owner, self.entity, 'view', custom_objects.list_records(self.entity))
        self.assertEqual(qs.count(), 0)  # not mapped -> contributes nothing, never "everything"

    def test_core_entity_raises_authz_error_not_silently_approximated(self):
        core_entity = EntityDefinition.objects.get(code='branch')
        with self.assertRaises(authz.AuthzError):
            authz.scope_queryset(self.owner, core_entity, 'view', object())


class FieldSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(code='vehicle_allocation_fs', label='VA', kind=EntityDefinition.KIND_CUSTOM, attributes_column='data')
        self.sensitive_field = FieldDefinition.objects.create(entity=self.entity, code='bank_account', label='Bank Account', data_type='text', is_sensitive=True, status=FieldDefinition.STATUS_PUBLISHED)
        self.normal_field = FieldDefinition.objects.create(entity=self.entity, code='notes', label='Notes', data_type='text', status=FieldDefinition.STATUS_PUBLISHED)
        self.user = make_user('field-sec-user@test.com')
        self.seat = _seat_held_by(self.user, 'Field Security Seat')

    def test_sensitive_field_masked_by_default(self):
        access = field_security.resolve_field_access(self.user, self.entity, self.sensitive_field)
        self.assertEqual(access, FieldPermission.ACCESS_MASKED)

    def test_normal_field_defaults_to_read(self):
        access = field_security.resolve_field_access(self.user, self.entity, self.normal_field)
        self.assertEqual(access, FieldPermission.ACCESS_READ)

    def test_explicit_grant_overrides_default(self):
        FieldPermission.objects.create(position=self.seat, entity=self.entity, field_code='bank_account', access=FieldPermission.ACCESS_EDIT)
        access = field_security.resolve_field_access(self.user, self.entity, self.sensitive_field)
        self.assertEqual(access, FieldPermission.ACCESS_EDIT)

    def test_hidden_field_dropped_from_response(self):
        FieldPermission.objects.create(position=self.seat, entity=self.entity, field_code='notes', access=FieldPermission.ACCESS_HIDDEN)
        result = field_security.apply_field_security(self.user, self.entity, [self.normal_field], {'notes': 'secret note'})
        self.assertNotIn('notes', result)

    def test_masked_field_is_masked_in_response(self):
        result = field_security.apply_field_security(self.user, self.entity, [self.sensitive_field], {'bank_account': '1234567890123456'})
        self.assertNotEqual(result['bank_account'], '1234567890123456')
        self.assertTrue(result['bank_account'].endswith('3456'))

    def test_write_to_read_only_field_rejected(self):
        with self.assertRaises(field_security.FieldSecurityError):
            field_security.apply_field_security(self.user, self.entity, [self.normal_field], {'notes': 'x'}, for_write=True)

    def test_write_to_edit_field_allowed(self):
        FieldPermission.objects.create(position=self.seat, entity=self.entity, field_code='notes', access=FieldPermission.ACCESS_EDIT)
        result = field_security.apply_field_security(self.user, self.entity, [self.normal_field], {'notes': 'x'}, for_write=True)
        self.assertEqual(result['notes'], 'x')

    def test_filter_by_masked_field_rejected(self):
        with self.assertRaises(field_security.FieldSecurityError):
            field_security.validate_filter_sort_fields(
                self.user, self.entity, {'bank_account': self.sensitive_field},
                filter_fields=['bank_account'], sort_field=None,
            )

    def test_sort_by_hidden_field_rejected(self):
        FieldPermission.objects.create(position=self.seat, entity=self.entity, field_code='notes', access=FieldPermission.ACCESS_HIDDEN)
        with self.assertRaises(field_security.FieldSecurityError):
            field_security.validate_filter_sort_fields(
                self.user, self.entity, {'notes': self.normal_field},
                filter_fields=[], sort_field='notes',
            )

    def test_filter_by_readable_field_allowed(self):
        field_security.validate_filter_sort_fields(
            self.user, self.entity, {'notes': self.normal_field},
            filter_fields=['notes'], sort_field=None,
        )  # no exception


class SoDTests(TestCase):
    def setUp(self):
        self.perm_a = Permission.objects.create(module='sodtest', action='a', codename='sodtest.a')
        self.perm_b = Permission.objects.create(module='sodtest', action='b', codename='sodtest.b')
        self.rule = SoDRule.objects.create(
            code='test_rule', conflicting_permissions_a=['sodtest.a'], conflicting_permissions_b=['sodtest.b'],
            severity=SoDRule.SEVERITY_BLOCK, is_active=True,
        )
        self.role = make_role('sod_role', permission_codenames=['sodtest.a'])
        self.user = make_user('sod-user@test.com', role=self.role)

    def test_block_severity_raises(self):
        with self.assertRaises(sod.SoDBlockedError):
            sod.check(self.user, additional_codenames={'sodtest.b'})

    def test_no_conflict_does_not_raise(self):
        sod.check(self.user)  # only holds sodtest.a, no conflict yet

    def test_warn_severity_requires_reason(self):
        self.rule.severity = SoDRule.SEVERITY_WARN
        self.rule.save()
        with self.assertRaises(sod.SoDBlockedError):
            sod.check(self.user, additional_codenames={'sodtest.b'})
        sod.check(self.user, additional_codenames={'sodtest.b'}, reason='Approved by owner for pilot.')  # does not raise

    def test_existing_violations_report_finds_real_conflict(self):
        PositionPermission.objects.get_or_create(position=current_seat(self.user), permission=self.perm_b)
        report = sod.existing_violations_report()
        matching = [v for v in report if v['rule'] == 'test_rule' and v['user_id'] == str(self.user.pk)]
        self.assertEqual(len(matching), 1)


class AdminToolsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.perm = Permission.objects.create(module='admintest', action='view', codename='admintest.view')
        self.role = make_role('admin_tools_role', permission_codenames=['admintest.view'])
        self.user = make_user('admintools-user@test.com', role=self.role)

    def test_who_can_finds_the_user_via_their_position(self):
        results = authz_admin.who_can('admintest.view')
        self.assertTrue(any(r['user_id'] == str(self.user.pk) and r['via'] == 'position' for r in results))

    def test_what_can_lists_effective_permissions(self):
        result = authz_admin.what_can(self.user)
        codenames = {p['codename'] for p in result['permissions']}
        self.assertIn('admintest.view', codenames)

    def test_clone_position_access_copies_permissions(self):
        source = current_seat(self.user)
        target = _seat_held_by(make_user('clone-target@test.com'), 'Clone Target')
        authz_admin.clone_position_access(source, target)
        cloned_codenames = set(PositionPermission.objects.filter(position=target).values_list('permission__codename', flat=True))
        self.assertIn('admintest.view', cloned_codenames)

    def test_compare_positions_shows_differences(self):
        other = _seat_held_by(make_user('compare-other@test.com'), 'Compare Other')
        result = authz_admin.compare_positions(current_seat(self.user), other)
        self.assertIn('admintest.view', result['only_in_a'])
        self.assertEqual(result['only_in_b'], [])

    def test_simulate_reflects_has_perm_v2(self):
        result = authz_admin.simulate(self.user, codename='admintest.view')
        self.assertTrue(result['granted'])
        result_denied = authz_admin.simulate(self.user, codename='admintest.nonexistent')
        self.assertFalse(result_denied['granted'])


class IsFullAccessTests(TestCase):
    def test_only_a_superuser_has_full_access(self):
        superuser = make_user('full-access-user@test.com', is_superuser=True)
        self.assertTrue(authz.is_full_access(superuser))
        self.assertTrue(authz.has_perm_v2(superuser, 'anything.at.all'))

    def test_a_seat_with_settings_edit_is_not_full_access(self):
        user = make_user('settings-seat-user@test.com', role=make_role('settings_seat_role', permission_codenames=['settings.edit']))
        self.assertFalse(authz.is_full_access(user))
        self.assertFalse(authz.has_perm_v2(user, 'anything.at.all'))

    def test_a_seat_without_full_access_does_not_grant_everything(self):
        user = make_user('limited-user@test.com', role=make_role('limited_test_role', permission_codenames=['leave.view']))
        self.assertFalse(authz.is_full_access(user))
        self.assertFalse(authz.has_perm_v2(user, 'anything.at.all'))

    def test_superuser_is_always_full_access(self):
        user = make_user('su-user@test.com', is_superuser=True)
        self.assertTrue(authz.is_full_access(user))


class ExternalAPIKeyScopeTests(TestCase):
    def test_empty_scope_allows_everything_legacy_behaviour(self):
        from apps.accounts.models import ExternalAPIKey
        key = ExternalAPIKey.objects.create(name='legacy_key', key_hash='x' * 64)
        self.assertTrue(key.allows_scope('anything.at.all'))

    def test_explicit_scope_restricts(self):
        from apps.accounts.models import ExternalAPIKey
        key = ExternalAPIKey.objects.create(name='scoped_key', key_hash='y' * 64, scope_codenames=['employees.view'])
        self.assertTrue(key.allows_scope('employees.view'))
        self.assertFalse(key.allows_scope('payroll.view'))

    def test_ip_allowlist(self):
        from apps.accounts.models import ExternalAPIKey
        key = ExternalAPIKey.objects.create(name='ip_key', key_hash='z' * 64, ip_allowlist=['10.0.0.0/24'])
        self.assertTrue(key.allows_ip('10.0.0.5'))
        self.assertFalse(key.allows_ip('192.168.1.1'))

    def test_expiry(self):
        from apps.accounts.models import ExternalAPIKey
        from django.utils import timezone
        import datetime as dt
        key = ExternalAPIKey.objects.create(name='expiring_key', key_hash='w' * 64, expires_at=timezone.now() - dt.timedelta(days=1))
        self.assertTrue(key.is_expired())
