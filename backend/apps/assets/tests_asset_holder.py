"""
Asset API → `active_assignment`: the current holder shown read-only in the
Edit Asset modal. Only the one assignment in status 'assigned' counts;
returned assignments are history.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.assets.models import Asset, AssetAssignment
from apps.assets.serializers import AssetSerializer
from apps.assets.services_assignment import assign_asset
from apps.assets.tests import _login, _make_branch


class AssetCurrentHolderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.branch = _make_branch('HolderBranch')
        b = self.branch.branch_name
        admin_role = make_role('holder_admin', permission_codenames=['assets.view', 'assets.edit', 'settings.edit'])
        self.admin = make_user('holder.admin@test.com', role=admin_role, employee_id='HADM', full_name='Holder Admin', branch=b)
        emp_role = make_role('holder_emp')
        self.emp1 = make_user('holder.e1@test.com', role=emp_role, employee_id='HE1', full_name='First Holder', branch=b)
        self.emp2 = make_user('holder.e2@test.com', role=emp_role, employee_id='HE2', full_name='Second Holder', branch=b)
        self.asset = Asset.objects.create(asset_tag='HOLD-1', asset_name='Laptop', category='IT',
                                          asset_type='Laptop', branch=self.branch)
        self.api = APIClient()

    def _detail(self, client=None):
        return (client or self.api).get(reverse('asset-detail', kwargs={'pk': self.asset.pk}))

    def _assign(self, employee, expected=None):
        return assign_asset(asset=self.asset, employee=employee, assigned_date=datetime.date(2026, 3, 1),
                            condition_at_assignment='good', expected_return_date=expected, assigned_by=self.admin)

    def test_assigned_asset_shows_current_holder(self):
        self._assign(self.emp1, expected=datetime.date(2027, 2, 28))
        _login(self.api, self.admin.email)
        resp = self._detail()
        self.assertEqual(resp.status_code, 200, resp.data)
        holder = resp.data['data']['active_assignment']
        self.assertEqual(
            {k: holder[k] for k in ('status', 'employee_name', 'employee_code', 'employee_hidden')},
            {'status': 'assigned', 'employee_name': 'First Holder', 'employee_code': 'HE1', 'employee_hidden': False},
        )
        self.assertEqual((str(holder['assigned_date']), str(holder['expected_return_date'])), ('2026-03-01', '2027-02-28'))

    def test_available_asset_has_no_holder(self):
        _login(self.api, self.admin.email)
        data = self._detail().data['data']
        self.assertEqual((data['status'], data['active_assignment']), ('available', None))

    def test_returned_assignment_is_not_the_current_holder(self):
        first = self._assign(self.emp1)
        _login(self.api, self.admin.email)
        resp = self.api.post(reverse('asset-return', kwargs={'assignment_id': first.pk}), {
            'return_date': '2026-04-01', 'return_condition': 'good', 'return_reason': 'Project ended',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(self._detail().data['data']['active_assignment'])          # returned → not assigned
        self.asset.refresh_from_db()
        self._assign(self.emp2)                                                      # reassigned later
        holder = self._detail().data['data']['active_assignment']
        self.assertEqual((holder['employee_name'], holder['employee_code']), ('Second Holder', 'HE2'))
        self.assertEqual(AssetAssignment.objects.filter(asset=self.asset).count(), 2)  # history kept

    def test_list_endpoint_includes_holder(self):
        self._assign(self.emp1)
        Asset.objects.create(asset_tag='HOLD-2', asset_name='Phone', category='IT', asset_type='Phone', branch=self.branch)
        _login(self.api, self.admin.email)
        rows = {r['asset_tag']: r for r in self.api.get(reverse('asset-list-create')).data['data']['results']}
        self.assertEqual(rows['HOLD-1']['active_assignment']['employee_code'], 'HE1')
        self.assertIsNone(rows['HOLD-2']['active_assignment'])

    def test_holder_hidden_from_users_who_cannot_see_that_employee(self):
        # A manager sees branch assets but only their own direct reports' details.
        manager_role = make_role('holder_mgr', permission_codenames=['assets.view'], can_manage_team=True)
        manager = make_user('holder.mgr@test.com', role=manager_role, employee_id='HMGR',
                            branch=self.branch.branch_name)
        self._assign(self.emp1)                       # emp1 does not report to this manager
        api = APIClient()
        _login(api, manager.email)
        holder = self._detail(api).data['data']['active_assignment']
        self.assertEqual((holder['status'], holder['employee_hidden'], holder['employee_name'], holder['employee_code']),
                         ('assigned', True, None, None))
        self.emp1.reporting_manager = manager
        self.emp1.save(update_fields=['reporting_manager'])
        holder = self._detail(api).data['data']['active_assignment']
        self.assertEqual((holder['employee_hidden'], holder['employee_name']), (False, 'First Holder'))

    def test_other_branch_cannot_read_the_asset_at_all(self):
        other = _make_branch('HolderOther')
        role = make_role('holder_other', permission_codenames=['assets.view'])
        outsider = make_user('holder.out@test.com', role=role, employee_id='HOUT', branch=other.branch_name)
        self._assign(self.emp1)
        api = APIClient()
        _login(api, outsider.email)
        self.assertEqual(self._detail(api).status_code, 403)

    def test_without_request_context_employee_is_withheld(self):
        self._assign(self.emp1)
        holder = AssetSerializer(Asset.objects.get(pk=self.asset.pk)).data['active_assignment']
        self.assertEqual((holder['employee_hidden'], holder['employee_name']), (True, None))
