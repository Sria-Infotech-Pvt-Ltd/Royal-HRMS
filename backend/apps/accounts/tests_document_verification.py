"""
Regression tests for OnboardingDocumentVerifyView — HR's per-document
Verified/Needs Correction call during onboarding review.
"""
from __future__ import annotations

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeDocument


class DocumentVerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_doc_verify_test', permission_codenames=['onboarding.approve'])
        self.hr_user = make_user('hr-docverify@test.com', role=self.hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)

        self.target = make_user('doc-owner@test.com', role=make_role('employee_doc_verify_test'))
        self.doc = EmployeeDocument.objects.create(
            user=self.target, document_type='pan_card',
            file_name='pan.pdf', file_size=1024,
        )
        self.doc.file.save('pan.pdf', ContentFile(b'%PDF-1.4 fake'), save=True)

    def test_mark_verified(self):
        resp = self.client.post(reverse('onboarding-document-verify', args=[self.doc.id]), {
            'verification_status': 'verified',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.verification_status, 'verified')
        self.assertEqual(self.doc.verified_by_id, self.hr_user.id)
        self.assertIsNotNone(self.doc.verified_at)

    def test_needs_correction_requires_a_note(self):
        resp = self.client.post(reverse('onboarding-document-verify', args=[self.doc.id]), {
            'verification_status': 'needs_correction',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.verification_status, 'pending')

    def test_needs_correction_with_note_succeeds(self):
        resp = self.client.post(reverse('onboarding-document-verify', args=[self.doc.id]), {
            'verification_status': 'needs_correction', 'verification_note': 'Blurry scan, please re-upload.',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.verification_status, 'needs_correction')
        self.assertEqual(self.doc.verification_note, 'Blurry scan, please re-upload.')

    def test_invalid_status_rejected(self):
        resp = self.client.post(reverse('onboarding-document-verify', args=[self.doc.id]), {
            'verification_status': 'approved',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_denied_without_permission(self):
        no_perm = make_user('no-perm-docverify@test.com', role=make_role('no_perm_doc_verify_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.post(reverse('onboarding-document-verify', args=[self.doc.id]), {
            'verification_status': 'verified',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
