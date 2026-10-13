"""
Tests for Settings → ID Card and the per-employee ID card data endpoint.

Every FileField/ImageField involved is pointed at an in-memory storage for
the duration of each test, so nothing reaches Cloudinary.
"""
from __future__ import annotations

import datetime
import io
from unittest import mock

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, Company, EmployeeProfile, IdCardSettings, User
from apps.branch.models import Branch, City, State
from config.test_runner import TEST_COMPANY_CODE

PDF_BYTES = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _png(name: str = 'sign.png') -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new('RGB', (20, 10), color=(40, 40, 160)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class _InMemoryFilesMixin:
    def _use_memory_storage(self):
        storage = InMemoryStorage(base_url='/media/')
        for model, field in ((Company, 'logo'), (User, 'profile_photo'),
                             (IdCardSettings, 'reference_pdf'), (IdCardSettings, 'signature_image')):
            patcher = mock.patch.object(model._meta.get_field(field), 'storage', storage)
            patcher.start()
            self.addCleanup(patcher.stop)


class IdCardSettingsApiTests(_InMemoryFilesMixin, TestCase):
    def setUp(self):
        cache.clear()
        self._use_memory_storage()
        self.client = APIClient()
        make_user('idc.editor@test.com', role=make_role('idc_editor', permission_codenames=['settings.view', 'settings.edit']))
        make_user('idc.viewer@test.com', role=make_role('idc_viewer', permission_codenames=['settings.view']))
        make_user('idc.plain@test.com', role=make_role('idc_plain'))
        self.url = reverse('id-card-settings')

    def test_requires_settings_permissions(self):
        _login(self.client, 'idc.plain@test.com')
        self.assertEqual(self.client.get(self.url).status_code, 403)

        _login(self.client, 'idc.viewer@test.com')
        self.assertEqual(self.client.get(self.url).status_code, 200)
        resp = self.client.put(self.url, {'signatory_label': 'HR Head'}, format='multipart')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(IdCardSettings.get().signatory_label, IdCardSettings.DEFAULT_SIGNATORY_LABEL)

    def test_save_persists_and_is_audited(self):
        _login(self.client, 'idc.editor@test.com')
        resp = self.client.put(self.url, {
            'signatory_label': 'HR Manager', 'terms': 'Line one\n\nLine two',
            'show_contact_details': 'false',
        }, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = IdCardSettings.get()
        self.assertEqual((cfg.signatory_label, cfg.terms, cfg.show_contact_details),
                         ('HR Manager', 'Line one\nLine two', False))
        self.assertTrue(AuditLog.objects.filter(action='id_card_settings_updated').exists())
        # Persisted: a fresh GET returns the saved values
        data = self.client.get(self.url).data['data']
        self.assertEqual(data['signatory_label'], 'HR Manager')
        self.assertFalse(data['show_contact_details'])

    def test_reference_pdf_upload_validate_and_remove(self):
        _login(self.client, 'idc.editor@test.com')
        bad = SimpleUploadedFile('card.pdf', b'not a pdf', content_type='application/pdf')
        resp = self.client.put(self.url, {'reference_pdf': bad}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not a valid PDF', resp.data['message'])

        wrong_ext = SimpleUploadedFile('card.png', PDF_BYTES, content_type='image/png')
        self.assertEqual(self.client.put(self.url, {'reference_pdf': wrong_ext}, format='multipart').status_code, 400)

        good = SimpleUploadedFile('Approved ID Card.pdf', PDF_BYTES, content_type='application/pdf')
        resp = self.client.put(self.url, {'reference_pdf': good}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['reference_pdf_name'], 'Approved ID Card.pdf')
        self.assertEqual(resp.data['data']['reference_pdf_size'], len(PDF_BYTES))
        self.assertTrue(resp.data['data']['reference_pdf_url'])

        resp = self.client.put(self.url, {'remove_reference_pdf': 'true'}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = IdCardSettings.get()
        self.assertFalse(cfg.reference_pdf)
        self.assertEqual(cfg.reference_pdf_name, '')

    def test_signature_image_must_be_an_image(self):
        _login(self.client, 'idc.editor@test.com')
        fake = SimpleUploadedFile('sign.png', b'plain text', content_type='image/png')
        self.assertEqual(self.client.put(self.url, {'signature_image': fake}, format='multipart').status_code, 400)
        resp = self.client.put(self.url, {'signature_image': _png()}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['signature_url'])

    def test_terms_limited_to_what_fits(self):
        _login(self.client, 'idc.editor@test.com')
        resp = self.client.put(self.url, {'terms': '\n'.join(f'Rule {i}' for i in range(7))}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_no_separate_logo_storage(self):
        field_names = {f.name for f in IdCardSettings._meta.get_fields()}
        self.assertFalse({'logo', 'company_logo'} & field_names)


class EmployeeIdCardApiTests(_InMemoryFilesMixin, TestCase):
    BRANCH = 'Hyd Office'

    def setUp(self):
        cache.clear()
        self._use_memory_storage()
        self.client = APIClient()
        state, _ = State.objects.get_or_create(name='IdcState', defaults={'code': '9911'})
        city, _ = City.objects.get_or_create(name='Idc City', state=state)
        Branch.objects.create(branch_code='IDCBR', branch_name=self.BRANCH, status=Branch.STATUS_ACTIVE,
                              state=state, city=city, address='Floor 2, Test Tower, Test Road')
        company = Company.objects.create(
            company_name='Acme Staffing Pvt Ltd', trade_name='Acme Staffing',
            gstin='x', cin='x', pan='x', tan='x',
            address='1 Main Street', city='Testville', state='Teststate', pin_code='500001',
            website='https://www.acme.example/',
        )
        company.logo.save('logo.png', ContentFile(b'logo-bytes'))

        viewer_role = make_role('idc_hr', permission_codenames=['employees.view'])
        make_user('idc.hr@test.com', role=viewer_role, branch=self.BRANCH)
        make_user('idc.otherhr@test.com', role=viewer_role, branch='Elsewhere')
        make_user('idc.noperm@test.com', role=make_role('idc_noperm'), branch=self.BRANCH)

        emp_role = make_role('idc_employee')
        self.full = make_user(
            'full.idc@test.com', role=emp_role, full_name='Full Person', employee_id='IDC0001',
            designation='Engineer', department='IT', branch=self.BRANCH, phone='+91 90000 00000',
            date_of_joining=datetime.date(2026, 8, 3),
        )
        self.full.profile_photo.save('p.png', ContentFile(b'photo'))
        EmployeeProfile.objects.create(
            user=self.full, date_of_birth=datetime.date(2002, 1, 29), blood_group='O+',
            current_address='Flat 1, Test Colony',
        )
        self.sparse = make_user('sparse.idc@test.com', role=emp_role, full_name='Sparse Person',
                                employee_id='IDC0002', branch=self.BRANCH)

    def _get(self, employee):
        return self.client.get(reverse('employee-id-card', kwargs={'employee_id': employee.employee_id}))

    def test_permission_and_branch_scope(self):
        _login(self.client, 'idc.noperm@test.com')
        self.assertEqual(self._get(self.full).status_code, 403)
        _login(self.client, 'idc.otherhr@test.com')
        self.assertEqual(self._get(self.full).status_code, 404)

    def test_card_uses_real_fields_and_company_logo(self):
        _login(self.client, 'idc.hr@test.com')
        resp = self._get(self.full)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        emp, company = data['employee'], data['company']
        self.assertEqual(emp['full_name'], 'Full Person')
        self.assertEqual(emp['employee_id'], 'IDC0001')
        self.assertEqual(emp['date_of_birth'], '29/01/2002')
        self.assertEqual(emp['date_of_joining'], '03/08/2026')
        self.assertEqual(emp['blood_group'], 'O+')
        self.assertEqual(emp['location'], 'Idc City')
        self.assertEqual(emp['residential_address'], 'Flat 1, Test Colony')
        self.assertTrue(emp['photo_url'])
        # Logo and website come straight from Company Settings
        self.assertIn(Company.objects.get().logo.name.split('/')[-1], company['logo_url'])
        self.assertEqual(company['website'], 'www.acme.example')
        self.assertEqual(company['office_address'], 'Floor 2, Test Tower, Test Road')
        self.assertEqual(data['card']['terms'][0], 'This ID card is the property of Acme Staffing.')
        self.assertEqual(data['missing'], ['Authorised signature'])

    def test_missing_fields_are_blank_not_invented(self):
        _login(self.client, 'idc.hr@test.com')
        data = self._get(self.sparse).data['data']
        emp = data['employee']
        for key in ('designation', 'department', 'date_of_birth', 'date_of_joining', 'blood_group',
                    'photo_url', 'residential_address', 'phone'):
            self.assertIsNone(emp[key], key)
        for label in ('Employee photo', 'Designation', 'Date of birth', 'Blood group', 'Residential address'):
            self.assertIn(label, data['missing'])
        self.assertEqual(emp['location'], 'Idc City')

    def test_privacy_toggles_hide_fields(self):
        cfg = IdCardSettings.get()
        cfg.show_contact_details = cfg.show_date_of_birth = cfg.show_residential_address = False
        cfg.save()
        _login(self.client, 'idc.hr@test.com')
        data = self._get(self.full).data['data']
        for key in ('phone', 'email', 'date_of_birth', 'residential_address'):
            self.assertIsNone(data['employee'][key], key)
        self.assertNotIn('Phone', data['missing'])
        self.assertNotIn('Date of birth', data['missing'])

    def test_office_address_falls_back_to_company(self):
        self.sparse.branch = ''
        self.sparse.save(update_fields=['branch'])
        make_user('idc.admin@test.com', role=make_role('idc_admin', permission_codenames=['employees.view', 'settings.edit']))
        _login(self.client, 'idc.admin@test.com')
        data = self._get(self.sparse).data['data']
        self.assertEqual(data['company']['office_address'], '1 Main Street, Testville, Teststate 500001')
        self.assertIsNone(data['employee']['location'])
        self.assertIn('Location', data['missing'])
