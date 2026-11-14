"""Phase 2: submitting and resubmitting, the business rules, approver routing and the history written on submit."""
from __future__ import annotations

import datetime

from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, EmployeeApprovalOverride
from apps.attendance.models import AttendanceRecord
from apps.attendance.models_timesheet import Timesheet, TimesheetEvent
from apps.attendance.services_timesheet import save_draft, submit
from apps.attendance.services_timesheet_common import TimesheetConflict, TimesheetError, TimesheetNotFound
from apps.hrms.models import Holiday, LeaveRequest, SEP_APPROVED, STATUS_APPROVED, SeparationRequest
from apps.attendance.tests_timesheet_support import (
    LAST_MONDAY, MONDAY, TimesheetTestBase, assign, cell, internal_line, pinned_today, project_line,
)


class SubmitBase(TimesheetTestBase):
    def setUp(self):
        super().setUp()
        self.alpha = assign(self.employee, 1, 'Alpha')

    def save(self, *lines, employee=None, week=MONDAY):
        with pinned_today():
            return save_draft(employee or self.employee, week, {'lines': list(lines)})

    def submit(self, employee=None, week=MONDAY, today=None):
        with pinned_today(*([today] if today else [])):
            return submit(employee or self.employee, week)

    def problems(self, employee=None, week=MONDAY) -> list[str]:
        with self.assertRaises(TimesheetError) as caught:
            self.submit(employee, week)
        return caught.exception.errors


class SubmitTests(SubmitBase):
    def test_submit_locks_the_sheet_and_sends_it_to_the_reporting_manager(self):
        self.save(project_line(1, cell(0, '8'), cell(1, '8'), billable=True))
        view = self.submit()
        sheet = Timesheet.objects.get()
        self.assertEqual((view['status'], view['is_editable'], sheet.status), ('submitted', False, 'submitted'))
        self.assertEqual((sheet.approver, sheet.submit_count, sheet.is_late), (self.manager, 1, False))
        self.assertIsNotNone(sheet.submitted_at)

    def test_submit_records_one_history_event_with_a_snapshot_and_one_audit_row(self):
        self.save(project_line(1, cell(0, '8', 'api work'), billable=True))
        self.submit()
        event = TimesheetEvent.objects.get()
        self.assertEqual((event.event_type, event.from_status, event.to_status, event.actor), ('submitted', 'draft', 'submitted', self.employee))
        self.assertEqual(event.snapshot['total_hours'], '8.00')
        self.assertEqual(event.snapshot['lines'][0]['project_name'], 'Alpha')
        self.assertEqual(event.snapshot['lines'][0]['entries'][0]['note'], 'api work')
        audit = AuditLog.objects.get(module='timesheet')
        self.assertEqual((audit.action, audit.user, audit.object_id), ('timesheet_submitted', self.employee, str(Timesheet.objects.get().pk)))

    def test_the_attendance_hours_are_snapshotted_apart_from_project_hours(self):
        for offset, minutes in ((0, 480), (1, 450)):
            AttendanceRecord.objects.create(employee=self.employee, date=MONDAY + datetime.timedelta(days=offset), status='present', total_working_minutes=minutes)
        self.save(project_line(1, cell(0, '6')))
        self.submit()
        sheet = Timesheet.objects.get()
        self.assertEqual((sheet.attendance_minutes, str(sheet.total_hours)), (930, '6.00'))

    def test_submitting_after_friday_is_allowed_but_flagged_late(self):
        self.save(project_line(1, cell(0, '8', week=LAST_MONDAY)), week=LAST_MONDAY)
        self.submit(week=LAST_MONDAY)
        self.assertTrue(Timesheet.objects.get().is_late)

    def test_an_empty_sheet_cannot_be_submitted(self):
        self.save(project_line(1, cell(0, '0')))
        self.assertEqual(self.problems(), ['Enter some hours before submitting.'])

    def test_submitting_with_nothing_saved_is_not_found(self):
        with pinned_today(), self.assertRaises(TimesheetNotFound):
            submit(self.employee, MONDAY)

    def test_a_second_submit_is_a_conflict_and_changes_nothing(self):
        self.save(project_line(1, cell(0, '8')))
        self.submit()
        with self.assertRaises(TimesheetConflict):
            self.submit()
        self.assertEqual((Timesheet.objects.get().submit_count, TimesheetEvent.objects.count()), (1, 1))

    def test_a_failed_submit_changes_nothing(self):
        self.save(project_line(1, cell(0, '8'), cell(3, '8')))          # Thursday is after the pinned "today" (Wednesday)
        self.problems()
        self.assertEqual((Timesheet.objects.get().status, TimesheetEvent.objects.count(), AuditLog.objects.count()), ('draft', 0, 0))

    def test_a_returned_sheet_is_resubmitted_and_the_old_reason_is_cleared(self):
        self.save(project_line(1, cell(0, '8')))
        self.submit()
        Timesheet.objects.update(status='returned', return_reason='Wrong project', decided_by=self.manager)
        self.save(project_line(1, cell(0, '7')))
        view = self.submit()
        sheet = Timesheet.objects.get()
        self.assertEqual((sheet.status, sheet.submit_count, sheet.return_reason, sheet.decided_by), ('submitted', 2, '', None))
        self.assertEqual(view['return_reason'], '')
        self.assertEqual(list(TimesheetEvent.objects.order_by('created_at').values_list('event_type', flat=True)), ['submitted', 'resubmitted'])
        self.assertEqual(TimesheetEvent.objects.get(event_type='submitted').snapshot['total_hours'], '8.00')      # the first version is kept


