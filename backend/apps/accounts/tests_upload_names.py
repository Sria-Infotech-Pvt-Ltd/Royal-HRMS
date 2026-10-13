"""
Company logo and profile photo uploads: stored names must fit the
ImageField's varchar(100) whatever the original filename, and a replaced
logo file must only be deleted after the database update succeeds.

FakeCloudinaryStorage mimics how cloudinary_storage names files — the
stored name is the returned public_id: 'media/' prefix (MEDIA_URL) + path +
'_xxxxxx' suffix — so no test talks to Cloudinary.
"""
from __future__ import annotations

import io
import os
import uuid
from unittest import mock

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DataError, connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Company, User
from config.test_runner import TEST_COMPANY_CODE
from core.storage import company_logo_upload_path, profile_photo_upload_path

LONG_NAME = 'Company Logo Final Approved Version ' + 'x' * 160 + '.PNG'
COMPANY = dict(
    company_name='Demo Corp', trade_name='', gstin='22AAAAA0000A1Z5', cin='U74999MH2020PTC123456',
    pan='AAAAA0000A', tan='PNEA12345B', address='1 Main St', city='Testville', state='Teststate',
    pin_code='500001', website='', official_phone='',
)


class FakeCloudinaryStorage(InMemoryStorage):
    def get_available_name(self, name, max_length=None):
        return name[:max_length] if max_length else name   # same as cloudinary_storage

    def _save(self, name, content):
        base, ext = os.path.splitext(name)
        return super()._save(f'media/{base}_{uuid.uuid4().hex[:6]}{ext}', content)


def _png(name: str, size_bytes: int = 0) -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), color=(30, 60, 90)).save(buf, format='PNG')
    data = buf.getvalue()
    return SimpleUploadedFile(name, data + b'\x00' * max(0, size_bytes - len(data)), content_type='image/png')


def _login(client: APIClient, email: str):
    resp = client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': email,
                                          'password': 'TestPass123!'}, format='json')
    assert resp.status_code == 200, resp.data


class UploadPathTests(SimpleTestCase):
    LONGEST_SCHEMA = 'tenant_' + 'x' * 50     # company_code max_length is 50

    def test_paths_fit_the_column_for_the_longest_schema(self):
        with mock.patch('core.storage._tenant_schema', return_value=self.LONGEST_SCHEMA):
            for fn, folder in ((company_logo_upload_path, 'company'), (profile_photo_upload_path, 'profile_photos')):
                for ext in ('.jpeg', '.webp', '.png', ''):
                    with self.subTest(folder=folder, ext=ext):
                        path = fn(None, LONG_NAME[:-4] + ext)
                        self.assertTrue(path.startswith(f'{self.LONGEST_SCHEMA}/{folder}/'))
                        self.assertTrue(path.endswith(ext.lower()))
                        # + 'media/' prefix + '_xxxxxx' Cloudinary suffix
                        self.assertLessEqual(len('media/') + len(path) + 7, 100)
                        self.assertGreaterEqual(len(os.path.basename(path)) - len(ext), 8)

    def test_extension_kept_lowercased_original_name_dropped(self):
        with mock.patch('core.storage._tenant_schema', return_value='tenant_ris'):
            path = company_logo_upload_path(None, 'My Logo.JPG')
            self.assertRegex(path, r'^tenant_ris/company/[0-9a-f]{16}\.jpg$')
            self.assertRegex(profile_photo_upload_path(None, 'no-extension'), r'^tenant_ris/profile_photos/[0-9a-f]{16}$')
            self.assertNotIn('evil', company_logo_upload_path(None, 'evil.php5abc'))

    def test_names_do_not_collide(self):
        self.assertEqual(len({company_logo_upload_path(None, 'logo.png') for _ in range(200)}), 200)


class CompanyLogoUpdateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.storage = FakeCloudinaryStorage(base_url='/m/')
        patcher = mock.patch.object(Company._meta.get_field('logo'), 'storage', self.storage)
        patcher.start()
        self.addCleanup(patcher.stop)
        make_user('logo.editor@test.com', role=make_role('logo_editor', permission_codenames=['settings.view', 'settings.edit']))
        self.client = APIClient()
        _login(self.client, 'logo.editor@test.com')
        company = Company.objects.create(**{**COMPANY, 'company_name': 'Old Name'})
        company.logo.save('old.png', ContentFile(b'old-logo'))
        self.old_name = company.logo.name

    def _put(self, extra=None):
        return self.client.put(reverse('company'), {**COMPANY, **(extra or {})}, format='multipart')

    def test_long_original_filename_saves_within_limit(self):
        resp = self._put({'logo': _png(LONG_NAME)})
        self.assertEqual(resp.status_code, 200, resp.data)
        name = Company.objects.get().logo.name
        self.assertLessEqual(len(name), 100)
        self.assertTrue(name.startswith(f'media/{connection.schema_name}/company/'))
        self.assertTrue(name.endswith('.png'))
        self.assertTrue(self.storage.exists(name))
        self.assertFalse(self.storage.exists(self.old_name))   # replaced file cleaned up

    def test_text_only_update_keeps_logo(self):
        resp = self._put()
        self.assertEqual(resp.status_code, 200, resp.data)
        company = Company.objects.get()
        self.assertEqual((company.company_name, company.logo.name), ('Demo Corp', self.old_name))
        self.assertTrue(self.storage.exists(self.old_name))

    def test_remove_logo(self):
        resp = self._put({'remove_logo': 'true'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(Company.objects.get().logo)
        self.assertFalse(self.storage.exists(self.old_name))

    def test_failed_save_keeps_old_logo(self):
        with mock.patch.object(Company, 'save', side_effect=DataError('value too long')):
            resp = self._put({'logo': _png('new.png')})
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(Company.objects.get().logo.name, self.old_name)
        self.assertTrue(self.storage.exists(self.old_name))

    def test_cleanup_failure_does_not_fail_update(self):
        with mock.patch.object(self.storage, 'delete', side_effect=RuntimeError('cloudinary down')):
            resp = self._put({'logo': _png('new.png')})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotEqual(Company.objects.get().logo.name, self.old_name)


class ProfilePhotoLongNameTests(TestCase):
    def setUp(self):
        cache.clear()
        self.storage = FakeCloudinaryStorage(base_url='/m/')
        patcher = mock.patch.object(User._meta.get_field('profile_photo'), 'storage', self.storage)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = make_user('long.photo@test.com', role=make_role('long_photo_role'))
        self.client = APIClient()
        _login(self.client, 'long.photo@test.com')

    def test_long_filename_saves_within_limit(self):
        resp = self.client.post(reverse('my-profile-photo'), {'photo': _png(LONG_NAME, 120 * 1024)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        name = self.user.profile_photo.name
        self.assertLessEqual(len(name), 100)
        self.assertTrue(name.startswith(f'media/{connection.schema_name}/profile_photos/'))
        self.assertTrue(name.endswith('.png'))
