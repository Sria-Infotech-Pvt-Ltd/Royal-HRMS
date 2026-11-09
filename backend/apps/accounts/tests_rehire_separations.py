"""
Rehire and separation rules for the derived lifecycle (services_lifecycle_status):

  * a separation only applies to the CURRENT employment: its approved last working day must be on or after the current joining date,
    so an older separation from before a rehire is history;
  * the LATEST applicable approved last working day decides, so an extension replaces an earlier last day;
  * a new joining date may not fall before the last working day of the previous employment, and changing the joining date of
    someone with separations on record writes an audit entry.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts import services_lifecycle_status as lifecycle
from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, User
from apps.accounts.tests_employee_scope import make_branch
from apps.hrms.models import SEP_APPROVED, SEP_CANCELLED, SEP_PENDING, SeparationRequest

TODAY = lifecycle.today()
DAY = datetime.timedelta(days=1)


def _ago(days: int) -> datetime.date:
    return TODAY - days * DAY


def _separate(employee: User, last_day: datetime.date, status=SEP_APPROVED) -> SeparationRequest:
    return SeparationRequest.objects.create(
        employee=employee, separation_type='resignation', request_date=last_day - 30 * DAY, proposed_last_working_day=last_day, status=status,
    )


class _People(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch = make_branch('RH-A', 'Rehire Branch').branch_name
        cls.admin = make_user('rh_admin@test.com', employee_id='RH000', is_superuser=True, branch=cls.branch, date_of_joining=_ago(900))
        number = iter(range(1, 100))

        def person(name, joined, *separations, **extra):
            user = make_user(f'rh_{name}@test.com', employee_id=f'RH1{next(number):02d}', branch=cls.branch, date_of_joining=joined, **extra)
            for entry in separations:
                last_day, status = entry if isinstance(entry, tuple) else (entry, SEP_APPROVED)
                _separate(user, last_day, status)
            return user

        # name -> (person, expected stage)
        cls.cases = {
            'left': (person('left', _ago(400), _ago(10)), lifecycle.STAGE_TERMINATED),
            'on_notice': (person('notice', _ago(400), TODAY + 10 * DAY), lifecycle.STAGE_ACTIVE),
            'last_day_today': (person('lastday', _ago(400), TODAY), lifecycle.STAGE_ACTIVE),
            # Rehire: an old separation from before the new joining date is history.
            'rehired': (person('rehired', _ago(60), _ago(200)), lifecycle.STAGE_ACTIVE),
            'rehired_then_left': (person('rehiredleft', _ago(60), _ago(200), _ago(5)), lifecycle.STAGE_TERMINATED),
            # Extension: the latest approved last day decides.
            'extended': (person('extended', _ago(400), _ago(10), TODAY + 20 * DAY), lifecycle.STAGE_ACTIVE),
            'extended_but_still_past': (person('extpast', _ago(400), _ago(30), _ago(10)), lifecycle.STAGE_TERMINATED),
            'shortened_order_does_not_matter': (person('order', _ago(400), TODAY + 20 * DAY, _ago(10)), lifecycle.STAGE_ACTIVE),
            # Several historical separations.
            'history_only': (person('history', _ago(300), _ago(900), _ago(600)), lifecycle.STAGE_ACTIVE),
            'history_plus_current': (person('histcur', _ago(300), _ago(900), _ago(600), _ago(20)), lifecycle.STAGE_TERMINATED),
            'history_plus_current_extended': (person('histext', _ago(300), _ago(900), _ago(600), _ago(20), TODAY + 5 * DAY), lifecycle.STAGE_ACTIVE),
            # Only approved separations count.
            'pending_separation': (person('pend', _ago(400), (_ago(10), SEP_PENDING)), lifecycle.STAGE_ACTIVE),
            'cancelled_separation': (person('canc', _ago(400), (_ago(10), SEP_CANCELLED)), lifecycle.STAGE_ACTIVE),
            # With no joining date nothing can be said to apply: Unknown, not Terminated.
            'no_joining_date': (person('nodoj', None, _ago(10)), lifecycle.STAGE_UNKNOWN),
            # Documented edge: a joining date EQUAL to the old last day leaves that separation applicable.
            'same_day_rehire': (person('sameday', _ago(100), _ago(100)), lifecycle.STAGE_TERMINATED),
        }
        cls.people = {name: user for name, (user, _stage) in cls.cases.items()}

    def api(self) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=self.admin)
        return client


class PureRuleTests(TestCase):
    D = datetime.date

    def test_latest_applicable_last_working_day(self):
        d = self.D
        self.assertEqual(lifecycle.latest_last_working_day(d(2024, 1, 1), [d(2020, 5, 5), d(2022, 6, 30)]), None)             # history only
        self.assertEqual(lifecycle.latest_last_working_day(d(2024, 1, 1), [d(2020, 5, 5), d(2026, 3, 31)]), d(2026, 3, 31))   # one applies
        self.assertEqual(lifecycle.latest_last_working_day(d(2024, 1, 1), [d(2026, 3, 31), d(2026, 9, 30)]), d(2026, 9, 30))  # extension
        self.assertEqual(lifecycle.latest_last_working_day(d(2024, 1, 1), [d(2024, 1, 1)]), d(2024, 1, 1))                   # on the joining date
        self.assertIsNone(lifecycle.latest_last_working_day(None, [d(2026, 3, 31)]))
        self.assertIsNone(lifecycle.latest_last_working_day(d(2024, 1, 1), []))

    def test_separation_has_ended(self):
        d = self.D
        joined, lwds = d(2024, 1, 1), [d(2026, 3, 31)]
        self.assertFalse(lifecycle.separation_has_ended(joined, lwds, d(2026, 3, 31)))   # still employed on the last day
        self.assertTrue(lifecycle.separation_has_ended(joined, lwds, d(2026, 4, 1)))
        self.assertFalse(lifecycle.separation_has_ended(d(2026, 6, 1), lwds, d(2026, 7, 1)))   # rehired after it: history
        self.assertFalse(lifecycle.separation_has_ended(None, lwds, d(2026, 7, 1)))

    def test_attendance_date_problem_codes(self):
        d = self.D
        problem = lifecycle.attendance_date_problem_code
        lwds = [d(2026, 3, 31)]
        self.assertEqual(problem(None, lwds, d(2026, 1, 5)), 'no_joining_date')
        self.assertEqual(problem(d(2024, 1, 1), lwds, d(2023, 12, 31)), 'before_joining')
        self.assertIsNone(problem(d(2024, 1, 1), lwds, d(2024, 1, 1)))                 # the joining day itself
        self.assertIsNone(problem(d(2024, 1, 1), lwds, d(2026, 3, 31)))                # the last working day itself
        self.assertEqual(problem(d(2024, 1, 1), lwds, d(2026, 4, 1)), 'after_last_working_day')
        self.assertIsNone(problem(d(2024, 1, 1), lwds + [d(2026, 9, 30)], d(2026, 4, 1)))   # extended: a later last day applies
        self.assertIsNone(problem(d(2026, 6, 1), lwds, d(2026, 7, 1)))                  # rehired: the old last day is history


class StageRuleTests(_People):
    def test_every_case(self):
        for name, (person, expected) in self.cases.items():
            self.assertEqual(lifecycle.employment_stage(person), expected, name)

    def test_queries_agree_with_the_function(self):
        everyone = User.objects.filter(pk__in=[p.pk for p in self.people.values()])
        for stage in lifecycle.STAGES:
            by_query = set(everyone.filter(lifecycle.stage_q(stage)).values_list('pk', flat=True))
            by_function = {p.pk for name, (p, expected) in self.cases.items() if expected == stage}
            self.assertEqual(by_query, by_function, stage)

    def test_batch_lookup_agrees_with_the_function(self):
        ended = lifecycle.ended_employee_ids(self.people.values())
        expected = {p.pk for _name, (p, stage) in self.cases.items() if stage == lifecycle.STAGE_TERMINATED}
        self.assertEqual(ended, expected)

    def test_boundaries_follow_the_latest_applicable_day(self):
        extended = self.people['extended']
        self.assertEqual(lifecycle.employment_stage(extended, TODAY + 19 * DAY), lifecycle.STAGE_ACTIVE)
        self.assertEqual(lifecycle.employment_stage(extended, TODAY + 21 * DAY), lifecycle.STAGE_TERMINATED)   # after the extended day
        rehired = self.people['rehired']
        self.assertEqual(lifecycle.employment_stage(rehired, _ago(70)), lifecycle.STAGE_PRE_JOINING)             # before the new joining date

    def test_attendance_eligibility(self):
        eligible = set(User.objects.filter(pk__in=[p.pk for p in self.people.values()]).filter(lifecycle.attendance_eligible_q())
                       .values_list('employee_id', flat=True))
        expected = {p.employee_id for name, (p, stage) in self.cases.items() if stage == lifecycle.STAGE_ACTIVE}
        self.assertEqual(eligible, expected)
        for name in ('rehired', 'extended', 'history_only', 'history_plus_current_extended'):
            self.assertIn(self.people[name].employee_id, eligible, name)
        for name in ('left', 'rehired_then_left', 'extended_but_still_past', 'history_plus_current', 'no_joining_date'):
            self.assertNotIn(self.people[name].employee_id, eligible, name)

    def test_the_live_punch_rule_follows_the_same_stages(self):
        for name, (person, stage) in self.cases.items():
            blocked = lifecycle.block_message(person, lifecycle.ACTION_PUNCH) is not None
            self.assertEqual(blocked, stage != lifecycle.STAGE_ACTIVE, name)


class DirectoryAndReportTests(_People):
    def test_directory_uses_the_same_rule_with_prefetched_separations(self):
        response = self.api().get('/api/employees/?page_size=50')
        self.assertEqual(response.status_code, 200, response.content)
        rows = {row['employee_id']: row for row in response.json()['data']['results']}
        for name, (person, expected) in self.cases.items():
            self.assertEqual(rows[person.employee_id]['employment_stage'], expected, name)

    def test_directory_query_count_stays_flat(self):
        client = self.api()
        with CaptureQueriesContext(connection) as small:
            client.get('/api/employees/?page=1&page_size=3')
        with CaptureQueriesContext(connection) as large:
            client.get('/api/employees/?page=1&page_size=50')
        self.assertLessEqual(len(large), len(small) + 2)

    def test_stage_filter_and_counts(self):
        terminated = self.api().get('/api/employees/?page_size=50&employment_stage=terminated').json()['data']['results']
        self.assertEqual({r['employee_id'] for r in terminated},
                         {p.employee_id for _n, (p, stage) in self.cases.items() if stage == lifecycle.STAGE_TERMINATED})
        stages = self.api().get('/api/employees/stats/').json()['data']['stages']
        people = User.objects.exclude(employee_id='').filter(is_active=True)
        self.assertEqual(stages, {s: sum(1 for p in people if lifecycle.employment_stage(p) == s) for s in lifecycle.STAGES})

    def test_employees_report_uses_the_same_rule(self):
        from apps.dashboard.services_reports import _employees

        report = _employees(self.admin, {})
        by_id = {row[0]: row for row in report.rows}
        for name, (person, expected) in self.cases.items():
            self.assertEqual(by_id[person.employee_id][-2], lifecycle.STAGE_LABELS[expected], name)


class JoiningDateChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch = make_branch('RJ-A', 'Rejoin Branch').branch_name
        cls.admin = make_user('rj_admin@test.com', employee_id='RJ000', is_superuser=True, branch=cls.branch, date_of_joining=_ago(900))

        def person(name, number, joined, *last_days, **extra):
            user = make_user(f'rj_{name}@test.com', employee_id=f'RJ{number:03d}', branch=cls.branch, date_of_joining=joined, **extra)
            for last_day in last_days:
                _separate(user, last_day)
            return user

        # Previous employment ended 600 days ago; current employment began 300 days ago.
        cls.rehired = person('rehired', 1, _ago(300), _ago(600))
        cls.current_sep = person('current', 2, _ago(300), TODAY + 30 * DAY)
        cls.no_sep = person('nosep', 3, _ago(300))
        cls.locked = person('locked', 4, _ago(300), _ago(600), onboarding_status=User.ONBOARDING_COMPLETE)

    def _patch(self, employee: User, new_date: datetime.date):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        return client.patch(f'/api/employees/{employee.employee_id}/', {'date_of_joining': new_date.isoformat()}, format='json')

    def _joining_audits(self, employee: User):
        return AuditLog.objects.filter(action='employee_joining_date_changed', object_id=str(employee.id))

    def test_a_date_before_the_previous_last_working_day_is_refused(self):
        response = self._patch(self.rehired, _ago(700))
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('previous employment', response.json()['message'])
        self.assertEqual(User.objects.get(pk=self.rehired.pk).date_of_joining, _ago(300))
        self.assertFalse(self._joining_audits(self.rehired).exists())

    def test_a_date_after_the_previous_last_working_day_is_accepted_and_audited(self):
        response = self._patch(self.rehired, _ago(100))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(User.objects.get(pk=self.rehired.pk).date_of_joining, _ago(100))
        entry = self._joining_audits(self.rehired).get()
        self.assertEqual(entry.changes['joining_date'], {'from': str(_ago(300)), 'to': str(_ago(100))})
        self.assertEqual(entry.changes['approved_last_working_days'], [str(_ago(600))])
        self.assertIsNone(entry.changes['applicable_last_working_day_before'])
        self.assertIsNone(entry.changes['applicable_last_working_day_after'])
        self.assertEqual(entry.user_id, self.admin.pk)
        self.assertTrue(AuditLog.objects.filter(action='employee_updated', object_id=str(self.rehired.id)).exists())   # still written

    def test_a_date_equal_to_the_previous_last_working_day_is_not_earlier_so_it_is_accepted(self):
        self.assertEqual(self._patch(self.rehired, _ago(600)).status_code, 200)

    def test_changing_the_date_of_a_current_separation_is_audited_and_allowed(self):
        response = self._patch(self.current_sep, _ago(400))     # earlier, but not before any PREVIOUS last day
        self.assertEqual(response.status_code, 200, response.content)
        entry = self._joining_audits(self.current_sep).get()
        last_day = str(TODAY + 30 * DAY)
        self.assertEqual((entry.changes['applicable_last_working_day_before'], entry.changes['applicable_last_working_day_after']), (last_day, last_day))

    def test_moving_the_date_past_the_last_working_day_is_a_rehire_and_retires_the_separation(self):
        self.assertEqual(self._patch(self.current_sep, TODAY + 60 * DAY).status_code, 200)
        entry = self._joining_audits(self.current_sep).get()
        self.assertEqual(entry.changes['applicable_last_working_day_before'], str(TODAY + 30 * DAY))
        self.assertIsNone(entry.changes['applicable_last_working_day_after'])

    def test_no_joining_audit_without_separations_or_without_a_change(self):
        self.assertEqual(self._patch(self.no_sep, _ago(200)).status_code, 200)
        self.assertFalse(self._joining_audits(self.no_sep).exists())
        self.assertEqual(self._patch(self.rehired, _ago(300)).status_code, 200)     # same date: nothing changed
        self.assertFalse(self._joining_audits(self.rehired).exists())

    def test_the_existing_lock_after_onboarding_is_unchanged(self):
        response = self._patch(self.locked, _ago(100))
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(self._joining_audits(self.locked).exists())

    def test_validation_helper(self):
        self.assertIsNotNone(lifecycle.validate_joining_date_change(self.rehired, _ago(601)))
        self.assertIsNone(lifecycle.validate_joining_date_change(self.rehired, _ago(600)))
        self.assertIsNone(lifecycle.validate_joining_date_change(self.no_sep, _ago(1000)))
        self.assertIsNone(lifecycle.validate_joining_date_change(self.current_sep, _ago(1000)))   # its separation is current, not previous
        blank = User(email='blank@test.com', date_of_joining=None)
        self.assertIsNone(lifecycle.validate_joining_date_change(blank, _ago(5)))
