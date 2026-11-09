"""
Derived employee lifecycle statuses: Employment Stage, Account Status, onboarding labels, and everything that follows from them
(the punching / request guards, HR attendance eligibility, payroll joining-date gate, joining notifications, directory API).

Everything is derived from existing fields, so none of these tests needs a scheduler to have run.
"""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import services_lifecycle_status as lifecycle
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User
from apps.accounts.services_joining_notifications import notify_joiners
from apps.accounts.tests_employee_scope import make_branch
from apps.hrms.models import SEP_APPROVED, SEP_CANCELLED, SeparationRequest
from apps.notifications.models import Notification

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)
STAGES_BY_NAME = {
    'active': lifecycle.STAGE_ACTIVE, 'joiner_today': lifecycle.STAGE_ACTIVE, 'pre': lifecycle.STAGE_PRE_JOINING,
    'unknown': lifecycle.STAGE_UNKNOWN, 'terminated': lifecycle.STAGE_TERMINATED, 'on_notice': lifecycle.STAGE_ACTIVE,
    'cancelled': lifecycle.STAGE_ACTIVE, 'lwd_today': lifecycle.STAGE_ACTIVE, 'disabled': lifecycle.STAGE_ACTIVE,
}


def _separation(employee, last_day, status=SEP_APPROVED):
    return SeparationRequest.objects.create(
        employee=employee, separation_type='resignation', request_date=TODAY - 40 * DAY, proposed_last_working_day=last_day, status=status,
    )


