"""
Phase 2 Task C — custom attribute storage tests. Uses the `branch` core
entity (plain `attributes` column — simplest case) and the `employee`
entity (dotted `profile__custom_field_values` path — the special case
Task A.3 explicitly asked to be designed and documented) to prove both
storage shapes work identically through the same service.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile
from apps.branch.models import Branch, City, State
from apps.platform_core import services_attributes as attrs
from apps.platform_core.models import EntityDefinition, FieldDefinition


class AttributesServiceBranchTests(TestCase):
    """Branch has a plain `attributes` JSONB column — the simple case."""

    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(branch_code='ATTR01', branch_name='Attr Test Branch', state=state, city=city)
        self.entity = EntityDefinition.objects.get(code='branch')
        self.field = FieldDefinition.objects.create(
            entity=self.entity, code='shoe_size', label='Shoe Size', data_type='integer',
            status=FieldDefinition.STATUS_PUBLISHED, validation={'min': 1, 'max': 20},
        )

    def test_save_and_read_round_trip(self):
        attrs.save(self.entity, self.branch, {'shoe_size': '9'})
        self.branch.refresh_from_db()
        result = attrs.read(self.entity, self.branch, for_user=None)
        self.assertEqual(result['shoe_size'], 9)

    def test_validation_error_rejects_out_of_range(self):
        with self.assertRaises(attrs.AttributeValidationError) as ctx:
            attrs.save(self.entity, self.branch, {'shoe_size': '999'})
        self.assertIn('shoe_size', ctx.exception.errors)

    def test_unknown_field_rejected(self):
        with self.assertRaises(attrs.AttributeValidationError) as ctx:
            attrs.save(self.entity, self.branch, {'not_a_real_field': 'x'})
        self.assertIn('not_a_real_field', ctx.exception.errors)

    def test_archived_field_excluded_from_read_but_data_kept(self):
        attrs.save(self.entity, self.branch, {'shoe_size': '10'})
        self.field.status = FieldDefinition.STATUS_ARCHIVED
        self.field.save()
        self.branch.refresh_from_db()

        result = attrs.read(self.entity, self.branch, for_user=None)
        self.assertNotIn('shoe_size', result)  # excluded from the read
        self.assertEqual(self.branch.attributes.get('shoe_size'), 10)  # but data is untouched in storage

        # Restoring brings it back.
        self.field.status = FieldDefinition.STATUS_PUBLISHED
        self.field.save()
        result2 = attrs.read(self.entity, self.branch, for_user=None)
        self.assertEqual(result2['shoe_size'], 10)

    def test_partial_save_skips_required_check_for_absent_fields(self):
        FieldDefinition.objects.create(
            entity=self.entity, code='required_field', label='Required', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, required=True,
        )
        # Omitting required_field entirely should be fine under partial=True
        # (PATCH semantics) — only an explicitly-blank value should fail.
        attrs.save(self.entity, self.branch, {'shoe_size': '5'}, partial=True)

    def test_required_field_rejected_when_explicitly_blank(self):
        FieldDefinition.objects.create(
            entity=self.entity, code='required_field', label='Required', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, required=True,
        )
        with self.assertRaises(attrs.AttributeValidationError):
            attrs.save(self.entity, self.branch, {'required_field': ''})


class AttributesServiceUniquenessTests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch1 = Branch.objects.create(branch_code='ATTR02', branch_name='B1', state=state, city=city)
        self.branch2 = Branch.objects.create(branch_code='ATTR03', branch_name='B2', state=state, city=city)
        self.entity = EntityDefinition.objects.get(code='branch')
        self.field = FieldDefinition.objects.create(
            entity=self.entity, code='fleet_tag', label='Fleet Tag', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, is_unique=True,
        )

    def test_duplicate_unique_value_rejected(self):
        attrs.save(self.entity, self.branch1, {'fleet_tag': 'ABC123'})
        with self.assertRaises(attrs.AttributeValidationError) as ctx:
            attrs.save(self.entity, self.branch2, {'fleet_tag': 'ABC123'})
        self.assertIn('fleet_tag', ctx.exception.errors)

    def test_same_value_on_same_record_does_not_self_collide(self):
        attrs.save(self.entity, self.branch1, {'fleet_tag': 'XYZ999'})
        # Re-saving the SAME value on the SAME record (e.g. re-submitting
        # an unchanged form) must not be rejected as a duplicate of itself.
        attrs.save(self.entity, self.branch1, {'fleet_tag': 'XYZ999'})


class AttributesServiceSensitiveMaskingTests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(branch_code='ATTR04', branch_name='Sensitive Test', state=state, city=city)
        self.entity = EntityDefinition.objects.get(code='branch')
        FieldDefinition.objects.create(
            entity=self.entity, code='secret_code', label='Secret Code', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, is_sensitive=True,
        )
        self.viewer_role = make_role('attr_viewer_role')
        self.privileged_role = make_role('attr_privileged_role', permission_codenames=['employees.view_sensitive'])

    def test_sensitive_value_masked_for_user_without_permission(self):
        attrs.save(self.entity, self.branch, {'secret_code': 'TOPSECRET'})
        viewer = make_user('attr-viewer@test.com', role=self.viewer_role)
        result = attrs.read(self.entity, self.branch, for_user=viewer)
        self.assertEqual(result['secret_code'], '***')

    def test_sensitive_value_visible_for_user_with_permission(self):
        attrs.save(self.entity, self.branch, {'secret_code': 'TOPSECRET'})
        privileged = make_user('attr-privileged@test.com', role=self.privileged_role)
        result = attrs.read(self.entity, self.branch, for_user=privileged)
        self.assertEqual(result['secret_code'], 'TOPSECRET')

    def test_sensitive_value_never_stored_in_clear(self):
        attrs.save(self.entity, self.branch, {'secret_code': 'TOPSECRET'})
        self.branch.refresh_from_db()
        raw = self.branch.attributes['secret_code']
        self.assertNotEqual(raw, 'TOPSECRET')
        self.assertIsInstance(raw, dict)
        self.assertIn('__encrypted__', raw)


class AttributesServiceEmployeeDottedPathTests(TestCase):
    """The employee entity's attributes_column is the dotted path
    "profile__custom_field_values" — proves the special-cased traversal
    in services_attributes._get_attributes_container works, and that
    EmployeeProfile.custom_field_values itself is untouched/unmoved."""

    def setUp(self):
        cache.clear()
        role = make_role('attr_employee_role')
        self.user = make_user('attr-employee@test.com', role=role)
        self.profile = EmployeeProfile.objects.create(user=self.user)
        self.entity = EntityDefinition.objects.get(code='employee')
        FieldDefinition.objects.create(
            entity=self.entity, code='shoe_size', label='Shoe Size', data_type='integer',
            status=FieldDefinition.STATUS_PUBLISHED,
        )

    def test_save_writes_through_to_employeeprofile_custom_field_values(self):
        attrs.save(self.entity, self.user, {'shoe_size': '11'})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.custom_field_values.get('shoe_size'), 11)

    def test_read_returns_value_from_employeeprofile(self):
        self.profile.custom_field_values = {'shoe_size': 8}
        self.profile.save(update_fields=['custom_field_values'])
        result = attrs.read(self.entity, self.user, for_user=None)
        self.assertEqual(result['shoe_size'], 8)
