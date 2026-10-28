"""UAT-036: replacing an employee document is audited with what it replaced, and the employee API hands out a link for viewing every document."""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.audit_descriptions import describe_audit_event
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog


class DocumentReplaceAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('hr_doc_replace_test', permission_codenames=['employees.view', 'documents.create', 'settings.edit'])
        self.hr_user = make_user('hr-doc@test.com', role=role, employee_id='EMPDOC0001')
        self.employee = make_user('doc.employee@test.com', employee_id='EMPDOC0002')
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)
        self.url = reverse('employee-documents', args=[self.employee.employee_id])

    def _upload(self, name):
        upload = SimpleUploadedFile(name, b'%PDF-1.4\n' + b'0' * 4096, content_type='application/pdf')
        return self.client.post(self.url, {'document_type': 'pan_card', 'file': upload}, format='multipart')

    def test_first_upload_is_logged_as_an_upload(self):
        self.assertEqual(self._upload('first.pdf').status_code, 201)
        event = AuditLog.objects.get(module='documents')
        self.assertEqual(event.action, 'document_uploaded')
        self.assertNotIn('replaced', event.changes)

    def test_replacing_is_logged_with_the_file_it_replaced(self):
        self._upload('first.pdf')
        self.assertEqual(self._upload('second.pdf').status_code, 201)
        event = AuditLog.objects.filter(module='documents').order_by('-created_at').first()
        self.assertEqual(event.action, 'document_replaced')
        self.assertEqual(event.changes['file_name'], 'second.pdf')
        self.assertEqual([row['file_name'] for row in event.changes['replaced']], ['first.pdf'])

    def test_description_wording(self):
        self.assertEqual(
            describe_audit_event('Asha', 'document_replaced', {'document_type': 'experience_letter'}),
            'Asha replaced experience letter',
        )

    def test_employee_detail_lists_each_document_with_its_view_link(self):
        self._upload('first.pdf')
        documents = self.client.get(reverse('employee-detail', args=[self.employee.employee_id])).json()['data']['documents']
        self.assertEqual(len(documents), 1)
        self.assertIn('file', documents[0])
