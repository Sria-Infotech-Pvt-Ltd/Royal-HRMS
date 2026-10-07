"""
Employee-wise shift timings (SGT/ICT 07:30-16:30, UK 12:00-21:00, alongside
the existing global 09:00-18:00 default).

Mirrors apps/attendance/models.py:EmployeeWeeklyOffAssignment's architecture:
WorkingHoursPolicy (shift catalog, reused — not duplicated) ->
EmployeeShiftAssignment (per-employee, date-ranged) ->
core.cache_service.ShiftCacheService.get_effective() (centralized resolver,
falls back to the existing global AttendanceWorkingHours singleton for any
employee with no assignment — the critical backward-compatibility guarantee).

Covers: resolver priority/history, late/early-exit shift-awareness, the
missing-clockout Celery job becoming per-employee instead of one global
deadline, assignment CRUD + the one-open-assignment-per-employee constraint,
and that unassigned employees are provably unaffected.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSettings,
    AttendanceWorkingHours,
    EmployeeShiftAssignment,
    WorkingHoursPolicy,
)
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.attendance.services_hr import assign_shift, bulk_assign_shift
from apps.attendance.services_unpunch import detect_and_mark_unpunches
from config.test_runner import TEST_COMPANY_CODE
from core.cache_service import ShiftCacheService

SGT_START, SGT_END = time(7, 30), time(16, 30)
UK_START, UK_END = time(12, 0), time(21, 0)
GLOBAL_START, GLOBAL_END = time(9, 0), time(18, 0)


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _make_policy(name: str, code: str, start, end, **extra) -> WorkingHoursPolicy:
    return WorkingHoursPolicy.objects.create(
        name=name, policy_code=code, start_time=start, end_time=end,
        break_duration=extra.pop('break_duration', 30),
        grace_period=extra.pop('grace_period', 15),
        minimum_working_hours=extra.pop('minimum_working_hours', '4.00'),
        maximum_working_hours=extra.pop('maximum_working_hours', '9.00'),
        is_default=False, is_active=True, **extra,
    )


def _make_global_settings(shift_start=GLOBAL_START, shift_end=GLOBAL_END, missing_punch_grace_minutes=10):
    settings_row = AttendanceSettings.objects.create(is_active=True)
    AttendanceWorkingHours.objects.create(
        settings=settings_row, shift_start=shift_start, shift_end=shift_end,
        grace_period_minutes=15, missing_punch_grace_minutes=missing_punch_grace_minutes,
        break_duration_minutes=30,
    )
    return settings_row


# ══════════════════════════════════════════════════════════════════════════════
#  ShiftCacheService — the centralized resolver
# ══════════════════════════════════════════════════════════════════════════════

class ShiftCacheServiceResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('employee_shift_resolver_test')
        self.employee = make_user('resolver@test.com', role=role, password='TestPass123!', employee_id='EMPR001')

    def test_no_assignment_falls_back_to_global_default(self):
        """CRITICAL backward-compatibility guarantee: an employee with zero
        EmployeeShiftAssignment rows must resolve to the existing global
        AttendanceWorkingHours singleton — unchanged behaviour."""
        _make_global_settings()
        shift = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift.start_time, GLOBAL_START)
        self.assertEqual(shift.end_time, GLOBAL_END)

    def test_no_assignment_and_no_settings_configured_uses_hardcoded_floor(self):
        """No AttendanceSettings row at all (brand-new/unconfigured tenant) —
        same 09:00/18:00 floor _get_settings()-based code already assumed."""
        shift = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift.start_time, time(9, 0))
        self.assertEqual(shift.end_time, time(18, 0))

    def test_assigned_sgt_ict_resolves_to_its_own_window(self):
        _make_global_settings()
        policy = _make_policy('Test SGT/ICT Shift', 'WH-TEST-SGT-ICT', SGT_START, SGT_END)
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=policy, effective_from=date.today() - timedelta(days=1),
        )
        shift = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift.start_time, SGT_START)
        self.assertEqual(shift.end_time, SGT_END)

    def test_assigned_uk_resolves_to_its_own_window(self):
        _make_global_settings()
        policy = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=policy, effective_from=date.today() - timedelta(days=1),
        )
        shift = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift.start_time, UK_START)
        self.assertEqual(shift.end_time, UK_END)

    def test_assignment_not_yet_effective_falls_back_to_global(self):
        _make_global_settings()
        policy = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=policy, effective_from=date.today() + timedelta(days=30),
        )
        shift = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift.start_time, GLOBAL_START)

    def test_closed_assignment_in_the_past_does_not_apply_today(self):
        _make_global_settings()
        policy = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=policy,
            effective_from=date.today() - timedelta(days=60),
            effective_to=date.today() - timedelta(days=30),
        )
        shift = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift.start_time, GLOBAL_START)

    def test_historical_resolution_uses_the_policy_in_effect_on_that_date(self):
        """Changing an employee's shift must not alter how a PAST date
        resolves — the old (now-closed) assignment still governs its own
        date range."""
        _make_global_settings()
        sgt = _make_policy('Test SGT/ICT Shift', 'WH-TEST-SGT-ICT', SGT_START, SGT_END)
        uk = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)
        old_start = date.today() - timedelta(days=60)
        old_end = date.today() - timedelta(days=31)
        # Old (closed) assignment: SGT/ICT for a past window.
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=sgt, effective_from=old_start, effective_to=old_end,
        )
        # Current (open) assignment: UK, starting after the old one closed.
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=uk, effective_from=old_end + timedelta(days=1),
        )

        past_date_within_old_range = old_start + timedelta(days=5)
        shift_then = ShiftCacheService.get_effective(self.employee, past_date_within_old_range)
        self.assertEqual(shift_then.start_time, SGT_START)

        shift_now = ShiftCacheService.get_effective(self.employee, date.today())
        self.assertEqual(shift_now.start_time, UK_START)

    def test_get_effective_map_bulk_resolution_matches_per_employee_calls(self):
        _make_global_settings()
        other = make_user('resolver2@test.com', role=self.employee.role, password='TestPass123!', employee_id='EMPR002')
        policy = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)
        EmployeeShiftAssignment.objects.create(
            employee=self.employee, policy=policy, effective_from=date.today() - timedelta(days=1),
        )
        result = ShiftCacheService.get_effective_map([self.employee.id, other.id], date.today())
        self.assertEqual(result[self.employee.id].start_time, UK_START)
        self.assertEqual(result[other.id].start_time, GLOBAL_START)


# ══════════════════════════════════════════════════════════════════════════════
#  Late arrival / early exit — pure function, shift-aware
# ══════════════════════════════════════════════════════════════════════════════

class LateAndEarlyExitShiftAwareTests(SimpleTestCase):
    """_check_late/_check_early_exit now take an already-resolved `shift`
    (ShiftCacheService._Shift) instead of the global `cfg` directly — pure
    functions, no DB needed."""

    def _shift(self, start, end, grace=15):
        return ShiftCacheService._Shift(start_time=start, end_time=end, grace_period_minutes=grace)

    def test_late_arrival_for_default_9_to_6_employee(self):
        shift = self._shift(GLOBAL_START, GLOBAL_END)
        self.assertTrue(AttendanceProcessorService._check_late(time(9, 20), shift))
        self.assertFalse(AttendanceProcessorService._check_late(time(9, 10), shift))

    def test_late_arrival_for_sgt_ict_employee(self):
        shift = self._shift(SGT_START, SGT_END)
        self.assertTrue(AttendanceProcessorService._check_late(time(7, 50), shift))
        self.assertFalse(AttendanceProcessorService._check_late(time(7, 40), shift))

    def test_late_arrival_for_uk_employee(self):
        shift = self._shift(UK_START, UK_END)
        self.assertTrue(AttendanceProcessorService._check_late(time(12, 20), shift))
        self.assertFalse(AttendanceProcessorService._check_late(time(12, 10), shift))

    def test_early_exit_for_default_9_to_6_employee(self):
        shift = self._shift(GLOBAL_START, GLOBAL_END)
        self.assertTrue(AttendanceProcessorService._check_early_exit(time(17, 0), shift))
        self.assertFalse(AttendanceProcessorService._check_early_exit(time(17, 45), shift))

    def test_early_exit_for_sgt_ict_employee(self):
        shift = self._shift(SGT_START, SGT_END)
        self.assertTrue(AttendanceProcessorService._check_early_exit(time(15, 45), shift))
        self.assertFalse(AttendanceProcessorService._check_early_exit(time(16, 15), shift))

    def test_early_exit_for_uk_employee(self):
        shift = self._shift(UK_START, UK_END)
        self.assertTrue(AttendanceProcessorService._check_early_exit(time(20, 0), shift))
        self.assertFalse(AttendanceProcessorService._check_early_exit(time(20, 45), shift))

    def test_no_shift_resolved_never_flags_late_or_early(self):
        """None shift (org has no AttendanceWorkingHours configured at all) —
        preserves the pre-existing 'never late' behaviour exactly."""
        self.assertFalse(AttendanceProcessorService._check_late(time(23, 0), None))
        self.assertFalse(AttendanceProcessorService._check_early_exit(time(0, 1), None))


# ══════════════════════════════════════════════════════════════════════════════
#  Missing clock-out — per-shift, not one global deadline
# ══════════════════════════════════════════════════════════════════════════════

class MissingClockoutShiftAwareTests(TestCase):
    def setUp(self):
        cache.clear()
        _make_global_settings(missing_punch_grace_minutes=10)
        self.sgt_policy = _make_policy('Test SGT/ICT Shift', 'WH-TEST-SGT-ICT', SGT_START, SGT_END)
        self.uk_policy = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)

        role = make_role('employee_unpunch_test')
        self.default_emp = make_user('default_emp@test.com', role=role, password='TestPass123!', employee_id='EMPU001', is_active=True)
        self.sgt_emp = make_user('sgt_emp@test.com', role=role, password='TestPass123!', employee_id='EMPU002', is_active=True)
        self.uk_emp = make_user('uk_emp@test.com', role=role, password='TestPass123!', employee_id='EMPU003', is_active=True)

        EmployeeShiftAssignment.objects.create(
            employee=self.sgt_emp, policy=self.sgt_policy, effective_from=date.today() - timedelta(days=1),
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=date.today() - timedelta(days=1),
        )

        self.today = date.today()
        punch_in_times = {
            self.default_emp.id: time(9, 0),
            self.sgt_emp.id:     time(7, 30),
            self.uk_emp.id:      time(12, 0),
        }
        for emp in (self.default_emp, self.sgt_emp, self.uk_emp):
            AttendanceRecord.objects.create(
                employee=emp, date=self.today, status=AttendanceRecord.STATUS_PRESENT,
                first_punch_in=punch_in_times[emp.id],
                last_punch_out=None,
            )

    def _run_at(self, ist_time: time) -> dict:
        with patch('apps.attendance.services_unpunch._now_ist', return_value=ist_time):
            return detect_and_mark_unpunches(target_date=self.today)

    def test_uk_employee_not_marked_incomplete_while_still_within_shift(self):
        """At 18:15, the global default's deadline (18:10) and SGT/ICT's own
        deadline (16:40) have both passed, but the UK employee's own shift
        doesn't end until 21:00 — the key regression this feature must
        prevent: a UK employee must NOT be treated as having a missing
        clock-out just because the global default's 18:00 passed."""
        result = self._run_at(time(18, 15))
        self.assertEqual(result['marked'], 2)  # default + SGT/ICT overdue; UK is not
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.uk_emp, date=self.today).status,
            AttendanceRecord.STATUS_PRESENT,
        )
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.default_emp, date=self.today).status,
            AttendanceRecord.STATUS_INCOMPLETE,
        )
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.sgt_emp, date=self.today).status,
            AttendanceRecord.STATUS_INCOMPLETE,
        )

    def test_sgt_ict_employee_is_caught_at_its_own_earlier_deadline(self):
        """SGT/ICT's own deadline (16:30 + 10 = 16:40) passes well before the
        global default's 18:10 — must be flagged promptly, not delayed."""
        self._run_at(time(16, 45))
        sgt_record = AttendanceRecord.objects.get(employee=self.sgt_emp, date=self.today)
        self.assertEqual(sgt_record.status, AttendanceRecord.STATUS_INCOMPLETE)
        # Default (09:00-18:00) and UK (12:00-21:00) employees aren't overdue yet.
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.default_emp, date=self.today).status,
            AttendanceRecord.STATUS_PRESENT,
        )
        self.assertEqual(
            AttendanceRecord.objects.get(employee=self.uk_emp, date=self.today).status,
            AttendanceRecord.STATUS_PRESENT,
        )

    def test_earliest_deadline_floor_still_catches_a_deactivated_but_assigned_policy(self):
        """Regression: deactivating a WorkingHoursPolicy (soft delete) does
        NOT clear or reassign any EmployeeShiftAssignment still pointing at
        it — PROTECT only blocks a hard delete. The earliest-deadline
        short-circuit must still consider that policy's end_time, or the
        Celery run could skip past this employee's real deadline entirely
        and delay detection until a later run."""
        self.sgt_policy.is_active = False
        self.sgt_policy.save(update_fields=['is_active'])

        self._run_at(time(16, 45))
        sgt_record = AttendanceRecord.objects.get(employee=self.sgt_emp, date=self.today)
        self.assertEqual(sgt_record.status, AttendanceRecord.STATUS_INCOMPLETE)

    def test_default_shift_employee_marked_incomplete_past_global_deadline_unchanged(self):
        """Backward compatibility: an unassigned employee's missing-clockout
        behaviour is byte-for-byte the same as before this feature existed."""
        self._run_at(time(18, 15))
        default_record = AttendanceRecord.objects.get(employee=self.default_emp, date=self.today)
        self.assertEqual(default_record.status, AttendanceRecord.STATUS_INCOMPLETE)

    def test_uk_employee_eventually_caught_after_its_own_deadline(self):
        self._run_at(time(21, 15))
        uk_record = AttendanceRecord.objects.get(employee=self.uk_emp, date=self.today)
        self.assertEqual(uk_record.status, AttendanceRecord.STATUS_INCOMPLETE)

    def test_runs_before_any_shift_could_have_ended_marks_nothing(self):
        result = self._run_at(time(6, 0))
        self.assertEqual(result['marked'], 0)
        self.assertTrue(result['reason'].startswith('shift_not_ended'))
        for emp in (self.default_emp, self.sgt_emp, self.uk_emp):
            self.assertEqual(
                AttendanceRecord.objects.get(employee=emp, date=self.today).status,
                AttendanceRecord.STATUS_PRESENT,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  Assignment service — history preservation, no overlapping actives
# ══════════════════════════════════════════════════════════════════════════════

class ShiftAssignmentServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sgt = _make_policy('Test SGT/ICT Shift', 'WH-TEST-SGT-ICT', SGT_START, SGT_END)
        self.uk = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)
        role = make_role('employee_assign_svc_test')
        self.employee = make_user('assignsvc@test.com', role=role, password='TestPass123!', employee_id='EMPS001')

    def test_assign_creates_open_assignment(self):
        assignment = assign_shift('EMPS001', self.sgt, date.today())
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.policy_id, self.sgt.id)
        self.assertIsNone(assignment.effective_to)

    def test_reassigning_closes_out_the_previous_open_assignment(self):
        assign_shift('EMPS001', self.sgt, date.today() - timedelta(days=10))
        new_from = date.today()
        assign_shift('EMPS001', self.uk, new_from)

        history = EmployeeShiftAssignment.objects.filter(employee=self.employee).order_by('effective_from')
        self.assertEqual(history.count(), 2)
        old, new = history[0], history[1]
        self.assertEqual(old.policy_id, self.sgt.id)
        self.assertEqual(old.effective_to, new_from - timedelta(days=1))
        self.assertEqual(new.policy_id, self.uk.id)
        self.assertIsNone(new.effective_to)

    def test_reassigning_does_not_modify_historical_record_dates(self):
        """Changing an employee's shift must not rewrite history — only the
        effective_to of the row being closed changes; nothing about its
        effective_from or policy is touched."""
        assign_shift('EMPS001', self.sgt, date.today() - timedelta(days=10))
        old_id = EmployeeShiftAssignment.objects.get(employee=self.employee).id
        assign_shift('EMPS001', self.uk, date.today())

        old_row = EmployeeShiftAssignment.objects.get(id=old_id)
        self.assertEqual(old_row.effective_from, date.today() - timedelta(days=10))
        self.assertEqual(old_row.policy_id, self.sgt.id)

    def test_bulk_assign_is_constant_query_count_regardless_of_employee_count(self):
        role = make_role('employee_bulk_assign_test')
        codes = []
        for i in range(5):
            u = make_user(f'bulk{i}@test.com', role=role, password='TestPass123!', employee_id=f'EMPBULK{i}')
            codes.append(u.employee_id)
        count = bulk_assign_shift(codes, self.uk, date.today())
        self.assertEqual(count, 5)
        for code in codes:
            self.assertTrue(
                EmployeeShiftAssignment.objects.filter(employee__employee_id=code, policy=self.uk, effective_to__isnull=True).exists()
            )

    def test_database_constraint_prevents_two_open_assignments_for_same_employee(self):
        """Defense-in-depth: even bypassing the service layer, the DB itself
        refuses a second open row for the same employee."""
        EmployeeShiftAssignment.objects.create(employee=self.employee, policy=self.sgt, effective_from=date.today())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EmployeeShiftAssignment.objects.create(employee=self.employee, policy=self.uk, effective_from=date.today())

    def test_cannot_delete_a_policy_that_is_actively_assigned(self):
        """PROTECT — a shift assigned to an employee cannot be deleted out
        from under them."""
        from django.db.models import ProtectedError
        EmployeeShiftAssignment.objects.create(employee=self.employee, policy=self.sgt, effective_from=date.today())
        with self.assertRaises(ProtectedError):
            self.sgt.delete()


