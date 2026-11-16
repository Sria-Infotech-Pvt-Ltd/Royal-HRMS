"""Phase 7: timesheet notifications (in-app + email) respect settings and never break a decision; Friday and Monday reminders send once.
No real email is sent: the queue call that would deliver it is replaced by a recorder."""
from __future__ import annotations

import datetime
from unittest import mock

from apps.accounts.factories import make_role, make_user
from apps.attendance.models_timesheet import Timesheet
from apps.attendance.services_timesheet import save_draft, submit
from apps.attendance.services_timesheet_decisions import approve, return_to_employee, unlock
from apps.attendance.services_timesheet_reminders import approver_key, employee_key, send_approver_reminders, send_employee_reminders
from apps.attendance.tests_timesheet_support import MONDAY, TimesheetTestBase, assign, cell, internal_line, pinned_today, project_line
from apps.hrms.models import STATUS_APPROVED as LEAVE_APPROVED
from apps.hrms.models import LeaveRequest, SEP_APPROVED, SeparationRequest
from apps.notifications.models import Notification, NotificationSettings

FRIDAY = MONDAY + datetime.timedelta(days=4)
HR_ACCESS = ['timesheet.approve', 'timesheet.unlock', 'timesheet.report']
EMAIL_TASK = 'apps.notifications.tasks.send_lifecycle_email_task.apply_async'


