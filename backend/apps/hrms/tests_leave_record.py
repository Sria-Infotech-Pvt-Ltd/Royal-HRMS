"""HR recording leave on an employee's behalf (POST /api/leave/requests/record/)."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import LeaveBalance, LeavePolicy, LeaveRequest

BRANCH = 'Test Branch'
URL = '/api/leave/requests/record/'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _next_weekday(start: datetime.date) -> datetime.date:
    day = start
    while day.weekday() >= 5:
        day += datetime.timedelta(days=1)
    return day


class LeaveRecordTests(TestCase):
    def setUp(self):
        cache.clear()
        hr_role = make_role('lr_hr', permission_codenames=['employees.view', 'leave.view', 'leave.record'])
        plain_role = make_role('lr_plain', permission_codenames=['employees.view', 'leave.view'])
        self.hr = make_user('lr_hr@test.com', role=hr_role, employee_id='LH1', branch=BRANCH)
        self.viewer = make_user('lr_view@test.com', role=plain_role, employee_id='LV1', branch=BRANCH)
        self.employee = make_user('lr_emp@test.com', employee_id='LE1', branch=BRANCH)
        self.other_branch = make_user('lr_other@test.com', employee_id='LO1', branch='Elsewhere')
        # Confirmed, not probation — this suite isn't testing UAT-028's
        # probation-eligibility rule, and make_user() defaults to probation,
        # which _without_application_windows() deliberately does NOT lift
        # (probation is an eligibility rule, same category as gender/branch/
        # department, not an application-window rule).
        from apps.accounts.models import User
        self.employee.employment_status = User.EMPLOYMENT_STATUS_CONFIRMED
        self.employee.save(update_fields=['employment_status'])
        LeavePolicy.objects.get_or_create(leave_type='casual', defaults={'annual_days': Decimal('12')})
        self.year = datetime.date.today().year
        self.day = _next_weekday(datetime.date(self.year, 6, 1))
        LeaveBalance.objects.create(employee=self.employee, leave_type='casual', year=self.year, total_days=Decimal('12'))

    def _body(self, **overrides):
        body = {'employee_id': 'LE1', 'leave_type': 'casual', 'start_date': self.day.isoformat(),
                'end_date': self.day.isoformat(), 'reason': 'Family function'}
        body.update(overrides)
        return body

    def test_hr_records_leave_and_the_balance_is_deducted(self):
        response = _api(self.hr).post(URL, self._body(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        leave = LeaveRequest.objects.get(employee=self.employee)
        self.assertEqual(leave.status, 'approved')
        self.assertEqual(LeaveBalance.objects.get(employee=self.employee, leave_type='casual').used_days, Decimal('1.0'))

    def test_requires_the_record_permission(self):
        self.assertEqual(_api(self.viewer).post(URL, self._body(), format='json').status_code, 403)

    def test_cannot_record_leave_for_yourself(self):
        LeaveBalance.objects.create(employee=self.hr, leave_type='casual', year=self.year, total_days=Decimal('12'))
        response = _api(self.hr).post(URL, self._body(employee_id='LH1'), format='json')
        self.assertEqual(response.status_code, 403)

    def test_out_of_branch_employee_is_not_found(self):
        self.assertEqual(_api(self.hr).post(URL, self._body(employee_id='LO1'), format='json').status_code, 404)

    def test_overlapping_leave_is_refused(self):
        self.assertEqual(_api(self.hr).post(URL, self._body(), format='json').status_code, 201)
        self.assertEqual(_api(self.hr).post(URL, self._body(), format='json').status_code, 400)

    def test_more_than_the_balance_is_refused_without_a_lop_policy(self):
        LeaveBalance.objects.filter(employee=self.employee).update(total_days=Decimal('0'))
        self.assertEqual(_api(self.hr).post(URL, self._body(), format='json').status_code, 400)

    def test_half_day_must_be_a_single_date(self):
        end = self.day + datetime.timedelta(days=1)
        response = _api(self.hr).post(URL, self._body(duration='first_half', end_date=end.isoformat()), format='json')
        self.assertEqual(response.status_code, 400)

    def test_balance_listing_includes_the_annual_entitlement(self):
        rows = _api(self.hr).get('/api/leave/balance/', {'employee_id': 'LE1', 'year': self.year}).data['data']
        self.assertEqual(rows[0]['annual_entitlement'], 12.0)
