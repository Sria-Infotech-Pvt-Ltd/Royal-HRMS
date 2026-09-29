"""
Regression tests for the Employee Directory KPI cards (EmployeeStatsView)
— QA report issues #5 and #6:

- #6: the "Active" stat used to count anyone `is_active=True,
  must_change_password=False` regardless of employment_status or notice
  period, while the table's own "Active" status filter
  (EmployeeListCreateView.get()) requires `employment_status=confirmed`
  and excludes anyone on an approved notice period. The two definitions
  must agree.
- #5: EmployeeStatsView only accepted a `branch` filter, so narrowing the
  table further by Org Unit (department) left the cards showing a stale,
  branch-only count instead of reflecting the narrower result set.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User


class EmployeeStatsConsistencyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.viewer_role = make_role('stats_test_viewer', permission_codenames=['employees.view', 'settings.edit'])
        self.viewer = make_user('stats-viewer@test.com', role=self.viewer_role)
        self.client.force_authenticate(user=self.viewer)

        confirmed_role = make_role('stats_test_confirmed_role')
        probation_role = make_role('stats_test_probation_role')

        # Confirmed, active — should count as "active" on both the table's
        # Active filter and the stats card.
        make_user(
            'confirmed@test.com', role=confirmed_role, employee_id='STC001',
            branch='Kondapur', department='', is_active=True,
            must_change_password=False, employment_status=User.EMPLOYMENT_STATUS_CONFIRMED,
        )
        # Still on probation — must NOT count as "active" (this used to be
        # miscounted as active by the stats endpoint).
        make_user(
            'probation@test.com', role=probation_role, employee_id='STC002',
            branch='Kondapur', department='', is_active=True,
            must_change_password=False, employment_status=User.EMPLOYMENT_STATUS_PROBATION,
        )

    def _stats(self, **params):
        url = reverse('employee-stats')
        return self.client.get(url, params)

    def test_active_count_excludes_probation_like_the_table_filter(self):
        stats_resp = self._stats()
        self.assertEqual(stats_resp.status_code, 200, stats_resp.data)
        self.assertEqual(stats_resp.data['data']['active'], 1)

        list_resp = self.client.get(reverse('employee-list-create'), {'status': 'active'})
        self.assertEqual(list_resp.status_code, 200, list_resp.data)
        self.assertEqual(list_resp.data['data']['count'], 1)

    def test_department_filter_narrows_stats_like_the_table(self):
        # No employee is placed in "Nonexistent Unit" — both the table and
        # the stats cards should agree on an empty result.
        list_resp = self.client.get(
            reverse('employee-list-create'), {'branch': 'Kondapur', 'department': 'Nonexistent Unit'},
        )
        self.assertEqual(list_resp.status_code, 200, list_resp.data)
        self.assertEqual(list_resp.data['data']['count'], 0)

        stats_resp = self._stats(branch='Kondapur', department='Nonexistent Unit')
        self.assertEqual(stats_resp.status_code, 200, stats_resp.data)
        self.assertEqual(stats_resp.data['data']['total'], 0)
        self.assertEqual(stats_resp.data['data']['active'], 0)
