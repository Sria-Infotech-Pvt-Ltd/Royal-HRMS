"""
Settings → Notice Period → Import (Employee ID, Notice Period (days)):
preview then confirm, re-validated on confirm; employees.edit and the same
branch / Manager scope as a single save; Employee ID matching only; blank =
skip (never clears); duplicates, unknown / out-of-scope, inactive and invalid
values are row errors; unchanged values are "no change"; one audit entry per
update; the values reach the profile and Separation & Exit. The employee
import is unchanged.
"""
from __future__ import annotations

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User
from apps.accounts.tests_employee_notice_period import HYD, NoticeFixture


def _csv(*rows, header='Employee ID,Notice Period (days)'):
    return SimpleUploadedFile('np.csv', ('\n'.join([header, *rows]) + '\n').encode(), content_type='text/csv')


class NoticeImportTests(NoticeFixture):
    def setUp(self):
        super().setUp()
        self.emp2 = self.employee('np.emp2@test.com', 'NPE2', 'Hyd Emp Two', HYD)
        self.gone = self.employee('np.gone@test.com', 'NPG1', 'Gone Emp', HYD, is_active=False)

    def send(self, user, upload, dry_run):
        data = {'file': upload}
        if dry_run:
            data['dry_run'] = 'true'
        return self.api(user).post(reverse('notice-period-import'), data, format='multipart')

    def by_id(self, resp):
        return {r['employee_id']: r for r in resp.data['data']['rows']}

    def test_preview_saves_nothing_then_confirm_updates_with_audit(self):
        upload = lambda: _csv('NPE1,60', 'npe2,90')        # lower-case ID still matches
        preview = self.send(self.hr_hyd, upload(), dry_run=True)
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['data']['summary']['update'], 2)
        self.assertIsNone(User.objects.get(pk=self.emp.pk).notice_period_days)

        done = self.send(self.hr_hyd, upload(), dry_run=False)
        self.assertEqual(done.data['data']['summary']['updated'], 2)
        self.assertEqual(User.objects.get(pk=self.emp.pk).notice_period_days, 60)
        self.assertEqual(User.objects.get(pk=self.emp2.pk).notice_period_days, 90)
        logs = AuditLog.objects.filter(action='employee_updated', changes__source='notice_period_import')
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.get(object_id=str(self.emp.pk)).changes['notice_period_days'], {'from': None, 'to': 60})

    def test_row_errors_and_no_change(self):
        User.objects.filter(pk=self.emp2.pk).update(notice_period_days=30)
        rows = self.by_id(self.send(self.hr_hyd, _csv(
            'NPE1,abc', 'NPE2,30', 'NPG1,30', 'NOPE99,30', 'NPM1,30', ',30'), dry_run=True))
        self.assertIn('whole number', rows['NPE1']['message'])
        self.assertEqual(rows['NPE2']['status'], 'no_change')
        self.assertEqual(rows['NPG1']['message'], 'Employee is inactive.')
        self.assertEqual(rows['NOPE99']['message'], 'Employee not found.')
        self.assertEqual(rows['NPM1']['message'], 'Employee not found.')       # other branch — not revealed
        self.assertEqual(rows['']['message'], 'Employee ID is required.')

    def test_out_of_range_rejected(self):
        rows = self.by_id(self.send(self.hr_hyd, _csv('NPE1,366', 'NPE2,-1'), dry_run=True))
        self.assertEqual({r['status'] for r in rows.values()}, {'error'})

    def test_duplicate_ids_are_all_rejected(self):
        resp = self.send(self.hr_hyd, _csv('NPE1,30', 'NPE2,45', 'npe1,60'), dry_run=False)
        statuses = [r['status'] for r in resp.data['data']['rows']]
        self.assertEqual(statuses, ['error', 'updated', 'error'])
        self.assertIsNone(User.objects.get(pk=self.emp.pk).notice_period_days)

    def test_blank_skips_and_never_clears(self):
        User.objects.filter(pk=self.emp.pk).update(notice_period_days=30)
        resp = self.send(self.hr_hyd, _csv('NPE1,'), dry_run=False)
        self.assertEqual(resp.data['data']['rows'][0]['status'], 'skipped')
        self.assertEqual(User.objects.get(pk=self.emp.pk).notice_period_days, 30)

    def test_confirm_revalidates(self):
        self.send(self.hr_hyd, _csv('NPE1,60'), dry_run=True)
        User.objects.filter(pk=self.emp.pk).update(is_active=False)        # changed after the preview
        resp = self.send(self.hr_hyd, _csv('NPE1,60'), dry_run=False)
        self.assertEqual(resp.data['data']['rows'][0]['message'], 'Employee is inactive.')
        self.assertIsNone(User.objects.get(pk=self.emp.pk).notice_period_days)

    def test_permissions(self):
        self.assertEqual(self.send(self.viewer, _csv('NPE1,30'), dry_run=True).status_code, 403)   # no employees.edit
        self.assertEqual(self.send(self.emp, _csv('NPE1,30'), dry_run=False).status_code, 403)
        sample = self.api(self.viewer).get(reverse('notice-period-import-sample'), {'format': 'csv'})
        self.assertEqual(sample.status_code, 403)
        self.assertIsNone(User.objects.get(pk=self.emp.pk).notice_period_days)

    def test_manager_limited_to_direct_reports(self):
        manager = make_user('np.mgr@test.com', role=make_role('np_mgr', can_manage_team=True,
                            permission_codenames=['employees.view', 'employees.edit']),
                            employee_id='NPMGR', full_name='Mgr', branch=HYD)
        User.objects.filter(pk=self.emp.pk).update(reporting_manager=manager)
        rows = self.by_id(self.send(manager, _csv('NPE1,45', 'NPE2,45'), dry_run=False))
        self.assertEqual(rows['NPE1']['status'], 'updated')
        self.assertEqual(rows['NPE2']['message'], 'Employee not found.')

    def test_file_level_checks(self):
        self.assertEqual(self.send(self.hr_hyd, _csv('NPE1', header='Employee ID'), dry_run=True).status_code, 400)
        bad = SimpleUploadedFile('np.txt', b'x', content_type='text/plain')
        self.assertEqual(self.send(self.hr_hyd, bad, dry_run=True).status_code, 400)
        too_many = _csv(*[f'X{i},30' for i in range(1001)])
        self.assertEqual(self.send(self.hr_hyd, too_many, dry_run=True).status_code, 400)

    def test_xlsx_and_samples(self):
        import openpyxl
        api = self.api(self.hr_hyd)
        for fmt in ('csv', 'xlsx'):
            resp = api.get(reverse('notice-period-import-sample'), {'format': fmt})
            self.assertEqual(resp.status_code, 200)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Employee ID', 'Notice Period (days)'])
        ws.append(['NPE1', 45])                                            # numeric cell
        buf = io.BytesIO()
        wb.save(buf)
        upload = SimpleUploadedFile('np.xlsx', buf.getvalue(),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp = self.send(self.hr_hyd, upload, dry_run=False)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(User.objects.get(pk=self.emp.pk).notice_period_days, 45)

    def test_imported_value_reaches_profile_and_separation(self):
        self.send(self.hr_hyd, _csv('NPE1,60'), dry_run=False)
        self.assertEqual(self.api(self.emp).get(reverse('my-profile')).data['data']['notice_period_days'], 60)
        today = timezone.localdate()
        resp = self.api(self.emp).post(reverse('separation-request-list'), {
            'separation_type': 'resignation', 'reason': 'personal_reason', 'request_date': today.isoformat(),
            'proposed_last_working_day': today.isoformat(), 'notice_period_days': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['notice_period_days'], 60)