class BusinessRuleTests(SubmitBase):
    def test_no_hours_before_the_joining_date(self):
        joiner = make_user('ts_joiner@test.com', employee_id='TSE002', reporting_manager=self.manager, date_of_joining=datetime.date(2026, 11, 10))
        self.save(internal_line(cell(0, '8')), employee=joiner)
        self.assertIn('had not joined', self.problems(joiner)[0])

    def test_no_hours_after_the_last_working_day(self):
        SeparationRequest.objects.create(
            employee=self.employee, separation_type='resignation', request_date=datetime.date(2026, 10, 1),
            proposed_last_working_day=datetime.date(2026, 11, 10), status=SEP_APPROVED,
        )
        self.save(internal_line(cell(1, '8'), cell(2, '4')))              # Tuesday is the last day, Wednesday is after it
        errors = self.problems()
        self.assertEqual(len(errors), 1)
        self.assertIn('Wed 11 Nov', errors[0])

    def test_no_hours_on_a_project_outside_its_assignment_dates(self):
        self.alpha.assignment_end_date = datetime.date(2026, 11, 10)
        self.alpha.save()
        self.save(project_line(1, cell(1, '4'), cell(2, '4')))
        self.assertIn('not assigned to "Alpha"', self.problems()[0])

    def test_an_assignment_that_starts_mid_week_blocks_the_days_before_it(self):
        self.alpha.assignment_start_date = datetime.date(2026, 11, 11)
        self.alpha.save()
        self.save(project_line(1, cell(0, '4'), cell(2, '4')))
        self.assertIn('Mon 9 Nov', self.problems()[0])

    def test_no_hours_for_a_day_that_has_not_happened(self):
        self.save(internal_line(cell(3, '2')))
        self.assertIn('has not happened yet', self.problems()[0])

    def test_more_than_24_hours_in_a_day_across_projects_blocks_submit_but_not_save(self):
        assign(self.employee, 2, 'Beta')
        self.save(project_line(1, cell(0, '14')), project_line(2, cell(0, '14')))
        self.assertIn('28.00 hours', self.problems()[0])

    def test_over_12_hours_is_only_a_warning(self):
        self.save(project_line(1, cell(0, '13')))
        view = self.submit()
        self.assertEqual([w['code'] for w in view['issues']['warnings']], ['long_day'])
        self.assertEqual(view['status'], 'submitted')

    def test_hours_on_leave_and_holiday_days_are_allowed_with_a_warning(self):
        LeaveRequest.objects.create(employee=self.employee, leave_type='casual', start_date=MONDAY, end_date=MONDAY, total_days=1, reason='x', status=STATUS_APPROVED)
        Holiday.objects.create(name='Founders Day', date=MONDAY + datetime.timedelta(days=1))
        self.save(project_line(1, cell(0, '4'), cell(1, '4'), cell(2, '4')))
        view = self.submit()
        flagged = sorted(w['date'] for w in view['issues']['warnings'] if w['code'] == 'non_working_day')
        self.assertEqual(flagged, ['2026-11-09', '2026-11-10'])
        self.assertEqual(view['status'], 'submitted')
        statuses = {d['date']: d['status'] for d in view['days']}
        self.assertEqual((statuses['2026-11-09'], statuses['2026-11-10']), ('on_leave', 'holiday'))

    def test_every_problem_is_listed_not_just_the_first(self):
        self.alpha.assignment_end_date = datetime.date(2026, 11, 9)
        self.alpha.save()
        self.save(project_line(1, cell(1, '4'), cell(3, '4')))
        errors = self.problems()
        # Tuesday and Thursday are both outside the assignment, and Thursday has also not happened yet.
        self.assertEqual(len(errors), 3)
        self.assertEqual(sum('not assigned' in e for e in errors), 2)
        self.assertEqual(sum('not happened' in e for e in errors), 1)


