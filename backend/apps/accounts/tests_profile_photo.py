"""
Tests for the self-service profile photo upload/remove endpoint.

Split out of tests.py (already at the 300-line convention) — see
views_profile_photo.py for the endpoint under test.
"""
from __future__ import annotations

import io

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _make_image_upload(size_bytes: int, image_format: str = 'PNG', filename: str = 'photo.png'):
    """
    A real, Pillow-parseable image padded with trailing zero bytes to an
    exact size — image readers stop at the format's terminator chunk
    (PNG's IEND), so trailing bytes are ignored, giving a deterministic
    file size for boundary testing without needing a specific image content.

    image_format must be the TRUE underlying format, not just a claimed
    content_type header — DRF's ImageField re-detects the real MIME type
    from the file's actual content (via Pillow) and overwrites whatever
    content_type was declared, so a mislabeled-but-really-PNG file cannot
    be used to test format rejection.
    """
    buf = io.BytesIO()
    Image.new('RGB', (10, 10), color=(120, 45, 200)).save(buf, format=image_format)
    base = buf.getvalue()
    if size_bytes > len(base):
        base = base + b'\x00' * (size_bytes - len(base))
    content_type = f'image/{image_format.lower()}'
    return SimpleUploadedFile(filename, base, content_type=content_type)


class ProfilePhotoUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user   = make_user('photo-employee@test.com', role=make_role('employee_photo'))
        _login(self.client, 'photo-employee@test.com')

    def test_upload_within_size_range_succeeds(self):
        photo = _make_image_upload(150 * 1024)
        resp  = self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['data']['profile_photo_url'])

        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile_photo))

    def test_upload_below_minimum_size_is_rejected(self):
        photo = _make_image_upload(50 * 1024)
        resp  = self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertIn('too small', resp.data['message'].lower())

    def test_upload_above_maximum_size_is_rejected(self):
        photo = _make_image_upload(250 * 1024)
        resp  = self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertIn('too large', resp.data['message'].lower())

    def test_disallowed_format_is_rejected(self):
        photo = _make_image_upload(150 * 1024, image_format='GIF', filename='photo.gif')
        resp  = self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertIn('jpg, jpeg, and png', resp.data['message'].lower())

    def test_reuploading_replaces_the_old_photo(self):
        first  = _make_image_upload(150 * 1024)
        self.client.post(reverse('my-profile-photo'), {'photo': first}, format='multipart')
        self.user.refresh_from_db()
        first_name = self.user.profile_photo.name

        second = _make_image_upload(160 * 1024)
        resp = self.client.post(reverse('my-profile-photo'), {'photo': second}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)

        self.user.refresh_from_db()
        self.assertNotEqual(self.user.profile_photo.name, first_name)

    def test_delete_removes_the_photo(self):
        photo = _make_image_upload(150 * 1024)
        self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')

        resp = self.client.delete(reverse('my-profile-photo'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['data']['profile_photo_url'])

        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile_photo))

    def test_my_profile_endpoint_reflects_uploaded_photo_url(self):
        photo = _make_image_upload(150 * 1024)
        self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')

        resp = self.client.get(reverse('my-profile'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['data']['profile_photo_url'])

    def test_any_role_including_system_admin_can_set_their_own_photo(self):
        admin_role = make_role('system_admin')
        make_user('photo-admin@test.com', role=admin_role)
        client = APIClient()
        _login(client, 'photo-admin@test.com')

        photo = _make_image_upload(150 * 1024)
        resp  = client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
