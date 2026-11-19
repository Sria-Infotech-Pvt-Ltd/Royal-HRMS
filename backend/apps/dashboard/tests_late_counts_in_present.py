"""Late people count in BOTH numbers: Present (they came in) and Late (they arrived after the grace time).

Covers the HR dashboard's attendance summary and the HR employee month view's day counts. The Attendance page's own cards and tabs are
covered in apps.attendance.tests_dashboard_five_cards.
"""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord

TODAY = timezone.localdate()


class HrDashboardSummaryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('late-sum-admin@test.com', make_role('r_latesum', permission_codenames=['employees.view']),
                               full_name='Admin', employee_id='LS0', onboarding_status=User.ONBOARDING_COMPLETE)
        for number, fields in enumerate((
            dict(status='present'),
            dict(status='present', is_late=True),     # late login: full hours, stored as Present
            dict(status='late', is_late=True),        # late and short
            dict(status='absent'),
        ), start=1):
            employee = make_user(f'late-sum-{number}@test.com', employee_id=f'LS{number}', full_name=f'Emp {number}')
            AttendanceRecord.objects.create(employee=employee, date=TODAY, **fields)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_late_people_are_in_present_and_in_late(self):
        response = self.client.get('/api/dashboard/hr/attendance-summary/')
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data['data']
        self.assertEqual(data['present'], 3)     # on time + late login + late
        self.assertEqual(data['late'], 2)        # late login + late
        self.assertEqual(data['absent'], 1)


class EmployeeMonthCountsTests(TestCase):
    def test_present_days_include_late_days_and_late_days_include_late_logins(self):
        admin = make_user('late-month-admin@test.com', make_role('r_latemonth', permission_codenames=['attendance.view']),
                          full_name='Admin', employee_id='LM0', onboarding_status=User.ONBOARDING_COMPLETE)
        employee = make_user('late-month-emp@test.com', employee_id='LM1', full_name='Month Emp')
        month_start = TODAY.replace(day=1)
        for offset, fields in enumerate((dict(status='present'), dict(status='present', is_late=True), dict(status='late', is_late=True))):
            AttendanceRecord.objects.create(employee=employee, date=month_start + datetime.timedelta(days=offset), **fields)
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.get(reverse('hr-employee-month-calendar'), {'employee_id': str(employee.pk), 'month': TODAY.strftime('%Y-%m')})
        self.assertEqual(response.status_code, 200, response.data)
        stats = response.data['data']['stats']
        self.assertEqual(stats['present'], 3)    # on time + late login + late
        self.assertEqual(stats['late'], 2)       # late login + late