class NotifyBase(TimesheetTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.hr_admin = make_user('ts_n_hr@test.com', make_role('ts_n_hr', permission_codenames=HR_ACCESS, can_manage_branch=True), employee_id='TSH020', branch='TS-Branch')

    def setUp(self):
        super().setUp()
        assign(self.employee, 1, 'Alpha')
        patcher = mock.patch(EMAIL_TASK)
        self.queued = patcher.start()
        self.addCleanup(patcher.stop)

    def do(self, action, *args, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return action(*args, **kwargs)

    def save_and_submit(self, hours='8', week=MONDAY):
        with pinned_today():
            save_draft(self.employee, week, {'lines': [project_line(1, cell(0, hours, week=week), billable=True)]})
            self.do(submit, self.employee, week)
        return Timesheet.objects.get(employee=self.employee, week_start=week)

    def notices(self, user, kind=None):
        rows = Notification.objects.filter(user=user, module='timesheet')
        return rows.filter(notification_type=kind) if kind else rows

    def emails(self):
        """(template name, recipient user id, context) of every email queued so far."""
        return [(call.kwargs['args'][1], call.kwargs['args'][0], call.kwargs['args'][2]) for call in self.queued.call_args_list]


class EventNotificationTests(NotifyBase):
    def test_submit_tells_the_approver_in_app_and_by_email_and_nobody_else(self):
        sheet = self.save_and_submit()
        notice = self.notices(self.manager, 'timesheet_submitted').get()
        self.assertEqual((notice.reference_id, notice.created_by), (f'{MONDAY}:{sheet.pk}', self.employee))      # the week lets the bell open the right sheet
        self.assertIn('9 Nov – 15 Nov 2026', notice.message)
        self.assertIn('8.00 hours', notice.message)
        self.assertEqual([(name, uid) for name, uid, _ in self.emails()], [('timesheet_submitted', self.manager.pk)])
        context = self.emails()[0][2]
        self.assertEqual((context['employee_name'], context['total_hours'], context['billable_hours'], context['late_note']), ('Test User', '8.00', '8.00', ''))
        self.assertFalse(self.notices(self.employee).exists())

    def test_a_late_submission_says_so_in_the_email(self):
        with pinned_today(datetime.date(2026, 11, 16)):                       # the Monday after
            save_draft(self.employee, MONDAY, {'lines': [project_line(1, cell(0, '8'))]})
            self.do(submit, self.employee, MONDAY)
        self.assertIn('after the Friday due date', self.emails()[0][2]['late_note'])

    def test_a_resubmission_is_worded_as_one(self):
        sheet = self.save_and_submit()
        self.do(return_to_employee, sheet.pk, self.manager, 'Fix Monday')
        self.queued.reset_mock()
        with pinned_today():
            save_draft(self.employee, MONDAY, {'lines': [project_line(1, cell(0, '7'))]})
            self.do(submit, self.employee, MONDAY)
        self.assertEqual(self.notices(self.manager, 'timesheet_submitted').order_by('created_at').last().title, 'Timesheet resubmitted for approval')

    def test_approval_tells_the_employee_only(self):
        sheet = self.save_and_submit()
        self.queued.reset_mock()
        self.do(approve, sheet.pk, self.manager)
        approved = self.notices(self.employee, 'timesheet_approved').get()
        self.assertIn('was approved by', approved.message)
        self.assertEqual(approved.reference_id, f'{MONDAY}:{sheet.pk}')
        self.assertEqual([(name, uid) for name, uid, _ in self.emails()], [('timesheet_approved', self.employee.pk)])
        self.assertEqual(self.notices(self.manager, 'timesheet_approved').count(), 0)

    def test_sending_back_carries_the_reason(self):
        sheet = self.save_and_submit()
        self.queued.reset_mock()
        self.do(return_to_employee, sheet.pk, self.manager, 'Wrong project on Monday')
        notice = self.notices(self.employee, 'timesheet_returned').get()
        self.assertIn('Wrong project on Monday', notice.message)
        self.assertEqual(notice.reference_id, f'{MONDAY}:{sheet.pk}')
        name, uid, context = self.emails()[0]
        self.assertEqual((name, uid, context['reason'], context['decided_by']), ('timesheet_returned', self.employee.pk, 'Wrong project on Monday', 'Test User'))

    def test_reopening_by_hr_is_worded_as_a_reopen(self):
        sheet = self.save_and_submit()
        self.do(approve, sheet.pk, self.manager)
        self.queued.reset_mock()
        self.do(unlock, sheet.pk, self.hr_admin, 'Billable flag was wrong')
        notice = self.notices(self.employee, 'timesheet_returned').get()
        self.assertEqual(notice.title, 'Timesheet reopened')
        self.assertIn('reopened by HR', notice.message)

    def test_nothing_is_sent_when_the_action_is_refused(self):
        with pinned_today():
            save_draft(self.employee, MONDAY, {'lines': [project_line(1, cell(0, '0'))]})
            with self.assertRaises(Exception):
                self.do(submit, self.employee, MONDAY)                          # no hours: refused
        self.assertFalse(Notification.objects.filter(module='timesheet').exists())
        self.queued.assert_not_called()

    def test_no_real_email_is_sent(self):
        from django.core import mail
        self.save_and_submit()
        self.assertEqual(len(mail.outbox), 0)


class PreferenceAndFailureTests(NotifyBase):
    def test_an_approver_who_switched_approval_notices_off_gets_neither_notice_nor_email(self):
        NotificationSettings.objects.create(user=self.manager, is_approval_enabled=False)
        self.save_and_submit()
        self.assertFalse(self.notices(self.manager).exists())
        self.assertEqual(self.emails(), [])

    def test_an_employee_who_switched_attendance_notices_off_gets_none_of_the_decisions(self):
        NotificationSettings.objects.create(user=self.employee, is_attendance_enabled=False)
        sheet = self.save_and_submit()
        self.queued.reset_mock()
        self.do(approve, sheet.pk, self.manager)
        self.assertFalse(self.notices(self.employee).exists())
        self.assertEqual(self.emails(), [])

    def test_one_category_off_does_not_silence_the_other(self):
        NotificationSettings.objects.create(user=self.manager, is_attendance_enabled=False)        # approval is still on
        self.save_and_submit()
        self.assertEqual(self.notices(self.manager, 'timesheet_submitted').count(), 1)

    def test_a_failing_notifier_never_undoes_the_submit(self):
        with mock.patch('apps.notifications.signals._notify', side_effect=RuntimeError('boom')):
            sheet = self.save_and_submit()
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, 'submitted')
        self.assertEqual(sheet.events.count(), 1)

    def test_a_failing_notifier_never_undoes_an_approval(self):
        sheet = self.save_and_submit()
        with mock.patch('apps.notifications.signals._notify', side_effect=RuntimeError('boom')):
            self.do(approve, sheet.pk, self.manager)
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, 'approved')

    def test_a_down_email_queue_never_undoes_the_decision(self):
        self.queued.side_effect = ConnectionError('broker down')
        sheet = self.save_and_submit()
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, 'submitted')
        self.assertEqual(self.notices(self.manager, 'timesheet_submitted').count(), 1)             # the in-app notice still arrived


