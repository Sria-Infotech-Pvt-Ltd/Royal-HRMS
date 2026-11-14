"""Phase 4: the timesheet HTTP API (envelope, status codes, who can reach what) and the old endpoint that must keep working."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import WeeklyTimesheetSubmission
from apps.attendance.models_timesheet import Timesheet
from apps.attendance.tests_timesheet_support import (
    LAST_MONDAY, MONDAY, TimesheetTestBase, WEDNESDAY, assign, cell, internal_line, pinned_today, project_line,
)

BASE = '/api/attendance/timesheets'
HR_ACCESS = ['timesheet.approve', 'timesheet.unlock', 'timesheet.report']


class ApiBase(TimesheetTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hr_admin = make_user('ts_api_hr@test.com', make_role('ts_api_hr', permission_codenames=HR_ACCESS, can_manage_branch=True),
                                 employee_id='TSH010', branch='TS-Branch')
        cls.outsider = make_user('ts_api_out@test.com', make_role('ts_api_out', permission_codenames=HR_ACCESS, can_manage_branch=True),
                                 employee_id='TSH011', branch='Elsewhere')

    def setUp(self):
        super().setUp()
        assign(self.employee, 1, 'Alpha')

    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def call(self, user, method, path, body=None):
        with pinned_today():
            return getattr(self.client_for(user), method)(f'{BASE}{path}', body, format='json')

    def put_week(self, hours='8', user=None, week=MONDAY):
        return self.call(user or self.employee, 'put', f'/my/{week}/', {'lines': [project_line(1, cell(0, hours, week=week))]})

    def submitted_id(self) -> str:
        self.put_week()
        self.call(self.employee, 'post', f'/my/{MONDAY}/submit/')
        return str(Timesheet.objects.get().pk)


class EmployeeEndpointTests(ApiBase):
    def test_get_week_returns_the_standard_envelope_with_a_prefilled_draft(self):
        response = self.call(self.employee, 'get', f'/my/?week={WEDNESDAY}')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body['status'], body['data']['week_start'], body['data']['status']), ('success', '2026-11-09', 'draft'))
        self.assertEqual([line['project_name'] for line in body['data']['lines']], ['Alpha', 'Internal / Non-project work'])

    def test_a_bad_week_is_a_422_with_the_envelope(self):
        response = self.call(self.employee, 'get', '/my/?week=nonsense')
        self.assertEqual((response.status_code, response.json()['status']), (422, 'error'))

    def test_put_saves_and_get_reads_it_back(self):
        self.assertEqual(self.put_week('7.5').status_code, 200)
        data = self.call(self.employee, 'get', f'/my/?week={MONDAY}').json()['data']
        self.assertEqual((data['totals']['week'], data['status']), ('7.50', 'draft'))

    def test_bad_hours_are_a_400_listing_every_problem(self):
        response = self.call(self.employee, 'put', f'/my/{MONDAY}/', {'lines': [internal_line(cell(0, '0.1'), cell(1, '30'))]})
        body = response.json()
        self.assertEqual((response.status_code, body['status'], len(body['data']['errors'])), (400, 'error', 2))
        self.assertEqual(Timesheet.objects.count(), 0)

    def test_the_week_in_the_path_must_be_a_monday_date(self):
        self.assertEqual(self.call(self.employee, 'put', '/my/2026-11-10/', {'lines': []}).status_code, 400)
        self.assertEqual(self.call(self.employee, 'put', '/my/not-a-date/', {'lines': []}).status_code, 400)

    def test_submit_then_a_second_submit_conflicts_and_a_submitted_sheet_is_read_only(self):
        self.put_week()
        self.assertEqual(self.call(self.employee, 'post', f'/my/{MONDAY}/submit/').status_code, 200)
        self.assertEqual(self.call(self.employee, 'post', f'/my/{MONDAY}/submit/').status_code, 409)
        self.assertEqual(self.put_week('1').status_code, 409)
        self.assertEqual(Timesheet.objects.get().submit_count, 1)

    def test_submit_without_hours_or_without_a_saved_sheet(self):
        self.put_week('0')
        empty = self.call(self.employee, 'post', f'/my/{MONDAY}/submit/')
        self.assertEqual((empty.status_code, empty.json()['data']['errors']), (400, ['Enter some hours before submitting.']))
        self.assertEqual(self.call(self.employee, 'post', f'/my/{LAST_MONDAY}/submit/').status_code, 404)

    def test_history_lists_only_my_sheets_paginated(self):
        self.put_week()
        response = self.call(self.employee, 'get', '/my/')
        data = response.json()['data']
        self.assertEqual((data['count'], data['page'], data['page_size'], len(data['results'])), (1, 1, 20, 1))
        self.assertEqual(self.call(self.manager, 'get', '/my/').json()['data']['count'], 0)

    def test_anonymous_requests_are_refused(self):
        with pinned_today():
            self.assertIn(APIClient().get(f'{BASE}/my/?week={MONDAY}').status_code, (401, 403))
            self.assertIn(APIClient().put(f'{BASE}/my/{MONDAY}/', {'lines': []}, format='json').status_code, (401, 403))


class ApproverEndpointTests(ApiBase):
    def test_team_list_shows_the_managers_reports_with_a_pending_count(self):
        sheet_id = self.submitted_id()
        data = self.call(self.manager, 'get', '/team/?status=submitted').json()['data']
        self.assertEqual((data['count'], data['pending_count'], data['results'][0]['id']), (1, 1, sheet_id))
        row = data['results'][0]
        self.assertEqual((row['status'], row['total_hours'], row['can_decide'], row['employee']['employee_id']), ('submitted', '8.00', True, 'TSE001'))

    def test_team_list_is_empty_for_everyone_else(self):
        self.submitted_id()
        for user in (self.employee, self.outsider):
            self.assertEqual(self.call(user, 'get', '/team/').json()['data']['count'], 0, user.email)
        self.assertEqual(self.call(self.hr_admin, 'get', '/team/').json()['data']['count'], 1)

    def test_team_list_rejects_an_unknown_status(self):
        self.assertEqual(self.call(self.manager, 'get', '/team/?status=bogus').status_code, 422)

    def test_detail_is_visible_to_the_owner_and_approver_but_not_outsiders_or_for_a_draft(self):
        sheet_id = self.submitted_id()
        for user, code in ((self.employee, 200), (self.manager, 200), (self.hr_admin, 200), (self.outsider, 404)):
            self.assertEqual(self.call(user, 'get', f'/{sheet_id}/').status_code, code, user.email)
        self.assertTrue(self.call(self.manager, 'get', f'/{sheet_id}/').json()['data']['can_decide'])
        self.assertEqual(self.call(self.manager, 'get', '/00000000-0000-0000-0000-000000000000/').status_code, 404)

    def test_approve_and_the_rules_around_it(self):
        sheet_id = self.submitted_id()
        self.assertEqual(self.call(self.employee, 'post', f'/{sheet_id}/approve/').status_code, 403)
        self.assertEqual(self.call(self.outsider, 'post', f'/{sheet_id}/approve/').status_code, 404)
        approved = self.call(self.manager, 'post', f'/{sheet_id}/approve/')
        self.assertEqual((approved.status_code, approved.json()['data']['status']), (200, 'approved'))
        self.assertEqual(self.call(self.manager, 'post', f'/{sheet_id}/approve/').status_code, 409)
        self.assertEqual(self.put_week('1').status_code, 409)

    def test_return_needs_a_reason_and_then_the_employee_can_edit_again(self):
        sheet_id = self.submitted_id()
        for body in (None, {}, {'reason': ''}, {'reason': '   '}):
            self.assertEqual(self.call(self.manager, 'post', f'/{sheet_id}/return/', body).status_code, 400)
        self.assertEqual(Timesheet.objects.get().status, 'submitted')
        returned = self.call(self.manager, 'post', f'/{sheet_id}/return/', {'reason': 'Wrong project'})
        self.assertEqual((returned.status_code, returned.json()['data']['return_reason']), (200, 'Wrong project'))
        self.assertEqual(self.put_week('6').status_code, 200)
        self.assertEqual(self.call(self.employee, 'post', f'/my/{MONDAY}/submit/').status_code, 200)

    def test_unlock_is_for_hr_with_the_permission_and_needs_a_reason(self):
        sheet_id = self.submitted_id()
        self.call(self.manager, 'post', f'/{sheet_id}/approve/')
        self.assertEqual(self.call(self.manager, 'post', f'/{sheet_id}/unlock/', {'reason': 'x'}).status_code, 403)
        self.assertEqual(self.call(self.outsider, 'post', f'/{sheet_id}/unlock/', {'reason': 'x'}).status_code, 404)
        self.assertEqual(self.call(self.hr_admin, 'post', f'/{sheet_id}/unlock/', {}).status_code, 400)
        reopened = self.call(self.hr_admin, 'post', f'/{sheet_id}/unlock/', {'reason': 'Fix billable'})
        self.assertEqual((reopened.status_code, reopened.json()['data']['status']), (200, 'returned'))


class LegacyEndpointTests(ApiBase):
    def legacy(self, method):
        with mock.patch('apps.attendance.views.my_attendance.timezone', SimpleNamespace(localdate=lambda: WEDNESDAY)):
            return getattr(self.client_for(self.employee), method)('/api/attendance/my-weekly-timesheet/', {} if method == 'post' else None, format='json')

    def test_the_old_get_keeps_its_shape(self):
        data = self.legacy('get').json()['data']
        for key in ('hours_logged', 'target_hours', 'week_start', 'week_end', 'submitted', 'submitted_at'):
            self.assertIn(key, data)
        self.assertEqual((data['submitted'], data['week_start']), (False, '2026-11-09'))

    def test_the_old_post_still_writes_its_tick_row_and_is_idempotent(self):
        self.assertEqual(self.legacy('post').json()['message'], 'Timesheet submitted.')
        self.assertEqual(self.legacy('post').json()['message'], 'Timesheet already submitted for this week.')
        self.assertEqual(WeeklyTimesheetSubmission.objects.count(), 1)
        self.assertTrue(self.legacy('get').json()['data']['submitted'])

    def test_a_real_timesheet_that_is_submitted_also_shows_as_submitted_to_old_clients(self):
        self.submitted_id()
        data = self.legacy('get').json()['data']
        self.assertEqual((data['submitted'], data['timesheet_status']), (True, 'submitted'))
        self.assertEqual(WeeklyTimesheetSubmission.objects.count(), 0)               # nothing was written to the old table

    def test_a_draft_does_not_count_as_submitted(self):
        self.put_week()
        data = self.legacy('get').json()['data']
        self.assertEqual((data['submitted'], data['timesheet_status']), (False, 'draft'))
