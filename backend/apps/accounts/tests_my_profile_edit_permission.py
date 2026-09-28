"""
Regression tests for the employees.edit_own_profile permission gate on
MyProfileView.patch (self-service "Edit my details") — mirrors the same
gate added to ProfilePhotoView (see tests_profile_photo.py).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class MyProfileEditPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_role_with_permission_can_edit_own_profile(self):
        role = make_role('employee_edit_own', permission_codenames=['employees.edit_own_profile'])
        make_user('edit-allowed@test.com', role=role)
        _login(self.client, 'edit-allowed@test.com')

        resp = self.client.patch(reverse('my-profile'), {'phone': '9876543210'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_role_without_permission_is_denied(self):
        role = make_role('locked_down_employee_edit')
        make_user('edit-locked@test.com', role=role)
        _login(self.client, 'edit-locked@test.com')

        resp = self.client.patch(reverse('my-profile'), {'phone': '9876543210'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_superuser_bypasses_the_permission_check(self):
        role = make_role('no_perms_role_edit')
        make_user('edit-superuser@test.com', role=role, is_superuser=True)
        _login(self.client, 'edit-superuser@test.com')

        resp = self.client.patch(reverse('my-profile'), {'phone': '9876543210'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
