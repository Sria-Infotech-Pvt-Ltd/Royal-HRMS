"""
Regression tests for the Employee Directory KPI cards (EmployeeStatsView)
— QA report issues #5 and #6:

- #6: the "Active" stat used to count anyone `is_active=True,
  must_change_password=False` regardless of notice period, while the
  table's own "Active" status filter (EmployeeListCreateView.get())
  excludes anyone on an approved notice period. The two definitions must
  agree. A hired, onboarded employee is Active even while on probation —
  probation is a separate employment label, not a different status.
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
            must_change_password=False, onboarding_status=User.ONBOARDING_COMPLETE,
            employment_status=User.EMPLOYMENT_STATUS_CONFIRMED,
        )
        # A direct hire may still need to change their temporary password;
        # that is not incomplete onboarding and must not hide their
        # probation status from the directory.
        make_user(
            'probation@test.com', role=probation_role, employee_id='STC002',
            branch='Kondapur', department='', is_active=True,
            must_change_password=True, onboarding_status=User.ONBOARDING_COMPLETE,
            employment_status=User.EMPLOYMENT_STATUS_PROBATION,
        )

    def _stats(self, **params):
        url = reverse('employee-stats')
        return self.client.get(url, params)

    def test_active_count_includes_probation_like_the_table_filter(self):
        # A hired, onboarded employee is Active even while on probation; the
        # card and the table's Active filter must agree.
        stats_resp = self._stats()
        self.assertEqual(stats_resp.status_code, 200, stats_resp.data)

        list_resp = self.client.get(reverse('employee-list-create'), {'status': 'active'})
        self.assertEqual(list_resp.status_code, 200, list_resp.data)
        codes = {row['employee_id'] for row in list_resp.data['data']['results']}
        self.assertTrue({'STC001', 'STC002'} <= codes)
        self.assertEqual(list_resp.data['data']['count'], stats_resp.data['data']['active'])

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

    def test_password_change_is_not_reported_as_onboarding(self):
        probation_resp = self.client.get(reverse('employee-list-create'), {'status': 'probation'})
        self.assertEqual(probation_resp.status_code, 200, probation_resp.data)
        self.assertEqual(probation_resp.data['data']['count'], 1)

        onboarding_resp = self.client.get(reverse('employee-list-create'), {'status': 'onboarding'})
        self.assertEqual(onboarding_resp.status_code, 200, onboarding_resp.data)
        self.assertEqual(onboarding_resp.data['data']['count'], 0)

        employee = next(
            row for row in probation_resp.data['data']['results']
            if row['employee_id'] == 'STC002'
        )
        self.assertEqual(employee['status'], 'active')
        self.assertEqual(employee['onboarding_status'], User.ONBOARDING_COMPLETE)

        stats_resp = self._stats()
        self.assertEqual(stats_resp.status_code, 200, stats_resp.data)
        self.assertEqual(stats_resp.data['data']['onboarding'], 0)
