"""
Attendance CSV import: single-employee and bulk modes, preview (dry run),
row validation, duplicates, permission scope and tenant isolation.
"""
from __future__ import annotations

import datetime
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendanceImportLog, AttendanceRecord
from config.test_runner import TEST_COMPANY_CODE

PASSWORD = 'TestPass123!'
HYD = 'Hyderabad Import'
MUM = 'Mumbai Import'
D1, D2, D3 = datetime.date(2026, 9, 1), datetime.date(2026, 9, 2), datetime.date(2026, 9, 3)


def _csv(*rows, header='employee_id,date,punch_in,punch_out') -> SimpleUploadedFile:
    body = '\n'.join([header, *rows]) + '\n'
    return SimpleUploadedFile('attendance.csv', body.encode('utf-8'), content_type='text/csv')


class AttendanceImportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user(
            'imp.admin@test.com', role=make_role('imp_admin', permission_codenames=['attendance.create', 'settings.edit']),
            employee_id='IMPADM1', full_name='Import Admin', branch=HYD,
        )
        branch_hr_role = make_role('imp_branch_hr', permission_codenames=['attendance.create', 'attendance.view'])
        self.hr_hyd = make_user('imp.hr.hyd@test.com', role=branch_hr_role, employee_id='IMPHRH1', full_name='HR Hyd', branch=HYD)
        manager_role = make_role('imp_manager', permission_codenames=['attendance.create'], can_manage_team=True)
        self.manager = make_user('imp.mgr@test.com', role=manager_role, employee_id='IMPMGR1', full_name='Manager', branch=HYD)
        staff = make_role('imp_staff')
        self.emp_a = make_user('imp.a@test.com', role=staff, employee_id='IMPA001', full_name='Emp A', branch=HYD, reporting_manager=self.manager)
        self.emp_b = make_user('imp.b@test.com', role=staff, employee_id='IMPB001', full_name='Emp B', branch=HYD)
        self.emp_mum = make_user('imp.mum@test.com', role=staff, employee_id='IMPM001', full_name='Emp Mum', branch=MUM)
        self.no_perm = make_user('imp.noperm@test.com', role=staff, employee_id='IMPNP01', full_name='No Perm', branch=HYD)

    def _login(self, user):
        resp = self.client.post(
            reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email, 'password': PASSWORD}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def _import(self, file, **fields):
        return self.client.post(reverse('hr-attendance-import'), {'file': file, **fields}, format='multipart')

    def _records(self, employee):
        return AttendanceRecord.objects.filter(employee=employee)

    # ── Bulk mode ──────────────────────────────────────────────────────────────

    def test_bulk_import_multiple_employees(self):
        self._login(self.admin)
        resp = self._import(_csv(f'IMPA001,{D1},09:00,18:00', f'IMPB001,{D1},09:30,18:30', f'IMPM001,{D2},10:00,19:00'))
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual((data['successful'], data['failed'], data['skipped']), (3, 0, 0))
        rec = self._records(self.emp_a).get(date=D1)
        self.assertEqual(rec.status, AttendanceRecord.STATUS_PRESENT)  # existing ≥240-minute rule unchanged
        self.assertEqual(rec.total_working_minutes, 540)

    def test_preview_writes_nothing_and_classifies_rows(self):
        AttendanceRecord.objects.create(employee=self.emp_b, date=D1, status=AttendanceRecord.STATUS_ABSENT)
        self._login(self.admin)
        resp = self._import(
            _csv(f'IMPA001,{D1},09:00,18:00', f'IMPB001,{D1},09:00,18:00', f'NOPE999,{D1},09:00,18:00'),
            dry_run='true',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['status'], 'preview')
        self.assertEqual((data['to_create'], data['to_update'], data['failed']), (1, 1, 1))
        self.assertEqual({r['employee_id']: r['action'] for r in data['rows']}, {'IMPA001': 'create', 'IMPB001': 'update'})
        self.assertFalse(self._records(self.emp_a).exists())
        self.assertEqual(self._records(self.emp_b).get().status, AttendanceRecord.STATUS_ABSENT)
        self.assertFalse(AttendanceImportLog.objects.exists())

    def test_invalid_rows_are_reported_and_valid_rows_still_import(self):
        self._login(self.admin)
        resp = self._import(_csv(
            f'IMPA001,{D1},09:00,18:00',
            'IMPA001,not-a-date,09:00,18:00',
            f'IMPA001,{D2},18:00,09:00',
            f'NOPE999,{D3},09:00,18:00',
            f',{D3},09:00,18:00',
        ))
        self.assertEqual(resp.status_code, 207, resp.data)
        data = resp.data['data']
        self.assertEqual((data['successful'], data['failed']), (1, 4))
        reasons = ' | '.join(e['reason'] for e in data['errors'])
        self.assertIn('not a valid date', reasons)
        self.assertIn("Punch-out time '09:00' is invalid", reasons)  # existing wording for out <= in
        self.assertIn("'NOPE999' was not found", reasons)
        self.assertIn('Employee ID is missing', reasons)
        self.assertTrue(data.get('error_report_csv'))

    def test_duplicates_in_file_and_existing_records_never_create_duplicates(self):
        AttendanceRecord.objects.create(employee=self.emp_a, date=D2, status=AttendanceRecord.STATUS_ABSENT)
        self._login(self.admin)
        resp = self._import(_csv(
            f'IMPA001,{D1},09:00,13:00', f'IMPA001,{D1},09:00,18:00',  # same day twice → last wins
            f'IMPA001,{D2},09:00,18:00',                               # existing → update
        ))
        data = resp.data['data']
        self.assertEqual((data['successful'], data['skipped'], data['failed']), (2, 1, 0))
        self.assertEqual(self._records(self.emp_a).count(), 2)
        self.assertEqual(self._records(self.emp_a).get(date=D1).total_working_minutes, 540)
        self.assertEqual(self._records(self.emp_a).get(date=D2).status, AttendanceRecord.STATUS_PRESENT)

    def test_on_leave_record_is_never_overwritten(self):
        AttendanceRecord.objects.create(employee=self.emp_a, date=D1, status=AttendanceRecord.STATUS_ON_LEAVE)
        self._login(self.admin)
        data = self._import(_csv(f'IMPA001,{D1},09:00,18:00')).data['data']
        self.assertEqual(data['skipped'], 1)
        self.assertEqual(self._records(self.emp_a).get().status, AttendanceRecord.STATUS_ON_LEAVE)

    # ── Single-employee mode ───────────────────────────────────────────────────

    def test_single_employee_imports_only_that_employee(self):
        AttendanceRecord.objects.create(employee=self.emp_b, date=D1, status=AttendanceRecord.STATUS_ABSENT)
        self._login(self.admin)
        resp = self._import(
            _csv(f'IMPA001,{D1},09:00,18:00', f',{D2},09:00,18:00', f'IMPB001,{D1},09:00,18:00'),
            employee_id='IMPA001',
        )
        data = resp.data['data']
        self.assertEqual(resp.status_code, 207, resp.data)
        self.assertEqual((data['successful'], data['failed']), (2, 1))
        self.assertEqual(data['employee'], {'employee_id': 'IMPA001', 'full_name': 'Emp A'})
        self.assertIn("not the selected employee 'IMPA001'", data['errors'][0]['reason'])
        self.assertEqual(set(self._records(self.emp_a).values_list('date', flat=True)), {D1, D2})
        self.assertEqual(self._records(self.emp_b).get().status, AttendanceRecord.STATUS_ABSENT)  # untouched

    def test_single_employee_preview(self):
        self._login(self.admin)
        data = self._import(_csv(f',{D1},09:00,18:00'), employee_id='IMPA001', dry_run='1').data['data']
        self.assertEqual((data['to_create'], data['failed']), (1, 0))
        self.assertEqual(data['rows'][0]['employee_id'], 'IMPA001')
        self.assertFalse(self._records(self.emp_a).exists())

    def test_date_range_rejects_rows_outside_it(self):
        self._login(self.admin)
        data = self._import(
            _csv(f'IMPA001,{D1},09:00,18:00', f'IMPA001,{D3},09:00,18:00'),
            employee_id='IMPA001', date_from=str(D2), date_to=str(D3),
        ).data['data']
        self.assertEqual((data['successful'], data['failed']), (1, 1))
        self.assertIn('outside the selected range', data['errors'][0]['reason'])
        self.assertEqual(list(self._records(self.emp_a).values_list('date', flat=True)), [D3])

    def test_invalid_date_range_parameters(self):
        self._login(self.admin)
        self.assertEqual(self._import(_csv(f'IMPA001,{D1},09:00,18:00'), date_from='01-09-2026').status_code, 400)
        self.assertEqual(self._import(_csv(f'IMPA001,{D1},09:00,18:00'), date_from=str(D3), date_to=str(D1)).status_code, 400)

    def test_unknown_selected_employee_is_404(self):
        self._login(self.admin)
        self.assertEqual(self._import(_csv(f',{D1},09:00,18:00'), employee_id='NOPE999').status_code, 404)

    # ── Permissions and scope ──────────────────────────────────────────────────

    def test_user_without_attendance_create_is_denied(self):
        self._login(self.no_perm)
        self.assertEqual(self._import(_csv(f'IMPA001,{D1},09:00,18:00')).status_code, 403)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_branch_hr_cannot_import_other_branch_employees(self):
        self._login(self.hr_hyd)
        data = self._import(_csv(f'IMPA001,{D1},09:00,18:00', f'IMPM001,{D1},09:00,18:00')).data['data']
        self.assertEqual((data['successful'], data['failed']), (1, 1))
        self.assertIn('outside your access', data['errors'][0]['reason'])
        self.assertFalse(self._records(self.emp_mum).exists())
        self.assertEqual(self._import(_csv(f',{D1},09:00,18:00'), employee_id='IMPM001').status_code, 404)

    def test_manager_limited_to_direct_reports(self):
        self._login(self.manager)
        data = self._import(_csv(f'IMPA001,{D1},09:00,18:00', f'IMPB001,{D1},09:00,18:00')).data['data']
        self.assertEqual((data['successful'], data['failed']), (1, 1))
        self.assertTrue(self._records(self.emp_a).exists())
        self.assertFalse(self._records(self.emp_b).exists())
        self.assertEqual(self._import(_csv(f',{D1},09:00,18:00'), employee_id='IMPB001').status_code, 404)

    def test_tenant_isolation_employee_from_another_schema_is_not_found(self):
        # Another company's schema holding an employee that exists only there
        # (created inside this test's transaction, rolled back afterwards).
        current = connection.schema_name
        table = User._meta.db_table
        with connection.cursor() as cur:
            cur.execute('CREATE SCHEMA tenant_import_other')
            cur.execute(f'CREATE TABLE tenant_import_other.{table} (LIKE {current}.{table} INCLUDING ALL)')
            cur.execute(
                f'INSERT INTO tenant_import_other.{table} SELECT * FROM {current}.{table} WHERE id = %s',
                [self.emp_b.pk],
            )
            cur.execute(
                f"UPDATE tenant_import_other.{table} SET employee_id = 'IMPOTH1', email = 'other@test.com'",
            )
            cur.execute(f"SELECT count(*) FROM tenant_import_other.{table} WHERE employee_id = 'IMPOTH1'")
            self.assertEqual(cur.fetchone()[0], 1)

        self._login(self.admin)
        data = self._import(_csv(f'IMPOTH1,{D1},09:00,18:00')).data['data']
        self.assertEqual((data['successful'], data['failed']), (0, 1))
        self.assertIn("'IMPOTH1' was not found", data['errors'][0]['reason'])
        self.assertFalse(AttendanceRecord.objects.filter(date=D1).exists())
        self.assertEqual(self._import(_csv(f',{D1},09:00,18:00'), employee_id='IMPOTH1').status_code, 404)

    # ── Large files (background job) carry the same restrictions ──────────────

    def test_large_file_queues_with_single_employee_options(self):
        rows = [f'IMPA001,{D1 + datetime.timedelta(days=i)},09:00,18:00' for i in range(501)]
        self._login(self.admin)
        with patch('apps.attendance.tasks.process_attendance_import.apply_async') as mock_async:
            mock_async.return_value.id = 'task-1'
            resp = self._import(_csv(*rows), employee_id='IMPA001', date_from=str(D1))
        self.assertEqual(resp.status_code, 202, resp.data)
        kwargs = mock_async.call_args.kwargs['kwargs']
        self.assertEqual(kwargs, {'employee_code': 'IMPA001', 'date_from': str(D1), 'date_to': None})

    def test_background_task_enforces_single_employee_and_scope(self):
        from apps.attendance.tasks import process_attendance_import
        log = AttendanceImportLog.objects.create(imported_by=self.hr_hyd, file_name='big.csv', total_rows=3,
                                                 status=AttendanceImportLog.STATUS_PROCESSING)
        content = '\n'.join([
            'employee_id,date,punch_in,punch_out',
            f'IMPA001,{D1},09:00,18:00', f'IMPB001,{D1},09:00,18:00', f'IMPM001,{D1},09:00,18:00',
        ])
        process_attendance_import(connection.schema_name, str(log.id), str(self.hr_hyd.pk), content, employee_code='IMPA001')
        log.refresh_from_db()
        self.assertEqual((log.success_rows, log.failed_rows), (1, 2))
        self.assertTrue(self._records(self.emp_a).exists())
        self.assertFalse(self._records(self.emp_b).exists())
        self.assertFalse(self._records(self.emp_mum).exists())
