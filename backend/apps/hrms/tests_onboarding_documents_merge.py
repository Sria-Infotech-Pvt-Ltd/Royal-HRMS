"""Onboarding uploads (accounts.EmployeeDocument) must appear in the employee's own My Documents list."""
from __future__ import annotations

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeDocument
from apps.hrms.models import EmployeeDocumentSubmission


class OnboardingDocumentsInMyDocumentsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('employee_onb_docs_merge_test')
        self.user = make_user('onb-merge-owner@test.com', role=role)
        self.other = make_user('onb-merge-other@test.com', role=role)
        self.url = reverse('employee-document-submission-list-create')

    def _onboarding_doc(self, user, doc_type='pan_card', name='pan.pdf', **extra):
        doc = EmployeeDocument.objects.create(
            user=user, document_type=doc_type, file_name=name, file_size=10, **extra,
        )
        doc.file.save(name, ContentFile(b'%PDF-1.4 fake'), save=True)
        return doc

    def test_onboarding_documents_listed_read_only_and_mapped(self):
        self._onboarding_doc(self.user, 'pan_card', 'pan.pdf')
        self._onboarding_doc(self.user, 'degree_certificate', 'degree.pdf',
                             verification_status='needs_correction')
        EmployeeDocumentSubmission.objects.create(employee=self.user, category='other', file_name='extra.pdf')

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['count'], 3)
        by_name = {row['file_name']: row for row in data['results']}
        # Onboarding rows are titled by document type, not by the uploaded file's name.
        self.assertEqual(by_name['pan.pdf']['title'], 'PAN Card')
        self.assertEqual(by_name['extra.pdf']['title'], 'extra.pdf')
        self.assertEqual(by_name['pan.pdf']['source'], 'onboarding')
        self.assertEqual(by_name['pan.pdf']['category'], 'identity')
        self.assertEqual(by_name['pan.pdf']['status'], 'pending')
        self.assertTrue(by_name['pan.pdf']['id'].startswith('onb-'))
        self.assertEqual(by_name['degree.pdf']['category'], 'education')
        self.assertEqual(by_name['degree.pdf']['status'], 'rejected')
        self.assertEqual(by_name['extra.pdf']['source'], 'submission')

    def test_other_employees_onboarding_documents_not_leaked(self):
        self._onboarding_doc(self.other, 'aadhaar_card', 'secret.pdf')
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.data['data']['count'], 0)

    def test_merged_list_is_paginated(self):
        for index in range(3):
            self._onboarding_doc(self.user, 'other', f'doc{index}.pdf')
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {'page_size': 2})
        data = resp.data['data']
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['total_pages'], 2)
        self.assertEqual(len(data['results']), 2)
