"""
HR-initiated attendance entry points follow the employment dates of the employee, for the DAY being recorded:
manual attendance creation, the CSV attendance import, invalid-punch assignment and conversion, and approval of a correction
request that was submitted earlier. A day before the employee joined, a day for someone with no joining date, and a day after their
last working day are refused; a day inside the employment is fine even if the employee has since left. There is no override:
HR corrects the joining date first (an audited edit), then records the day. Existing permission and branch-scope checks still apply.
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.accounts.tests_employee_scope import make_branch
from apps.attendance.models import AttendanceCorrection, AttendanceImportLog, AttendancePunch, AttendanceRecord
from apps.attendance.models import InvalidPunch
from apps.attendance.services_hr_corrections import approve_correction, reject_correction
from apps.attendance.services_hr_ops import _run_import_bulk
from apps.attendance.services_invalid_punch import assign_invalid_punch, convert_invalid_punch, discard_invalid_punch
from apps.hrms.models import SEP_APPROVED, SeparationRequest

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)
IST = ZoneInfo('Asia/Kolkata')


def _ago(days: int) -> datetime.date:
    return TODAY - days * DAY


def _punches_on(employee: User, day: datetime.date, **filters) -> int:
    start = datetime.datetime.combine(day, datetime.time.min, tzinfo=IST)
    return AttendancePunch.objects.filter(employee=employee, punched_at__gte=start, punched_at__lt=start + DAY, **filters).count()


def _separate(employee: User, last_day: datetime.date) -> None:
    SeparationRequest.objects.create(
        employee=employee, separation_type='resignation', request_date=last_day - 30 * DAY,
        proposed_last_working_day=last_day, status=SEP_APPROVED,
    )


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch = make_branch('HE-A', 'HR Entry Branch').branch_name

        def person(name, number, joined, **extra):
            return make_user(f'he_{name}@test.com', employee_id=f'HE{number:03d}', branch=cls.branch, date_of_joining=joined, **extra)

        cls.admin = person('admin', 0, _ago(900), is_superuser=True)
        cls.active = person('active', 1, _ago(30))
        cls.pre = person('pre', 2, TODAY + 5 * DAY)
        cls.unknown = person('unknown', 3, None)
        cls.terminated = person('terminated', 4, _ago(100))
        _separate(cls.terminated, _ago(10))
        cls.rehired = person('rehired', 5, _ago(60))
        _separate(cls.rehired, _ago(200))
        # The checks every HR route runs: (employee, day, allowed?). Days are chosen to sit inside or outside each employment.
        cls.matrix = [
            (cls.active, _ago(1), True), (cls.active, _ago(31), False),                    # the day before joining
            (cls.pre, _ago(1), False),
            (cls.unknown, _ago(1), False),
            (cls.terminated, _ago(20), True), (cls.terminated, _ago(10), True),            # inside, and the last working day itself
            (cls.terminated, _ago(9), False),                                              # the day after
            (cls.rehired, _ago(10), True),                                                 # the new employment
            (cls.rehired, _ago(100), False), (cls.rehired, _ago(250), False),             # between the periods / the old period
        ]

    def api(self) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=self.admin)
        return client


class ManualCreateTests(_Base):
    def _create(self, employee: User, day: datetime.date):
        return self.api().post('/api/attendance/records/create/', {
            'employee_id': employee.employee_id, 'date': day.isoformat(), 'status': 'present',
            'clock_in': '09:00:00', 'clock_out': '18:00:00', 'reason': 'HR entry lifecycle test',
        }, format='json')

    def test_every_stage_and_day(self):
        for employee, day, allowed in self.matrix:
            response = self._create(employee, day)
            exists = AttendanceRecord.objects.filter(employee=employee, date=day).exists()
            if allowed:
                self.assertEqual((response.status_code, exists), (201, True), f'{employee.email} {day}: {response.content}')
            else:
                self.assertEqual((response.status_code, exists), (400, False), f'{employee.email} {day}: {response.content}')

    def test_the_refusal_says_why(self):
        self.assertIn('not joined', self._create(self.pre, _ago(1)).json()['message'])
        self.assertIn('no joining date', self._create(self.unknown, _ago(1)).json()['message'])
        self.assertIn('ended', self._create(self.terminated, _ago(9)).json()['message'])

    def test_permission_and_scope_checks_still_apply_first(self):
        nobody = make_user('he_nobody@test.com', employee_id='HE900', branch=self.branch, date_of_joining=_ago(900))
        client = APIClient()
        client.force_authenticate(user=nobody)
        body = {'employee_id': self.pre.employee_id, 'date': _ago(1).isoformat(), 'status': 'present', 'reason': 'x'}
        self.assertEqual(client.post('/api/attendance/records/create/', body, format='json').status_code, 403)   # permission first
        # The existing single-record scope gate: a team manager reaches only their own direct reports (404 otherwise), and for a
        # direct report the lifecycle check then applies.
        manager = make_user('he_mgr@test.com', role=make_role('he_mgr', permission_codenames=['attendance.create'], can_manage_team=True),
                            employee_id='HE901', branch=self.branch, date_of_joining=_ago(900))
        report = make_user('he_report@test.com', employee_id='HE902', branch=self.branch, date_of_joining=TODAY + 3 * DAY, reporting_manager=manager)
        client.force_authenticate(user=manager)
        stranger = client.post('/api/attendance/records/create/', body, format='json')
        self.assertEqual(stranger.status_code, 404, stranger.content)                       # not their report: refused before any lifecycle message
        own = client.post('/api/attendance/records/create/', {**body, 'employee_id': report.employee_id}, format='json')
        self.assertEqual(own.status_code, 400, own.content)
        self.assertIn('not joined', own.json()['message'])


class CsvImportTests(_Base):
    def _import(self, pairs):
        rows = [{'employee_id': e.employee_id, 'date': d.isoformat(), 'punch_in': '09:00', 'punch_out': '18:00'} for e, d in pairs]
        log = AttendanceImportLog.objects.create(imported_by=self.admin, file_name='lifecycle.csv', total_rows=len(rows))
        _run_import_bulk(log, rows, self.admin)
        log.refresh_from_db()
        return log

    def test_each_row_follows_the_employment_dates(self):
        pairs = [(e, d) for e, d, _allowed in self.matrix]
        log = self._import(pairs)
        allowed_count = sum(1 for _e, _d, allowed in self.matrix if allowed)
        self.assertEqual((log.success_rows, log.failed_rows), (allowed_count, len(pairs) - allowed_count))
        refused_rows = {error['row'] for error in log.errors}
        self.assertEqual(refused_rows, {i for i, (_e, _d, allowed) in enumerate(self.matrix, 1) if not allowed})
        for employee, day, allowed in self.matrix:
            self.assertEqual(AttendanceRecord.objects.filter(employee=employee, date=day).exists(), allowed, f'{employee.email} {day}')

    def test_the_row_error_says_why_and_how_to_fix_it(self):
        log = self._import([(self.pre, _ago(1)), (self.unknown, _ago(1)), (self.terminated, _ago(9))])
        reasons = [error['reason'] for error in sorted(log.errors, key=lambda e: e['row'])]
        self.assertIn('not joined', reasons[0])
        self.assertIn('no joining date', reasons[1])
        self.assertIn('ended', reasons[2])
        self.assertTrue(all('joining date' in error['resolution'] for error in log.errors))

    def test_other_rows_still_import_when_some_are_refused(self):
        log = self._import([(self.active, _ago(2)), (self.pre, _ago(2)), (self.rehired, _ago(3))])
        self.assertEqual((log.success_rows, log.failed_rows), (2, 1))


class InvalidPunchTests(_Base):
    def _punch(self, employee: User, day: datetime.date) -> AttendancePunch:
        moment = datetime.datetime.combine(day, datetime.time(9, 0), tzinfo=IST)
        return AttendancePunch.objects.create(
            employee=employee, punch_type='IN', punched_at=moment, device_time=moment, source='biometric', attendance_mode='office',
        )

    def test_assignment_follows_the_employment_dates(self):
        for employee, day, allowed in self.matrix:
            punch = self._punch(employee, day)
            if allowed:
                self.assertEqual(assign_invalid_punch(str(punch.id), str(self.admin.id), self.admin)['status'], 'assigned')
            else:
                with self.assertRaises(ValueError) as caught:
                    assign_invalid_punch(str(punch.id), str(self.admin.id), self.admin)
                self.assertIn('Discard this punch instead', str(caught.exception), f'{employee.email} {day}')

    def test_conversion_follows_the_employment_dates(self):
        for employee, day, allowed in self.matrix:
            punch = self._punch(employee, day)
            if allowed:
                self.assertEqual(convert_invalid_punch(str(punch.id), 'OUT', '18:00', self.admin)['status'], 'converted', f'{employee.email} {day}')
            else:
                with self.assertRaises(ValueError):
                    convert_invalid_punch(str(punch.id), 'OUT', '18:00', self.admin)
                self.assertEqual(_punches_on(employee, day, punch_type='OUT'), 0, f'{employee.email} {day}')

    def test_discarding_is_always_possible(self):
        punch = self._punch(self.pre, _ago(1))
        self.assertEqual(discard_invalid_punch(str(punch.id), 'not employed yet', self.admin)['status'], 'discarded')

    def test_the_api_answers_with_the_reason(self):
        punch = self._punch(self.unknown, _ago(1))
        client = self.api()
        assigned = client.post(f'/api/attendance/invalid-punches/{punch.id}/assign/', {'assigned_to': str(self.admin.id)}, format='json')
        self.assertEqual(assigned.status_code, 400, assigned.content)
        self.assertIn('Discard this punch instead', assigned.json()['message'])
        converted = client.post(f'/api/attendance/invalid-punches/{punch.id}/convert/', {'target_punch_type': 'OUT', 'target_time': '18:00:00'}, format='json')
        self.assertEqual(converted.status_code, 400, converted.content)
        self.assertEqual(InvalidPunch.objects.filter(punch=punch, status='converted').count(), 0)


class CorrectionApprovalTests(_Base):
    def _correction(self, employee: User, day: datetime.date) -> AttendanceCorrection:
        return AttendanceCorrection.objects.create(
            employee=employee, date=day, punch_type='IN', requested_in_time=datetime.time(9, 30),
            reason=AttendanceCorrection.REASON_CHOICES[0][0],
        )

    def test_approval_follows_the_employment_dates(self):
        for employee, day, allowed in self.matrix:
            correction = self._correction(employee, day)
            if allowed:
                self.assertEqual(approve_correction(str(correction.id), self.admin)['status'], 'approved', f'{employee.email} {day}')
                self.assertEqual(_punches_on(employee, day, source='manual'), 1, f'{employee.email} {day}')
            else:
                with self.assertRaises(PermissionError) as caught:
                    approve_correction(str(correction.id), self.admin)
                self.assertIn('reject it instead', str(caught.exception))
                correction.refresh_from_db()
                self.assertEqual(correction.status, AttendanceCorrection.STATUS_PENDING)           # unchanged: no silent bypass
                self.assertEqual(_punches_on(employee, day, source='manual'), 0, f'{employee.email} {day}')

    def test_rejecting_is_always_possible(self):
        correction = self._correction(self.pre, _ago(1))
        self.assertEqual(reject_correction(str(correction.id), self.admin)['status'], 'rejected')

    def test_the_api_answers_403_with_the_reason_and_leaves_the_request_pending(self):
        correction = self._correction(self.unknown, _ago(1))
        response = self.api().patch(f'/api/attendance/corrections/{correction.id}/review/', {'action': 'approve'}, format='json')
        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn('no joining date', response.json()['message'])
        correction.refresh_from_db()
        self.assertEqual(correction.status, AttendanceCorrection.STATUS_PENDING)
        rejected = self.api().patch(f'/api/attendance/corrections/{correction.id}/review/', {'action': 'reject'}, format='json')
        self.assertEqual(rejected.status_code, 200, rejected.content)
