"""The four timesheet reports: what they total, who may run them, and that they never reach past the person's scope."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models_timesheet import Timesheet, TimesheetEntry, TimesheetLine
from apps.attendance.tests_timesheet_support import MONDAY, TimesheetTestBase

NEXT_MONDAY = MONDAY + datetime.timedelta(days=7)
LAST_MONDAY = MONDAY - datetime.timedelta(days=7)
REPORT = ['timesheet.report']


def _as(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def make_sheet(employee, week, status='approved', lines=(), attendance_minutes=0, is_late=False, approver=None) -> Timesheet:
    """lines: (assignment_id | None, name, code, is_billable, {day offset: hours}); None means the Internal row."""
    total = sum(Decimal(str(hours)) for *_, cells in lines for hours in cells.values())
    billable = sum(Decimal(str(hours)) for _, _, _, is_billable, cells in lines if is_billable for hours in cells.values())
    sheet = Timesheet.objects.create(
        employee=employee, week_start=week, status=status, total_hours=total, billable_hours=billable, attendance_minutes=attendance_minutes,
        is_late=is_late, branch_name=employee.branch or '', approver=approver,
    )
    for order, (assignment_id, name, code, is_billable, cells) in enumerate(lines):
        line = TimesheetLine.objects.create(
            timesheet=sheet, assignment_id=assignment_id, project_id=assignment_id and assignment_id * 10, project_code=code,
            project_name=name, is_internal=assignment_id is None, is_billable=is_billable, sort_order=order,
        )
        for offset, hours in cells.items():
            TimesheetEntry.objects.create(line=line, entry_date=week + datetime.timedelta(days=offset), hours=Decimal(str(hours)))
    return sheet


class ReportBase(TimesheetTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hr = make_user('tr_hr@test.com', make_role('tr_hr', permission_codenames=REPORT, can_manage_branch=True), employee_id='TRH001', branch='TS-Branch', full_name='Hema HR')
        cls.lead = make_user('tr_lead@test.com', make_role('tr_lead', permission_codenames=REPORT, can_manage_team=True), employee_id='TRL001', branch='TS-Branch', full_name='Lead Person')
        cls.far = make_user('tr_far@test.com', employee_id='TRF001', branch='Elsewhere', full_name='Far Person')
        cls.admin = make_user('tr_admin@test.com', employee_id='TRA001', is_superuser=True)
        cls.employee.full_name = 'Asha Rao'
        cls.employee.save()

    def setUp(self):
        super().setUp()
        make_sheet(self.employee, MONDAY, 'approved', [(1, 'Alpha', 'P1', True, {0: 8, 1: 8}), (None, '', '', False, {0: 1})], attendance_minutes=1080, approver=self.manager)
        make_sheet(self.far, MONDAY, 'approved', [(1, 'Alpha', 'P1', True, {0: 8, 1: 8, 2: 8, 3: 8, 4: 8}), (2, 'Secret', 'S9', False, {0: 5})])

    def rows(self, user, key, **query):
        response = _as(user).get(reverse('report-preview', args=[key]), query)
        self.assertEqual(response.status_code, 200, key)
        return response.data['data']['headers'], response.data['data']['rows']

    def table(self, user, key, **query) -> list[dict]:
        headers, rows = self.rows(user, key, **query)
        return [dict(zip(headers, row)) for row in rows]


class EmployeeWiseTests(ReportBase):
    def test_one_row_per_sheet_with_the_hours_split_and_approval_details(self):
        row = self.table(self.hr, 'timesheets')[0]
        self.assertEqual(
            (row['Employee ID'], row['Name'], row['Week starting'], row['Status'], row['Project hours'], row['Billable hours'], row['Non-billable hours'], row['Attendance hours'], row['Late'], row['Approver']),
            ('TSE001', 'Asha Rao', str(MONDAY), 'Approved', '17.00', '16.00', '1.00', '18.00', 'No', 'Test User'),
        )

    def test_it_never_includes_drafts_or_the_requesters_own_sheet(self):
        make_sheet(self.employee, NEXT_MONDAY, 'draft', [(1, 'Alpha', 'P1', True, {0: 3})])
        make_sheet(self.hr, MONDAY, 'approved', [(None, '', '', False, {0: 2})])
        names = {row['Name'] for row in self.table(self.hr, 'timesheets')}
        self.assertEqual(names, {'Asha Rao'})
        self.assertNotIn(str(NEXT_MONDAY), {row['Week starting'] for row in self.table(self.hr, 'timesheets')})

    def test_it_shows_a_sent_back_sheet_and_filters_by_status(self):
        make_sheet(self.employee, LAST_MONDAY, 'returned', [(1, 'Alpha', 'P1', True, {0: 4})])
        self.assertEqual({row['Status'] for row in self.table(self.hr, 'timesheets')}, {'Approved', 'Returned'})
        self.assertEqual({row['Status'] for row in self.table(self.hr, 'timesheets', status='returned')}, {'Returned'})

    def test_the_week_range_picks_the_weeks_that_contain_the_dates(self):
        make_sheet(self.employee, NEXT_MONDAY, 'approved', [(1, 'Alpha', 'P1', True, {0: 3})])
        make_sheet(self.employee, LAST_MONDAY, 'approved', [(1, 'Alpha', 'P1', True, {0: 2})])
        wednesday = MONDAY + datetime.timedelta(days=2)
        weeks = lambda **q: {row['Week starting'] for row in self.table(self.hr, 'timesheets', **q)}     # noqa: E731
        self.assertEqual(weeks(**{'from': str(wednesday), 'to': str(wednesday)}), {str(MONDAY)})
        self.assertEqual(weeks(**{'from': str(wednesday)}), {str(MONDAY), str(NEXT_MONDAY)})
        self.assertEqual(weeks(**{'to': str(wednesday)}), {str(LAST_MONDAY), str(MONDAY)})


class ScopeTests(ReportBase):
    def test_a_branch_hr_sees_only_their_branch_and_a_superuser_sees_all(self):
        self.assertEqual({row['Employee ID'] for row in self.table(self.hr, 'timesheets')}, {'TSE001'})
        self.assertEqual({row['Employee ID'] for row in self.table(self.admin, 'timesheets')}, {'TSE001', 'TRF001'})

    def test_a_team_lead_sees_only_their_direct_reports(self):
        mine = make_user('tr_mine@test.com', employee_id='TRE001', branch='TS-Branch', reporting_manager=self.lead, full_name='Lead Report')
        make_sheet(mine, MONDAY, 'submitted', [(None, '', '', False, {0: 4})])
        self.assertEqual({row['Employee ID'] for row in self.table(self.lead, 'timesheets')}, {'TRE001'})

    def test_no_report_leaks_another_branchs_projects_or_hours(self):
        project_names = {row['Project'] for row in self.table(self.hr, 'timesheet_projects')}
        self.assertNotIn('Secret', project_names)
        alpha = next(row for row in self.table(self.hr, 'timesheet_projects') if row['Project'] == 'Alpha')
        self.assertEqual(alpha['Total hours'], '16.00')                      # Asha's 16, not Far Person's 40 on top
        self.assertEqual({row['Employee ID'] for row in self.table(self.hr, 'timesheet_billable')}, {'TSE001'})

    def test_everyone_without_the_permission_is_refused_even_an_assigned_approver(self):
        for key in ('timesheets', 'timesheet_projects', 'timesheet_billable', 'timesheet_weekly'):
            for user in (self.employee, self.manager, self.far):
                self.assertEqual(_as(user).get(reverse('report-preview', args=[key])).status_code, 403, f'{key} {user.email}')

    def test_the_catalog_lists_the_timesheet_reports_only_to_people_who_may_run_them(self):
        keys = lambda u: {e['key'] for e in _as(u).get(reverse('report-catalog')).data['data']['reports']}      # noqa: E731
        self.assertTrue({'timesheets', 'timesheet_projects', 'timesheet_billable', 'timesheet_weekly'} <= keys(self.hr))
        self.assertFalse({k for k in keys(self.employee) if k.startswith('timesheet')})


class ProjectWiseTests(ReportBase):
    def test_totals_billable_split_and_counts_per_project_with_the_internal_row_last(self):
        other = make_user('tr_other@test.com', employee_id='TRE002', branch='TS-Branch', full_name='Other Person')
        make_sheet(other, MONDAY, 'submitted', [(1, 'Alpha', 'P1', False, {0: 4}), (None, '', '', False, {1: 2})])
        table = self.table(self.hr, 'timesheet_projects')
        self.assertEqual([row['Project'] for row in table], ['Alpha', 'Internal / Non-project work'])
        alpha, internal = table
        self.assertEqual((alpha['Total hours'], alpha['Billable hours'], alpha['Non-billable hours'], alpha['Employees'], alpha['Timesheets']), ('20.00', '16.00', '4.00', '2', '2'))
        self.assertEqual((internal['Project code'], internal['Total hours'], internal['Employees']), ('', '3.00', '2'))

    def test_only_submitted_and_approved_sheets_count_unless_a_status_is_chosen(self):
        make_sheet(self.employee, LAST_MONDAY, 'returned', [(1, 'Alpha', 'P1', True, {0: 6})])
        make_sheet(self.employee, NEXT_MONDAY, 'draft', [(1, 'Alpha', 'P1', True, {0: 7})])
        alpha = next(row for row in self.table(self.hr, 'timesheet_projects') if row['Project'] == 'Alpha')
        self.assertEqual(alpha['Total hours'], '16.00')
        make_sheet(self.employee, LAST_MONDAY - datetime.timedelta(days=7), 'submitted', [(1, 'Alpha', 'P1', True, {0: 3})])
        only_submitted = self.table(self.hr, 'timesheet_projects', status='submitted')
        self.assertEqual([(r['Project'], r['Total hours']) for r in only_submitted], [('Alpha', '3.00')])

    def test_a_renamed_project_is_one_row(self):
        make_sheet(self.employee, LAST_MONDAY, 'approved', [(1, 'Alpha Renamed', 'P1', True, {0: 2})])
        names = [row['Project'] for row in self.table(self.hr, 'timesheet_projects') if row['Project'] != 'Internal / Non-project work']
        self.assertEqual(len(names), 1)


class BillableAndWeeklyTests(ReportBase):
    def test_billable_percent_per_employee_and_a_zero_total_is_safe(self):
        row = self.table(self.hr, 'timesheet_billable')[0]
        self.assertEqual((row['Total hours'], row['Billable hours'], row['Non-billable hours'], row['Billable %']), ('17.00', '16.00', '1.00', '94.1'))
        empty = make_user('tr_empty@test.com', employee_id='TRE003', branch='TS-Branch')
        make_sheet(empty, MONDAY, 'submitted', [])
        self.assertIn('TSE001', {r['Employee ID'] for r in self.table(self.hr, 'timesheet_billable')})

    def test_the_weekly_summary_counts_by_status_late_and_hours(self):
        second = make_user('tr_two@test.com', employee_id='TRE004', branch='TS-Branch')
        third = make_user('tr_three@test.com', employee_id='TRE005', branch='TS-Branch')
        make_sheet(second, MONDAY, 'submitted', [(None, '', '', False, {0: 4})], is_late=True)
        make_sheet(third, MONDAY, 'returned', [(None, '', '', False, {0: 2})])
        make_sheet(self.far, LAST_MONDAY, 'approved', [(None, '', '', False, {0: 9})])
        table = self.table(self.hr, 'timesheet_weekly')
        self.assertEqual([row['Week starting'] for row in table], [str(MONDAY)])           # the other branch's week is not here
        row = table[0]
        self.assertEqual(
            (row['Timesheets'], row['Awaiting approval'], row['Approved'], row['Sent back'], row['Late'], row['Project hours'], row['Billable hours']),
            ('3', '1', '1', '1', '1', '23.00', '16.00'),
        )

    def test_weeks_are_newest_first(self):
        make_sheet(self.employee, NEXT_MONDAY, 'approved', [(1, 'Alpha', 'P1', True, {0: 1})])
        make_sheet(self.employee, LAST_MONDAY, 'approved', [(1, 'Alpha', 'P1', True, {0: 1})])
        self.assertEqual([row['Week starting'] for row in self.table(self.hr, 'timesheet_weekly')], [str(NEXT_MONDAY), str(MONDAY), str(LAST_MONDAY)])


class DownloadTests(ReportBase):
    def test_every_timesheet_report_downloads_as_csv_for_a_superuser(self):
        for key in ('timesheets', 'timesheet_projects', 'timesheet_billable', 'timesheet_weekly'):
            response = _as(self.admin).get(reverse('report-download', args=[key]))
            self.assertEqual((response.status_code, response['Content-Type']), (200, 'text/csv; charset=utf-8'), key)

    def test_a_name_that_looks_like_a_formula_is_defused_in_the_csv(self):
        self.employee.full_name = '=HYPERLINK("http://x","click")'
        self.employee.save()
        text = _as(self.hr).get(reverse('report-download', args=['timesheets'])).content.decode('utf-8')
        self.assertIn("'=HYPERLINK", text)
        self.assertNotIn('"=HYPERLINK', text)

    def test_an_empty_scope_still_gives_a_header_row(self):
        text = _as(self.lead).get(reverse('report-download', args=['timesheets'])).content.decode('utf-8')
        # The downloader starts the file with a byte-order mark (so Excel reads UTF-8) and quotes every cell.
        self.assertTrue(text.lstrip('﻿').startswith('"Employee ID","Name","Branch","Week starting"'))
        self.assertEqual(len(text.strip().splitlines()), 1)

    def test_preview_reports_the_row_count(self):
        response = _as(self.hr).get(reverse('report-preview', args=['timesheets']))
        self.assertEqual(response.data['data']['row_count'], 1)