class EmployeeReminderTests(NotifyBase):
    def reminded(self):
        return set(Notification.objects.filter(module='timesheet', notification_type='timesheet_reminder', reference_id=employee_key(MONDAY)).values_list('user__email', flat=True))

    def test_reminds_everyone_who_has_not_submitted_and_nobody_who_has(self):
        done = make_user('ts_done@test.com', employee_id='TSE010', branch='TS-Branch')
        approved = make_user('ts_apprd@test.com', employee_id='TSE011', branch='TS-Branch')
        draft = make_user('ts_draft@test.com', employee_id='TSE012', branch='TS-Branch')
        Timesheet.objects.create(employee=done, week_start=MONDAY, status='submitted')
        Timesheet.objects.create(employee=approved, week_start=MONDAY, status='approved')
        Timesheet.objects.create(employee=draft, week_start=MONDAY, status='draft')
        send_employee_reminders(as_of=FRIDAY)
        got = self.reminded()
        self.assertIn(self.employee.email, got)
        self.assertIn(draft.email, got)
        self.assertNotIn(done.email, got)
        self.assertNotIn(approved.email, got)

    def test_a_returned_sheet_is_still_outstanding(self):
        Timesheet.objects.create(employee=self.employee, week_start=MONDAY, status='returned')
        send_employee_reminders(as_of=FRIDAY)
        self.assertIn(self.employee.email, self.reminded())

    def test_people_not_expected_at_work_are_left_out(self):
        pre = make_user('ts_pre@test.com', employee_id='TSE020', date_of_joining=datetime.date(2026, 12, 1))
        gone = make_user('ts_gone@test.com', employee_id='TSE021')
        SeparationRequest.objects.create(employee=gone, separation_type='resignation', request_date=datetime.date(2026, 9, 1),
                                         proposed_last_working_day=datetime.date(2026, 10, 31), status=SEP_APPROVED)
        inactive = make_user('ts_off@test.com', employee_id='TSE022', is_active=False)
        unactivated = make_user('ts_new@test.com', employee_id='TSE023', account_activated_at=None)
        send_employee_reminders(as_of=FRIDAY)
        got = self.reminded()
        for person in (pre, gone, inactive, unactivated):
            self.assertNotIn(person.email, got, person.email)

    def test_someone_on_leave_the_whole_week_is_left_out_but_part_of_the_week_is_not(self):
        away = make_user('ts_away@test.com', employee_id='TSE030')
        partly = make_user('ts_part@test.com', employee_id='TSE031')
        LeaveRequest.objects.create(employee=away, leave_type='casual', start_date=MONDAY, end_date=FRIDAY, total_days=5, reason='x', status=LEAVE_APPROVED)
        LeaveRequest.objects.create(employee=partly, leave_type='casual', start_date=MONDAY, end_date=MONDAY + datetime.timedelta(days=2), total_days=3, reason='x', status=LEAVE_APPROVED)
        send_employee_reminders(as_of=FRIDAY)
        got = self.reminded()
        self.assertNotIn(away.email, got)
        self.assertIn(partly.email, got)

    def test_running_it_again_never_reminds_anyone_twice(self):
        send_employee_reminders(as_of=FRIDAY)
        first = Notification.objects.filter(notification_type='timesheet_reminder').count()
        second = send_employee_reminders(as_of=FRIDAY)
        self.assertEqual(Notification.objects.filter(notification_type='timesheet_reminder').count(), first)
        self.assertEqual(second['attempted'], 0)
        self.assertGreater(second['already_reminded'], 0)

    def test_a_new_week_gets_a_new_reminder(self):
        send_employee_reminders(as_of=FRIDAY)
        send_employee_reminders(as_of=FRIDAY + datetime.timedelta(days=7))
        weeks = set(Notification.objects.filter(user=self.employee, notification_type='timesheet_reminder').values_list('reference_id', flat=True))
        self.assertEqual(weeks, {employee_key(MONDAY), employee_key(MONDAY + datetime.timedelta(days=7))})

    def test_a_person_who_turned_the_notices_off_gets_none(self):
        NotificationSettings.objects.create(user=self.employee, is_attendance_enabled=False)
        send_employee_reminders(as_of=FRIDAY)
        self.assertNotIn(self.employee.email, self.reminded())


