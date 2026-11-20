"""When HR / an admin punches someone in on the Attendance screen, that person's own dashboard shows Punch out, not Punch in again."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.services_manual_punches import sync_manual_punches

TODAY = timezone.localdate()


class HrPunchSyncTests(TestCase):
    def setUp(self):
        cache.clear()
        self.hr = make_user('sync-hr@test.com', role=make_role('sync_hr', permission_codenames=['attendance.create', 'attendance.edit', 'attendance.view']), branch='Mulugu')
        self.employee = make_user('sync-emp@test.com', employee_id='EMPSY001', role=make_role('sync_emp'), branch='Mulugu',
                                  date_of_joining=TODAY - datetime.timedelta(days=90))
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_COMPLETE, account_activated_at=timezone.now())

    def _client(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _hr_marks(self, **extra):
        body = {'employee_id': self.employee.employee_id, 'date': TODAY.isoformat(), 'status': 'present', 'clock_in': '09:05:00', 'reason': 'Forgot to punch in', **extra}
        return self._client(self.hr).post(reverse('hr-attendance-create'), body, format='json')

    def _session(self) -> dict:
        response = self._client(self.employee).get(reverse('attendance-today'))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def test_after_hr_punches_someone_in_their_dashboard_shows_punch_out(self):
        self.assertFalse(self._session()['is_clocked_in'])
        response = self._hr_marks()
        self.assertEqual(response.status_code, 201, response.data)
        session = self._session()
        self.assertTrue(session['is_clocked_in'], 'the dashboard must offer Punch out, not Punch in')
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertEqual((punch.punch_type, punch.source), ('IN', 'manual'))
        self.assertEqual(timezone.localtime(punch.punched_at).strftime('%H:%M'), '09:05')

    def test_marking_today_as_worked_without_a_clock_in_time_is_refused(self):
        for status in ('present', 'late', 'half_day', 'incomplete'):
            response = self._hr_marks(status=status, clock_in=None)
            self.assertEqual(response.status_code, 400, status)
            self.assertIn('clock-in time', response.data['message'])
        self.assertEqual(AttendanceRecord.objects.filter(employee=self.employee).count(), 0)

    def test_the_time_is_not_needed_for_other_statuses_or_other_days(self):
        self.assertEqual(self._hr_marks(status='on_leave', clock_in=None).status_code, 201)
        AttendanceRecord.objects.filter(employee=self.employee).delete()
        yesterday = (TODAY - datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self._hr_marks(date=yesterday, status='present', clock_in=None).status_code, 201)

    def test_editing_today_to_a_worked_status_needs_a_time_unless_one_exists(self):
        record_id = self._hr_marks(status='on_leave', clock_in=None).data['data']['record_id']
        url = reverse('hr-attendance-detail', kwargs={'pk': record_id})
        refused = self._client(self.hr).patch(url, {'status': 'present', 'reason': 'He came in'}, format='json')
        self.assertEqual(refused.status_code, 400, refused.data)
        allowed = self._client(self.hr).patch(url, {'status': 'present', 'clock_in': '09:10:00', 'reason': 'He came in'}, format='json')
        self.assertEqual(allowed.status_code, 200, allowed.data)
        self.assertTrue(self._session()['is_clocked_in'])

    def test_when_the_person_then_punches_out_the_day_closes_normally(self):
        self._hr_marks()
        out = self._client(self.employee).post(reverse('attendance-punch'), {'punch_type': 'OUT', 'attendance_mode': 'field'}, format='json')
        self.assertIn(out.status_code, (200, 201), getattr(out, 'data', None))
        self.assertFalse(self._session()['is_clocked_in'])

    def test_hr_giving_both_times_closes_the_day_so_nothing_is_asked_of_the_employee(self):
        self._hr_marks(clock_out='18:10:00')
        session = self._session()
        self.assertFalse(session['is_clocked_in'])
        self.assertEqual(list(AttendancePunch.objects.filter(employee=self.employee).order_by('punched_at').values_list('punch_type', flat=True)), ['IN', 'OUT'])

    def test_hr_adding_the_clock_out_later_closes_an_open_punch_in(self):
        record_id = self._hr_marks().data['data']['record_id']
        self.assertTrue(self._session()['is_clocked_in'])
        edited = self._client(self.hr).patch(reverse('hr-attendance-detail', kwargs={'pk': record_id}), {'clock_out': '18:20:00', 'reason': 'Left at 6:20'}, format='json')
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertFalse(self._session()['is_clocked_in'])

    def test_it_never_adds_punches_to_a_person_who_already_punched_and_never_duplicates(self):
        AttendancePunch.objects.create(employee=self.employee, punch_type='IN', punched_at=timezone.now() - datetime.timedelta(minutes=30), source='web', attendance_mode='office')
        self.assertEqual(sync_manual_punches(self.employee, TODAY, datetime.time(9, 0), None, 'present'), 0)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 1)

    def test_it_only_touches_today_and_only_days_marked_as_worked(self):
        yesterday = TODAY - datetime.timedelta(days=1)
        self.assertEqual(sync_manual_punches(self.employee, yesterday, datetime.time(9, 0), datetime.time(18, 0), 'present'), 0)
        self.assertEqual(sync_manual_punches(self.employee, TODAY, datetime.time(9, 0), None, 'absent'), 0)
        self.assertEqual(sync_manual_punches(self.employee, TODAY, datetime.time(9, 0), None, 'on_leave'), 0)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_a_clock_out_before_the_punch_in_is_ignored(self):
        self.assertEqual(sync_manual_punches(self.employee, TODAY, datetime.time(9, 0), datetime.time(8, 0), 'present'), 1)
        self.assertEqual(list(AttendancePunch.objects.filter(employee=self.employee).values_list('punch_type', flat=True)), ['IN'])

    def test_running_it_twice_is_harmless(self):
        sync_manual_punches(self.employee, TODAY, datetime.time(9, 0), datetime.time(18, 0), 'present')
        sync_manual_punches(self.employee, TODAY, datetime.time(9, 0), datetime.time(18, 0), 'present')
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 2)
        self.assertEqual(AttendanceRecord.objects.filter(employee=self.employee).count(), 0)
