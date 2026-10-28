"""
Attendance CSV export, month-wise: GET /api/attendance/export/?month=YYYY-MM.

One row per in-scope employee per day, same columns as the daily export.
Days with an AttendanceRecord export the record; days without one follow the
employee calendar: Holiday, then Weekly Off, then approved leave, else Absent.
Both daily and monthly export require attendance.export.
"""
from __future__ import annotations

import csv
import datetime
import io
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendancePunch, WeeklyDayPolicy
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, Holiday, LeaveRequest
from config.test_runner import TEST_COMPANY_CODE

IST = ZoneInfo('Asia/Kolkata')
BRANCH = 'Month Export Branch'
OTHER_BRANCH = 'Month Export Other'
EXPORT_PERMS = ['attendance.view', 'attendance.export']


def _at(day: date, hh: int) -> datetime.datetime:
    return datetime.datetime(day.year, day.month, day.day, hh, 0, tzinfo=IST)


def _rows(resp) -> list[dict]:
    return list(csv.DictReader(io.StringIO(resp.content.decode('utf-8').lstrip('﻿'))))


class MonthExportTests(TestCase):
    def setUp(self):
        cache.clear()
        # Weekly off = Sunday only (explicit default policy, so the test does not
        # depend on the org fallback).
        WeeklyDayPolicy.objects.update(is_default=False)
        WeeklyDayPolicy.objects.create(name='Sun off', policy_code='MEX-SUN', saturday='working',
                                       sunday='off', is_default=True)
        staff = make_role('mex_staff')
        self.emp = make_user('mex.emp@test.com', role=staff, employee_id='MEX001', full_name='Alpha Emp',
                             branch=BRANCH, department='Ops')
        self.emp2 = make_user('mex.emp2@test.com', role=staff, employee_id='MEX002', full_name='Beta Emp',
                              branch=BRANCH, department='Sales')
        self.outsider = make_user('mex.out@test.com', role=staff, employee_id='MEX009', full_name='Other Emp',
                                  branch=OTHER_BRANCH, department='Ops')
        self.hr = make_user('mex.hr@test.com', role=make_role('mex_hr', permission_codenames=EXPORT_PERMS),
                            employee_id='MEXHR', full_name='Month HR', branch=BRANCH)
        self.client = APIClient()

    def _login(self, user):
        resp = self.client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email,
                                                   'password': 'TestPass123!'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _export(self, user=None, **params):
        self._login(user or self.hr)
        return self.client.get(reverse('hr-attendance-export'), params)

    def _work(self, emp, day, label):
        AttendancePunch.objects.create(employee=emp, punch_type=AttendancePunch.PUNCH_IN,
                                       punched_at=_at(day, 9), location_label=label, accuracy=Decimal('10'))
        AttendancePunch.objects.create(employee=emp, punch_type=AttendancePunch.PUNCH_OUT,
                                       punched_at=_at(day, 18), location_label=label)
        AttendanceProcessorService.process_day(emp, day)

    def _by(self, rows, employee_id):
        return {r['date']: r for r in rows if r['employee_id'] == employee_id}

    # ── Month boundaries and rows ─────────────────────────────────────────────

    def test_one_row_per_employee_per_day_within_month(self):
        self._work(self.emp, date(2026, 8, 31), 'Before')   # outside the month
        self._work(self.emp, date(2026, 10, 1), 'After')    # outside the month
        resp = self._export(month='2026-09')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Disposition'], 'attachment; filename="attendance_2026-09.csv"')
        rows = _rows(resp)
        mine = self._by(rows, 'MEX001')
        self.assertEqual(len(mine), 30)
        self.assertIn('01-09-2026', mine)
        self.assertIn('30-09-2026', mine)
        self.assertNotIn('31-08-2026', mine)
        self.assertNotIn('01-10-2026', mine)

    def test_leap_february_has_29_days(self):
        rows = _rows(self._export(month='2024-02'))
        self.assertEqual(len(self._by(rows, 'MEX001')), 29)

    def test_current_month_stops_at_today(self):
        today = date.today()
        rows = _rows(self._export(month=today.strftime('%Y-%m')))
        self.assertEqual(len(self._by(rows, 'MEX001')), today.day)

    def test_same_columns_as_daily_export(self):
        monthly = self._export(month='2026-09')
        daily = self._export(date='2026-09-01')
        self.assertEqual(monthly.content.decode('utf-8').splitlines()[0], daily.content.decode('utf-8').splitlines()[0])

    # ── Statuses for days with and without records ────────────────────────────

    def test_empty_days_follow_calendar_rules(self):
        Holiday.objects.create(name='Test Holiday', date=date(2026, 9, 15))  # company-wide, a Tuesday
        LeaveRequest.objects.create(employee=self.emp, leave_type='casual', start_date=date(2026, 9, 21),
                                    end_date=date(2026, 9, 22), total_days=Decimal('2'), reason='x',
                                    status=REQ_APPROVED)
        LeaveRequest.objects.create(employee=self.emp, leave_type='casual', start_date=date(2026, 9, 24),
                                    end_date=date(2026, 9, 24), total_days=Decimal('1'), reason='x',
                                    status=REQ_PENDING)
        self._work(self.emp, date(2026, 9, 1), 'Office')
        mine = self._by(_rows(self._export(month='2026-09')), 'MEX001')

        self.assertEqual(mine['01-09-2026']['status'], 'Present')
        self.assertEqual(mine['15-09-2026']['status'], 'Holiday')
        self.assertEqual(mine['06-09-2026']['status'], 'Weekly Off')      # Sunday
        self.assertEqual(mine['05-09-2026']['status'], 'Absent')          # Saturday is a working day here
        self.assertEqual(mine['21-09-2026']['status'], 'On Leave')
        self.assertEqual(mine['22-09-2026']['status'], 'On Leave')
        self.assertEqual(mine['24-09-2026']['status'], 'Absent')          # pending leave does not count
        self.assertEqual(mine['02-09-2026']['status'], 'Absent')
        for empty in ('02-09-2026', '15-09-2026'):
            self.assertEqual((mine[empty]['clock_in'], mine[empty]['clock_out'], mine[empty]['clock_in_location']),
                             ('', '', ''))

    def test_record_status_is_used_when_present(self):
        self._work(self.emp, date(2026, 9, 6), 'Office')  # worked on a Sunday
        mine = self._by(_rows(self._export(month='2026-09')), 'MEX001')
        self.assertNotEqual(mine['06-09-2026']['status'], 'Weekly Off')
        self.assertEqual(mine['06-09-2026']['clock_in'], '09:00')

    # ── Locations per date ────────────────────────────────────────────────────

    def test_locations_and_accuracy_belong_to_each_date(self):
        # Same clock times on both days — locations must not leak across dates.
        self._work(self.emp, date(2026, 9, 1), 'Place One')
        self._work(self.emp, date(2026, 9, 2), 'Place Two')
        mine = self._by(_rows(self._export(month='2026-09')), 'MEX001')
        self.assertEqual(mine['01-09-2026']['clock_in_location'], 'Place One')
        self.assertEqual(mine['02-09-2026']['clock_out_location'], 'Place Two')
        self.assertEqual(mine['01-09-2026']['clock_in_gps_accuracy_m'], '10')
        self.assertEqual(mine['01-09-2026']['clock_out_gps_accuracy_m'], '')

    # ── Access restrictions ───────────────────────────────────────────────────

    def test_branch_scoped_user_cannot_export_other_branch(self):
        rows = _rows(self._export(month='2026-09', branch=OTHER_BRANCH))
        ids = {r['employee_id'] for r in rows}
        self.assertIn('MEX001', ids)
        self.assertNotIn('MEX009', ids)

    def test_department_filter_applies(self):
        ids = {r['employee_id'] for r in _rows(self._export(month='2026-09', department='Sales'))}
        self.assertEqual(ids, {'MEX002'})

    def test_manager_exports_only_direct_reports(self):
        manager = make_user('mex.mgr@test.com',
                            role=make_role('mex_mgr', can_manage_team=True, permission_codenames=EXPORT_PERMS),
                            employee_id='MEXMGR', full_name='Month Mgr', branch=BRANCH)
        self.emp2.reporting_manager = manager
        self.emp2.save(update_fields=['reporting_manager'])
        ids = {r['employee_id'] for r in _rows(self._export(manager, month='2026-09'))}
        self.assertEqual(ids, {'MEX002'})

    def test_view_only_role_cannot_export_daily_or_monthly(self):
        viewer = make_user('mex.view@test.com', role=make_role('mex_view', permission_codenames=['attendance.view']),
                           employee_id='MEXVW', full_name='Viewer', branch=BRANCH)
        self.assertEqual(self._export(viewer, month='2026-09').status_code, 403)
        self.assertEqual(self._export(viewer, date='2026-09-01').status_code, 403)

    # ── Invalid parameters ────────────────────────────────────────────────────

    def test_invalid_parameters_rejected(self):
        future = (date.today().replace(day=1) + datetime.timedelta(days=32)).strftime('%Y-%m')
        for params in ({'month': '2026-13'}, {'month': '2026-1'}, {'month': 'abc'}, {'month': '2026-00'},
                       {'month': future}, {'month': '2026-09', 'date': '2026-09-01'}):
            self.assertEqual(self._export(**params).status_code, 400, params)

    # ── Daily export unchanged ────────────────────────────────────────────────

    def test_daily_export_unchanged(self):
        self._work(self.emp, date(2026, 9, 1), 'Office')
        resp = self._export(date='2026-09-01')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Disposition'], 'attachment; filename="attendance_2026-09-01.csv"')
        rows = _rows(resp)
        self.assertEqual({r['date'] for r in rows}, {'01-09-2026'})
        by_id = {r['employee_id']: r for r in rows}
        self.assertEqual(by_id['MEX001']['status'], 'Present')
        self.assertEqual(by_id['MEX001']['clock_in_location'], 'Office')
        self.assertEqual(by_id['MEX002']['status'], 'Absent')
        self.assertNotIn('MEX009', by_id)
