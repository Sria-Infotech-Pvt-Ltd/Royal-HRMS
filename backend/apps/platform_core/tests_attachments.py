"""Phase 2 Task H — generic attachment tests. Uses a custom entity
(vehicle_allocation's RC document field, the acceptance-criteria scenario)
rather than mocking storage — AuthenticatedImageKitStorage writes are not
mocked here; these tests only exercise validation/permission logic that
runs BEFORE the storage write, using a tiny real PNG payload."""
from __future__ import annotations

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import EntityDefinition, FieldDefinition

_TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    b'\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
)


class AttachmentUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(
            code='vehicle_allocation', label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM,
            attributes_column='data',
        )
        self.file_field = FieldDefinition.objects.create(
            entity=self.entity, code='rc_document', label='RC Document', data_type='image',
            status=FieldDefinition.STATUS_PUBLISHED,
        )
        custom_objects.publish_entity(self.entity)
        self.record = custom_objects.create_record(self.entity, {})

        self.privileged_role = make_role('vehicle_uploader', permission_codenames=['custom_vehicle_allocation.change'])
        self.outsider_role = make_role('vehicle_upload_outsider')
        self.privileged_user = make_user('uploader@test.com', role=self.privileged_role)
        self.outsider = make_user('upload-outsider@test.com', role=self.outsider_role)

        self.upload_url = reverse('platform-attachment-upload', kwargs={
            'entity_code': 'vehicle_allocation', 'record_id': str(self.record.pk), 'field_code': 'rc_document',
        })

    def test_upload_requires_change_permission(self):
        client = APIClient()
        client.force_authenticate(self.outsider)
        upload = SimpleUploadedFile('rc.png', _TINY_PNG, content_type='image/png')
        response = client.post(self.upload_url, {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_rejects_spoofed_extension(self):
        client = APIClient()
        client.force_authenticate(self.privileged_user)
        fake_png = SimpleUploadedFile('not_really.png', b'#!/bin/sh\necho hi\n', content_type='image/png')
        response = client.post(self.upload_url, {'file': fake_png}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_oversized_file(self):
        client = APIClient()
        client.force_authenticate(self.privileged_user)
        oversized = SimpleUploadedFile('big.png', _TINY_PNG + b'\x00' * (5 * 1024 * 1024 + 1), content_type='image/png')
        response = client.post(self.upload_url, {'file': oversized}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_disallowed_field(self):
        client = APIClient()
        client.force_authenticate(self.privileged_user)
        upload = SimpleUploadedFile('rc.png', _TINY_PNG, content_type='image/png')
        bad_url = reverse('platform-attachment-upload', kwargs={
            'entity_code': 'vehicle_allocation', 'record_id': str(self.record.pk), 'field_code': 'does_not_exist',
        })
        response = client.post(bad_url, {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
