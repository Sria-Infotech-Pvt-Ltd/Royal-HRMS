"""
Tests for the HR-side employee photo upload endpoint (Edit full record >
Personal identity) — see views_employee_photo.py. Distinct from
tests_profile_photo.py's self-service endpoint tests.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests_profile_photo import _make_image_upload


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class EmployeePhotoUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_photo_test', permission_codenames=['employees.edit'])
        self.hr_user = make_user('hr-photo@test.com', role=self.hr_role, password='TestPass123!')
        self.employee_role = make_role('employee_photo_test', permission_codenames=[])
        self.employee = make_user(
            'employee-photo@test.com', role=self.employee_role, password='TestPass123!',
            full_name='Photo Test', employee_id='EMPPHOTO1',
        )
        _login(self.client, 'hr-photo@test.com')

    def test_hr_can_upload_employee_photo(self):
        upload = _make_image_upload(50_000, filename='photo.png')
        resp = self.client.post(
            reverse('employee-photo', args=[self.employee.employee_id]),
            {'photo': upload}, format='multipart',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.employee.refresh_from_db()
        self.assertTrue(bool(self.employee.profile_photo))

    def test_without_permission_is_forbidden(self):
        plain_role = make_role('employee_photo_noperm_test', permission_codenames=[])
        plain_user = make_user('plain-photo@test.com', role=plain_role, password='TestPass123!')
        client = APIClient()
        _login(client, 'plain-photo@test.com')
        upload = _make_image_upload(50_000, filename='photo.png')
        resp = client.post(
            reverse('employee-photo', args=[self.employee.employee_id]),
            {'photo': upload}, format='multipart',
        )
        self.assertEqual(resp.status_code, 403)

    def test_unknown_employee_is_not_found(self):
        upload = _make_image_upload(50_000, filename='photo.png')
        resp = self.client.post(
            reverse('employee-photo', args=['NOTREAL99']),
            {'photo': upload}, format='multipart',
        )
        self.assertEqual(resp.status_code, 404)