class ProjectChangeTests(SubmitBase):
    def test_a_renamed_or_closed_project_does_not_change_a_saved_sheet(self):
        self.save(project_line(1, cell(0, '8')))
        self.alpha.project_name, self.alpha.assignment_status = 'Alpha Renamed', 'completed'
        self.alpha.save()
        self.submit()
        sheet = Timesheet.objects.get()
        self.assertEqual(sheet.lines.get().project_name, 'Alpha')
        self.assertEqual(TimesheetEvent.objects.get().snapshot['lines'][0]['project_name'], 'Alpha')

    def test_a_project_removed_after_saving_still_shows_on_the_saved_sheet(self):
        self.save(project_line(1, cell(0, '8')))
        self.alpha.assignment_status = 'removed'
        self.alpha.save()
        with pinned_today():
            from apps.attendance.services_timesheet import get_week
            names = [line['project_name'] for line in get_week(self.employee, MONDAY)['lines']]
        self.assertIn('Alpha', names)


class ApproverRoutingTests(SubmitBase):
    def test_a_manager_without_a_manager_goes_to_their_hr_partner(self):
        self.save(internal_line(cell(0, '8')), employee=self.manager)
        self.submit(self.manager)
        self.assertEqual(Timesheet.objects.get(employee=self.manager).approver, self.hr)

    def test_a_per_employee_override_wins(self):
        EmployeeApprovalOverride.objects.create(employee=self.employee, workflow_type='timesheet', l1_override=self.hr)
        self.save(internal_line(cell(0, '8')))
        self.submit()
        self.assertEqual(Timesheet.objects.get().approver, self.hr)

    def test_an_inactive_manager_falls_through_to_hr(self):
        self.manager.is_active = False
        self.manager.save()
        self.save(internal_line(cell(0, '8')))
        self.submit()
        self.assertEqual(Timesheet.objects.get().approver, self.hr)

    def test_nobody_to_approve_is_a_clear_error_and_nothing_is_submitted(self):
        lone = make_user('ts_lone@test.com', employee_id='TSE003', branch='Nowhere')
        self.save(internal_line(cell(0, '8')), employee=lone)
        self.assertIn('No approver', self.problems(lone)[0])
        self.assertEqual(Timesheet.objects.get(employee=lone).status, 'draft')

    def test_nobody_approves_their_own_sheet(self):
        # The HR person has no manager and no HR partner of their own: the sheet is refused, never routed back to themselves.
        self.save(internal_line(cell(0, '8')), employee=self.hr)
        self.assertIn('No approver', self.problems(self.hr)[0])
        sheet = Timesheet.objects.get(employee=self.hr)
        self.assertEqual((sheet.status, sheet.approver), ('draft', None))