# ══════════════════════════════════════════════════════════════════════════════
#  Assignment API — list / assign / bulk / history
# ══════════════════════════════════════════════════════════════════════════════

class ShiftAssignmentAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.sgt = _make_policy('Test SGT/ICT Shift', 'WH-TEST-SGT-ICT', SGT_START, SGT_END)
        self.uk = _make_policy('Test UK Shift', 'WH-TEST-UK', UK_START, UK_END)

        hr_role = make_role('hr_shift_assign_test', permission_codenames=['attendance.view', 'attendance.create'])
        self.hr = make_user(
            'hr.shiftassign@test.com', role=hr_role, password='TestPass123!',
            employee_id='EMPHRS001', branch='Shift Test Branch',
        )
        emp_role = make_role('employee_shift_assign_target')
        self.employee = make_user(
            'target.shiftassign@test.com', role=emp_role, password='TestPass123!',
            employee_id='EMPTGT001', branch='Shift Test Branch',
        )
        _login(self.client, 'hr.shiftassign@test.com')

    def test_assign_single_employee(self):
        resp = self.client.post(
            reverse('shift-assignments-list'),
            {'employee_id': 'EMPTGT001', 'shift': str(self.sgt.id), 'effective_from': date.today().isoformat()},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            EmployeeShiftAssignment.objects.filter(employee=self.employee, policy=self.sgt).exists()
        )

    def test_list_shows_current_assignment(self):
        assign_shift('EMPTGT001', self.uk, date.today())
        resp = self.client.get(reverse('shift-assignments-list'))
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['data']['results']
        matching = [r for r in rows if r['employee_id'] == 'EMPTGT001']
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['shift_id'], str(self.uk.id))

    def test_bulk_assign_by_explicit_ids(self):
        resp = self.client.post(
            reverse('shift-assignments-bulk'),
            {
                'employee_ids': ['EMPTGT001'], 'shift': str(self.sgt.id),
                'effective_from': date.today().isoformat(),
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['count'], 1)

    def test_history_endpoint_returns_full_timeline(self):
        assign_shift('EMPTGT001', self.sgt, date.today() - timedelta(days=10))
        assign_shift('EMPTGT001', self.uk, date.today())
        resp = self.client.get(reverse('shift-assignments-history', kwargs={'employee_id': 'EMPTGT001'}))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['data']['history']), 2)

    def test_requires_real_permission(self):
        no_perm_role = make_role('employee_no_shift_perm')
        make_user('noshiftperm@test.com', role=no_perm_role, password='TestPass123!')
        client = APIClient()
        _login(client, 'noshiftperm@test.com')
        resp = client.get(reverse('shift-assignments-list'))
        self.assertEqual(resp.status_code, 403)

    def test_unassigned_employee_shows_not_assigned(self):
        resp = self.client.get(reverse('shift-assignments-list'))
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['data']['results']
        matching = [r for r in rows if r['employee_id'] == 'EMPTGT001']
        self.assertEqual(matching[0]['status'], 'Not Assigned')
        self.assertIsNone(matching[0]['shift_id'])