class LifecycleFixtures(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch_a = make_branch('LC-A', 'Lifecycle A')
        cls.branch_b = make_branch('LC-B', 'Lifecycle B')
        a = cls.branch_a.branch_name
        cls.admin = make_user('lc_admin@test.com', employee_id='LC000', is_superuser=True, branch=a, date_of_joining=TODAY - 400 * DAY)
        cls.manager = make_user('lc_mgr@test.com', role=make_role('lc_mgr', permission_codenames=['leave.approve'], can_manage_team=True),
                                employee_id='LC001', branch=a, date_of_joining=TODAY - 300 * DAY)
        cls.hr_a = make_user('lc_hr_a@test.com', role=make_role('lc_hr_a', permission_codenames=['onboarding.approve', 'employees.view']),
                             employee_id='LC002', branch=a, date_of_joining=TODAY - 300 * DAY)
        cls.hr_b = make_user('lc_hr_b@test.com', role=make_role('lc_hr_b', permission_codenames=['onboarding.approve', 'employees.view']),
                             employee_id='LC003', branch=cls.branch_b.branch_name, date_of_joining=TODAY - 300 * DAY)
        cls.hr_plain = make_user('lc_hr_plain@test.com', role=make_role('lc_hr_plain', permission_codenames=['employees.view']),
                                 employee_id='LC004', branch=a, date_of_joining=TODAY - 300 * DAY)

        def person(name, number, joined, **extra):
            return make_user(f'lc_{name}@test.com', employee_id=f'LC1{number:02d}', branch=a, date_of_joining=joined, **extra)

        cls.active = person('active', 1, TODAY - 30 * DAY)
        cls.joiner_today = person('joiner', 2, TODAY, reporting_manager=cls.manager)
        cls.pre = person('pre', 3, TODAY + 5 * DAY)
        cls.unknown = person('unknown', 4, None)
        cls.terminated = person('terminated', 5, TODAY - 100 * DAY)
        _separation(cls.terminated, TODAY - DAY)
        cls.on_notice = person('notice', 6, TODAY - 100 * DAY)
        _separation(cls.on_notice, TODAY + 3 * DAY)
        cls.cancelled = person('cancelled', 7, TODAY - 100 * DAY)
        _separation(cls.cancelled, TODAY - DAY, status=SEP_CANCELLED)
        cls.lwd_today = person('lwdtoday', 8, TODAY - 100 * DAY)
        _separation(cls.lwd_today, TODAY)
        cls.disabled = person('disabled', 9, TODAY - 50 * DAY, is_active=False)
        # Superusers (pass every permission check) used to exercise the endpoint guards.
        cls.pre_super = person('pre_super', 20, TODAY + 9 * DAY, is_superuser=True, onboarding_status=User.ONBOARDING_COMPLETE)
        cls.unknown_super = person('unknown_super', 21, None, is_superuser=True, onboarding_status=User.ONBOARDING_COMPLETE)
        cls.active_super = person('active_super', 22, TODAY - 9 * DAY, is_superuser=True, onboarding_status=User.ONBOARDING_COMPLETE)
        cls.by_name = {
            'active': cls.active, 'joiner_today': cls.joiner_today, 'pre': cls.pre, 'unknown': cls.unknown, 'terminated': cls.terminated,
            'on_notice': cls.on_notice, 'cancelled': cls.cancelled, 'lwd_today': cls.lwd_today, 'disabled': cls.disabled,
        }

    def api(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client


class EmploymentStageTests(LifecycleFixtures):
    def test_stage_rules(self):
        for name, person in self.by_name.items():
            self.assertEqual(lifecycle.employment_stage(person), STAGES_BY_NAME[name], name)

    def test_is_active_alone_never_makes_someone_inactive_or_terminated(self):
        self.assertEqual(lifecycle.employment_stage(self.disabled), lifecycle.STAGE_ACTIVE)
        self.assertEqual(lifecycle.account_status(self.disabled), lifecycle.ACCOUNT_DISABLED)

    def test_query_builders_agree_with_the_function(self):
        everyone = {p.pk for p in [*self.by_name.values()]}
        for stage in lifecycle.STAGES:
            by_query = set(User.objects.filter(pk__in=everyone).filter(lifecycle.stage_q(stage)).values_list('pk', flat=True))
            by_function = {p.pk for p in self.by_name.values() if lifecycle.employment_stage(p) == stage}
            self.assertEqual(by_query, by_function, stage)

    def test_boundaries_use_the_given_date(self):
        # Joining today: Pre-Joining the day before, Active from today.
        self.assertEqual(lifecycle.employment_stage(self.joiner_today, TODAY - DAY), lifecycle.STAGE_PRE_JOINING)
        self.assertEqual(lifecycle.employment_stage(self.joiner_today, TODAY), lifecycle.STAGE_ACTIVE)
        # Last working day = yesterday: still Active on that day, Terminated from the next.
        self.assertEqual(lifecycle.employment_stage(self.terminated, TODAY - DAY), lifecycle.STAGE_ACTIVE)
        self.assertEqual(lifecycle.employment_stage(self.terminated, TODAY), lifecycle.STAGE_TERMINATED)

    def test_today_is_the_kolkata_date(self):
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')
        self.assertEqual(lifecycle.today(), timezone.localdate())

    def test_a_blank_joining_date_is_never_active_or_eligible(self):
        self.assertTrue(lifecycle.lifecycle_summary(self.unknown)['date_missing'])
        self.assertFalse(User.objects.filter(pk=self.unknown.pk).filter(lifecycle.attendance_eligible_q()).exists())
        self.assertFalse(User.objects.filter(pk=self.unknown.pk).filter(lifecycle.joined_q()).exists())


class AccountAndOnboardingTests(TestCase):
    def test_account_status(self):
        now = timezone.now()
        cases = [
            (dict(is_active=False, activation_pending=False, account_activated_at=now), lifecycle.ACCOUNT_DISABLED),
            (dict(is_active=True, activation_pending=True, account_activated_at=None), lifecycle.ACCOUNT_INVITATION_PENDING),
            (dict(is_active=True, activation_pending=False, account_activated_at=None), lifecycle.ACCOUNT_INVITATION_PENDING),
            (dict(is_active=True, activation_pending=True, account_activated_at=now), lifecycle.ACCOUNT_INVITATION_PENDING),
            (dict(is_active=True, activation_pending=False, account_activated_at=now), lifecycle.ACCOUNT_ACTIVE),
        ]
        for fields, expected in cases:
            self.assertEqual(lifecycle.account_status(User(email='x@test.com', **fields)), expected, fields)

    def test_locked_is_separate_from_disabled(self):
        user = User(email='x@test.com', is_active=True, activation_pending=False, account_activated_at=timezone.now(),
                    locked_until=timezone.now() + datetime.timedelta(minutes=10))
        self.assertTrue(lifecycle.account_locked(user))
        self.assertEqual(lifecycle.account_status(user), lifecycle.ACCOUNT_ACTIVE)
        user.locked_until = timezone.now() - datetime.timedelta(minutes=1)
        self.assertFalse(lifecycle.account_locked(user))

    def test_onboarding_labels_keep_raw_values(self):
        expected = {'pending': 'Not Started', 'draft': 'In Progress', 'submitted': 'Awaiting Review',
                    'rejected': 'Needs Revision', 'complete': 'Completed'}
        for raw, label in expected.items():
            stage = lifecycle.onboarding_stage(User(email='x@test.com', onboarding_status=raw))
            self.assertEqual(lifecycle.ONBOARDING_STAGE_LABELS[stage], label, raw)
        self.assertEqual(sorted(lifecycle.ONBOARDING_STAGE_BY_STATUS), sorted(expected))


class GuardTests(LifecycleFixtures):
    def test_block_message_matrix(self):
        blocked = {
            lifecycle.ACTION_PUNCH: {'pre', 'unknown', 'terminated'},
            lifecycle.ACTION_WFH: {'pre', 'unknown'},
            lifecycle.ACTION_LEAVE: {'pre'},
            lifecycle.ACTION_EXPENSE: {'pre'},
            lifecycle.ACTION_PAYSLIP: {'pre'},
        }
        for action, names in blocked.items():
            for name, person in self.by_name.items():
                message = lifecycle.block_message(person, action)
                self.assertEqual(message is not None, name in names, f'{action} / {name}: {message}')

    def test_messages_are_plain_and_say_why(self):
        self.assertIn('joining date', lifecycle.block_message(self.pre, lifecycle.ACTION_PUNCH))
        self.assertIn('missing', lifecycle.block_message(self.unknown, lifecycle.ACTION_PUNCH))
        self.assertIn('ended', lifecycle.block_message(self.terminated, lifecycle.ACTION_PUNCH))

    def test_record_punch_refuses_before_anything_else(self):
        from apps.attendance.services_attendance import PunchService

        for person in (self.pre, self.unknown, self.terminated):
            with self.assertRaises(ValueError) as caught:
                PunchService.record_punch(person, {'punch_type': 'IN'})
            self.assertEqual(str(caught.exception), lifecycle.block_message(person, lifecycle.ACTION_PUNCH))

    def test_leave_wfh_expense_are_blocked_through_the_api(self):
        pre, unknown, active = self.api(self.pre_super), self.api(self.unknown_super), self.api(self.active_super)
        self.assertEqual(pre.post('/api/leave/requests/', {}, format='json').status_code, 403)
        self.assertEqual(pre.post('/api/wfh/requests/', {}, format='json').status_code, 403)
        self.assertEqual(unknown.post('/api/wfh/requests/', {}, format='json').status_code, 403)
        self.assertEqual(pre.post('/api/expenses/', {}, format='multipart').status_code, 403)
        # A joined employee is not blocked by the lifecycle guard: an empty body is a plain validation error instead.
        for client, url, fmt in ((active, '/api/leave/requests/', 'json'), (active, '/api/wfh/requests/', 'json'), (active, '/api/expenses/', 'multipart')):
            response = client.post(url, {}, format=fmt)
            self.assertNotEqual(response.status_code, 403, (url, response.content))

    def test_own_payslips_are_closed_until_joining(self):
        response = self.api(self.pre_super).get('/api/payroll/my-payslips/')
        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn('joining date', response.json()['message'])
        self.assertNotEqual(self.api(self.active_super).get('/api/payroll/my-payslips/').status_code, 403)


class AttendanceEligibilityTests(LifecycleFixtures):
    def test_attendance_eligible_today(self):
        eligible = set(User.objects.filter(pk__in=[p.pk for p in self.by_name.values()]).filter(lifecycle.attendance_eligible_q())
                       .values_list('pk', flat=True))
        expected = {self.active, self.joiner_today, self.on_notice, self.cancelled, self.lwd_today}
        self.assertEqual(eligible, {p.pk for p in expected})  # not pre, unknown, terminated, disabled

    def test_eligibility_is_as_of_the_day_asked_for(self):
        yesterday = {p.pk for p in User.objects.filter(pk__in=[p.pk for p in self.by_name.values()])
                     .filter(lifecycle.attendance_eligible_q(as_of=TODAY - DAY))}
        self.assertNotIn(self.joiner_today.pk, yesterday)    # had not joined yet
        self.assertIn(self.terminated.pk, yesterday)         # last working day was yesterday: still expected that day
        self.assertIn(self.active.pk, yesterday)

    def test_onboarding_state_does_not_matter_for_attendance(self):
        self.assertEqual(self.joiner_today.onboarding_status, User.ONBOARDING_PENDING)
        self.assertTrue(User.objects.filter(pk=self.joiner_today.pk).filter(lifecycle.attendance_eligible_q()).exists())

    def test_hr_attendance_list_skips_blank_joining_dates_and_shows_not_yet_joined(self):
        from apps.attendance.services_hr import get_attendance_list

        rows = {row['employee_id']: row for row in get_attendance_list({'date': TODAY, 'branch': self.branch_a.branch_name})}
        self.assertIn(self.joiner_today.employee_id, rows)
        self.assertIn(self.active.employee_id, rows)
        self.assertNotIn(self.unknown.employee_id, rows)
        self.assertEqual(rows[self.pre.employee_id]['status'].lower().replace('_', ' '), 'not employed')


class PayrollJoiningGateTests(TestCase):
    CYCLE = SimpleNamespace(cycle_start=datetime.date(2026, 11, 1), cycle_end=datetime.date(2026, 11, 30), branch=None)

    @classmethod
    def setUpTestData(cls):
        cache.clear()

        def employee(name, number, joined, **extra):
            extra.setdefault('onboarding_status', User.ONBOARDING_COMPLETE)
            return make_user(f'pay_{name}@test.com', employee_id=f'PY{number:03d}', branch='Payroll Gate Branch', date_of_joining=joined, **extra)

        cls.before = employee('before', 1, datetime.date(2026, 10, 1))
        cls.first_day = employee('first', 2, datetime.date(2026, 11, 1))
        cls.mid = employee('mid', 3, datetime.date(2026, 11, 16))
        cls.last_day = employee('last', 4, datetime.date(2026, 11, 30))
        cls.after = employee('after', 5, datetime.date(2026, 12, 1))
        cls.blank = employee('blank', 6, None)
        cls.onboarding_incomplete = employee('pending', 7, datetime.date(2026, 10, 1), onboarding_status=User.ONBOARDING_PENDING)

    def test_joining_date_gate(self):
        from apps.payroll.engine.legacy import _eligible_employees_qs

        ids = set(_eligible_employees_qs(self.CYCLE).values_list('employee_id', flat=True))
        for kept in (self.before, self.first_day, self.mid, self.last_day):
            self.assertIn(kept.employee_id, ids, kept.employee_id)
        self.assertNotIn(self.after.employee_id, ids)      # joins after the cycle ends
        self.assertNotIn(self.blank.employee_id, ids)      # blank joining date: never eligible

    def test_existing_onboarding_gate_is_unchanged(self):
        from apps.payroll.engine.legacy import _eligible_employees_qs

        ids = set(_eligible_employees_qs(self.CYCLE).values_list('employee_id', flat=True))
        self.assertNotIn(self.onboarding_incomplete.employee_id, ids)

    def test_proration_window_starts_on_the_right_day(self):
        from apps.payroll.engine.legacy import _proration_start

        cycle = self.CYCLE
        self.assertEqual(_proration_start(self.before, cycle), cycle.cycle_start)       # whole cycle
        self.assertEqual(_proration_start(self.first_day, cycle), cycle.cycle_start)    # first day: whole cycle
        self.assertEqual(_proration_start(self.mid, cycle), datetime.date(2026, 11, 16))  # mid-cycle: from the joining date
        self.assertEqual(_proration_start(self.last_day, cycle), datetime.date(2026, 11, 30))
        after_start = _proration_start(self.after, cycle)
        self.assertGreater(after_start, cycle.cycle_end)                                 # empty window -> factor 0, not 1 day
        days_employed = (cycle.cycle_end - after_start).days + 1
        self.assertLessEqual(days_employed, 0)


class DirectoryApiTests(LifecycleFixtures):
    def _list(self, query: str = 'page_size=50'):
        response = self.api(self.admin).get(f'/api/employees/?{query}')
        self.assertEqual(response.status_code, 200, response.content)
        return {row['employee_id']: row for row in response.json()['data']['results']}

    def test_new_fields_are_present_and_legacy_fields_unchanged(self):
        rows = self._list()
        for name, person in self.by_name.items():
            row = rows[person.employee_id]
            self.assertEqual(row['employment_stage'], STAGES_BY_NAME[name], name)
            for legacy in ('status', 'is_active', 'employment_status', 'onboarding_status', 'awaiting_activation', 'needs_onboarding_data'):
                self.assertIn(legacy, row)
            self.assertEqual(row['employment_status'], User.EMPLOYMENT_STATUS_PROBATION)   # probation/confirmed untouched
        self.assertTrue(rows[self.unknown.employee_id]['date_missing'])
        self.assertEqual(rows[self.disabled.employee_id]['account_status'], 'disabled')
        self.assertEqual(rows[self.active.employee_id]['onboarding_stage'], 'not_started')

    def test_filters(self):
        pre = self._list('page_size=50&employment_stage=pre_joining')
        self.assertIn(self.pre.employee_id, pre)
        self.assertNotIn(self.active.employee_id, pre)
        self.assertIn(self.terminated.employee_id, self._list('page_size=50&employment_stage=terminated'))
        self.assertIn(self.unknown.employee_id, self._list('page_size=50&employment_stage=unknown'))
        self.assertIn(self.disabled.employee_id, self._list('page_size=50&account_status=disabled'))
        self.assertNotIn(self.active.employee_id, self._list('page_size=50&account_status=disabled'))
        self.assertIn(self.active.employee_id, self._list('page_size=50&onboarding_stage=not_started'))
        for bad in ('employment_stage=nope', 'account_status=nope', 'onboarding_stage=nope'):
            self.assertEqual(self.api(self.admin).get(f'/api/employees/?{bad}').status_code, 400, bad)

    def test_legacy_status_filter_still_works(self):
        self.assertEqual(self.api(self.admin).get('/api/employees/?status=onboarding').status_code, 200)
        self.assertEqual(self.api(self.admin).get('/api/employees/?status=bogus').status_code, 400)

    def test_stage_counts_sit_beside_the_legacy_kpis(self):
        data = self.api(self.admin).get('/api/employees/stats/').json()['data']
        for legacy in ('total', 'active', 'probation', 'onboarding', 'notice_period', 'exited'):
            self.assertIn(legacy, data)
        stages = data['stages']
        people = User.objects.exclude(employee_id='').filter(is_active=True)
        expected = {stage: sum(1 for p in people if lifecycle.employment_stage(p) == stage) for stage in lifecycle.STAGES}
        self.assertEqual(stages, expected)
        self.assertEqual(sum(stages.values()), data['total'])   # same people as the legacy total, grouped differently
        self.assertGreaterEqual(stages['unknown'], 1)

    def test_directory_query_count_does_not_grow_with_the_page(self):
        client = self.api(self.admin)
        with CaptureQueriesContext(connection) as small:
            client.get('/api/employees/?page=1&page_size=3')
        with CaptureQueriesContext(connection) as large:
            client.get('/api/employees/?page=1&page_size=50')
        self.assertLessEqual(len(large), len(small) + 2, f'{len(small)} queries for 3 rows, {len(large)} for a full page')
        self.assertLessEqual(len(large), 25)

    def test_external_api_shape_is_unchanged(self):
        from apps.accounts.views_external_api import _basic_employee_dict

        payload = _basic_employee_dict(self.active)
        self.assertEqual(payload['is_active'], True)
        for key in ('employment_stage', 'account_status', 'onboarding_stage', 'date_missing', 'account_locked'):
            self.assertNotIn(key, payload)

    def test_employees_report_gets_two_trailing_lifecycle_columns(self):
        from apps.dashboard.services_reports import _employees

        report = _employees(self.admin, {})
        self.assertEqual(report.headers[-2:], ['Employment stage', 'Account status'])
        self.assertEqual(report.headers[:10][0], 'Employee ID')
        by_id = {row[0]: row for row in report.rows}
        self.assertEqual(by_id[self.pre.employee_id][-2:], ['Pre-Joining', 'Active'])
        self.assertEqual(by_id[self.unknown.employee_id][-2], 'Unknown (Date Missing)')
        self.assertEqual(by_id[self.terminated.employee_id][-2], 'Terminated')


class JoiningNotificationTests(LifecycleFixtures):
    def _system_notices(self, user):
        return Notification.objects.filter(user=user, notification_type='system', module='system')

    def test_employee_manager_and_in_scope_hr_are_told(self):
        result = notify_joiners()
        self.assertEqual(result['failed'], 0)
        recipients = {self.joiner_today: 'profile', self.manager: f'employee:{self.joiner_today.employee_id}',
                      self.hr_a: f'employee:{self.joiner_today.employee_id}'}
        for user, reference in recipients.items():
            notices = list(self._system_notices(user))
            self.assertEqual(len(notices), 1, user.email)
            self.assertEqual(notices[0].reference_id, reference, user.email)
        self.assertFalse(self._system_notices(self.hr_b).exists())       # other branch
        self.assertFalse(self._system_notices(self.hr_plain).exists())   # no onboarding.approve
        self.assertEqual(AuditLog.objects.filter(action='joining_notification_sent', object_id=str(self.joiner_today.pk)).count(), 3)

    def test_notices_are_typed_system_and_never_announcements(self):
        notify_joiners()
        self.assertFalse(Notification.objects.filter(notification_type='announcement').exists())
        self.assertFalse(Notification.objects.filter(module='announcement').exists())
        self.assertEqual(Notification.objects.filter(notification_type='system', module='system').count(), 3)

    def test_running_twice_does_not_notify_twice(self):
        notify_joiners()
        second = notify_joiners()
        self.assertEqual(second['sent'], 0)
        for user in (self.joiner_today, self.manager, self.hr_a):
            self.assertEqual(self._system_notices(user).count(), 1, user.email)

    def test_system_notification_preference_is_respected(self):
        from apps.notifications.models import NotificationSettings

        NotificationSettings.objects.create(user=self.hr_a, is_system_enabled=False)
        result = notify_joiners()
        self.assertFalse(self._system_notices(self.hr_a).exists())          # switched off: nothing delivered
        self.assertTrue(self._system_notices(self.manager).exists())        # others unaffected
        self.assertTrue(self._system_notices(self.joiner_today).exists())
        self.assertEqual(result['sent'], 2)
        marker = AuditLog.objects.get(action='joining_notification_sent', changes__recipient=str(self.hr_a.pk))
        self.assertFalse(marker.changes['delivered'])
        # The marker stops later runs from retrying, and enabling the preference afterwards does not back-fill.
        NotificationSettings.objects.filter(user=self.hr_a).update(is_system_enabled=True)
        notify_joiners()
        self.assertFalse(self._system_notices(self.hr_a).exists())

    def test_default_preference_is_enabled_without_a_settings_row(self):
        from apps.notifications.models import NotificationSettings

        self.assertFalse(NotificationSettings.objects.filter(user=self.hr_a).exists())
        notify_joiners()
        self.assertTrue(self._system_notices(self.hr_a).exists())

    def test_catch_up_window_and_exclusions(self):
        late = make_user('lc_late@test.com', employee_id='LC300', branch=self.branch_a.branch_name, date_of_joining=TODAY - 2 * DAY)
        stale = make_user('lc_stale@test.com', employee_id='LC301', branch=self.branch_a.branch_name, date_of_joining=TODAY - 4 * DAY)
        off = make_user('lc_off@test.com', employee_id='LC302', branch=self.branch_a.branch_name, date_of_joining=TODAY, is_active=False)
        notify_joiners()
        self.assertTrue(self._system_notices(late).exists())        # a missed run is made up for
        self.assertFalse(self._system_notices(stale).exists())      # outside the catch-up window
        self.assertFalse(self._system_notices(off).exists())        # disabled account
        self.assertFalse(self._system_notices(self.pre).exists())   # not joined yet

    def test_task_and_schedule_are_registered_without_a_status_write(self):
        from celery.schedules import crontab

        from apps.accounts.tasks import notify_joining_today
        from apps.platform_core.job_types_registry import ALL_JOB_TYPES

        entry = settings.CELERY_BEAT_SCHEDULE['notify-joining-today']
        self.assertEqual(entry['task'], 'apps.accounts.tasks.notify_joining_today')
        self.assertEqual(entry['schedule'], crontab(hour=6, minute=0))
        self.assertIn('notify_joining_today', {job['code'] for job in ALL_JOB_TYPES})
        before = dict(User.objects.values_list('pk', 'onboarding_status'))
        self.assertIn('sent', notify_joining_today())
        self.assertEqual(dict(User.objects.values_list('pk', 'onboarding_status')), before)   # nothing about status changed

    def test_stage_is_correct_without_the_task_ever_running(self):
        self.assertFalse(Notification.objects.filter(notification_type='system').exists())
        self.assertEqual(lifecycle.employment_stage(self.joiner_today), lifecycle.STAGE_ACTIVE)
        with mock.patch('apps.accounts.services_joining_notifications.notify_joiners', side_effect=RuntimeError('beat down')):
            self.assertEqual(lifecycle.employment_stage(self.joiner_today), lifecycle.STAGE_ACTIVE)
