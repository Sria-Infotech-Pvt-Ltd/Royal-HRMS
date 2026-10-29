"""
WFH medical proof (policy section 6) and the daily work report (section 7).

- Medical WFH needs a PDF/JPG/PNG proof up to 5 MB; ordinary WFH doesn't.
- Reports: only for an approved WFH day, not the future, one per day,
  editable until reviewed; reviewed by the request's L1 approver or HR, never
  the employee; Not accepted needs a reason.
- Attendance only changes with Attendance Settings → WFH report rule on:
  reviewer Half Day / Not accepted → Half Day / Absent; a past day with no
  on-time report → Absent. Off = attendance untouched.
"""
from __future__ import annotations

import datetime
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from apps.attendance.models import (
    AttendancePunch, AttendancePunchRules, AttendanceRecord, AttendanceSettings, AttendanceWorkingHours,
)
from apps.attendance.services_attendance import AttendanceProcessorService
from apps.hrms.models import REQ_APPROVED, WFHDailyReport, WorkFromHomeRequest

IST = ZoneInfo('Asia/Kolkata')
DAY = date(2026, 9, 1)   # a past Tuesday


class WfhFixture(TestCase):
    def setUp(self):
        cache.clear()
        storage = InMemoryStorage(base_url='/media/')
        patcher = mock.patch.object(WorkFromHomeRequest._meta.get_field('supporting_document'), 'storage', storage)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.manager = make_user('wfh.mgr@test.com', role=make_role('wfh_mgr', can_manage_team=True,
                                 permission_codenames=['wfh.approve']), employee_id='WM1', full_name='Senior', branch='WB')
        self.emp = make_user('wfh.emp@test.com', role=make_role('wfh_staff', permission_codenames=['wfh.create']),
                             employee_id='WE1', full_name='Remote Emp', branch='WB')
        self.emp.reporting_manager = self.manager
        self.emp.save(update_fields=['reporting_manager'])
        self.peer = make_user('wfh.peer@test.com', role=make_role('wfh_staff'), employee_id='WE2',
                              full_name='Peer', branch='WB')
        self.wfh = WorkFromHomeRequest.objects.create(
            employee=self.emp, start_date=DAY - timedelta(days=3), end_date=date.today(),
            latitude=Decimal('17.0'), longitude=Decimal('78.0'), status=REQ_APPROVED, l1_approver=self.manager,
        )

        settings_row = AttendanceSettings.objects.create(is_active=True)
        AttendanceWorkingHours.objects.create(settings=settings_row, shift_start=time(9, 30), shift_end=time(18, 30),
                                              grace_period_minutes=10, break_duration_minutes=45)
        self.rules = AttendancePunchRules.objects.create(settings=settings_row)

    def api(self, user):
        client = APIClient()
        _login(client, user.email)
        return client

    def submit(self, user=None, day=DAY, **extra):
        body = {'date': day.isoformat(), 'completed_work': 'Closed 3 tickets', **extra}
        return self.api(user or self.emp).post(reverse('wfh-report-list'), body, format='json')

    def review(self, user, report_id, outcome, remarks=''):
        return self.api(user).post(reverse('wfh-report-review', kwargs={'report_id': report_id}),
                                   {'outcome': outcome, 'remarks': remarks}, format='json')

    def work_full_day(self, day=DAY):
        for kind, hh in ((AttendancePunch.PUNCH_IN, 9), (AttendancePunch.PUNCH_OUT, 18)):
            AttendancePunch.objects.create(employee=self.emp, punch_type=kind,
                                           punched_at=datetime.datetime(day.year, day.month, day.day, hh, 30, tzinfo=IST))
        return AttendanceProcessorService.process_day(self.emp, day)

    def rule_on(self):
        AttendancePunchRules.objects.filter(pk=self.rules.pk).update(wfh_daily_report_required=True)
        cache.clear()


