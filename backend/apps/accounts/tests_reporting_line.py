"""UAT-012: one answer to "who is this employee's manager", Auto-assign that works for Position-based hires, and a bulk assign for HR."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, OrgUnit, Placement, Position
from apps.accounts.services_reporting_line import (
    SOURCE_ASSIGNED, SOURCE_NONE, SOURCE_ORG_CHART, resolve_manager, resolve_manager_with_source,
)
from apps.accounts.views.shared import _auto_assign_managers
from apps.hrms.views.separation import _resolve_separation_chain

TODAY = datetime.date.today()
LONG_AGO = TODAY - datetime.timedelta(days=30)


def _seat(unit, title, holder, *, is_chief=False, can_manage_team=False):
    position = Position.objects.create(org_unit=unit, title=title, is_chief=is_chief, can_manage_team=can_manage_team)
    Placement.objects.create(position=position, employee=holder, effective_from=LONG_AGO)
    return position


class ManagerResolutionTests(TestCase):
    def setUp(self):
        self.unit = OrgUnit.objects.create(name='Zeta Operations')
        self.chief = make_user('chief@test.com', employee_id='EMPRL001', branch='Kondapur', department='')
        _seat(self.unit, 'Head of Operations', self.chief, is_chief=True, can_manage_team=True)
        self.employee = make_user('worker@test.com', employee_id='EMPRL002', branch='Kondapur', department='')
        _seat(self.unit, 'Executive', self.employee)

    def test_org_chart_chief_when_nobody_is_stored(self):
        resolution = resolve_manager_with_source(self.employee)
        self.assertEqual((resolution.user, resolution.source), (self.chief, SOURCE_ORG_CHART))

    def test_a_stored_manager_wins(self):
        other = make_user('other@test.com', employee_id='EMPRL003')
        self.employee.reporting_manager = other
        self.employee.save()
        resolution = resolve_manager_with_source(self.employee)
        self.assertEqual((resolution.user, resolution.source), (other, SOURCE_ASSIGNED))

    def test_an_inactive_stored_manager_falls_through_to_the_chief(self):
        gone = make_user('gone@test.com', employee_id='EMPRL004', is_active=False)
        self.employee.reporting_manager = gone
        self.employee.save()
        self.assertEqual(resolve_manager(self.employee), self.chief)

    def test_nobody_means_none_and_never_oneself(self):
        loner = make_user('loner@test.com', employee_id='EMPRL005')  # no seat at all
        self.assertEqual(resolve_manager_with_source(loner).source, SOURCE_NONE)
        self.assertIsNone(resolve_manager(self.chief))  # the chief of their own unit is not their own manager

    def test_auto_assign_works_when_the_legacy_department_text_is_blank(self):
        # The root cause of "Auto-assign leaves nobody": it required `department`, blank for everyone hired onto a Position.
        changed = _auto_assign_managers(self.employee)
        self.assertIn('reporting_manager', changed)
        self.assertEqual(self.employee.reporting_manager, self.chief)
        self.assertTrue(self.employee.reporting_manager_from_org_chart)

    def test_separation_manager_stage_uses_the_same_answer(self):
        stages = dict(_resolve_separation_chain(self.employee))
        self.assertEqual(stages['manager'], self.chief)  # same person the directory and profile show


class ScreensAgreeTests(TestCase):
    def setUp(self):
        cache.clear()
        unit = OrgUnit.objects.create(name='Zeta Support')
        self.chief = make_user('chief2@test.com', employee_id='EMPSA001', branch='Kondapur')
        _seat(unit, 'Head', self.chief, is_chief=True, can_manage_team=True)
        self.covered = make_user('covered@test.com', employee_id='EMPSA002', branch='Kondapur')
        _seat(unit, 'Agent', self.covered)
        self.orphan = make_user('orphan@test.com', employee_id='EMPSA003', branch='Kondapur')  # no seat, no manager
        role = make_role('hr_screens_test', permission_codenames=['employees.view', 'settings.edit'])
        self.client = APIClient()
        self.client.force_authenticate(user=make_user('hr-screens@test.com', role=role, employee_id='EMPSA000'))

    def _manager(self, employee):
        return self.client.get(reverse('employee-detail', args=[employee.employee_id])).json()['data']['reporting_manager']

    def test_api_shows_the_resolved_manager_or_nobody(self):
        covered = self._manager(self.covered)
        self.assertEqual((covered['name'], covered['from_org_chart']), (self.chief.full_name, True))
        self.assertIsNone(self._manager(self.orphan)['name'])  # the frontend shows "Not assigned"


class BulkAssignManagerTests(TestCase):
    def setUp(self):
        cache.clear()
        unit = OrgUnit.objects.create(name='Zeta Sales')
        self.manager = make_user('mgr@test.com', employee_id='EMPBM001', branch='Kondapur')
        _seat(unit, 'Sales Head', self.manager, can_manage_team=True)
        self.a = make_user('a@test.com', employee_id='EMPBM002', branch='Kondapur')
        self.b = make_user('b@test.com', employee_id='EMPBM003', branch='Kondapur')
        other_branch = make_user('c@test.com', employee_id='EMPBM004', branch='Mulugu')
        self.c = other_branch
        self.hr = make_user(
            'hr-bulk@test.com', role=make_role('hr_bulk_test', permission_codenames=['employees.edit', 'employees.view']),
            employee_id='EMPBM000', branch='Kondapur',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr)
        self.url = reverse('employee-bulk-assign-manager')

    def test_assigns_audits_each_change_and_skips_with_reasons(self):
        response = self.client.post(self.url, {
            'manager_id': 'EMPBM001', 'employee_ids': ['EMPBM002', 'EMPBM003', 'EMPBM001', 'EMPBM004', 'NOPE'],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()['data']
        self.assertEqual(sorted(data['assigned']), ['EMPBM002', 'EMPBM003'])
        reasons = {item['employee_id']: item['reason'] for item in data['skipped']}
        self.assertEqual(reasons['EMPBM001'], 'An employee cannot be their own manager.')
        self.assertEqual(reasons['EMPBM004'], 'Employee not found.')  # other branch: out of this HR's scope
        self.assertEqual(reasons['NOPE'], 'Employee not found.')
        self.a.refresh_from_db()
        self.assertEqual(self.a.reporting_manager, self.manager)
        entries = AuditLog.objects.filter(action='employee_updated', changes__via='bulk_assign_manager')
        self.assertEqual(entries.count(), 2)
        self.assertEqual(entries.first().user_id, self.hr.id)
        self.assertEqual(entries.first().changes['reporting_manager']['to'], 'EMPBM001')

    def test_running_it_again_reports_already_assigned(self):
        body = {'manager_id': 'EMPBM001', 'employee_ids': ['EMPBM002']}
        self.client.post(self.url, body, format='json')
        again = self.client.post(self.url, body, format='json').json()['data']
        self.assertEqual(again['assigned'], [])
        self.assertEqual(again['skipped'][0]['reason'], 'Already reports to this manager.')

    def test_the_chosen_manager_must_be_a_team_manager(self):
        response = self.client.post(self.url, {'manager_id': 'EMPBM002', 'employee_ids': ['EMPBM003']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('manager_id', response.json()['data'])

    def test_needs_employees_and_permission(self):
        self.assertEqual(self.client.post(self.url, {'manager_id': 'EMPBM001', 'employee_ids': []}, format='json').status_code, 400)
        plain = make_user('plain-bulk@test.com', employee_id='EMPBM010')
        self.client.force_authenticate(user=plain)
        self.assertEqual(self.client.post(self.url, {'manager_id': 'EMPBM001', 'employee_ids': ['EMPBM002']}, format='json').status_code, 403)

    def test_manager_list_filters_by_org_unit_name_and_supports_all(self):
        listing = self.client.get(reverse('employee-manager-list'), {'department': 'Zeta Sales'}).json()['data']
        self.assertEqual([row['employee_id'] for row in listing], ['EMPBM001'])
        self.assertEqual(listing[0]['department'], 'Zeta Sales')
        everyone = self.client.get(reverse('employee-manager-list'), {'all': 'true'})
        self.assertEqual(everyone.status_code, 200)
        self.assertEqual(self.client.get(reverse('employee-manager-list')).status_code, 400)  # still needs a scope unless all=true
