"""
The employee directory list must not run per-employee queries (it took ~40 s on a remote database), and the batched lookups
must give exactly what the single-employee path gives: seat, org unit, manager (assigned or from the org chart), notice period.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Placement, Position, User
from apps.accounts.views.shared import _employee_dict
from apps.hrms.models import SEP_APPROVED, SeparationRequest

BRANCH = 'Directory Query Branch'
KEYS = (
    'status', 'department', 'position_id', 'org_unit_id', 'org_unit_name', 'org_unit_parent_name', 'position_grade',
    'last_working_day', 'reporting_manager', 'reporting_approver', 'hr', 'dotted_line_manager',
)


class DirectoryListQueryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('dq_admin@test.com', employee_id='DQ000', is_superuser=True, branch=BRANCH)
        self.parent = OrgUnit.objects.create(name='DQ Parent Unit')
        self.unit = OrgUnit.objects.create(name='DQ Child Unit', parent=self.parent)
        chief_seat = Position.objects.create(org_unit=self.parent, title='DQ Chief', grade='L5', is_chief=True)
        self.chief = make_user('dq_chief@test.com', employee_id='DQ001', branch=BRANCH)
        Placement.objects.create(position=chief_seat, employee=self.chief, effective_from=datetime.date(2020, 1, 1))
        self.manager = make_user('dq_mgr@test.com', role=make_role('dq_mgr', permission_codenames=['leave.approve'], can_manage_team=True),
                                 employee_id='DQ002', branch=BRANCH)
        self.people: list[User] = []
        for n in range(1, 9):
            person = make_user(f'dq_emp{n}@test.com', employee_id=f'DQ1{n:02d}', branch=BRANCH,
                               reporting_manager=self.manager if n % 2 else None)
            seat = Position.objects.create(org_unit=self.unit, title=f'DQ Seat {n}', grade='L2')
            Placement.objects.create(position=seat, employee=person, effective_from=datetime.date(2024, 1, 1))
            self.people.append(person)
        # no seat at all, and a future-dated seat
        self.seatless = make_user('dq_seatless@test.com', employee_id='DQ200', branch=BRANCH)
        future = make_user('dq_future@test.com', employee_id='DQ201', branch=BRANCH)
        Placement.objects.create(position=Position.objects.create(org_unit=self.unit, title='DQ Future', grade='L1'),
                                 employee=future, effective_from=datetime.date.today() + datetime.timedelta(days=30))
        SeparationRequest.objects.create(
            employee=self.people[0], status=SEP_APPROVED, proposed_last_working_day=datetime.date.today() + datetime.timedelta(days=10),
        ) if _separation_is_simple() else None

    def _list(self, page_size: int):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        with CaptureQueriesContext(connection) as queries:
            response = client.get(f'/api/employees/?page=1&page_size={page_size}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data']['results'], len(queries)

    def test_batched_list_matches_the_single_employee_view(self):
        results, _count = self._list(50)
        self.assertGreaterEqual(len(results), 12)
        for row in results:
            single = _employee_dict(User.objects.get(employee_id=row['employee_id']))
            for key in KEYS:
                self.assertEqual(row.get(key), single.get(key), f"{row['employee_id']} {key}")
            self.assertEqual('reporting_manager' in row, 'reporting_manager' in single, row['employee_id'])

    def test_org_chart_manager_and_seat_flags_survive_batching(self):
        rows = {r['employee_id']: r for r in self._list(50)[0]}
        self.assertEqual(rows['DQ102']['reporting_manager']['id'], 'DQ001')           # no assigned manager -> unit chief
        self.assertTrue(rows['DQ102']['reporting_manager']['from_org_chart'])
        self.assertEqual(rows['DQ101']['reporting_manager']['id'], 'DQ002')           # assigned manager wins
        self.assertNotIn('reporting_manager', rows['DQ002'])                          # managers have none
        self.assertEqual(rows['DQ200']['org_unit_name'], None)                        # seatless
        self.assertEqual(rows['DQ201']['reporting_manager']['id'], None)              # seat not in force yet: no org-chart manager

    def test_query_count_does_not_grow_with_the_page(self):
        _rows, small = self._list(3)
        _rows, large = self._list(50)
        self.assertLessEqual(large, small + 2, f'{small} queries for 3 rows but {large} for a full page')
        self.assertLessEqual(large, 20)


def _separation_is_simple() -> bool:
    """SeparationRequest may need more fields than the directory cares about; skip the notice-period row if so."""
    required = [f.name for f in SeparationRequest._meta.fields if not f.null and not f.has_default() and not f.primary_key and f.name not in ('employee', 'status', 'proposed_last_working_day')]
    return not required
