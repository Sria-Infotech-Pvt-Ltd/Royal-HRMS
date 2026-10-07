"""
Daily Clock In / Clock Out limit — hard cap of exactly one successful Clock In
and one successful Clock Out per employee per attendance day.

Root cause this replaces: PunchService.record_punch() previously only
enforced an "alternating state" rule (_is_clocked_in()) — can't punch IN while
already IN, can't punch OUT while not IN — which is a DIFFERENT, looser rule
that the pre-existing model/frontend both deliberately supported: an employee
could Clock In, Clock Out, then Clock In again (and again), any number of
times per day, as long as each punch alternated correctly. There was also no
DB constraint and no row locking between the "am I already clocked in" check
and the punch INSERT, so two near-simultaneous requests (double-click, retry,
or a direct API race) could both pass the check before either committed.

This suite covers the new PunchService._validate_daily_punch_limit() hard cap
and the select_for_update()-based race protection in record_punch().
"""
from __future__ import annotations

import threading
from datetime import date, time, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    AttendancePunch,
    AttendanceRecord,
    AttendanceSettings,
    AttendanceWorkingHours,
    EmployeeShiftAssignment,
    WorkingHoursPolicy,
)
from apps.attendance.services_attendance import PunchService
from config.test_runner import TEST_COMPANY_CODE

# 'field' mode is always allowed (services_geofencing._validate_no_geofence) —
# no branch/geofence setup needed and, unlike 'wfh', no approved
# WorkFromHomeRequest is required — keeps these tests isolated from fixtures
# this feature has nothing to do with.
MODE = 'field'


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _punch(client: APIClient, punch_type: str):
    return client.post(
        reverse('attendance-punch'),
        {'punch_type': punch_type, 'attendance_mode': MODE},
        format='json',
    )


