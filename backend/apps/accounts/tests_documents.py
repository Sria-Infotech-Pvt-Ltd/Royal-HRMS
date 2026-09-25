"""Regression tests for the Document Center — no prior test coverage
exercised document upload validation (title uniqueness/length, category,
file type/size/content, path-injection sanitization) or permission gating
across create/edit/delete.
"""
from __future__ import annotations

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Document


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


def _pdf_file(name: str = 'policy.pdf', content: bytes | None = None) -> SimpleUploadedFile:
    # Minimal real PDF header + trailer — enough to pass the content-sniffing check.
    body = content or (b'%PDF-1.4\n' + b'x' * 200 + b'\n%%EOF')
    return SimpleUploadedFile(name, body, content_type='application/pdf')


class DocumentUploadValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('doc_admin_test', permission_codenames=['documents.create', 'documents.edit', 'documents.delete'])
        self.admin = make_user('docadmin@test.com', role=role, password='TestPass123!')
        _login(self.client, 'docadmin@test.com')

    def _upload(self, **overrides):
        payload = {
            'title': 'Leave Policy 2026', 'category': 'policy', 'file': _pdf_file(),
        }
        payload.update(overrides)
        return self.client.post(reverse('document-list-create'), payload, format='multipart')

    def test_valid_document_uploaded(self):
        resp = self._upload()
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_blank_title_rejected(self):
        resp = self._upload(title='   ')
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_title_rejected(self):
        first = self._upload(title='Unique Policy')
        self.assertEqual(first.status_code, 201, first.data)
        second = self._upload(title='Unique Policy', file=_pdf_file('policy2.pdf'))
        self.assertEqual(second.status_code, 400)

    def test_duplicate_title_case_insensitive_rejected(self):
        first = self._upload(title='Casing Policy')
        self.assertEqual(first.status_code, 201, first.data)
        second = self._upload(title='CASING POLICY', file=_pdf_file('policy2.pdf'))
        self.assertEqual(second.status_code, 400)

    def test_invalid_category_rejected(self):
        resp = self._upload(category='not_a_real_category')
        self.assertEqual(resp.status_code, 400)

    def test_missing_file_rejected(self):
        resp = self.client.post(reverse('document-list-create'), {'title': 'No File Doc', 'category': 'policy'}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_disallowed_file_type_rejected(self):
        exe = SimpleUploadedFile('malware.exe', b'MZ' + b'x' * 100, content_type='application/x-msdownload')
        resp = self._upload(title='Bad File Doc', file=exe)
        self.assertEqual(resp.status_code, 400)

    def test_disguised_file_content_rejected(self):
        # Declares itself as a PDF but the actual bytes aren't one.
        fake = SimpleUploadedFile('fake.pdf', b'not a real pdf' * 20, content_type='application/pdf')
        resp = self._upload(title='Disguised Doc', file=fake)
        self.assertEqual(resp.status_code, 400)

    def test_oversized_file_rejected(self):
        big = SimpleUploadedFile('huge.pdf', b'%PDF-1.4\n' + b'\x00' * (26 * 1024 * 1024), content_type='application/pdf')
        resp = self._upload(title='Huge Doc', file=big)
        self.assertEqual(resp.status_code, 400)

    def test_path_traversal_in_filename_is_sanitized(self):
        traversal = SimpleUploadedFile('../../etc/passwd.pdf', b'%PDF-1.4\n' + b'x' * 200, content_type='application/pdf')
        resp = self._upload(title='Traversal Doc', file=traversal)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('..', resp.data['data']['file_name'])
        self.assertNotIn('/', resp.data['data']['file_name'])

    def test_upload_denied_without_permission(self):
        no_perm = make_user('nodocperm@test.com', role=make_role('no_doc_perm_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self._upload()
        self.assertEqual(resp.status_code, 403)


class DocumentDeletePermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('doc_admin_test2', permission_codenames=['documents.create', 'documents.delete'])
        self.admin = make_user('docadmin2@test.com', role=role, password='TestPass123!')
        _login(self.client, 'docadmin2@test.com')
        self.doc = Document.objects.create(
            title='Deletable Doc', category='other', version='', file_name='x.pdf',
            file_type='PDF', file_size=100, uploaded_by=self.admin,
        )

    def test_delete_is_soft_delete_not_a_hard_delete(self):
        resp = self.client.delete(reverse('document-detail', args=[self.doc.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_active)
        # Row still exists in the DB — this is a soft delete.
        self.assertTrue(Document.objects.filter(pk=self.doc.pk).exists())

    def test_soft_deleted_document_no_longer_appears_in_list(self):
        self.client.delete(reverse('document-detail', args=[self.doc.pk]))
        resp = self.client.get(reverse('document-list-create'))
        titles = [d['title'] for d in resp.data['data']['results']]
        self.assertNotIn('Deletable Doc', titles)

    def test_delete_denied_without_permission(self):
        no_perm = make_user('nodeleteperm@test.com', role=make_role('no_delete_perm_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.delete(reverse('document-detail', args=[self.doc.pk]))
        self.assertEqual(resp.status_code, 403)
        self.doc.refresh_from_db()
        self.assertTrue(self.doc.is_active)
