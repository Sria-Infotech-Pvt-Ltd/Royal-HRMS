"""Regression tests for Org Chart's Position/OrgUnit endpoints — no prior
test coverage exercised position creation, the "one chief per org unit"
exclusivity rule, or the default_role restriction (a seat can't default to
a role that carries settings.edit or can_manage_branch).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Position


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class PositionCreateValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('org_admin_test', permission_codenames=['org_structure.create', 'org_structure.edit', 'org_chart.view'])
        self.admin = make_user('orgadmin@test.com', role=role, password='TestPass123!')
        _login(self.client, 'orgadmin@test.com')
        self.unit = OrgUnit.objects.create(name='Engineering')

    def test_valid_position_created(self):
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'Software Engineer', 'grade': 'L2',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_blank_title_rejected(self):
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': '   ',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_title_over_150_chars_rejected(self):
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'x' * 151,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_denied_without_permission(self):
        no_perm = make_user('noorgperm@test.com', role=make_role('no_org_perm_test'), password='TestPass123!')
        self.client.force_authenticate(user=no_perm)
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'Engineer',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_default_role_carrying_settings_edit_rejected(self):
        admin_role = make_role('would_be_sysadmin_test', permission_codenames=['settings.edit'])
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'Engineer', 'default_role': admin_role.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_default_role_with_can_manage_branch_rejected(self):
        branch_admin_role = make_role('would_be_branch_admin_test', can_manage_team=False)
        branch_admin_role.can_manage_branch = True
        branch_admin_role.save(update_fields=['can_manage_branch'])
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'Engineer', 'default_role': branch_admin_role.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ordinary_default_role_accepted(self):
        hr_role = make_role('ordinary_hr_test', permission_codenames=['employees.view'])
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'HR Associate', 'default_role': hr_role.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_creating_a_new_chief_unseats_the_previous_one_in_the_same_unit(self):
        first_chief = Position.objects.create(org_unit=self.unit, title='Head of Engineering', is_chief=True)
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(self.unit.id), 'title': 'New Head of Engineering', 'is_chief': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        first_chief.refresh_from_db()
        self.assertFalse(first_chief.is_chief)

    def test_editing_a_position_to_be_chief_unseats_the_previous_one(self):
        first_chief = Position.objects.create(org_unit=self.unit, title='Head of Engineering', is_chief=True)
        second = Position.objects.create(org_unit=self.unit, title='Deputy Head', is_chief=False)
        resp = self.client.put(reverse('position-detail', args=[second.id]), {
            'org_unit': str(self.unit.id), 'title': second.title, 'is_chief': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        first_chief.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first_chief.is_chief)
        self.assertTrue(second.is_chief)

    def test_chief_in_different_units_are_unaffected(self):
        other_unit = OrgUnit.objects.create(name='Sales')
        chief_a = Position.objects.create(org_unit=self.unit, title='Head of Engineering', is_chief=True)
        chief_b = Position.objects.create(org_unit=other_unit, title='Head of Sales', is_chief=True)
        resp = self.client.post(reverse('position-list'), {
            'org_unit': str(other_unit.id), 'title': 'Sales Rep', 'is_chief': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        chief_a.refresh_from_db()
        chief_b.refresh_from_db()
        self.assertTrue(chief_a.is_chief)
        self.assertTrue(chief_b.is_chief)
