"""Hire wizard document upload: each rejection returns a readable message the form can show (no raw field prefix)."""
import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import HireAction, OrgUnit, Position

_MB = 1024 * 1024


class HireDocumentUploadErrorTests(TestCase):
    def setUp(self):
        role = make_role('hr_hire_doc_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-hire-doc@test.com', role=role)
        unit = OrgUnit.objects.create(name='Engineering')
        position = Position.objects.create(org_unit=unit, title='Software Engineer', grade='L2')
        self.action = HireAction.objects.create(
            reason=HireAction.REASON_NEW_POSITION, effective_from=datetime.date.today(),
            position=position, created_by=self.hr_user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)
        self.url = reverse('hire-action-document-list', kwargs={'pk': self.action.pk})

    def _upload(self, name, content, content_type):
        upload = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post(self.url, {'document_type': 'pan_card', 'file': upload}, format='multipart')

    def test_wrong_file_type_is_explained(self):
        response = self._upload('photo.gif', b'GIF89a' + b'0' * 4096, 'image/gif')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Only PDF, JPG, and PNG files are allowed.')

    def test_oversized_file_reports_its_size(self):
        response = self._upload('scan.pdf', b'%PDF-1.4\n' + b'0' * (8 * _MB), 'application/pdf')
        self.assertEqual(response.status_code, 400)
        self.assertIn('exceeds the 5 MB limit', response.json()['message'])

    def test_tiny_file_is_not_accepted_as_a_document(self):
        response = self._upload('scan.pdf', b'%PDF-1.4\n' + b'0' * 100, 'application/pdf')
        self.assertEqual(response.status_code, 400)
        self.assertIn('too small', response.json()['message'])

    def test_field_errors_come_back_for_the_form(self):
        response = self._upload('photo.gif', b'GIF89a' + b'0' * 4096, 'image/gif')
        self.assertIn('file', response.json()['data'])
