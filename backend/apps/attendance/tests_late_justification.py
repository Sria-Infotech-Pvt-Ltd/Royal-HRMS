"""
Late-arrival justification (AttendanceCorrection, kind=late_justification).

Submission rules (medical proof, file type / size / real content, own late
days only, 3-day window, one open request), the Manager → HR chain (assigned
approvers only, reasons for reject / resubmission, resubmission), medical
proof privacy (owner + attendance.medical_proof_view in branch only; never a
manager by default, never a public URL), "Late (Excused)" (punches and
status untouched), and payroll late-mark deductions (excused days excluded,
pending / rejected still counted, processed cycles not recalculated until
reprocessed). Punch corrections keep working as before.
"""
from __future__ import annotations

import io
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule, EmployeeApprovalOverride
from apps.accounts.tests import _login
from apps.attendance.models import (
    AttendanceAuditLog, AttendanceCorrection, AttendanceLateMarkRules, AttendancePunch, AttendanceRecord,
    AttendanceSettings,
)
from apps.attendance.services_hr_corrections import approve_correction, reject_correction
from apps.notifications.models import Notification
from apps.payroll.tests_salary_components import SalaryFixtureMixin
from apps.payroll.views.cycles import process_payroll_cycle

IST = ZoneInfo('Asia/Kolkata')
PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def image_bytes(fmt):
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), (200, 30, 30)).save(buf, fmt)
    return buf.getvalue()