class DailyPunchLimitTests(TestCase):
    """A-G, I: single-process behaviour via the real HTTP endpoint."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('employee_punch_limit_test')
        self.employee = make_user(
            'punchlimit@test.com', role=role, password='TestPass123!', employee_id='EMPPL001',
        )
        _login(self.client, 'punchlimit@test.com')

    # A. First Clock In succeeds.
    def test_first_clock_in_succeeds(self):
        resp = _punch(self.client, 'IN')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee, punch_type='IN').count(), 1)

    # B. Second Clock In on the same attendance day is rejected.
    def test_second_clock_in_is_rejected(self):
        _punch(self.client, 'IN')
        resp = _punch(self.client, 'IN')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('already clocked in', resp.data['message'].lower())

    # C. First Clock Out succeeds.
    def test_first_clock_out_succeeds(self):
        _punch(self.client, 'IN')
        resp = _punch(self.client, 'OUT')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee, punch_type='OUT').count(), 1)

    # D. Second Clock Out on the same attendance day is rejected.
    def test_second_clock_out_is_rejected(self):
        _punch(self.client, 'IN')
        _punch(self.client, 'OUT')
        resp = _punch(self.client, 'OUT')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('already clocked out today', resp.data['message'].lower())

    # E. Clock In followed by Clock Out succeeds (normal flow).
    def test_clock_in_then_out_succeeds(self):
        in_resp = _punch(self.client, 'IN')
        self.assertEqual(in_resp.status_code, 200, in_resp.data)
        out_resp = _punch(self.client, 'OUT')
        self.assertEqual(out_resp.status_code, 200, out_resp.data)
        self.assertTrue(out_resp.data['data']['day_completed'])

    # F. A second Clock In attempt never creates a duplicate IN punch row.
    def test_repeated_clock_in_requests_do_not_create_duplicates(self):
        _punch(self.client, 'IN')
        for _ in range(3):
            resp = _punch(self.client, 'IN')
            self.assertEqual(resp.status_code, 400)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee, punch_type='IN').count(), 1)

    # G. A second Clock Out attempt never creates a duplicate OUT punch row.
    def test_repeated_clock_out_requests_do_not_create_duplicates(self):
        _punch(self.client, 'IN')
        _punch(self.client, 'OUT')
        for _ in range(3):
            resp = _punch(self.client, 'OUT')
            self.assertEqual(resp.status_code, 400)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee, punch_type='OUT').count(), 1)

    # IN -> OUT -> IN on the SAME day must be rejected (the actual hard-cap
    # rule, distinct from the old alternating-state rule which allowed this).
    def test_in_out_in_on_same_day_is_rejected(self):
        _punch(self.client, 'IN')
        _punch(self.client, 'OUT')
        resp = _punch(self.client, 'IN')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('already completed your attendance', resp.data['message'].lower())
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 2)

    # Clock Out without clocking in first is still rejected (unchanged rule).
    def test_clock_out_without_clock_in_still_rejected(self):
        resp = _punch(self.client, 'OUT')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('not currently clocked in', resp.data['message'].lower())

    # I. A new attendance day allows Clock In again.
    def test_new_attendance_day_allows_clock_in_again(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        # Simulate yesterday's completed cycle directly (bypassing "today"
        # validation, which only ever looks at today's calendar date).
        AttendancePunch.objects.create(
            employee=self.employee, punch_type=AttendancePunch.PUNCH_IN,
            punched_at=timezone.make_aware(timezone.datetime.combine(yesterday, time(9, 0))),
        )
        AttendancePunch.objects.create(
            employee=self.employee, punch_type=AttendancePunch.PUNCH_OUT,
            punched_at=timezone.make_aware(timezone.datetime.combine(yesterday, time(18, 0))),
        )
        resp = _punch(self.client, 'IN')
        self.assertEqual(resp.status_code, 200, resp.data)

    # day_completed is only true once BOTH exist — not after just one punch.
    def test_day_completed_flag_only_true_after_full_cycle(self):
        in_resp = _punch(self.client, 'IN')
        self.assertFalse(in_resp.data['data']['day_completed'])
        out_resp = _punch(self.client, 'OUT')
        self.assertTrue(out_resp.data['data']['day_completed'])


class DailyPunchLimitShiftRegressionTests(TestCase):
    """J, K, L, M: the daily punch limit must behave identically regardless
    of shift assignment — it was already shift-agnostic (date-only) before
    this change, and this confirms wiring the new check in didn't couple it
    to shift resolution by accident."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        settings_row = AttendanceSettings.objects.create(is_active=True)
        AttendanceWorkingHours.objects.create(
            settings=settings_row, shift_start=time(9, 0), shift_end=time(18, 0),
            grace_period_minutes=15, missing_punch_grace_minutes=10, break_duration_minutes=30,
        )
        self.sgt_policy = WorkingHoursPolicy.objects.create(
            name='Test SGT/ICT Shift (punch limit)', policy_code='WH-TEST-PL-SGT',
            start_time=time(7, 30), end_time=time(16, 30),
            break_duration=30, grace_period=15,
            minimum_working_hours='4.00', maximum_working_hours='9.00',
        )
        self.uk_policy = WorkingHoursPolicy.objects.create(
            name='Test UK Shift (punch limit)', policy_code='WH-TEST-PL-UK',
            start_time=time(12, 0), end_time=time(21, 0),
            break_duration=30, grace_period=15,
            minimum_working_hours='4.00', maximum_working_hours='9.00',
        )
        role = make_role('employee_punch_limit_shift_test')
        self.default_emp = make_user('plshift.default@test.com', role=role, password='TestPass123!', employee_id='EMPPLS001')
        self.sgt_emp      = make_user('plshift.sgt@test.com',     role=role, password='TestPass123!', employee_id='EMPPLS002')
        self.uk_emp       = make_user('plshift.uk@test.com',      role=role, password='TestPass123!', employee_id='EMPPLS003')
        EmployeeShiftAssignment.objects.create(employee=self.sgt_emp, policy=self.sgt_policy, effective_from=date.today())
        EmployeeShiftAssignment.objects.create(employee=self.uk_emp,  policy=self.uk_policy,  effective_from=date.today())

    def _cycle_and_assert_capped(self, email):
        client = APIClient()
        _login(client, email)
        in_resp = _punch(client, 'IN')
        self.assertEqual(in_resp.status_code, 200, in_resp.data)
        out_resp = _punch(client, 'OUT')
        self.assertEqual(out_resp.status_code, 200, out_resp.data)
        second_in = _punch(client, 'IN')
        self.assertEqual(second_in.status_code, 400, second_in.data)

    # M. Existing global 09:00-18:00 fallback (unassigned employee) unaffected.
    def test_default_shift_employee_punch_limit(self):
        self._cycle_and_assert_capped('plshift.default@test.com')

    # K. SGT/ICT-assigned employee: punch limit behaves identically.
    def test_sgt_ict_employee_punch_limit(self):
        self._cycle_and_assert_capped('plshift.sgt@test.com')

    # L. UK-assigned employee: punch limit behaves identically.
    def test_uk_employee_punch_limit(self):
        self._cycle_and_assert_capped('plshift.uk@test.com')

    # J. Shift-aware late-arrival detection still runs correctly through the
    # same record_punch() path the new lock/limit check was added to.
    def test_shift_aware_late_detection_still_works_through_the_new_punch_path(self):
        client = APIClient()
        _login(client, 'plshift.sgt@test.com')
        late_in_time = timezone.make_aware(
            timezone.datetime.combine(timezone.localdate(), time(8, 0))  # SGT/ICT starts 07:30, grace 15 -> late after 07:45
        )
        with patch('django.utils.timezone.now', return_value=late_in_time):
            resp = _punch(client, 'IN')
        self.assertEqual(resp.status_code, 200, resp.data)
        record = AttendanceRecord.objects.get(employee=self.sgt_emp, date=timezone.localdate())
        self.assertTrue(record.is_late)


