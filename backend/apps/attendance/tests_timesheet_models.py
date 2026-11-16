"""Phase 1: the timesheet tables enforce their own rules in the database, whoever writes to them."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import ApprovalWorkflowRule, EmployeeApprovalOverride, Permission
from apps.attendance.models_timesheet import (
    EVENT_SUBMITTED, STATUS_DRAFT, Timesheet, TimesheetEntry, TimesheetEvent, TimesheetLine,
)

MONDAY = datetime.date(2026, 11, 9)
TUESDAY = MONDAY + datetime.timedelta(days=1)


class TimesheetModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.employee = make_user('ts_model_emp@test.com', employee_id='TSM001')
        cls.other = make_user('ts_model_other@test.com', employee_id='TSM002')

    def sheet(self, employee=None, week=MONDAY) -> Timesheet:
        return Timesheet.objects.create(employee=employee or self.employee, week_start=week)

    def fails(self, **create_kwargs) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_kwargs.pop('model').objects.create(**create_kwargs)

    def test_new_sheet_is_a_draft_with_zero_totals(self):
        sheet = self.sheet()
        self.assertEqual((sheet.status, sheet.total_hours, sheet.billable_hours, sheet.submit_count), (STATUS_DRAFT, 0, 0, 0))
        self.assertIsNone(sheet.approver)

    def test_one_sheet_per_employee_per_week(self):
        self.sheet()
        self.fails(model=Timesheet, employee=self.employee, week_start=MONDAY)

    def test_another_employee_or_another_week_is_fine(self):
        self.sheet()
        self.sheet(self.other)
        self.sheet(week=MONDAY + datetime.timedelta(days=7))
        self.assertEqual(Timesheet.objects.count(), 3)

    def test_a_week_must_start_on_a_monday(self):
        self.fails(model=Timesheet, employee=self.employee, week_start=TUESDAY)
        self.fails(model=Timesheet, employee=self.employee, week_start=MONDAY - datetime.timedelta(days=1))   # a Sunday

    def test_only_one_internal_line_per_sheet(self):
        sheet = self.sheet()
        TimesheetLine.objects.create(timesheet=sheet, is_internal=True)
        self.fails(model=TimesheetLine, timesheet=sheet, is_internal=True)
        TimesheetLine.objects.create(timesheet=self.sheet(self.other), is_internal=True)         # a different sheet is fine

    def test_an_internal_line_cannot_point_at_a_project_assignment(self):
        self.fails(model=TimesheetLine, timesheet=self.sheet(), is_internal=True, assignment_id=7)

    def test_a_project_assignment_appears_once_per_sheet(self):
        sheet = self.sheet()
        TimesheetLine.objects.create(timesheet=sheet, assignment_id=7, project_id=1, project_name='Alpha')
        self.fails(model=TimesheetLine, timesheet=sheet, assignment_id=7, project_id=1, project_name='Alpha')
        TimesheetLine.objects.create(timesheet=sheet, assignment_id=8, project_id=2, project_name='Beta')

    def test_the_project_name_is_copied_onto_the_line_so_it_survives_the_assignment(self):
        line = TimesheetLine.objects.create(timesheet=self.sheet(), assignment_id=7, project_id=1, project_code='AL', project_name='Alpha')
        line.refresh_from_db()
        self.assertEqual((line.project_code, line.project_name), ('AL', 'Alpha'))

    def test_a_cell_is_unique_per_line_and_day(self):
        line = TimesheetLine.objects.create(timesheet=self.sheet(), is_internal=True)
        TimesheetEntry.objects.create(line=line, entry_date=MONDAY, hours=Decimal('8'))
        self.fails(model=TimesheetEntry, line=line, entry_date=MONDAY, hours=Decimal('1'))
        TimesheetEntry.objects.create(line=line, entry_date=TUESDAY, hours=Decimal('1'))

    def test_hours_are_between_0_and_24_in_the_database(self):
        line = TimesheetLine.objects.create(timesheet=self.sheet(), is_internal=True)
        TimesheetEntry.objects.create(line=line, entry_date=MONDAY, hours=Decimal('0'))
        TimesheetEntry.objects.create(line=line, entry_date=TUESDAY, hours=Decimal('24'))
        day = MONDAY + datetime.timedelta(days=2)
        self.fails(model=TimesheetEntry, line=line, entry_date=day, hours=Decimal('24.25'))
        self.fails(model=TimesheetEntry, line=line, entry_date=day, hours=Decimal('-0.25'))

    def test_deleting_a_sheet_removes_its_lines_and_cells_but_not_other_sheets(self):
        keep, drop = self.sheet(self.other), self.sheet()
        for sheet in (keep, drop):
            line = TimesheetLine.objects.create(timesheet=sheet, is_internal=True)
            TimesheetEntry.objects.create(line=line, entry_date=MONDAY, hours=Decimal('1'))
        drop.delete()
        self.assertEqual((TimesheetLine.objects.count(), TimesheetEntry.objects.count()), (1, 1))

    def test_an_event_can_be_written_but_never_changed(self):
        event = TimesheetEvent.objects.create(
            timesheet=self.sheet(), event_type=EVENT_SUBMITTED, actor=self.employee, from_status='draft', to_status='submitted',
            snapshot={'total_hours': '8.00'},
        )
        event.reason = 'edited later'
        with self.assertRaisesMessage(ValueError, 'append-only'):
            event.save()
        event.refresh_from_db()
        self.assertEqual((event.reason, event.snapshot), ('', {'total_hours': '8.00'}))


class TimesheetWorkflowSetupTests(TestCase):
    def test_timesheet_is_a_known_approval_workflow_type(self):
        self.assertIn('timesheet', dict(ApprovalWorkflowRule.WORKFLOW_CHOICES))
        self.assertIn('timesheet', dict(EmployeeApprovalOverride._meta.get_field('workflow_type').choices))

    def test_the_default_rule_is_reporting_manager_then_hr(self):
        rule = ApprovalWorkflowRule.objects.get(workflow_type='timesheet')
        self.assertEqual((rule.l1_approver_kind, rule.l2_approver_kind), ('reporting_manager', 'hr'))

    def test_the_new_permissions_are_defined_in_code_and_synced(self):
        codenames = set(Permission.objects.filter(codename__startswith='timesheet.').values_list('codename', flat=True))
        self.assertEqual(codenames, {'timesheet.approve', 'timesheet.unlock', 'timesheet.report'})