def upload(name='proof.pdf', content=PDF, content_type='application/pdf'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class LateBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        storage = InMemoryStorage(base_url='/media/')
        patcher = mock.patch.object(AttendanceCorrection._meta.get_field('supporting_document'), 'storage', storage)
        patcher.start()
        self.addCleanup(patcher.stop)

        emp_role = make_role('lj_staff', permission_codenames=['attendance.view', 'attendance.create'])
        mgr_role = make_role('lj_manager', can_manage_team=True,
                             permission_codenames=['attendance.view', 'attendance.create', 'attendance.edit'])
        hr_role = make_role('lj_hr', permission_codenames=['attendance.view', 'attendance.create',
                                                           'attendance.medical_proof_view'])
        self.manager = make_user('lj.mgr@test.com', role=mgr_role, full_name='LJ Manager', branch='North',
                                 employee_id='LJM')
        self.other_manager = make_user('lj.mgr2@test.com', role=mgr_role, full_name='Other Manager', branch='North',
                                       employee_id='LJM2')
        self.hr = make_user('lj.hr@test.com', role=hr_role, full_name='LJ HR', branch='North', employee_id='LJH')
        self.hr_south = make_user('lj.hr2@test.com', role=hr_role, full_name='South HR', branch='South',
                                  employee_id='LJH2')
        self.emp = make_user('lj.emp@test.com', role=emp_role, full_name='Late Emp', branch='North',
                             employee_id='LJE', reporting_manager=self.manager)
        self.peer = make_user('lj.peer@test.com', role=emp_role, full_name='Peer Emp', branch='North',
                              employee_id='LJP', reporting_manager=self.manager)
        for e in (self.emp, self.peer):
            EmployeeApprovalOverride.objects.create(
                employee=e, workflow_type=ApprovalWorkflowRule.WORKFLOW_ATTENDANCE_CORRECTION,
                l1_override=self.manager, l2_override=self.hr)

        self.today = timezone.localdate()
        self.day = self.today - timedelta(days=1)
        self.record = self.late_day(self.emp, self.day)
        self.clients = {}

    def late_day(self, employee, day):
        rec = AttendanceRecord.objects.create(
            employee=employee, date=day, status=AttendanceRecord.STATUS_LATE, is_late=True,
            first_punch_in=time(10, 7), last_punch_out=time(18, 40), total_working_minutes=500)
        for t, kind in ((time(10, 7), 'IN'), (time(18, 40), 'OUT')):
            AttendancePunch.objects.create(employee=employee, punch_type=kind,
                                           punched_at=timezone.datetime.combine(day, t).replace(tzinfo=IST))
        return rec

    def client_for(self, user):
        if user.email not in self.clients:
            c = APIClient()
            _login(c, user.email)
            self.clients[user.email] = c
        return self.clients[user.email]

    def submit(self, user=None, day=None, reason='medical', explanation='Fever, visited the clinic first.',
               document='default', **extra):
        body = {'date': (day or self.day).isoformat(), 'reason': reason, 'explanation': explanation, **extra}
        if document == 'default':
            document = upload() if reason == 'medical' else None
        if document is not None:
            body['document'] = document
        return self.client_for(user or self.emp).post(reverse('attendance-late-justification'), body,
                                                      format='multipart')

    def review(self, user, correction, action, remarks=''):
        return self.client_for(user).patch(reverse('hr-correction-review', kwargs={'pk': correction.pk}),
                                           {'action': action, 'remarks': remarks}, format='json')

    def doc(self, user, correction):
        return self.client_for(user).get(reverse('attendance-correction-document', kwargs={'pk': correction.pk}))

    def only(self):
        return AttendanceCorrection.objects.get(employee=self.emp, kind=AttendanceCorrection.KIND_LATE)


class SubmissionTests(LateBase):
    def test_medical_requires_proof(self):
        resp = self.submit(document=None)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('document', resp.data['data'])
        self.assertFalse(AttendanceCorrection.objects.exists())

    def test_medical_with_pdf_is_submitted_and_linked(self):
        resp = self.submit()
        self.assertEqual(resp.status_code, 201, resp.data)
        c = self.only()
        self.assertEqual((c.status, c.l1_approver, c.l2_approver, c.punch_type), ('pending', self.manager, self.hr, ''))
        self.assertEqual(c.attendance_record, self.record)
        self.assertTrue(c.supporting_document)
        audit = AttendanceAuditLog.objects.get(event='LATE_REASON_SUBMITTED')
        self.assertIn('proof attached (PDF', audit.new_value)
        self.assertNotIn('proof.pdf', audit.new_value + audit.action)        # file names are not logged
        self.assertTrue(Notification.objects.filter(user=self.emp, title__icontains='Late Arrival').exists())
        self.assertTrue(Notification.objects.filter(user=self.manager, title='Late Arrival Justification Pending').exists())

    def test_non_medical_proof_is_optional_but_still_validated(self):
        self.assertEqual(self.submit(reason='transport', explanation='Metro line was shut this morning.').status_code, 201)
        AttendanceCorrection.objects.all().delete()
        resp = self.submit(reason='personal', explanation='Family emergency at home today.',
                           document=upload('note.pdf', b'not a pdf at all'))
        self.assertEqual(resp.status_code, 400)

    def test_real_images_accepted(self):
        self.assertEqual(self.submit(document=upload('rx.png', image_bytes('PNG'), 'image/png')).status_code, 201)
        AttendanceCorrection.objects.all().delete()
        self.assertEqual(self.submit(document=upload('rx.jpg', image_bytes('JPEG'), 'image/jpeg')).status_code, 201)

    def test_invalid_type_and_size(self):
        self.assertEqual(self.submit(document=upload('rx.txt', b'hello', 'text/plain')).status_code, 400)
        big = PDF[:-6] + b'0' * (5 * 1024 * 1024) + b'%%EOF\n'
        resp = self.submit(document=upload('big.pdf', big))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('5 MB', resp.data['message'])

    def test_content_is_checked_not_the_name_or_declared_type(self):
        cases = [
            upload('rx.pdf', image_bytes('PNG'), 'application/pdf'),          # PNG renamed to .pdf
            upload('rx.png', b'\x89PNG\r\n\x1a\nnot really an image', 'image/png'),   # PNG header, junk body
            upload('rx.jpg', b'MZ\x90\x00 executable', 'image/jpeg'),           # not an image at all
            upload('rx.pdf', b'%PDF-1.4 truncated, no end marker', 'application/pdf'),
        ]
        for f in cases:
            resp = self.submit(document=f)
            self.assertEqual(resp.status_code, 400, f.name)
        self.assertFalse(AttendanceCorrection.objects.exists())

    def test_only_own_late_days(self):
        other_day = self.today - timedelta(days=2)
        self.late_day(self.peer, other_day)                       # the peer was late; the employee was not
        resp = self.submit(day=other_day, employee=str(self.peer.pk))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('marked late', resp.data['message'])
        self.assertFalse(AttendanceCorrection.objects.filter(employee=self.peer).exists())

    def test_non_late_day_refused(self):
        on_time = self.today - timedelta(days=2)
        AttendanceRecord.objects.create(employee=self.emp, date=on_time, status='present', is_late=False,
                                        first_punch_in=time(9, 0))
        self.assertEqual(self.submit(day=on_time).status_code, 400)

    def test_three_day_window(self):
        edge = self.today - timedelta(days=3)
        self.late_day(self.emp, edge)
        self.assertEqual(self.submit(day=edge).status_code, 201)
        too_old = self.today - timedelta(days=4)
        self.late_day(self.emp, too_old)
        resp = self.submit(day=too_old)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('within 3 calendar days', resp.data['message'])
        self.assertEqual(self.submit(day=self.today + timedelta(days=1)).status_code, 400)

    def test_one_open_request_per_date(self):
        self.assertEqual(self.submit().status_code, 201)
        resp = self.submit(reason='transport', explanation='Second attempt for the same day.')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already have an open', resp.data['message'])
        # After a final rejection a new request may be made (still inside the window).
        self.review(self.manager, self.only(), 'reject', 'Certificate is for a different date.')
        self.assertEqual(self.submit(reason='transport', explanation='Bus breakdown on the highway.').status_code, 201)

    def test_punch_corrections_unchanged(self):
        self.assertEqual(self.submit().status_code, 201)
        resp = self.client_for(self.emp).post(reverse('attendance-correction'), {
            'date': self.day.isoformat(), 'punch_type': 'IN', 'correct_in_time': '09:05',
            'reason': 'biometric_error', 'notes': 'Device did not read my face.'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)       # a pending justification does not block it
        punch = AttendanceCorrection.objects.get(kind='punch')
        self.assertEqual((punch.reason, punch.punch_type), ('biometric_error', 'IN'))
        bad = self.client_for(self.emp).post(reverse('attendance-correction'), {
            'date': self.day.isoformat(), 'punch_type': 'OUT', 'correct_out_time': '19:00', 'reason': 'medical'},
            format='json')
        self.assertEqual(bad.status_code, 422)                    # late reasons are not punch reasons


class ApprovalTests(LateBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.submit().status_code, 201)
        self.c = self.only()
        self.punches = list(AttendancePunch.objects.filter(employee=self.emp).order_by('punched_at')
                            .values_list('id', 'punched_at', 'punch_type'))

    def test_manager_then_hr_excuses_without_touching_punches(self):
        r = self.review(self.manager, self.c, 'approve')
        self.assertEqual((r.status_code, r.data['data']['status']), (200, 'l2_pending'))
        self.record.refresh_from_db()
        self.assertFalse(self.record.late_excused)                # not excused before the chain completes
        r = self.review(self.hr, self.c, 'approve')
        self.assertEqual((r.status_code, r.data['data']['status']), (200, 'approved'), r.data)
        self.record.refresh_from_db()
        self.assertTrue(self.record.late_excused)
        self.assertEqual((self.record.status, self.record.is_late), ('late', True))     # not converted to Present
        self.assertEqual((self.record.first_punch_in, self.record.last_punch_out), (time(10, 7), time(18, 40)))
        self.assertEqual(self.record.status_display, 'Late (Excused)')
        self.assertEqual(list(AttendancePunch.objects.filter(employee=self.emp).order_by('punched_at')
                              .values_list('id', 'punched_at', 'punch_type')), self.punches)
        self.c.refresh_from_db()
        self.assertEqual(self.c.attendance_record, self.record)
        events = set(AttendanceAuditLog.objects.filter(employee=self.emp).values_list('event', flat=True))
        self.assertTrue({'LATE_REASON_SUBMITTED', 'LATE_REASON_APPROVED', 'LATE_EXCUSED'} <= events)
        self.assertTrue(Notification.objects.filter(user=self.emp, title='Late Arrival Excused').exists())

    def test_calendar_and_history_show_late_excused(self):
        self.review(self.manager, self.c, 'approve')
        self.review(self.hr, self.c, 'approve')
        resp = self.client_for(self.emp).get(reverse('attendance-calendar'),
                                             {'month': self.day.month, 'year': self.day.year})
        self.assertEqual(resp.status_code, 200)
        day = resp.data['data']['calendar']['days'][str(self.day.day)]
        self.assertEqual((day['status'], day['clockIn'], day['canExplainLate']), ('Late (Excused)', '10:07', False))
        row = next(r for r in resp.data['data']['history'] if r['isoDate'] == self.day.isoformat())
        self.assertEqual((row['status'], row['lateJustificationStatus']), ('Late (Excused)', 'approved'))

    def test_only_assigned_approvers(self):
        self.assertEqual(self.review(self.other_manager, self.c, 'approve').status_code, 403)
        self.assertEqual(self.review(self.hr, self.c, 'approve').status_code, 403)       # HR is L2, not L1
        self.assertEqual(self.review(self.emp, self.c, 'approve').status_code, 403)      # no self-approval
        self.review(self.manager, self.c, 'approve')
        self.assertEqual(self.review(self.hr_south, self.c, 'approve').status_code, 403)  # not the assigned HR
        self.assertEqual(self.review(self.manager, self.c, 'approve').status_code, 403)   # L1 can't act at L2
        self.record.refresh_from_db()
        self.assertFalse(self.record.late_excused)

    def test_rejection_needs_a_reason_and_stays_late(self):
        resp = self.review(self.manager, self.c, 'reject')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('remarks', resp.data['data'])
        resp = self.review(self.manager, self.c, 'reject', 'The certificate is for another date.')
        self.assertEqual(resp.data['data']['status'], 'rejected')
        self.record.refresh_from_db()
        self.assertFalse(self.record.late_excused)
        mine = self.client_for(self.emp).get(reverse('attendance-corrections-my'), {'kind': 'late_justification'})
        row = mine.data['data']['results'][0]
        self.assertEqual((row['status'], row['rejection_reason']), ('rejected', 'The certificate is for another date.'))
        self.assertTrue(Notification.objects.filter(user=self.emp, title='Late Arrival Justification Rejected').exists())

    def test_resubmission_with_replacement_proof(self):
        self.assertEqual(self.review(self.manager, self.c, 'resubmit').status_code, 400)        # reason required
        resp = self.review(self.manager, self.c, 'resubmit', 'Upload the doctor\'s note, not the bill.')
        self.assertEqual(resp.data['data']['status'], 'resubmit')
        old_file = AttendanceCorrection.objects.get(pk=self.c.pk).supporting_document.name
        mine = self.client_for(self.emp).get(reverse('attendance-corrections-my'), {'kind': 'late_justification'})
        self.assertTrue(mine.data['data']['results'][0]['can_resubmit'])
        self.assertEqual(mine.data['data']['results'][0]['status_label'], 'Resubmission Required')
        # Someone else cannot resubmit it.
        url = reverse('attendance-late-justification-resubmit', kwargs={'pk': self.c.pk})
        self.assertEqual(self.client_for(self.peer).post(url, {'explanation': 'Trying to change it.'},
                                                         format='multipart').status_code, 404)
        resp = self.client_for(self.emp).post(url, {
            'explanation': 'Attached the doctor\'s note from the clinic.',
            'document': upload('note.png', image_bytes('PNG'), 'image/png')}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        c = AttendanceCorrection.objects.get(pk=self.c.pk)
        self.assertEqual((c.status, c.resubmission_count, c.l1_status), ('pending', 1, None))
        self.assertNotEqual(c.supporting_document.name, old_file)
        events = list(AttendanceAuditLog.objects.filter(employee=self.emp).values_list('event', flat=True))
        self.assertIn('LATE_REASON_RESUBMIT_ASKED', events)
        self.assertIn('LATE_REASON_RESUBMITTED', events)
        self.review(self.manager, c, 'approve')
        self.review(self.hr, c, 'approve')
        self.record.refresh_from_db()
        self.assertTrue(self.record.late_excused)

    def test_medical_proof_privacy(self):
        ok = self.doc(self.emp, self.c)
        self.assertEqual((ok.status_code, ok['Content-Type'], ok['Cache-Control']), (200, 'application/pdf',
                                                                                     'private, no-store'))
        self.assertEqual(self.doc(self.hr, self.c).status_code, 200)
        self.assertEqual(self.doc(self.manager, self.c).status_code, 404)          # manager: never the file
        self.assertEqual(self.doc(self.hr_south, self.c).status_code, 404)         # other branch
        self.assertEqual(self.doc(self.peer, self.c).status_code, 404)
        self.assertEqual(APIClient().get(reverse('attendance-correction-document',
                                                 kwargs={'pk': self.c.pk})).status_code, 401)

        def row(user):
            resp = self.client_for(user).get(reverse('hr-corrections-list'), {'kind': 'late_justification'})
            return resp.data['data']['results'][0]
        mgr_row, hr_row = row(self.manager), row(self.hr)
        self.assertEqual((mgr_row['has_document'], mgr_row['can_view_document'], mgr_row['document_name']),
                         (True, False, ''))
        self.assertEqual(mgr_row['explanation'], 'Fever, visited the clinic first.')   # managers see the reason
        self.assertEqual((hr_row['can_view_document'], hr_row['document_name']), (True, 'proof.pdf'))
        for r in (mgr_row, hr_row):
            self.assertFalse(any('media' in str(v) or 'http' in str(v) for v in r.values()))   # no file URLs

    def test_filters(self):
        self.late_day(self.peer, self.day)
        self.assertEqual(self.submit(user=self.peer, reason='transport',
                                     explanation='Train cancelled, took a bus.').status_code, 201)
        hr = self.client_for(self.manager)
        def ids(**q):
            resp = hr.get(reverse('hr-corrections-list'), {'kind': 'late_justification', **q})
            return {r['name'] for r in resp.data['data']['results']}
        self.assertEqual(ids(), {'Late Emp', 'Peer Emp'})
        self.assertEqual(ids(missing_proof='true'), {'Peer Emp'})
        self.assertEqual(ids(status='pending'), {'Late Emp', 'Peer Emp'})
        self.assertEqual(ids(status='approved'), set())


class PayrollLateExcusedTests(SalaryFixtureMixin, TestCase):
    """Late marks → LOP (after_allowance, 5 allowed, half day each after)."""

    def setUp(self):
        cache.clear()
        self.make_fixtures()
        self.assign(self.emp_a, ctc='600000', effective='2026-01-01')
        settings_row = AttendanceSettings.objects.create(is_active=True)
        AttendanceLateMarkRules.objects.create(settings=settings_row, late_marks_per_lop=5,
                                               lop_deduction_unit='half_day', late_mark_mode='after_allowance')
        self.records = [AttendanceRecord.objects.create(employee=self.emp_a, date=date(2026, 1, d),
                                                        status=AttendanceRecord.STATUS_LATE, is_late=True,
                                                        first_punch_in=time(10, 0))
                        for d in range(5, 12)]                              # 7 late days
        admin_role = make_role('lj_payroll_admin', permission_codenames=['settings.edit'])
        self.admin = make_user('lj.admin@test.com', role=admin_role, full_name='Admin', employee_id='LJA')

    def justification(self, rec, status='pending'):
        return AttendanceCorrection.objects.create(
            employee=self.emp_a, kind=AttendanceCorrection.KIND_LATE, date=rec.date, reason='transport',
            notes='Strike on the bus route.', status=status, attendance_record=rec)

    def lop(self, cycle=None):
        cycle = cycle or self.cycle(1)
        process_payroll_cycle(cycle)
        return self.payslip(cycle, self.emp_a).lop_days

    def test_excused_days_are_not_late_marks(self):
        self.assertEqual(self.lop(), Decimal('1.0'))                        # (7 − 5) × 0.5
        for rec in self.records[:2]:
            approve_correction(str(self.justification(rec, 'l2_pending').pk), self.admin)
        self.assertEqual(AttendanceRecord.objects.filter(late_excused=True).count(), 2)
        self.assertEqual(self.lop(), Decimal('0'))                          # 5 late marks — all allowed

    def test_pending_and_rejected_still_count(self):
        self.justification(self.records[0])                                 # pending
        rejected = self.justification(self.records[1], 'l2_pending')
        reject_correction(str(rejected.pk), self.admin, remarks='Not accepted.')
        self.assertEqual(self.lop(), Decimal('1.0'))

    def test_processed_cycle_changes_only_when_reprocessed(self):
        cycle = self.cycle(1)
        self.assertEqual(self.lop(cycle), Decimal('1.0'))
        for rec in self.records[:2]:
            approve_correction(str(self.justification(rec, 'l2_pending').pk), self.admin)
        self.assertEqual(self.payslip(cycle, self.emp_a).lop_days, Decimal('1.0'))   # stored payslip untouched
        self.assertEqual(self.lop(cycle), Decimal('0'))                               # reprocessing applies it