class MedicalProofTests(WfhFixture):
    def post_request(self, **extra):
        body = {'start_date': '2027-01-04', 'end_date': '2027-01-05', 'latitude': '17.1', 'longitude': '78.1', **extra}
        return self.api(self.peer).post(reverse('wfh-request-list'), body, format='multipart')

    def test_medical_wfh_requires_proof(self):
        resp = self.post_request(is_medical='true')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('medical proof', resp.data['message'])

    def test_medical_wfh_with_pdf_proof(self):
        proof = SimpleUploadedFile('rx.pdf', b'%PDF-1.4 rx', content_type='application/pdf')
        resp = self.post_request(is_medical='true', supporting_document=proof)
        self.assertEqual(resp.status_code, 201, resp.data)
        req = WorkFromHomeRequest.objects.get(employee=self.peer)
        self.assertTrue(req.is_medical)
        self.assertTrue(req.supporting_document.name)
        self.assertTrue(resp.data['data']['supporting_document_url'])

    def test_proof_type_checked(self):
        bad = SimpleUploadedFile('rx.txt', b'hello', content_type='text/plain')
        self.assertEqual(self.post_request(is_medical='true', supporting_document=bad).status_code, 400)

    def test_ordinary_wfh_unchanged(self):
        resp = self.api(self.peer).post(reverse('wfh-request-list'), {
            'start_date': '2027-01-04', 'end_date': '2027-01-05', 'latitude': 17.123456789, 'longitude': 78.1,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['data']['is_medical'])


class DailyReportTests(WfhFixture):
    def test_submit_and_edit_until_reviewed(self):
        resp = self.submit()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['data']['submitted_late'])          # DAY is in the past
        self.assertEqual(self.submit(completed_work='Closed 4 tickets').status_code, 200)
        self.assertEqual(WFHDailyReport.objects.get().completed_work, 'Closed 4 tickets')
        report_id = WFHDailyReport.objects.get().pk
        self.assertEqual(self.review(self.manager, report_id, 'full_day').status_code, 200)
        self.assertEqual(self.submit(completed_work='changed').status_code, 400)

    def test_today_is_on_time(self):
        resp = self.submit(day=date.today())
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['data']['submitted_late'])

    def test_rejected_without_approved_wfh_or_for_future(self):
        self.assertEqual(self.submit(user=self.peer).status_code, 400)
        self.assertEqual(self.submit(day=date.today() + timedelta(days=1)).status_code, 400)
        self.assertEqual(self.submit(completed_work='  ').status_code, 400)

    def test_review_permissions(self):
        report_id = self.submit().data['data']['id']
        self.assertEqual(self.review(self.emp, report_id, 'full_day').status_code, 403)     # own report
        self.assertEqual(self.review(self.peer, report_id, 'full_day').status_code, 403)
        self.assertEqual(self.review(self.manager, report_id, 'not_accepted').status_code, 400)  # needs reason
        self.assertEqual(self.review(self.manager, report_id, 'half_day').status_code, 200)

    def test_reviewer_queue(self):
        self.submit()
        mine = self.api(self.emp).get(reverse('wfh-report-list'), {'mine': '1'}).data['data']
        queue = self.api(self.manager).get(reverse('wfh-report-list')).data['data']
        self.assertEqual(len(mine), 1)
        self.assertEqual([r['employee_code'] for r in queue], ['WE1'])
        self.assertTrue(queue[0]['can_review'])
        self.assertEqual(self.api(self.peer).get(reverse('wfh-report-list')).data['data'], [])


class ReportAttendanceTests(WfhFixture):
    def test_rule_off_leaves_attendance_alone(self):
        rec = self.work_full_day()
        self.assertEqual((rec.status, rec.work_mode), (AttendanceRecord.STATUS_PRESENT, AttendanceRecord.WORK_MODE_WFH))

    def test_rule_on_missing_report_is_absent(self):
        self.rule_on()
        self.assertEqual(self.work_full_day().status, AttendanceRecord.STATUS_ABSENT)

    def test_rule_on_late_report_is_absent_until_reviewer_accepts(self):
        self.rule_on()
        self.work_full_day()
        report_id = self.submit().data['data']['id']
        self.assertEqual(AttendanceRecord.objects.get(employee=self.emp, date=DAY).status, AttendanceRecord.STATUS_ABSENT)
        self.review(self.manager, report_id, 'full_day')
        self.assertEqual(AttendanceRecord.objects.get(employee=self.emp, date=DAY).status, AttendanceRecord.STATUS_PRESENT)

    def test_rule_on_reviewer_half_day_and_not_accepted(self):
        self.rule_on()
        self.work_full_day()
        report_id = self.submit().data['data']['id']
        self.review(self.manager, report_id, 'half_day')
        self.assertEqual(AttendanceRecord.objects.get(employee=self.emp, date=DAY).status, AttendanceRecord.STATUS_HALF_DAY)

        day2 = DAY + timedelta(days=1)
        self.work_full_day(day2)
        report2 = self.submit(day=day2).data['data']['id']
        self.review(self.manager, report2, 'not_accepted', remarks='No detail')
        self.assertEqual(AttendanceRecord.objects.get(employee=self.emp, date=day2).status, AttendanceRecord.STATUS_ABSENT)

    def test_rule_on_today_without_report_not_penalised_yet(self):
        self.rule_on()
        today = date.today()
        AttendancePunch.objects.create(employee=self.emp, punch_type=AttendancePunch.PUNCH_IN,
                                       punched_at=datetime.datetime(today.year, today.month, today.day, 9, 30, tzinfo=IST))
        rec = AttendanceProcessorService.process_day(self.emp, today)
        self.assertNotEqual(rec.status, AttendanceRecord.STATUS_ABSENT)