class ApproverReminderTests(NotifyBase):
    def waiting(self):
        return Notification.objects.filter(user=self.manager, notification_type='timesheet_reminder', module='timesheet')

    def test_the_approver_is_told_how_many_are_waiting_and_the_oldest(self):
        self.save_and_submit(week=MONDAY - datetime.timedelta(days=7))
        self.save_and_submit()
        send_approver_reminders(as_of=MONDAY + datetime.timedelta(days=7))
        notice = self.waiting().get()
        self.assertIn('2 timesheets', notice.message)
        self.assertIn('02 Nov', notice.message)
        self.assertEqual(notice.reference_id, approver_key(MONDAY + datetime.timedelta(days=7)))

    def test_a_single_sheet_is_worded_in_the_singular(self):
        self.save_and_submit()
        send_approver_reminders(as_of=MONDAY)
        self.assertIn('1 timesheet waiting', self.waiting().get().message)

    def test_decided_sheets_do_not_count_and_an_approver_with_nothing_waiting_is_left_alone(self):
        sheet = self.save_and_submit()
        self.do(approve, sheet.pk, self.manager)
        Notification.objects.all().delete()
        send_approver_reminders(as_of=MONDAY)
        self.assertFalse(self.waiting().exists())

    def test_once_per_approver_per_day_but_again_the_next_day(self):
        self.save_and_submit()
        send_approver_reminders(as_of=MONDAY)
        again = send_approver_reminders(as_of=MONDAY)
        self.assertEqual((self.waiting().count(), again['attempted']), (1, 0))
        send_approver_reminders(as_of=MONDAY + datetime.timedelta(days=1))
        self.assertEqual(self.waiting().count(), 2)

    def test_an_inactive_approver_and_a_person_who_turned_it_off_are_skipped(self):
        self.save_and_submit()
        NotificationSettings.objects.create(user=self.manager, is_approval_enabled=False)
        send_approver_reminders(as_of=MONDAY)
        self.assertFalse(self.waiting().exists())
        NotificationSettings.objects.all().delete()
        self.manager.is_active = False
        self.manager.save()
        send_approver_reminders(as_of=MONDAY)
        self.assertFalse(self.waiting().exists())


class ScheduleTests(NotifyBase):
    def test_the_tasks_are_registered_and_scheduled_for_friday_and_monday(self):
        from celery import current_app
        from django.conf import settings

        import apps.attendance.tasks  # noqa: F401  (Celery's own autodiscovery imports this module in a worker)

        schedule = settings.CELERY_BEAT_SCHEDULE
        friday, monday = schedule['timesheet-employee-reminder'], schedule['timesheet-approver-reminder']
        self.assertEqual((friday['task'], monday['task']), ('apps.attendance.tasks.send_timesheet_employee_reminders', 'apps.attendance.tasks.send_timesheet_approver_reminders'))
        self.assertEqual(({str(d) for d in friday['schedule'].day_of_week}, {str(d) for d in monday['schedule'].day_of_week}), ({'5'}, {'1'}))
        for name in (friday['task'], monday['task']):
            self.assertIn(name, current_app.tasks)

    def test_the_tasks_run_and_report(self):
        from apps.attendance.tasks import send_timesheet_approver_reminders, send_timesheet_employee_reminders

        # .run() calls the task body directly. Going through .apply() would fire the project's Celery signal that closes
        # database connections after every task, which closes the test's own connection.
        self.assertIn('attempted', send_timesheet_employee_reminders.run())
        self.assertIn('attempted', send_timesheet_approver_reminders.run())
