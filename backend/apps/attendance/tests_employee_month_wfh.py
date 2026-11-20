"""The HR employee month calendar says which days were work from home (a tag beside the status, not a status of its own)."""
import datetime

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, WorkFromHomeRequest

MONTH_START = datetime.date(2026, 11, 1)


def wfh_request(employee, start, end, status):
    return WorkFromHomeRequest.objects.create(
        employee=employee, start_date=start, end_date=end, status=status, reason='Home', latitude=17.385044, longitude=78.486671,
    )


class EmployeeMonthWfhTests(TestCase):
    def setUp(self):
        self.admin = make_user('wfh-month-admin@test.com', make_role('r_wfhmonth', permission_codenames=['attendance.view']),
                               full_name='Admin', employee_id='WM0', onboarding_status=User.ONBOARDING_COMPLETE)
        self.employee = make_user('wfh-month-emp@test.com', employee_id='WM1', full_name='Samreen')

    def month(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get(reverse('hr-employee-month-calendar'), {'employee_id': str(self.employee.pk), 'month': '2026-11'})
        self.assertEqual(response.status_code, 200)
        return response.json()['data']

    def by_date(self, data):
        return {day['date']: day for day in data['days']}

    def test_a_day_whose_record_says_wfh_is_marked(self):
        AttendanceRecord.objects.create(employee=self.employee, date=datetime.date(2026, 11, 19), status='half_day', work_mode='wfh')
        AttendanceRecord.objects.create(employee=self.employee, date=datetime.date(2026, 11, 18), status='present', work_mode='office')
        data = self.month()
        days = self.by_date(data)
        self.assertTrue(days['2026-11-19']['is_wfh'])
        self.assertEqual(days['2026-11-19']['status'], 'half_day')               # the status itself is untouched
        self.assertFalse(days['2026-11-18']['is_wfh'])
        self.assertEqual(data['stats']['wfh'], 1)

    def test_an_approved_request_marks_its_days_even_without_a_punch(self):
        wfh_request(self.employee, datetime.date(2026, 11, 10), datetime.date(2026, 11, 12), REQ_APPROVED)
        data = self.month()
        days = self.by_date(data)
        self.assertEqual([d for d in days if days[d]['is_wfh']], ['2026-11-10', '2026-11-11', '2026-11-12'])
        self.assertEqual(days['2026-11-10']['status'], 'no_record')
        self.assertEqual(data['stats']['wfh'], 3)

    def test_a_request_that_is_not_approved_marks_nothing(self):
        wfh_request(self.employee, datetime.date(2026, 11, 10), datetime.date(2026, 11, 12), REQ_PENDING)
        data = self.month()
        self.assertFalse(any(day['is_wfh'] for day in data['days']))
        self.assertEqual(data['stats']['wfh'], 0)

    def test_a_day_with_both_a_wfh_record_and_a_request_counts_once(self):
        wfh_request(self.employee, datetime.date(2026, 11, 19), datetime.date(2026, 11, 19), REQ_APPROVED)
        AttendanceRecord.objects.create(employee=self.employee, date=datetime.date(2026, 11, 19), status='present', work_mode='wfh')
        self.assertEqual(self.month()['stats']['wfh'], 1)

    def test_a_request_that_started_last_month_marks_the_first_days(self):
        wfh_request(self.employee, datetime.date(2026, 10, 30), datetime.date(2026, 11, 2), REQ_APPROVED)
        days = self.by_date(self.month())
        self.assertTrue(days['2026-11-01']['is_wfh'] and days['2026-11-02']['is_wfh'])
        self.assertFalse(days['2026-11-03']['is_wfh'])
