"""
Company Policy acknowledgement and the Company Contact Matrix.

Acknowledgement: only the employee acknowledges, only the current version,
once per version; replacing the file asks everyone again; HR sees who has /
hasn't within their own scope; branch documents stay with their branch.
Contact Matrix: every signed-in user reads company-wide + own-branch contacts;
only documents.* holders manage them, branch HR only for their own branch.
"""
from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import CompanyContact, Document, DocumentAcknowledgement
from apps.accounts.tests import _login
from apps.assets.tests import _make_branch

PDF = b'%PDF-1.4 policy'


class PolicyFixture(TestCase):
    def setUp(self):
        cache.clear()
        storage = InMemoryStorage(base_url='/media/')
        patcher = mock.patch.object(Document._meta.get_field('file'), 'storage', storage)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.surat = _make_branch('Surat Policy')
        self.hyd = _make_branch('Hyd Policy')
        staff = make_role('pol_staff', permission_codenames=['documents.view'])
        self.emp = make_user('pol.emp@test.com', role=staff, employee_id='PE1', full_name='Emp One', branch='Surat Policy')
        self.emp2 = make_user('pol.emp2@test.com', role=staff, employee_id='PE2', full_name='Emp Two', branch='Surat Policy')
        self.other = make_user('pol.hyd@test.com', role=staff, employee_id='PH1', full_name='Hyd Emp', branch='Hyd Policy')
        self.no_perm = make_user('pol.np@test.com', role=make_role('pol_noperm'), employee_id='PN1',
                                 full_name='No Perm', branch='Surat Policy')
        hr_role = make_role('pol_hr', permission_codenames=[
            'documents.view', 'documents.create', 'documents.edit', 'documents.delete'])
        self.hr = make_user('pol.hr@test.com', role=hr_role, employee_id='PHR', full_name='Branch HR', branch='Surat Policy')
        self.admin = make_user('pol.admin@test.com', role=make_role('pol_admin', permission_codenames=['settings.edit']),
                               employee_id='PAD', full_name='Admin', branch='')
        self.policy = self.make_doc('Company Policy', requires=True)

    def make_doc(self, title, requires=False, branch=None):
        return Document.objects.create(
            title=title, category='policy', file=SimpleUploadedFile('p.pdf', PDF, content_type='application/pdf'),
            file_name='p.pdf', file_type='PDF', file_size=len(PDF), branch=branch,
            uploaded_by=self.hr if hasattr(self, 'hr') else None, requires_acknowledgement=requires,
        )

    def api(self, user):
        client = APIClient()
        _login(client, user.email)
        return client

    def ack(self, user, doc, version=None):
        return self.api(user).post(reverse('document-acknowledge', kwargs={'pk': doc.pk}),
                                   {'version': doc.version if version is None else version}, format='json')


