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
from apps.accounts.models import User
from apps.accounts.serializers_profile_photo import ProfilePhotoUploadSerializer


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
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


def _make_noisy_image_upload(pixel_size: int = 900, filename: str = 'photo.png'):
    """
    A real photo-like image with actual pixel entropy (random noise), unlike
    _make_image_upload's flat-color swatch — needed specifically for testing
    ProfilePhotoUploadSerializer's auto-fit re-encode (_fit_to_size_band),
    which re-compresses the DECODED pixel content, not the raw uploaded byte
    count. A flat color block has almost no entropy, so no JPEG quality
    setting can push its re-encoded size up to PROFILE_PHOTO_MIN_SIZE — that
    isn't a bug in auto-fit, it's just not a realistic "too small photo"
    case; random noise at a real resolution is.
    """
    import random
    rng = random.Random(42)
    img = Image.new('RGB', (pixel_size, pixel_size))
    img.putdata([
        (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        for _ in range(pixel_size * pixel_size)
    ])
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return SimpleUploadedFile(filename, buf.getvalue(), content_type='image/png')


class ProfilePhotoUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user   = make_user(
            'photo-employee@test.com',
            role=make_role('employee_photo', permission_codenames=['employees.edit_own_profile']),
        )
        _login(self.client, 'photo-employee@test.com')

    def test_upload_within_size_range_succeeds(self):
        photo = _make_image_upload(150 * 1024)
        resp  = self.client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['data']['profile_photo_url'])

        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile_photo))

    def test_upload_below_minimum_size_is_auto_fitted_up(self):
        # commit 7865cc8 deliberately replaced size-based rejection with
        # auto-fit (re-encode/resize into the allowed band) — "pick any
        # reasonable photo, it just works" rather than bouncing the user
        # back to find a differently-sized file. This asserts the real,
        # current behavior instead of the old reject-on-size-bounds
        # contract these two tests were still written against.
        #
        # 315px of random noise lands just under PROFILE_PHOTO_MIN_SIZE at
        # the initial quality-90 encode, and just over it once auto-fit
        # bumps to quality 95 — a genuine "near miss, auto-fit rescues it"
        # case. (_make_image_upload's flat-color swatch has almost no
        # pixel entropy, so no JPEG quality setting can push its re-encoded
        # size up to the 100KB floor — not a bug in auto-fit, just not a
        # realistic "too small photo" scenario to test this behavior with.)
        #
        # Checked at the serializer level, not by re-reading
        # user.profile_photo back from storage afterward — the real upload
        # storage (core.storage.ImageKitStorage) is deliberately write-only
        # (no size()/read() — every other upload in this app only ever
        # needs a signed .url(), see ProfileSummaryTab's own docstring).
        photo = _make_noisy_image_upload(pixel_size=315)
        serializer = ProfilePhotoUploadSerializer(data={'photo': photo})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertGreaterEqual(serializer.validated_data['photo'].size, User.PROFILE_PHOTO_MIN_SIZE)

        resp = self.client.post(reverse('my-profile-photo'), {'photo': _make_noisy_image_upload(pixel_size=315)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_upload_above_maximum_size_is_auto_fitted_down(self):
        photo = _make_noisy_image_upload(pixel_size=900)
        serializer = ProfilePhotoUploadSerializer(data={'photo': photo})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertLessEqual(serializer.validated_data['photo'].size, User.PROFILE_PHOTO_MAX_SIZE)

        resp = self.client.post(reverse('my-profile-photo'), {'photo': _make_noisy_image_upload(pixel_size=900)}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)

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

    def test_any_role_holding_the_permission_can_set_their_own_photo(self):
        # system_admin is a real superuser bypass elsewhere (has_perm) but
        # here we test a plain role explicitly granted the permission —
        # the actual "any role, as long as it holds employees.edit_own_profile"
        # behavior this endpoint now enforces.
        admin_role = make_role('branch_admin_photo', permission_codenames=['employees.edit_own_profile'])
        make_user('photo-admin@test.com', role=admin_role)
        client = APIClient()
        _login(client, 'photo-admin@test.com')

        photo = _make_image_upload(150 * 1024)
        resp  = client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_superuser_bypasses_the_permission_check(self):
        role = make_role('no_perms_role_photo')
        admin = make_user('photo-superuser@test.com', role=role, is_superuser=True)
        client = APIClient()
        _login(client, 'photo-superuser@test.com')

        photo = _make_image_upload(150 * 1024)
        resp  = client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_role_without_permission_is_denied(self):
        # HR revoked employees.edit_own_profile from this role — self-service
        # photo upload/remove must now be blocked, with a clear 403 message
        # rather than silently doing nothing.
        role = make_role('locked_down_employee')
        make_user('photo-locked@test.com', role=role)
        client = APIClient()
        _login(client, 'photo-locked@test.com')

        photo = _make_image_upload(150 * 1024)
        resp  = client.post(reverse('my-profile-photo'), {'photo': photo}, format='multipart')
        self.assertEqual(resp.status_code, 403, resp.data)

        resp = client.delete(reverse('my-profile-photo'))
        self.assertEqual(resp.status_code, 403, resp.data)
