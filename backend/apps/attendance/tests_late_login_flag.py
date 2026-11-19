"""A late punch-in with the full hours worked is stored as Present; the calendar must still say the person arrived late ("Late login")."""
import datetime as dt
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.services_attendance import AttendanceDashboardService, AttendanceProcessorService
from apps.attendance.tests_recalculate_attendance import cfg

IST = ZoneInfo('Asia/Kolkata')
TUE = dt.date(2026, 11, 3)


def punch(employee, day, kind, hour, minute):
    AttendancePunch.objects.create(
        employee=employee, punch_type=kind, source='web',
        punched_at=dt.datetime.combine(day, dt.time(hour, minute)).replace(tzinfo=IST),
    )


class LateLoginFlagTests(TestCase):
    def setUp(self):
        # The attendance settings are cached across tests, so these tests fix their own: shift 09:00, 15 minutes grace, 30 minute break,
        # full day 8 hours, late forgiven when the full hours are worked (the shipped defaults).
        patcher = mock.patch('apps.attendance.services_attendance._get_settings', return_value=cfg(full='8', half='4', break_minutes=30, grace=15, forgive_late=True))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.employee = make_user('late-login@test.com', full_name='Late Emp', employee_id='LL1', branch='Hyderabad')

    def day(self, number=3):
        return AttendanceDashboardService.get_calendar(self.employee, 2026, 11)['days'][number]

    def test_late_but_full_hours_is_present_and_marked_as_a_late_login(self):
        punch(self.employee, TUE, 'IN', 10, 14)
        punch(self.employee, TUE, 'OUT', 19, 20)                       # 9h06 on the clock, 8h36 after the break: a full day
        AttendanceProcessorService.process_day(self.employee, TUE)
        record = AttendanceRecord.objects.get(employee=self.employee, date=TUE)
        self.assertEqual(record.status, 'present')                      # the stored status is unchanged
        entry = self.day()
        self.assertEqual(entry['status'], 'Present')
        self.assertTrue(entry['is_late'])
        self.assertTrue(entry['late_forgiven'])
        self.assertEqual(entry['late_after'], '09:15')                  # shift 09:00 + 15 minutes grace

    def test_on_time_is_neither_late_nor_a_late_login(self):
        punch(self.employee, TUE, 'IN', 9, 5)
        punch(self.employee, TUE, 'OUT', 18, 10)
        AttendanceProcessorService.process_day(self.employee, TUE)
        entry = self.day()
        self.assertEqual(entry['status'], 'Present')
        self.assertFalse(entry['is_late'])
        self.assertFalse(entry['late_forgiven'])
        self.assertIsNone(entry['late_after'])

    def test_late_and_short_stays_late_and_is_not_a_late_login(self):
        punch(self.employee, TUE, 'IN', 10, 14)
        punch(self.employee, TUE, 'OUT', 17, 30)                       # 7h16 on the clock, under the full day after the break
        AttendanceProcessorService.process_day(self.employee, TUE)
        entry = self.day()
        self.assertEqual(entry['status'], 'Late')                       # already says late; no extra tag
        self.assertTrue(entry['is_late'])
        self.assertFalse(entry['late_forgiven'])

    def test_a_day_with_no_record_has_no_flags(self):
        entry = AttendanceDashboardService.get_calendar(self.employee, 2026, 11)['days'][4]
        self.assertFalse(entry['is_late'])
        self.assertFalse(entry['late_forgiven'])
        self.assertIsNone(entry['late_after'])

    def test_the_flag_reaches_the_employees_calendar_api(self):
        punch(self.employee, TUE, 'IN', 10, 14)
        punch(self.employee, TUE, 'OUT', 19, 20)
        AttendanceProcessorService.process_day(self.employee, TUE)
        client = APIClient()
        client.force_authenticate(user=User.objects.get(pk=self.employee.pk))
        response = client.get(reverse('attendance-calendar'), {'month': 11, 'year': 2026})
        self.assertEqual(response.status_code, 200, response.data)
        entry = response.data['data']['calendar']['days']['3']
        self.assertTrue(entry['late_forgiven'])
        self.assertEqual(entry['late_after'], '09:15')

    def test_the_hr_month_view_carries_it_for_managers(self):
        punch(self.employee, TUE, 'IN', 10, 14)
        punch(self.employee, TUE, 'OUT', 19, 20)
        AttendanceProcessorService.process_day(self.employee, TUE)
        admin = make_user('late-admin@test.com', make_role('r_lladmin', permission_codenames=['attendance.view', 'settings.edit']),
                          full_name='Admin', employee_id='LLA1', onboarding_status=User.ONBOARDING_COMPLETE)
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.get(reverse('hr-employee-month-calendar'), {'employee_id': str(self.employee.pk), 'month': '2026-11'})
        self.assertEqual(response.status_code, 200, response.data)
        days = {entry['date']: entry for entry in response.data['data']['days']}
        self.assertTrue(days['2026-11-03']['late_forgiven'])
        self.assertFalse(days['2026-11-04']['late_forgiven'])
