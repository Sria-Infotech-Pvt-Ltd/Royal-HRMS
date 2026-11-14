"""Phase 2: reading a week and saving a draft."""
from __future__ import annotations

import datetime
from decimal import Decimal

from apps.attendance.models_timesheet import STATUS_SUBMITTED, Timesheet, TimesheetEntry, TimesheetLine
from apps.attendance.services_timesheet import get_week, save_draft
from apps.attendance.services_timesheet_common import TimesheetConflict, TimesheetError, parse_hours
from apps.attendance.tests_timesheet_support import (
    LAST_MONDAY, MONDAY, TimesheetTestBase, assign, cell, internal_line, pinned_today, project_line, total_of,
)


class WeekViewTests(TimesheetTestBase):
    def test_a_new_week_is_a_virtual_draft_prefilled_with_projects_and_the_internal_row(self):
        assign(self.employee, 1, 'Alpha')
        assign(self.employee, 2, 'Beta')
        with pinned_today():
            view = get_week(self.employee, MONDAY + datetime.timedelta(days=3))        # any day in the week is accepted
        self.assertIsNone(view['id'])
        self.assertEqual((view['status'], view['week_start'], view['week_end'], view['due_date']), ('draft', '2026-11-09', '2026-11-15', '2026-11-13'))
        self.assertEqual([line['project_name'] for line in view['lines']], ['Alpha', 'Beta', 'Internal / Non-project work'])
        self.assertTrue(view['is_editable'])
        self.assertEqual(Timesheet.objects.count(), 0)                                  # reading never writes

    def test_assignments_outside_the_week_or_removed_are_not_prefilled(self):
        assign(self.employee, 1, 'Ended', end=datetime.date(2026, 11, 1))
        assign(self.employee, 2, 'NotStarted', start=datetime.date(2026, 11, 20))
        assign(self.employee, 3, 'Gone', status='removed')
        assign(self.employee, 4, 'Current')
        with pinned_today():
            names = [line['project_name'] for line in get_week(self.employee, MONDAY)['lines']]
        self.assertEqual(names, ['Current', 'Internal / Non-project work'])

    def test_someone_elses_assignment_is_never_shown(self):
        assign(self.manager, 1, 'ManagerOnly')
        with pinned_today():
            names = [line['project_name'] for line in get_week(self.employee, MONDAY)['lines']]
        self.assertEqual(names, ['Internal / Non-project work'])

    def test_the_week_has_seven_days_with_attendance_shown_separately(self):
        with pinned_today():
            view = get_week(self.employee, MONDAY)
        self.assertEqual([d['weekday'] for d in view['days']], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        self.assertEqual(view['totals']['attendance_hours'], '0.00')
        self.assertEqual(view['limits']['weekly_target_hours'], '40.00')


class SaveDraftTests(TimesheetTestBase):
    def setUp(self):
        super().setUp()
        assign(self.employee, 1, 'Alpha')
        assign(self.employee, 2, 'Beta')

    def save(self, *lines, week=MONDAY):
        with pinned_today():
            return save_draft(self.employee, week, {'lines': list(lines)})

    def test_saves_hours_notes_and_project_snapshots(self):
        view = self.save(project_line(1, cell(0, '8', 'design'), cell(1, '7.5'), billable=True), internal_line(cell(0, '1')))
        sheet = Timesheet.objects.get(employee=self.employee)
        self.assertEqual((sheet.status, sheet.total_hours, sheet.billable_hours), ('draft', Decimal('16.50'), Decimal('15.50')))
        line = TimesheetLine.objects.get(timesheet=sheet, assignment_id=1)
        self.assertEqual((line.project_id, line.project_code, line.project_name, line.is_billable), (10, 'P1', 'Alpha', True))
        self.assertEqual(TimesheetEntry.objects.get(line=line, entry_date=MONDAY).note, 'design')
        self.assertEqual((total_of(view), view['totals']['billable'], view['totals']['non_billable']), (Decimal('16.50'), '15.50', '1.00'))
        self.assertEqual(view['totals']['daily']['2026-11-09'], '9.00')

    def test_saving_again_replaces_the_rows_and_never_creates_a_second_sheet(self):
        self.save(project_line(1, cell(0, '8')))
        self.save(project_line(2, cell(1, '4')))
        self.assertEqual(Timesheet.objects.filter(employee=self.employee).count(), 1)
        self.assertEqual(list(TimesheetLine.objects.values_list('project_name', flat=True)), ['Beta'])
        self.assertEqual(TimesheetEntry.objects.count(), 1)

    def test_empty_cells_are_not_stored_but_a_note_alone_is_kept(self):
        self.save(project_line(1, cell(0, '0'), cell(1, '0', 'in training')))
        self.assertEqual(list(TimesheetEntry.objects.values_list('entry_date', 'note')), [(MONDAY + datetime.timedelta(days=1), 'in training')])

    def test_a_half_filled_sheet_can_always_be_saved(self):
        view = self.save()
        self.assertEqual((view['status'], total_of(view)), ('draft', Decimal('0.00')))

    def test_issues_are_returned_with_the_saved_sheet(self):
        view = self.save(project_line(1, cell(0, '8')), project_line(2, cell(0, '6')))     # 14 hours on Monday
        self.assertEqual([w['code'] for w in view['issues']['warnings']], ['long_day'])
        self.assertEqual(view['issues']['errors'], [])

    def test_a_submitted_sheet_cannot_be_changed(self):
        self.save(project_line(1, cell(0, '8')))
        Timesheet.objects.update(status=STATUS_SUBMITTED)
        with self.assertRaises(TimesheetConflict):
            self.save(project_line(1, cell(0, '1')))
        self.assertEqual(Timesheet.objects.get().total_hours, Decimal('8.00'))

    def test_a_returned_sheet_can_be_edited(self):
        self.save(project_line(1, cell(0, '8')))
        Timesheet.objects.update(status='returned')
        self.assertEqual(self.save(project_line(1, cell(0, '6')))['status'], 'returned')


class SaveRejectsBadInputTests(TimesheetTestBase):
    def setUp(self):
        super().setUp()
        assign(self.employee, 1, 'Alpha')

    def rejected(self, payload, week=MONDAY) -> TimesheetError:
        with pinned_today(), self.assertRaises(TimesheetError) as caught:
            save_draft(self.employee, week, payload)
        self.assertEqual(Timesheet.objects.count(), 0)                                  # nothing half-saved
        return caught.exception

    def test_hours_must_be_exact_quarters_between_0_and_24(self):
        for bad in ('0.1', '7.3', '24.25', '-1', 'abc', '', True, None, 'NaN', 'Infinity', '1e1000'):
            error = self.rejected({'lines': [internal_line(cell(0, bad))]})
            self.assertTrue(error.errors, bad)
        for good in ('0', '0.25', '8', '7.75', 24, 3.5, '24.00'):
            parse_hours(good)

    def test_float_noise_does_not_slip_through(self):
        self.assertEqual(parse_hours(0.25 + 0.5), Decimal('0.75'))          # binary-exact floats are fine
        with self.assertRaises(TimesheetError):
            parse_hours(0.1 + 0.2)                                            # 0.30000000000000004 is not a quarter hour

    def test_every_problem_is_reported_together(self):
        error = self.rejected({'lines': [internal_line(cell(0, '0.1'), cell(1, '25'))]})
        self.assertEqual(len(error.errors), 2)

    def test_a_date_outside_the_week_or_invalid_or_duplicated(self):
        self.assertIn('outside this week', self.rejected({'lines': [internal_line(cell(7, '1'))]}).errors[0])
        self.assertIn('not a valid date', self.rejected({'lines': [internal_line({'date': '2026-13-45', 'hours': '1'})]}).errors[0])
        self.assertIn('appears twice', self.rejected({'lines': [internal_line(cell(0, '1'), cell(0, '2'))]}).errors[0])

    def test_a_project_that_is_not_yours_or_listed_twice_or_two_internal_rows(self):
        self.assertIn('not one of your assignments', self.rejected({'lines': [project_line(99, cell(0, '1'))]}).errors[0])
        self.assertIn('more than one row', self.rejected({'lines': [project_line(1, cell(0, '1')), project_line(1, cell(1, '1'))]}).errors[0])
        self.assertIn('only one Internal', self.rejected({'lines': [internal_line(cell(0, '1')), internal_line(cell(1, '1'))]}).errors[0])

    def test_a_note_over_500_characters(self):
        self.assertIn('500', self.rejected({'lines': [internal_line(cell(0, '1', 'x' * 501))]}).errors[0])

    def test_malformed_payloads(self):
        for payload in (None, [], {}, {'lines': 'x'}, {'lines': ['x']}, {'lines': [{'entries': 'x'}]}, {'lines': [internal_line('x')]}):
            self.assertTrue(self.rejected(payload).errors)

    def test_the_week_must_start_on_a_monday_and_not_be_in_the_future(self):
        with pinned_today():
            with self.assertRaisesMessage(TimesheetError, 'Monday'):
                save_draft(self.employee, MONDAY + datetime.timedelta(days=1), {'lines': []})
            with self.assertRaisesMessage(TimesheetError, 'not started'):
                save_draft(self.employee, MONDAY + datetime.timedelta(days=7), {'lines': []})
        self.assertEqual(Timesheet.objects.count(), 0)

    def test_a_past_week_can_be_saved(self):
        with pinned_today():
            self.assertEqual(save_draft(self.employee, LAST_MONDAY, {'lines': []})['week_start'], '2026-11-02')
