"""
Attendance data privacy: ordinary employees see only their own attendance.

Employees can hold attendance.view / attendance.create / even
attendance.export (for their own punches and My Attendance) — none of that
may open up colleagues' records through lists, record ids, employee ids,
month calendars, exports, dashboards, audit history, the corrections queue,
the over-the-limit list or HR write actions. HR, branch HR, managers and
administrators keep their existing scopes (apps.attendance.access).
"""
from __future__ import annotations

import io
from datetime import time

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from apps.attendance.models import AttendanceCorrection, AttendanceRecord


class PrivacyBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.today = timezone.localdate()
        # An employee role that (as some companies configure) even carries export.
        emp_role = make_role('pv_staff', permission_codenames=['attendance.view', 'attendance.create',
                                                               'attendance.export'])
        mgr_role = make_role('pv_mgr', can_manage_team=True,
                             permission_codenames=['attendance.view', 'attendance.create', 'attendance.edit',
                                                   'attendance.export'])
        hr_role = make_role('pv_hr', permission_codenames=['attendance.view', 'attendance.create', 'attendance.edit',
                                                           'attendance.export'])
        admin_role = make_role('pv_admin', permission_codenames=['settings.edit', 'attendance.view',
                                                                 'attendance.export'])
        self.mgr = make_user('pv.mgr@test.com', role=mgr_role, full_name='Mona Manager', branch='North', employee_id='PVM')
        self.a = make_user('pv.a@test.com', role=emp_role, full_name='Alice Employee', branch='North', employee_id='PVA')
        self.b = make_user('pv.b@test.com', role=emp_role, full_name='Bob Colleague', branch='North', employee_id='PVB',
                           reporting_manager=self.mgr)
        self.c = make_user('pv.c@test.com', role=emp_role, full_name='Cara South', branch='South', employee_id='PVC')
        self.hr_north = make_user('pv.hrn@test.com', role=hr_role, full_name='North HR', branch='North', employee_id='PVH')
        self.hr_admin = make_user('pv.hra@test.com', role=hr_role, full_name='HR Admin', branch='', employee_id='PVHA')
        self.admin = make_user('pv.adm@test.com', role=admin_role, full_name='Sys Admin', branch='', employee_id='PVS')
        self.rec = {u.pk: AttendanceRecord.objects.create(
            employee=u, date=self.today, status='late', is_late=True, first_punch_in=time(10, 5),
            last_punch_out=time(18, 0), total_working_minutes=475) for u in (self.a, self.b, self.c)}
        self.clients = {}

    def api(self, user):
        if user.email not in self.clients:
            cl = APIClient()
            _login(cl, user.email)
            self.clients[user.email] = cl
        return self.clients[user.email]

    def names(self, user, url_name, **params):
        resp = self.api(user).get(reverse(url_name), {'date': self.today.isoformat(), **params})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        rows = data.get('results', data) if isinstance(data, dict) else data
        if isinstance(rows, dict):
            rows = rows.get('employees') or rows.get('records') or []
        return {r.get('name') or r.get('employee_name') for r in rows}


