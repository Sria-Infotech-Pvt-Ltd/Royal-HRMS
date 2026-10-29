"""
Employee notice period (User.notice_period_days, Settings → Notice Period):
HR assigns it through the employee API (employees.edit + branch scope, audited),
the employee sees it on their profile, the bulk import accepts an optional
column, and Separation & Exit uses it for the request and the expected last
working day without changing the assigned value.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, Department, Designation, User
from apps.accounts.notice_period import expected_last_working_day, parse_notice_period_days
from apps.accounts.tests import _login
from apps.assets.tests import _make_branch
from apps.hrms.models import SeparationRequest

HYD, MUM = 'Hyd NP', 'Mum NP'


class ParseTests(SimpleTestCase):
    def test_values(self):
        self.assertEqual(parse_notice_period_days('30'), (None, 30))
        self.assertEqual(parse_notice_period_days(60), (None, 60))
        self.assertEqual(parse_notice_period_days('90.0'), (None, 90))      # Excel cell
        self.assertEqual(parse_notice_period_days(''), (None, None))
        self.assertEqual(parse_notice_period_days(None), (None, None))
        for bad in ('-1', '366', 'abc', '30.5'):
            self.assertIsNotNone(parse_notice_period_days(bad)[0], bad)

    def test_expected_last_working_day(self):
        self.assertEqual(expected_last_working_day(datetime.date(2026, 10, 1), 30), datetime.date(2026, 10, 31))
        self.assertIsNone(expected_last_working_day(datetime.date(2026, 10, 1), None))


class NoticeFixture(TestCase):
    def setUp(self):
        cache.clear()
        hr_role = make_role('np_hr', permission_codenames=['employees.view', 'employees.edit', 'separation.approve'])
        self.hr_hyd = make_user('np.hr@test.com', role=hr_role, employee_id='NPHR1', full_name='HR Hyd', branch=HYD)
        self.viewer = make_user('np.viewer@test.com', role=make_role('np_viewer', permission_codenames=['employees.view']),
                                employee_id='NPV1', full_name='Viewer', branch=HYD)
        self.staff = make_role('np_staff')
        self.emp = self.employee('np.emp@test.com', 'NPE1', 'Hyd Emp', HYD)
        self.emp_mum = self.employee('np.mum@test.com', 'NPM1', 'Mum Emp', MUM)

    def employee(self, email, code, name, branch, **extra):
        return make_user(email, role=self.staff, employee_id=code, full_name=name, branch=branch,
                         department='Ops', onboarding_status='complete', assessment_status='complete', **extra)

    def api(self, user):
        client = APIClient()
        _login(client, user.email)
        return client

    def put(self, user, employee, value):
        return self.api(user).put(reverse('employee-detail', kwargs={'employee_id': employee.employee_id}),
                                  {'notice_period_days': value}, format='json')


class AssignmentTests(NoticeFixture):
    def test_hr_assigns_updates_and_clears_with_audit(self):
        self.assertEqual(self.put(self.hr_hyd, self.emp, 60).status_code, 200)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.notice_period_days, 60)
        log = AuditLog.objects.filter(action='employee_updated', object_id=str(self.emp.pk)).latest('id')
        self.assertEqual(log.changes.get('notice_period_days'), {'from': None, 'to': 60})
        self.assertEqual(self.put(self.hr_hyd, self.emp, 90).status_code, 200)
        self.assertEqual(self.put(self.hr_hyd, self.emp, '').status_code, 200)
        self.emp.refresh_from_db()
        self.assertIsNone(self.emp.notice_period_days)

    def test_invalid_values_rejected(self):
        for bad in (-1, 366, 'abc', 30.5):
            self.assertEqual(self.put(self.hr_hyd, self.emp, bad).status_code, 400, bad)
        self.emp.refresh_from_db()
        self.assertIsNone(self.emp.notice_period_days)

    def test_unauthorised_and_other_branch_cannot_change(self):
        self.assertEqual(self.put(self.viewer, self.emp, 30).status_code, 403)       # no employees.edit
        self.assertEqual(self.put(self.emp, self.emp, 30).status_code, 403)          # employee, own record
        self.assertEqual(self.put(self.hr_hyd, self.emp_mum, 30).status_code, 404)   # other branch
        self.emp.refresh_from_db()
        self.emp_mum.refresh_from_db()
        self.assertEqual((self.emp.notice_period_days, self.emp_mum.notice_period_days), (None, None))

    def test_list_and_own_profile_show_it(self):
        User.objects.filter(pk=self.emp.pk).update(notice_period_days=45)
        rows = self.api(self.hr_hyd).get(reverse('employee-list-create'), {'search': 'NPE1'}).data['data']['results']
        self.assertEqual(rows[0]['notice_period_days'], 45)
        me = self.api(self.emp).get(reverse('my-profile')).data['data']
        self.assertEqual(me['notice_period_days'], 45)


class BulkImportTests(NoticeFixture):
    def setUp(self):
        super().setUp()
        self.branch = _make_branch('NP Import Branch')
        dept = Department.objects.create(name='NP Dept')
        Designation.objects.create(name='NP Engineer', department=dept)
        self.importer = make_user('np.imp@test.com', role=make_role('np_imp', permission_codenames=[
            'employees.create', 'settings.edit']), employee_id='NPIMP', branch=self.branch.branch_name)

    def upload(self, header_extra='', row_extra=''):
        b = self.branch.branch_name
        text = (f'First Name,Last Name,Work Email,Role,Department,Designation,Branch,Date of Joining{header_extra}\n'
                f'Imp,One,np.imp1@test.com,np_staff,NP Dept,NP Engineer,{b},2026-04-01{row_extra}\n')
        return self.api(self.importer).post(
            reverse('employee-bulk-import'),
            {'file': SimpleUploadedFile('emp.csv', text.encode(), content_type='text/csv')}, format='multipart')

    def test_column_saved(self):
        resp = self.upload(',Notice Period (days)', ',60')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(User.objects.get(email='np.imp1@test.com').notice_period_days, 60)

    def test_old_template_without_column_still_imports(self):
        resp = self.upload()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(User.objects.get(email='np.imp1@test.com').notice_period_days)

    def test_blank_value_means_not_assigned(self):
        self.upload(',Notice Period', ',')
        self.assertIsNone(User.objects.get(email='np.imp1@test.com').notice_period_days)

    def test_invalid_value_is_a_row_error(self):
        resp = self.upload(',Notice Period', ',ninety')
        self.assertFalse(User.objects.filter(email='np.imp1@test.com').exists())
        body = str(resp.data)
        self.assertIn('notice_period_days', body)
        self.assertIn('whole number', body)


class SeparationTests(NoticeFixture):
    def payload(self, employee=None, notice=None):
        today = timezone.localdate()
        data = {'separation_type': 'resignation', 'reason': 'personal_reason', 'request_date': today.isoformat(),
                'proposed_last_working_day': (today + datetime.timedelta(days=60)).isoformat()}
        if employee is not None:
            data['employee_id'] = employee.employee_id
        if notice is not None:
            data['notice_period_days'] = notice
        return data

    def test_employee_cannot_shorten_assigned_notice(self):
        User.objects.filter(pk=self.emp.pk).update(notice_period_days=60)
        resp = self.api(self.emp).post(reverse('separation-request-list'), self.payload(notice=10), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        data = resp.data['data']
        self.assertEqual((data['notice_period_days'], data['assigned_notice_period_days']), (60, 60))
        expected = (timezone.localdate() + datetime.timedelta(days=60)).isoformat()
        self.assertEqual(data['expected_last_working_day'], expected)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.notice_period_days, 60)            # assigned value untouched

    def test_hr_may_enter_a_different_value_or_default_to_assigned(self):
        User.objects.filter(pk=self.emp.pk).update(notice_period_days=60)
        resp = self.api(self.hr_hyd).post(reverse('separation-request-list'), self.payload(self.emp, notice=15), format='json')
        self.assertEqual(resp.data['data']['notice_period_days'], 15)
        SeparationRequest.objects.all().update(status='cancelled')
        resp = self.api(self.hr_hyd).post(reverse('separation-request-list'), self.payload(self.emp), format='json')
        self.assertEqual(resp.data['data']['notice_period_days'], 60)
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.notice_period_days, 60)

    def test_without_assigned_notice_behaviour_unchanged(self):
        resp = self.api(self.emp).post(reverse('separation-request-list'), self.payload(notice=45), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['notice_period_days'], 45)
        self.assertIsNone(resp.data['data']['assigned_notice_period_days'])

    def test_employee_edit_keeps_assigned_notice(self):
        User.objects.filter(pk=self.emp.pk).update(notice_period_days=60)
        created = self.api(self.emp).post(reverse('separation-request-list'), self.payload(), format='json').data['data']
        resp = self.api(self.emp).patch(reverse('separation-request-detail', kwargs={'request_id': created['id']}),
                                        {'action': 'update', 'notice_period_days': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['notice_period_days'], 60)
