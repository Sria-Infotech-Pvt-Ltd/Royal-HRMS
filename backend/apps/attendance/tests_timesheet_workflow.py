"""Phase 3: approve, send back, unlock, who may do it, the approver queue, and the history that is never overwritten."""
from __future__ import annotations

from decimal import Decimal

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.attendance.models_timesheet import Timesheet, TimesheetEvent
from apps.attendance.services_timesheet import save_draft, submit
from apps.attendance.services_timesheet_access import team_queryset
from apps.attendance.services_timesheet_common import TimesheetConflict, TimesheetError, TimesheetForbidden, TimesheetNotFound
from apps.attendance.services_timesheet_decisions import approve, detail_for, return_to_employee, unlock
from apps.attendance.tests_timesheet_support import LAST_MONDAY, MONDAY, TimesheetTestBase, assign, cell, internal_line, pinned_today, project_line

HR_ACCESS = ['timesheet.approve', 'timesheet.unlock', 'timesheet.report']


class WorkflowBase(TimesheetTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hr_admin = make_user(
            'ts_hradmin@test.com', make_role('ts_hr_admin', permission_codenames=HR_ACCESS, can_manage_branch=True),
            employee_id='TSH002', branch='TS-Branch',
        )
        cls.other_branch_hr = make_user(
            'ts_otherhr@test.com', make_role('ts_other_hr', permission_codenames=HR_ACCESS, can_manage_branch=True),
            employee_id='TSH003', branch='Elsewhere',
        )
        cls.stranger_manager = make_user(
            'ts_stranger@test.com', make_role('ts_team', permission_codenames=HR_ACCESS, can_manage_team=True),
            employee_id='TSM002', branch='TS-Branch',
        )
        cls.admin = make_user('ts_super@test.com', employee_id='TSA001', is_superuser=True)

    def setUp(self):
        super().setUp()
        assign(self.employee, 1, 'Alpha')

    def submitted(self, employee=None, hours='8', week=MONDAY) -> Timesheet:
        person = employee or self.employee
        # Only self.employee has project 1; anyone else logs Internal work.
        line = project_line(1, cell(0, hours, week=week), billable=True) if person == self.employee else internal_line(cell(0, hours, week=week))
        with pinned_today():
            save_draft(person, week, {'lines': [line]})
            submit(person, week)
        return Timesheet.objects.get(employee=person, week_start=week)

    def sheet(self) -> Timesheet:
        return Timesheet.objects.get(employee=self.employee, week_start=MONDAY)


class ApproveTests(WorkflowBase):
    def test_the_assigned_manager_approves_and_the_sheet_is_locked(self):
        sheet = self.submitted()
        view = approve(sheet.pk, self.manager)
        sheet.refresh_from_db()
        self.assertEqual((sheet.status, sheet.decided_by, view['status'], view['is_editable']), ('approved', self.manager, 'approved', False))
        self.assertIsNotNone(sheet.decided_at)
        with pinned_today():
            with self.assertRaises(TimesheetConflict):
                save_draft(self.employee, MONDAY, {'lines': []})
            with self.assertRaises(TimesheetConflict):
                submit(self.employee, MONDAY)
        self.assertEqual(sheet.total_hours, Decimal('8.00'))

    def test_approval_writes_one_event_with_a_snapshot_and_one_audit_row(self):
        sheet = self.submitted()
        approve(sheet.pk, self.manager, ip_address='10.1.2.3')
        event = TimesheetEvent.objects.get(event_type='approved')
        self.assertEqual((event.actor, event.from_status, event.to_status, event.snapshot['total_hours']), (self.manager, 'submitted', 'approved', '8.00'))
        audit = AuditLog.objects.get(action='timesheet_approved')
        self.assertEqual((audit.user, audit.object_id, audit.ip_address), (self.manager, str(sheet.pk), '10.1.2.3'))

    def test_nobody_approves_their_own_sheet_not_even_a_superuser(self):
        mine = self.submitted(self.manager)
        with self.assertRaises(TimesheetForbidden):
            approve(mine.pk, self.manager)
        assign(self.admin, 9, 'Zed')
        with pinned_today():
            save_draft(self.admin, MONDAY, {'lines': [project_line(9, cell(0, '4'))]})
        Timesheet.objects.filter(employee=self.admin).update(status='submitted', approver=self.admin)
        with self.assertRaises(TimesheetForbidden):
            approve(Timesheet.objects.get(employee=self.admin).pk, self.admin)

    def test_who_may_approve(self):
        allowed = [self.manager, self.hr_admin, self.admin]
        denied = {'stranger manager (not a direct report)': self.stranger_manager, 'HR in another branch': self.other_branch_hr}
        sheet = self.submitted()
        for who in denied.values():
            with self.assertRaises(TimesheetNotFound):
                approve(sheet.pk, who)
        for index, actor in enumerate(allowed):
            Timesheet.objects.filter(pk=sheet.pk).update(status='submitted')
            self.assertEqual(approve(sheet.pk, actor)['status'], 'approved', index)

    def test_a_same_branch_user_without_the_approve_permission_cannot(self):
        peer = make_user('ts_peer@test.com', employee_id='TSE009', branch='TS-Branch')
        sheet = self.submitted()
        with self.assertRaises(TimesheetNotFound):
            approve(sheet.pk, peer)

    def test_an_inactive_approver_cannot_act(self):
        sheet = self.submitted()
        self.manager.is_active = False
        with self.assertRaises(TimesheetNotFound):
            approve(sheet.pk, self.manager)

    def test_only_a_submitted_sheet_can_be_decided(self):
        sheet = self.submitted()
        approve(sheet.pk, self.manager)
        with self.assertRaises(TimesheetConflict):
            approve(sheet.pk, self.manager)                                     # a second approval is refused, not repeated
        with self.assertRaises(TimesheetConflict):
            return_to_employee(sheet.pk, self.manager, 'too late')
        self.assertEqual((TimesheetEvent.objects.filter(event_type='approved').count(), self.sheet().status), (1, 'approved'))

    def test_an_unknown_or_malformed_id_is_not_found(self):
        for bad in ('00000000-0000-0000-0000-000000000000', 'not-a-uuid', None):
            with self.assertRaises(TimesheetNotFound):
                approve(bad, self.manager)

    def test_a_draft_is_invisible_to_the_manager(self):
        with pinned_today():
            save_draft(self.employee, MONDAY, {'lines': [internal_line(cell(0, '2'))]})
        with self.assertRaises(TimesheetNotFound):
            approve(self.sheet().pk, self.manager)


class ReturnTests(WorkflowBase):
    def test_return_needs_a_reason_and_changes_nothing_without_one(self):
        sheet = self.submitted()
        for bad in (None, '', '   ', 5, 'x' * 1001):
            with self.assertRaises(TimesheetError):
                return_to_employee(sheet.pk, self.manager, bad)
        self.assertEqual((self.sheet().status, TimesheetEvent.objects.count()), ('submitted', 1))

    def test_return_sends_it_back_with_the_reason_and_keeps_the_hours(self):
        sheet = self.submitted()
        view = return_to_employee(sheet.pk, self.manager, '  Wrong project on Monday  ')
        sheet.refresh_from_db()
        self.assertEqual((sheet.status, sheet.return_reason, view['return_reason'], view['is_editable']), ('returned', 'Wrong project on Monday', 'Wrong project on Monday', True))
        self.assertEqual(sheet.total_hours, Decimal('8.00'))
        event = TimesheetEvent.objects.get(event_type='returned')
        self.assertEqual((event.reason, event.actor), ('Wrong project on Monday', self.manager))
        self.assertTrue(AuditLog.objects.filter(action='timesheet_returned').exists())

    def test_the_employee_corrects_and_resubmits_and_it_can_then_be_approved(self):
        sheet = self.submitted()
        return_to_employee(sheet.pk, self.manager, 'Fix Monday')
        with pinned_today():
            save_draft(self.employee, MONDAY, {'lines': [project_line(1, cell(0, '6'))]})
            submit(self.employee, MONDAY)
        self.assertEqual(approve(sheet.pk, self.manager)['status'], 'approved')
        self.assertEqual(list(TimesheetEvent.objects.order_by('created_at').values_list('event_type', flat=True)), ['submitted', 'returned', 'resubmitted', 'approved'])

    def test_only_someone_who_may_decide_can_send_back(self):
        sheet = self.submitted()
        with self.assertRaises(TimesheetNotFound):
            return_to_employee(sheet.pk, self.other_branch_hr, 'no')
        with self.assertRaises(TimesheetForbidden):
            return_to_employee(sheet.pk, self.employee, 'self')


class UnlockTests(WorkflowBase):
    def approved(self) -> Timesheet:
        sheet = self.submitted()
        approve(sheet.pk, self.manager)
        return sheet

    def test_hr_unlocks_with_a_reason_and_the_whole_history_is_kept(self):
        sheet = self.approved()
        view = unlock(sheet.pk, self.hr_admin, 'Billable flag was wrong')
        sheet.refresh_from_db()
        self.assertEqual((sheet.status, sheet.return_reason, view['is_editable']), ('returned', 'Reopened by HR: Billable flag was wrong', True))
        with pinned_today():
            save_draft(self.employee, MONDAY, {'lines': [project_line(1, cell(0, '5'))]})
            submit(self.employee, MONDAY)
        approve(sheet.pk, self.manager)
        events = list(TimesheetEvent.objects.order_by('created_at'))
        self.assertEqual([e.event_type for e in events], ['submitted', 'approved', 'unlocked', 'resubmitted', 'approved'])
        self.assertEqual([e.snapshot['total_hours'] for e in events], ['8.00', '8.00', '8.00', '5.00', '5.00'])      # the 8-hour approval is still readable

    def test_unlock_needs_a_reason(self):
        sheet = self.approved()
        with self.assertRaises(TimesheetError):
            unlock(sheet.pk, self.hr_admin, ' ')
        self.assertEqual(self.sheet().status, 'approved')

    def test_only_an_approved_sheet_can_be_unlocked(self):
        sheet = self.submitted()
        with self.assertRaises(TimesheetConflict):
            unlock(sheet.pk, self.hr_admin, 'x')

    def test_the_approving_manager_cannot_unlock_without_the_permission(self):
        sheet = self.approved()
        with self.assertRaises(TimesheetForbidden):
            unlock(sheet.pk, self.manager, 'x')
        with self.assertRaises(TimesheetNotFound):
            unlock(sheet.pk, self.other_branch_hr, 'x')
        with self.assertRaises(TimesheetForbidden):
            unlock(sheet.pk, self.employee, 'x')
        self.assertEqual(self.sheet().status, 'approved')

    def test_hr_cannot_unlock_their_own_sheet(self):
        assign(self.hr_admin, 7, 'HRProj')
        with pinned_today():
            save_draft(self.hr_admin, MONDAY, {'lines': [project_line(7, cell(0, '4'))]})
        Timesheet.objects.filter(employee=self.hr_admin).update(status='approved', approver=self.admin)
        with self.assertRaises(TimesheetForbidden):
            unlock(Timesheet.objects.get(employee=self.hr_admin).pk, self.hr_admin, 'x')


class QueueAndViewTests(WorkflowBase):
    def test_the_managers_queue_has_their_reports_submitted_sheets_only(self):
        mine = self.submitted()
        with pinned_today():
            save_draft(self.employee, LAST_MONDAY, {'lines': [internal_line(cell(0, '2', week=LAST_MONDAY))]})   # a draft: not visible
        ids = set(team_queryset(self.manager).values_list('pk', flat=True))
        self.assertEqual(ids, {mine.pk})

    def test_a_managers_own_sheet_is_never_in_their_own_queue(self):
        own = self.submitted(self.manager)
        self.assertNotIn(own.pk, set(team_queryset(self.manager).values_list('pk', flat=True)))
        self.assertIn(own.pk, set(team_queryset(self.hr).values_list('pk', flat=True)))                       # it went to their HR partner

    def test_scope_for_hr_strangers_and_the_superuser(self):
        sheet = self.submitted()
        for actor, sees in ((self.hr_admin, True), (self.admin, True), (self.stranger_manager, False), (self.other_branch_hr, False), (self.employee, False)):
            self.assertEqual(team_queryset(actor).filter(pk=sheet.pk).exists(), sees, actor.email)

    def test_status_and_week_filters(self):
        first = self.submitted()
        second = self.submitted(week=LAST_MONDAY)
        approve(second.pk, self.manager)
        self.assertEqual(set(team_queryset(self.manager, status='submitted').values_list('pk', flat=True)), {first.pk})
        self.assertEqual(set(team_queryset(self.manager, status='approved,returned').values_list('pk', flat=True)), {second.pk})
        self.assertEqual(set(team_queryset(self.manager, week_start=LAST_MONDAY).values_list('pk', flat=True)), {second.pk})

    def test_detail_is_for_the_owner_and_people_in_scope_only(self):
        sheet = self.submitted()
        self.assertEqual(detail_for(self.employee, sheet)['can_decide'], False)
        self.assertEqual(detail_for(self.manager, sheet)['can_decide'], True)
        self.assertEqual(detail_for(self.hr_admin, sheet)['can_unlock'], False)               # not approved yet
        for outsider in (self.other_branch_hr, self.stranger_manager):
            with self.assertRaises(TimesheetNotFound):
                detail_for(outsider, sheet)

    def test_detail_after_approval_offers_unlock_only_to_hr_with_the_permission(self):
        sheet = self.submitted()
        approve(sheet.pk, self.manager)
        sheet.refresh_from_db()
        self.assertEqual((detail_for(self.hr_admin, sheet)['can_unlock'], detail_for(self.manager, sheet)['can_unlock']), (True, False))
        self.assertEqual(detail_for(self.manager, sheet)['can_decide'], False)
