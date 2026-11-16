"""Renaming a branch must carry the new name to the employees assigned to it (User.branch is a copy of the name)."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.branch.models import Branch, City, State


class BranchRenameSyncTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user(
            'branch-rename-admin@test.com',
            role=make_role('branch_rename_admin', permission_codenames=['branches.view', 'branches.edit', 'settings.edit']),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(branch_code='HYD', branch_name='Sria', address='Plot 14', state=state, city=city)
        self.other = Branch.objects.create(branch_code='MUL', branch_name='Mulugu', address='Azad Nagar', state=state, city=city)
        self.url = reverse('branch-detail', args=[self.branch.pk])

    def _employee(self, email, branch, **extra):
        return make_user(email, employee_id=extra.pop('employee_id'), branch=branch.branch_name, branch_fk=branch, **extra)

    def test_rename_updates_the_name_on_its_employees(self):
        staff = self._employee('rename-staff@test.com', self.branch, employee_id='EMP-R1')
        resp = self.client.patch(self.url, {'branch_name': 'Sria - Hyderabad'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(User.objects.get(pk=staff.pk).branch, 'Sria - Hyderabad')

    def test_put_rename_also_updates_employees(self):
        staff = self._employee('rename-put@test.com', self.branch, employee_id='EMP-R2')
        payload = {
            'branch_name': 'Sria Kondapur', 'address': self.branch.address, 'state': self.branch.state_id,
            'city': self.branch.city_id, 'status': 'active', 'allowed_radius_meters': 150,
        }
        resp = self.client.put(self.url, payload, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(User.objects.get(pk=staff.pk).branch, 'Sria Kondapur')

    def test_other_branches_employees_are_untouched(self):
        elsewhere = self._employee('rename-other@test.com', self.other, employee_id='EMP-R3')
        self.client.patch(self.url, {'branch_name': 'Sria - Hyderabad'}, format='json')
        self.assertEqual(User.objects.get(pk=elsewhere.pk).branch, 'Mulugu')

    def test_editing_something_else_leaves_the_name_alone(self):
        staff = self._employee('rename-same@test.com', self.branch, employee_id='EMP-R4')
        resp = self.client.patch(self.url, {'is_metro': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(User.objects.get(pk=staff.pk).branch, 'Sria')

    def test_rename_onto_an_existing_name_changes_nothing(self):
        staff = self._employee('rename-clash@test.com', self.branch, employee_id='EMP-R5')
        resp = self.client.patch(self.url, {'branch_name': 'Mulugu'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(User.objects.get(pk=staff.pk).branch, 'Sria')
