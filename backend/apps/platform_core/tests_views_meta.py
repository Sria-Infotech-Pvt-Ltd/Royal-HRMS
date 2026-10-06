"""Phase 2 Task F — generic custom-record API tests. Proves the whole
chain end to end: publish_entity() creates the right permission rows,
has_perm() actually gates the generic endpoint by them, and an
unpublished entity is unreachable even to an otherwise-permitted user."""
from __future__ import annotations

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import EntityDefinition, FieldDefinition


class CustomRecordAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(
            code='vehicle_allocation', label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM,
            attributes_column='data', title_template='{vehicle_number}',
        )
        FieldDefinition.objects.create(
            entity=self.entity, code='vehicle_number', label='Vehicle Number', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, required=True,
        )

        self.privileged_role = make_role('vehicle_admin', permission_codenames=[
            'custom_vehicle_allocation.view', 'custom_vehicle_allocation.add', 'custom_vehicle_allocation.change',
        ])
        self.unprivileged_role = make_role('vehicle_outsider')
        self.privileged_user = make_user('vehicle-admin@test.com', role=self.privileged_role)
        self.outsider = make_user('vehicle-outsider@test.com', role=self.unprivileged_role)

        self.list_url = reverse('platform-custom-record-list', kwargs={'entity_code': 'vehicle_allocation'})

    def test_unpublished_entity_returns_404_even_for_privileged_user(self):
        client = APIClient()
        client.force_authenticate(self.privileged_user)
        response = client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_requires_the_entity_specific_add_permission(self):
        custom_objects.publish_entity(self.entity)
        client = APIClient()
        client.force_authenticate(self.outsider)
        response = client.post(self.list_url, {'vehicle_number': 'TS09AB1234'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_privileged_user_can_create_and_list(self):
        custom_objects.publish_entity(self.entity)
        client = APIClient()
        client.force_authenticate(self.privileged_user)
        create_response = client.post(self.list_url, {'vehicle_number': 'TS09AB1234'}, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['data']['title'], 'TS09AB1234')

        list_response = client.get(self.list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data['data']['results']), 1)

    def test_create_validation_error_returns_400_with_field_errors(self):
        custom_objects.publish_entity(self.entity)
        client = APIClient()
        client.force_authenticate(self.privileged_user)
        response = client.post(self.list_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('vehicle_number', response.data['data'])
