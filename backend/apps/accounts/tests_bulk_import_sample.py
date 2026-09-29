"""
Regression tests for the Employee Bulk Import sample template — QA report
#57 (High): the sample CSV shipped hardcoded example values ("Mumbai HQ",
"Engineering" / "Software Engineer", "Human Resources" / "HR Manager")
that only happened to work on whichever database the mockup was built
against. On any other install, importing the sample as-is failed with
"Company Code not found" / "No active position found" — the sample
was never actually importable. The sample now pulls a real Branch, a
real Position (with its Org Unit), and a real Role from the current
database, so the row it ships is guaranteed to resolve.
"""
from __future__ import annotations

import csv
import io

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Position
from apps.branch.models import Branch, City, State


class BulkImportSampleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_sample_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-sample@test.com', role=self.hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)

    def test_sample_row_references_real_org_data_and_actually_imports(self):
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        branch = Branch.objects.create(
            branch_code='BR01', branch_name='Test Branch', state=state, city=city,
        )
        unit = OrgUnit.objects.create(name='Engineering')
        position = Position.objects.create(org_unit=unit, title='Software Engineer', grade='L2')

        resp = self.client.get(reverse('employee-bulk-import-sample') + '?format=csv')
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.reader(io.StringIO(resp.content.decode('utf-8'))))
        header, sample_row = rows[0], rows[1]

        sample = dict(zip(header, sample_row))
        # Whichever real branch/org-unit/position the endpoint happened to
        # pick (seed data from migrations may already have some), every
        # referenced value must correspond to a real, existing record.
        self.assertTrue(Branch.objects.filter(branch_code=sample['Company Code']).exists())
        self.assertTrue(Position.objects.filter(
            org_unit__name=sample['Org Unit'], title=sample['Position'],
        ).exists())

        # The sample row must actually round-trip through the real import
        # endpoint without any "not found" errors.
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = self.client.post(
            reverse('employee-bulk-import'),
            {'file': SimpleUploadedFile('sample.csv', resp.content, content_type='text/csv')},
            format='multipart',
        )
        self.assertEqual(upload.status_code, 200, upload.data)
        self.assertEqual(upload.data['data']['created'], 1)
        self.assertEqual(upload.data['data']['failed'], 0)

    def test_sample_gives_setup_hint_when_org_structure_is_empty(self):
        resp = self.client.get(reverse('employee-bulk-import-sample') + '?format=csv')
        self.assertEqual(resp.status_code, 200)
        rows = list(csv.reader(io.StringIO(resp.content.decode('utf-8'))))
        self.assertIn('Set up at least one Branch', rows[1][0])
