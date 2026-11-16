"""A branch name may only be used once, and a branch can be deleted once nobody is actually assigned to it."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.branch.utils import branch_assigned_employee_count


class BranchDuplicateNameTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user(
            'branch-dup-admin@test.com',
            role=make_role(
                'branch_dup_admin',
                permission_codenames=['branches.view', 'branches.create', 'branches.edit', 'branches.delete', 'settings.edit'],
            ),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        self.city, _ = City.objects.get_or_create(name='Hyderabad', state=self.state)
        self.list_url = reverse('branch-list-create')

    def _payload(self, name):
        return {
            'branch_name': name, 'address': 'Plot 14, Cyber Towers', 'state': self.state.pk, 'city': self.city.pk,
            'status': 'active', 'allowed_radius_meters': 150,
        }

    def _branch(self, code, name):
        return Branch.objects.create(
            branch_code=code, branch_name=name, address='Plot 14', state=self.state, city=self.city,
        )

    def test_same_name_cannot_be_created_twice(self):
        first = self.client.post(self.list_url, self._payload('Kondapur Office'), format='json')
        self.assertEqual(first.status_code, 201, first.data)

        again = self.client.post(self.list_url, self._payload('kondapur office '), format='json')
        self.assertEqual(again.status_code, 400, again.data)
        self.assertIn('already exists', again.data['message'])
        self.assertEqual(Branch.objects.filter(branch_name__iexact='Kondapur Office').count(), 1)

    def test_rename_onto_another_branchs_name_is_rejected(self):
        self._branch('HYD', 'Kondapur Office')
        other = self._branch('HYD-01', 'Gachibowli Office')
        resp = self.client.patch(reverse('branch-detail', args=[other.pk]), {'branch_name': 'Kondapur Office'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_editing_a_branch_keeps_working_with_its_own_name(self):
        branch = self._branch('HYD', 'Kondapur Office')
        resp = self.client.patch(reverse('branch-detail', args=[branch.pk]), {'branch_name': 'Kondapur Office', 'is_metro': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_existing_duplicate_pair_can_still_be_edited(self):
        self._branch('HYD', 'Kondapur Office')
        twin = self._branch('HYD-01', 'Kondapur Office')
        resp = self.client.patch(reverse('branch-detail', args=[twin.pk]), {'branch_name': 'Kondapur Office', 'is_metro': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_duplicate_twin_deletes_when_its_employees_belong_to_the_other_copy(self):
        original = self._branch('HYD', 'Kondapur Office')
        twin = self._branch('HYD-01', 'Kondapur Office')
        head = make_user('branch-dup-head@test.com', role=make_role('branch_dup_head'))
        head.branch = 'Kondapur Office'
        head.branch_fk = original
        head.save()

        self.assertEqual(branch_assigned_employee_count(original), 1)
        self.assertEqual(branch_assigned_employee_count(twin), 0)

        resp = self.client.delete(reverse('branch-detail', args=[twin.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(Branch.objects.filter(pk=twin.pk).exists())
        self.assertTrue(Branch.objects.filter(pk=original.pk).exists())

    def test_branch_with_linked_employees_is_still_protected(self):
        branch = self._branch('HYD', 'Kondapur Office')
        employee = make_user('branch-dup-emp@test.com', role=make_role('branch_dup_emp'))
        employee.branch = 'Kondapur Office'
        employee.branch_fk = branch
        employee.save()
        resp = self.client.delete(reverse('branch-detail', args=[branch.pk]))
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertTrue(Branch.objects.filter(pk=branch.pk).exists())

    def test_deleted_branch_name_can_be_used_again(self):
        branch = self._branch('HYD', 'Kondapur Office')
        self.assertEqual(self.client.delete(reverse('branch-detail', args=[branch.pk])).status_code, 200)
        resp = self.client.post(self.list_url, self._payload('Kondapur Office'), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['branch_code'], 'HYD')
