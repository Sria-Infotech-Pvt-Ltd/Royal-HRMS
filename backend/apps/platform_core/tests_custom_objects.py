"""Phase 2 Task E — custom object CRUD tests. Uses a brand-new CUSTOM
entity ("vehicle_allocation", the Master Prompt's own worked example)
rather than a core one, to prove the no-runtime-DDL path end-to-end."""
from __future__ import annotations

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase

from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import EntityDefinition, FieldDefinition


class CustomObjectLifecycleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(
            code='vehicle_allocation', label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM,
            attributes_column='data', title_template='{vehicle_number} — {driver_name}',
        )
        self.field_vehicle = FieldDefinition.objects.create(
            entity=self.entity, code='vehicle_number', label='Vehicle Number', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, required=True,
        )
        self.field_driver = FieldDefinition.objects.create(
            entity=self.entity, code='driver_name', label='Driver Name', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED,
        )

    def test_create_record_renders_title_from_template(self):
        record = custom_objects.create_record(self.entity, {'vehicle_number': 'TS09AB1234', 'driver_name': 'Ravi'})
        self.assertEqual(record.title, 'TS09AB1234 — Ravi')
        self.assertEqual(record.data['vehicle_number'], 'TS09AB1234')

    def test_create_record_rejects_missing_required_field(self):
        from apps.platform_core.services_attributes import AttributeValidationError
        with self.assertRaises(AttributeValidationError):
            custom_objects.create_record(self.entity, {'driver_name': 'Ravi'})
        # And the half-created record must not be left behind.
        from apps.platform_core.models import CustomRecord
        self.assertEqual(CustomRecord.objects.filter(entity=self.entity).count(), 0)

    def test_update_record_re_renders_title(self):
        record = custom_objects.create_record(self.entity, {'vehicle_number': 'TS09AB1234', 'driver_name': 'Ravi'})
        custom_objects.update_record(record, {'driver_name': 'Kiran'})
        record.refresh_from_db()
        self.assertEqual(record.title, 'TS09AB1234 — Kiran')

    def test_soft_delete_excludes_from_default_list(self):
        record = custom_objects.create_record(self.entity, {'vehicle_number': 'TS09AB1234'})
        self.assertEqual(custom_objects.list_records(self.entity).count(), 1)
        custom_objects.soft_delete_record(record)
        self.assertEqual(custom_objects.list_records(self.entity).count(), 0)
        self.assertEqual(custom_objects.list_records(self.entity, include_deleted=True).count(), 1)

    def test_publish_creates_scoped_permissions_idempotently(self):
        custom_objects.publish_entity(self.entity)
        self.entity.refresh_from_db()
        self.assertEqual(self.entity.status, EntityDefinition.STATUS_PUBLISHED)
        self.assertTrue(Permission.objects.filter(codename='view_custom_vehicle_allocation').exists())
        self.assertTrue(Permission.objects.filter(codename='add_custom_vehicle_allocation').exists())

        # Calling again must not create duplicates or raise.
        custom_objects.publish_entity(self.entity)
        self.assertEqual(Permission.objects.filter(codename='view_custom_vehicle_allocation').count(), 1)

    def test_publish_rejects_core_entity(self):
        core_entity = EntityDefinition.objects.get(code='branch')
        with self.assertRaises(custom_objects.CustomObjectError):
            custom_objects.publish_entity(core_entity)