class EmployeeSeesOnlyOwnTests(PrivacyBase):
    def test_own_attendance_works(self):
        resp = self.api(self.a).get(reverse('attendance-calendar'),
                                    {'month': self.today.month, 'year': self.today.year})
        self.assertEqual(resp.status_code, 200)
        day = resp.data['data']['calendar']['days'][str(self.today.day)]
        self.assertEqual(day['clockIn'], '10:05')
        stats = self.api(self.a).get(reverse('attendance-stats'), {'month': self.today.month, 'year': self.today.year})
        self.assertEqual((stats.status_code, stats.data['data']['late_arrivals']), (200, 1))

    def test_attendance_list_is_own_only(self):
        self.assertEqual(self.names(self.a, 'hr-attendance-list'), {'Alice Employee'})
        self.assertEqual(self.names(self.a, 'hr-attendance-list', branch='North', search='Bob'), set())

    def test_colleague_record_by_id_or_employee_id(self):
        url = reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.b.pk].pk})
        self.assertEqual(self.api(self.a).get(url).status_code, 404)
        own = reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.a.pk].pk})
        self.assertEqual(self.api(self.a).get(own).status_code, 200)
        by_code = reverse('hr-attendance-detail', kwargs={'pk': '00000000-0000-0000-0000-000000000000'})
        self.assertEqual(self.api(self.a).get(by_code, {'employee_id': 'PVB', 'date': self.today.isoformat()}).status_code, 404)
        audit = reverse('hr-attendance-audit', kwargs={'pk': self.rec[self.b.pk].pk})
        self.assertEqual(self.api(self.a).get(audit).status_code, 404)

    def test_monthly_calendar_of_colleague(self):
        url = reverse('hr-employee-month-calendar')
        month = f'{self.today:%Y-%m}'
        for who in (str(self.b.pk), 'PVB', str(self.c.pk)):
            self.assertEqual(self.api(self.a).get(url, {'employee_id': who, 'month': month}).status_code, 403, who)
        self.assertEqual(self.api(self.a).get(url, {'employee_id': str(self.a.pk), 'month': month}).status_code, 200)

    def test_export_contains_only_own_rows(self):
        resp = self.api(self.a).get(reverse('hr-attendance-export'), {'date': self.today.isoformat(), 'branch': 'North'})
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Alice Employee', body)
        self.assertNotIn('Bob Colleague', body)
        self.assertNotIn('Cara South', body)

    def test_reports_and_queues_are_own_only(self):
        for name in ('hr-un-punches', 'hr-invalid-punches', 'hr-overtime-list'):
            self.assertLessEqual(self.names(self.a, name), {'Alice Employee'}, name)
        resp = self.api(self.a).get(reverse('hr-attendance-dashboard'), {'date': self.today.isoformat()})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Bob Colleague', str(resp.data))

    def test_over_the_limit_list_refused(self):
        self.assertEqual(self.api(self.a).get(reverse('attendance-late-arrival-limit-employees')).status_code, 403)

    def test_hr_write_actions_refused(self):
        cl = self.api(self.a)
        day = self.today.isoformat()
        checks = [
            cl.post(reverse('hr-attendance-create'), {'employee_id': 'PVB', 'date': day, 'clock_in': '09:00',
                                                       'clock_out': '18:00'}, format='json'),
            cl.patch(reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.b.pk].pk}),
                     {'clock_in': '09:00'}, format='json'),
            cl.post(reverse('hr-overtime-create'), {'employee_id': 'PVB', 'date': day, 'ot_type': 'regular',
                                                     'ot_start': '18:00', 'ot_end': '20:00'}, format='json'),
            cl.post(reverse('hr-attendance-reprocess'), {'date': day}, format='json'),
            cl.post(reverse('weekly-off-assignments-bulk'), {}, format='json'),
            cl.post(reverse('hr-attendance-import'), {'file': io.BytesIO(b'x')}, format='multipart'),
        ]
        self.assertEqual([r.status_code for r in checks], [403] * len(checks))
        b = AttendanceRecord.objects.get(pk=self.rec[self.b.pk].pk)
        self.assertEqual(b.first_punch_in, time(10, 5))

    def test_corrections_queue_and_review(self):
        # Bob's correction with no HR assigned (the branch-wide "orphan" case).
        corr = AttendanceCorrection.objects.create(employee=self.b, date=self.today, punch_type='IN',
                                                   requested_in_time=time(9, 0), reason='forgot_to_punch',
                                                   status=AttendanceCorrection.STATUS_L2_PENDING)
        resp = self.api(self.a).get(reverse('hr-corrections-list'))
        self.assertEqual([r['name'] for r in resp.data['data']['results']], [])
        r = self.api(self.a).patch(reverse('hr-correction-review', kwargs={'pk': corr.pk}), {'action': 'approve'},
                                   format='json')
        self.assertEqual(r.status_code, 403)
        corr.refresh_from_db()
        self.assertEqual(corr.status, AttendanceCorrection.STATUS_L2_PENDING)
        # North HR still reaches it.
        resp = self.api(self.hr_north).get(reverse('hr-corrections-list'))
        self.assertIn('Bob Colleague', [r['name'] for r in resp.data['data']['results']])


class StaffKeepAccessTests(PrivacyBase):
    def test_branch_hr_limited_to_branch(self):
        north = {'Alice Employee', 'Bob Colleague', 'Mona Manager', 'North HR'}   # every active North employee
        self.assertEqual(self.names(self.hr_north, 'hr-attendance-list'), north)
        self.assertEqual(self.names(self.hr_north, 'hr-attendance-list', branch='South'), north)  # param ignored
        url = reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.c.pk].pk})
        self.assertEqual(self.api(self.hr_north).get(url).status_code, 404)
        self.assertEqual(self.api(self.hr_north).get(
            reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.b.pk].pk})).status_code, 200)
        month = reverse('hr-employee-month-calendar')
        self.assertEqual(self.api(self.hr_north).get(month, {'employee_id': str(self.c.pk),
                                                             'month': f'{self.today:%Y-%m}'}).status_code, 403)

    def test_hr_admin_and_system_admin_see_everyone(self):
        everyone = {'Alice Employee', 'Bob Colleague', 'Cara South'}
        self.assertTrue(everyone <= self.names(self.hr_admin, 'hr-attendance-list'))
        self.assertTrue(everyone <= self.names(self.admin, 'hr-attendance-list'))
        for user in (self.hr_admin, self.admin):
            url = reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.c.pk].pk})
            self.assertEqual(self.api(user).get(url).status_code, 200)
        body = self.api(self.admin).get(reverse('hr-attendance-export'), {'date': self.today.isoformat()}).content.decode()
        self.assertTrue(all(n in body for n in everyone))

    def test_manager_sees_direct_reports(self):
        self.assertEqual(self.names(self.mgr, 'hr-attendance-list'), {'Bob Colleague'})
        self.assertEqual(self.api(self.mgr).get(
            reverse('hr-attendance-detail', kwargs={'pk': self.rec[self.a.pk].pk})).status_code, 404)