class AcknowledgementTests(PolicyFixture):
    def test_employee_acknowledges_current_version_once(self):
        resp = self.ack(self.emp, self.policy)
        self.assertEqual(resp.status_code, 201, resp.data)
        again = self.ack(self.emp, self.policy)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(DocumentAcknowledgement.objects.filter(employee=self.emp).count(), 1)

    def test_stale_version_is_refused(self):
        self.assertEqual(self.ack(self.emp, self.policy, version=99).status_code, 409)
        self.assertFalse(DocumentAcknowledgement.objects.exists())

    def test_document_not_requiring_acknowledgement_is_refused(self):
        plain = self.make_doc('Leave Form')
        self.assertEqual(self.ack(self.emp, plain).status_code, 404)

    def test_needs_documents_view(self):
        self.assertEqual(self.ack(self.no_perm, self.policy).status_code, 403)

    def test_pending_list_and_serializer_flag(self):
        client = self.api(self.emp)
        pending = client.get(reverse('document-pending-acks')).data['data']
        self.assertEqual([d['title'] for d in pending], ['Company Policy'])
        self.ack(self.emp, self.policy)
        self.assertEqual(client.get(reverse('document-pending-acks')).data['data'], [])
        detail = client.get(reverse('document-list-create')).data['data']['results'][0]
        self.assertIsNotNone(detail['my_acknowledged_at'])

    def test_replacing_file_requires_new_acknowledgement(self):
        self.ack(self.emp, self.policy)
        resp = self.api(self.hr).patch(
            reverse('document-detail', kwargs={'pk': self.policy.pk}),
            {'file': SimpleUploadedFile('p2.pdf', PDF + b'v2', content_type='application/pdf')}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.version, 2)
        pending = self.api(self.emp).get(reverse('document-pending-acks')).data['data']
        self.assertEqual([d['version'] for d in pending], [2])

    def test_editing_title_keeps_version(self):
        self.api(self.hr).patch(reverse('document-detail', kwargs={'pk': self.policy.pk}), {'title': 'Policy 2026'}, format='json')
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.version, 1)

    def test_branch_document_only_for_that_branch(self):
        hyd_doc = self.make_doc('Hyd Rules', requires=True, branch=self.hyd)
        self.assertEqual(self.ack(self.emp, hyd_doc).status_code, 404)
        self.assertEqual(self.ack(self.other, hyd_doc).status_code, 201)
        titles = [d['title'] for d in self.api(self.emp).get(reverse('document-pending-acks')).data['data']]
        self.assertNotIn('Hyd Rules', titles)

    def test_hr_report_scoped_to_own_branch_and_never_auto_acknowledges(self):
        self.ack(self.emp, self.policy)
        report = self.api(self.hr).get(reverse('document-acknowledgements', kwargs={'pk': self.policy.pk})).data['data']
        ids = {r['employee_id']: r['acknowledged_at'] for r in report['employees']}
        self.assertNotIn('PH1', ids)                         # other branch
        self.assertIsNotNone(ids['PE1'])
        self.assertIsNone(ids['PE2'])
        self.assertEqual(DocumentAcknowledgement.objects.count(), 1)   # viewing the report created nothing
        full = self.api(self.admin).get(reverse('document-acknowledgements', kwargs={'pk': self.policy.pk})).data['data']
        self.assertIn('PH1', {r['employee_id'] for r in full['employees']})

    def test_report_needs_documents_edit(self):
        resp = self.api(self.emp).get(reverse('document-acknowledgements', kwargs={'pk': self.policy.pk}))
        self.assertEqual(resp.status_code, 403)


class ContactMatrixTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        self.company = CompanyContact.objects.create(name='Company HR Desk', email='hr-desk@example.com')
        self.surat_c = CompanyContact.objects.create(name='Surat HR', phone='0000000001', branch=self.surat)
        self.hyd_c = CompanyContact.objects.create(name='Hyd HR', phone='0000000002', branch=self.hyd)

    def names(self, user):
        resp = self.api(user).get(reverse('company-contact-list'))
        self.assertEqual(resp.status_code, 200)
        return {c['name'] for c in resp.data['data']['contacts']}, resp.data['data']['can_manage']

    def test_every_employee_sees_company_wide_and_own_branch(self):
        self.assertEqual(self.names(self.emp), ({'Company HR Desk', 'Surat HR'}, False))
        self.assertEqual(self.names(self.no_perm)[0], {'Company HR Desk', 'Surat HR'})
        self.assertEqual(self.names(self.admin)[0], {'Company HR Desk', 'Surat HR', 'Hyd HR'})

    def test_employee_cannot_manage(self):
        resp = self.api(self.emp).post(reverse('company-contact-list'), {'name': 'X', 'email': 'x@example.com'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_branch_hr_manages_only_own_branch(self):
        client = self.api(self.hr)
        ok = client.post(reverse('company-contact-list'),
                         {'name': 'New Surat', 'phone': '0000000003', 'branch': self.surat.pk}, format='json')
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertEqual(client.post(reverse('company-contact-list'), {'name': 'Global', 'email': 'g@example.com'},
                                     format='json').status_code, 403)
        self.assertEqual(client.patch(reverse('company-contact-detail', kwargs={'pk': self.hyd_c.pk}),
                                      {'name': 'Changed'}, format='json').status_code, 404)

    def test_contact_needs_email_or_phone(self):
        resp = self.api(self.admin).post(reverse('company-contact-list'), {'name': 'No Way To Reach'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_delete_is_soft_and_hides_contact(self):
        resp = self.api(self.admin).delete(reverse('company-contact-detail', kwargs={'pk': self.company.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CompanyContact.objects.filter(pk=self.company.pk, is_active=False).exists())
        self.assertNotIn('Company HR Desk', self.names(self.emp)[0])
