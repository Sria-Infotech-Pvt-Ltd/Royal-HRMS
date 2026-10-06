from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core import services_list_views as list_views
from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import EntityDefinition, FieldDefinition, ListViewDefinition


class ListViewResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(
            code='vehicle_allocation', label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM,
            attributes_column='data',
        )
        self.field = FieldDefinition.objects.create(
            entity=self.entity, code='vehicle_number', label='Vehicle Number', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, is_filterable=True, is_sortable=True,
        )
        self.non_sortable_field = FieldDefinition.objects.create(
            entity=self.entity, code='notes', label='Notes', data_type='long_text',
            status=FieldDefinition.STATUS_PUBLISHED,
        )
        self.role = make_role('fleet_role')
        self.user = make_user('fleet-user@test.com', role=self.role)

    def test_system_default_resolved_when_no_personal_or_role_view_exists(self):
        system_view = ListViewDefinition.objects.create(
            entity=self.entity, code='system_default', name='All vehicles',
            visibility=ListViewDefinition.VISIBILITY_SYSTEM, is_default=True,
        )
        resolved = list_views.resolve_default_view(self.entity, self.user)
        self.assertEqual(resolved.pk, system_view.pk)

    def test_personal_default_wins_over_system_default(self):
        ListViewDefinition.objects.create(
            entity=self.entity, code='system_default', name='All vehicles',
            visibility=ListViewDefinition.VISIBILITY_SYSTEM, is_default=True,
        )
        personal_view = ListViewDefinition.objects.create(
            entity=self.entity, code='my_view', name='My vehicles',
            visibility=ListViewDefinition.VISIBILITY_PERSONAL, owner=self.user, is_default=True,
        )
        resolved = list_views.resolve_default_view(self.entity, self.user)
        self.assertEqual(resolved.pk, personal_view.pk)

    def test_validate_columns_rejects_non_sortable_sort_field(self):
        with self.assertRaises(list_views.ListViewError):
            list_views.validate_columns(
                self.entity, [{'field': 'notes'}], sort_field='notes',
            )

    def test_validate_columns_accepts_sortable_sort_field(self):
        list_views.validate_columns(self.entity, [{'field': 'vehicle_number'}], sort_field='vehicle_number')

    def test_execute_query_rejects_filter_on_non_filterable_field(self):
        with self.assertRaises(list_views.ListViewError):
            list_views.execute_custom_entity_query(self.entity, filters={'notes': 'x'}, sort=None, for_user=self.user)

    def test_execute_query_filters_by_filterable_field(self):
        custom_objects.create_record(self.entity, {'vehicle_number': 'TS09AB1234'})
        custom_objects.create_record(self.entity, {'vehicle_number': 'TS09CD5678'})
        results = list_views.execute_custom_entity_query(
            self.entity, filters={'vehicle_number': 'TS09AB1234'}, sort=None, for_user=self.user,
        )
        self.assertEqual(results.count(), 1)
