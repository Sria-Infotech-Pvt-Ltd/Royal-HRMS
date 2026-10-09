"""
Attendance CSV export: clock_in_location / clock_out_location columns.

Each location comes from the exact punch behind the exported clock_in / clock_out
time (AttendanceRecord.first_punch_in / last_punch_out): the stored location_label
(e.g. "Office – <Branch>" or a geocoded place), else the stored coordinates, else
blank. Export never geocodes.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.serializers_hr import ImportRowSerializer
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.attendance.services_hr_ops import _normalize_row, _punch_locations_by_record, export_attendance_csv
from apps.attendance.services_hr import get_attendance_list
from config.test_runner import TEST_COMPANY_CODE

IST = ZoneInfo('Asia/Kolkata')
DAY = date(2026, 10, 7)  # a Wednesday
BRANCH = 'London Export Test'
OFFICE_LABEL = f'Office – {BRANCH}'

EXISTING_COLUMNS = [
    'employee_id', 'name', 'department', 'branch',
    'date', 'clock_in', 'clock_out', 'total_hours',
    'overtime', 'status',
]


def _at(hh: int, mm: int = 0) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hh, mm, tzinfo=IST)


def _parse(csv_text: str) -> tuple[list[str], dict[str, dict]]:
    reader = csv.DictReader(io.StringIO(csv_text.lstrip('﻿')))
    rows = list(reader)
    return reader.fieldnames, {r['employee_id']: r for r in rows}


class AttendanceExportLocationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.role = make_role('export_location_staff')
        self._seq = 0

    def _employee(self, department='Ops'):
        self._seq += 1
        return make_user(
            f'export.loc{self._seq}@test.com', role=self.role, employee_id=f'EMPXL{self._seq:03d}',
            full_name=f'Export Emp {self._seq}', branch=BRANCH, department=department,
        )

    def _punch(self, employee, punch_type, when, label='', lat=None, lon=None):
        return AttendancePunch.objects.create(
            employee=employee, punch_type=punch_type, punched_at=when,
            location_label=label, latitude=lat, longitude=lon,
        )

    def _export(self, **extra):
        filters = {'date': DAY, 'branch': BRANCH, 'department': '', 'employee_ids': None, **extra}
        return _parse(export_attendance_csv(filters))

    def _process(self, *employees):
        for emp in employees:
            AttendanceProcessorService.process_day(emp, DAY)

    def test_office_clock_in_and_out_export_office_label(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(12), OFFICE_LABEL, 51.5074, -0.1278)
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(21), OFFICE_LABEL, 51.5074, -0.1278)
        self._process(emp)

        _, rows = self._export()
        self.assertEqual(rows[emp.employee_id]['clock_in_location'], OFFICE_LABEL)
        self.assertEqual(rows[emp.employee_id]['clock_out_location'], OFFICE_LABEL)

    def test_uk_outside_office_exports_each_punchs_own_place(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(12), 'London, England, United Kingdom', 51.5074, -0.1278)
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(21), 'Croydon, England, United Kingdom', 51.3762, -0.0982)
        self._process(emp)

        _, rows = self._export()
        row = rows[emp.employee_id]
        self.assertEqual(row['clock_in_location'], 'London, England, United Kingdom')
        self.assertEqual(row['clock_out_location'], 'Croydon, England, United Kingdom')
        self.assertNotIn(BRANCH, row['clock_in_location'] + row['clock_out_location'])

    def test_missing_label_falls_back_to_stored_coordinates(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(12), '', 51.5074, -0.1278)
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(21), 'Croydon, England, United Kingdom', 51.3762, -0.0982)
        self._process(emp)

        _, rows = self._export()
        self.assertEqual(rows[emp.employee_id]['clock_in_location'], '51.507400, -0.127800')
        self.assertEqual(rows[emp.employee_id]['clock_out_location'], 'Croydon, England, United Kingdom')

    def test_no_label_and_no_coordinates_is_blank_not_branch(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(12))
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(21))
        self._process(emp)

        _, rows = self._export()
        self.assertEqual(rows[emp.employee_id]['clock_in_location'], '')
        self.assertEqual(rows[emp.employee_id]['clock_out_location'], '')
        self.assertEqual(rows[emp.employee_id]['clock_in'], '12:00')

    def test_missing_clock_out_leaves_out_location_blank(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(12), OFFICE_LABEL, 51.5074, -0.1278)
        self._process(emp)

        _, rows = self._export()
        self.assertEqual(rows[emp.employee_id]['clock_in_location'], OFFICE_LABEL)
        self.assertEqual(rows[emp.employee_id]['clock_out'], '')
        self.assertEqual(rows[emp.employee_id]['clock_out_location'], '')

    def test_absent_employee_without_record_has_blank_locations(self):
        emp = self._employee()

        _, rows = self._export()
        self.assertEqual(rows[emp.employee_id]['clock_in_location'], '')
        self.assertEqual(rows[emp.employee_id]['clock_out_location'], '')

    def test_multi_cycle_day_uses_punches_behind_exported_times(self):
        # Pre-daily-cap history: IN, OUT, IN, OUT. Export shows first IN and last OUT.
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(9), 'First In Place')
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(13), 'Lunch Out Place')
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(14), 'Lunch In Place')
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(18), 'Final Out Place')
        self._process(emp)

        _, rows = self._export()
        row = rows[emp.employee_id]
        self.assertEqual((row['clock_in'], row['clock_out']), ('09:00', '18:00'))
        self.assertEqual(row['clock_in_location'], 'First In Place')
        self.assertEqual(row['clock_out_location'], 'Final Out Place')

    def test_manually_edited_time_without_matching_punch_exports_blank(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(12), 'London, England, United Kingdom')
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(21), 'Croydon, England, United Kingdom')
        self._process(emp)
        AttendanceRecord.objects.filter(employee=emp, date=DAY).update(last_punch_out=time(20, 30))

        _, rows = self._export()
        row = rows[emp.employee_id]
        self.assertEqual(row['clock_out'], '20:30')
        self.assertEqual(row['clock_in_location'], 'London, England, United Kingdom')
        self.assertEqual(row['clock_out_location'], '')

    def test_existing_columns_unchanged_and_new_columns_appended(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(9), OFFICE_LABEL)
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(18), OFFICE_LABEL)
        self._process(emp)

        header, rows = self._export()
        self.assertEqual(header, EXISTING_COLUMNS + ['clock_in_location', 'clock_out_location'])

        list_row = next(r for r in get_attendance_list({'date': DAY, 'branch': BRANCH}) if r['employee_id'] == emp.employee_id)
        row = rows[emp.employee_id]
        self.assertEqual(row['date'], DAY.strftime('%d-%m-%Y'))
        self.assertEqual(row['clock_in'], list_row['clock_in'])
        self.assertEqual(row['clock_out'], list_row['clock_out'])
        self.assertEqual(row['total_hours'], list_row['total_hours'])
        self.assertEqual(row['status'], list_row['status'])

    def test_department_and_branch_filters_still_apply(self):
        ops = self._employee(department='Ops')
        sales = self._employee(department='Sales')
        elsewhere = make_user(
            'export.loc.other@test.com', role=self.role, employee_id='EMPXLOTH',
            full_name='Other Branch', branch='Other Branch', department='Ops',
        )

        _, rows = self._export(department='Ops')
        self.assertIn(ops.employee_id, rows)
        self.assertNotIn(sales.employee_id, rows)
        self.assertNotIn(elsewhere.employee_id, rows)

    def test_geocoder_label_cannot_inject_spreadsheet_formula(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(9), '=HYPERLINK("http://x","y")')
        self._process(emp)

        _, rows = self._export()
        self.assertEqual(rows[emp.employee_id]['clock_in_location'], '\'=HYPERLINK("http://x","y")')

    @patch('apps.attendance.services_geocoding.requests.get')
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_export_never_calls_geocoder(self, mock_geocode, mock_http):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(9), '', 51.5074, -0.1278)
        self._process(emp)

        self._export()
        mock_geocode.assert_not_called()
        mock_http.assert_not_called()

    def test_location_lookup_is_two_queries_regardless_of_row_count(self):
        employees = [self._employee() for _ in range(5)]
        for emp in employees:
            self._punch(emp, AttendancePunch.PUNCH_IN, _at(9), OFFICE_LABEL)
            self._punch(emp, AttendancePunch.PUNCH_OUT, _at(18), OFFICE_LABEL)
        self._process(*employees)

        rows = get_attendance_list({'date': DAY, 'branch': BRANCH})
        with CaptureQueriesContext(connection) as ctx:
            result = _punch_locations_by_record(rows, DAY)
        # django-tenants adds a SET search_path per cursor; count data queries only.
        selects = [q for q in ctx.captured_queries if q['sql'].lstrip().upper().startswith('SELECT')]
        self.assertEqual(len(selects), 2)
        self.assertEqual(len(result), 5)

    def test_exported_file_still_reimports_cleanly(self):
        emp = self._employee()
        self._punch(emp, AttendancePunch.PUNCH_IN, _at(9), OFFICE_LABEL)
        self._punch(emp, AttendancePunch.PUNCH_OUT, _at(18), OFFICE_LABEL)
        self._process(emp)

        _, rows = self._export()
        ser = ImportRowSerializer(data=_normalize_row(rows[emp.employee_id]))
        self.assertTrue(ser.is_valid(), ser.errors)


class AttendanceExportEndpointLocationTests(TestCase):
    def setUp(self):
        cache.clear()
        hr_role = make_role('export_location_hr', permission_codenames=['attendance.view'])
        make_user('export.hr@test.com', role=hr_role, employee_id='EMPXLHR1', full_name='Export HR', branch=BRANCH)
        self.emp = make_user(
            'export.ep@test.com', role=make_role('export_location_staff'), employee_id='EMPXLEP1',
            full_name='Endpoint Emp', branch=BRANCH,
        )
        AttendancePunch.objects.create(
            employee=self.emp, punch_type=AttendancePunch.PUNCH_IN, punched_at=_at(12),
            location_label='London, England, United Kingdom',
        )
        AttendanceProcessorService.process_day(self.emp, DAY)
        self.client = APIClient()

    def _login(self, email):
        resp = self.client.post(
            reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_export_endpoint_includes_location_columns(self):
        self._login('export.hr@test.com')
        resp = self.client.get(reverse('hr-attendance-export'), {'date': DAY.isoformat()})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['Content-Type'].startswith('text/csv'))
        header, rows = _parse(resp.content.decode('utf-8'))
        self.assertEqual(header[-2:], ['clock_in_location', 'clock_out_location'])
        self.assertEqual(rows[self.emp.employee_id]['clock_in_location'], 'London, England, United Kingdom')
        self.assertEqual(rows[self.emp.employee_id]['clock_out_location'], '')

    def test_export_endpoint_still_requires_attendance_view(self):
        make_user('export.noperm@test.com', role=make_role('export_location_noperm'),
                  employee_id='EMPXLNP1', full_name='No Perm', branch=BRANCH)
        self._login('export.noperm@test.com')
        resp = self.client.get(reverse('hr-attendance-export'), {'date': DAY.isoformat()})
        self.assertEqual(resp.status_code, 403)