class ConcurrentPunchRaceTests(TransactionTestCase):
    """H. Two genuinely concurrent requests for the same employee/day must
    never both succeed as the same punch type — needs TransactionTestCase
    (real commits, real separate DB connections per thread), not TestCase's
    wrapping-transaction isolation, to exercise actual Postgres row locking."""

    def setUp(self):
        cache.clear()
        role = make_role('employee_punch_race_test')
        self.employee = make_user(
            'punchrace@test.com', role=role, password='TestPass123!', employee_id='EMPPR001',
        )

    def tearDown(self):
        # TransactionTestCase truncates tables itself; just make sure no
        # thread-local connection is left open across tests.
        for conn in connections.all():
            conn.close()

    def test_concurrent_clock_in_requests_cannot_both_succeed(self):
        results = []

        def attempt_clock_in():
            # Each thread gets its own lazily-created DB connection, which
            # starts on the public schema — must activate the test tenant on
            # THIS thread's connection before any ORM query, same as
            # config.test_runner.TenantAwareTestRunner does for the main
            # thread's connection at the start of every test.
            from apps.tenants.models import Client
            connection.set_tenant(Client.objects.get(company_code=TEST_COMPANY_CODE))
            try:
                PunchService.record_punch(self.employee, {
                    'punch_type': 'IN', 'attendance_mode': MODE, 'source': 'web',
                })
                results.append('success')
            except ValueError:
                results.append('rejected')
            finally:
                connections.close_all()

        threads = [threading.Thread(target=attempt_clock_in) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count('success'), 1, results)
        self.assertEqual(results.count('rejected'), 4, results)
        self.assertEqual(
            AttendancePunch.objects.filter(employee=self.employee, punch_type='IN').count(), 1,
        )

    def test_concurrent_clock_out_requests_cannot_both_succeed(self):
        PunchService.record_punch(self.employee, {
            'punch_type': 'IN', 'attendance_mode': MODE, 'source': 'web',
        })
        results = []

        def attempt_clock_out():
            from apps.tenants.models import Client
            connection.set_tenant(Client.objects.get(company_code=TEST_COMPANY_CODE))
            try:
                PunchService.record_punch(self.employee, {
                    'punch_type': 'OUT', 'attendance_mode': MODE, 'source': 'web',
                })
                results.append('success')
            except ValueError:
                results.append('rejected')
            finally:
                connections.close_all()

        threads = [threading.Thread(target=attempt_clock_out) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count('success'), 1, results)
        self.assertEqual(results.count('rejected'), 4, results)
        self.assertEqual(
            AttendancePunch.objects.filter(employee=self.employee, punch_type='OUT').count(), 1,
        )
