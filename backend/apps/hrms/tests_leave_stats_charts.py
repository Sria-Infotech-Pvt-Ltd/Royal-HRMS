"""The leave analytics screen draws charts: the stats endpoint returns requests per month and approved days per leave type."""
import datetime
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, LeaveRequest

YEAR = 2030


def _leave(employee, leave_type, start, days, status):
    return LeaveRequest.objects.create(
        employee=employee, leave_type=leave_type, start_date=start, end_date=start + datetime.timedelta(days=int(days) - 1),
        total_days=Decimal(days), reason='Personal work', status=status,
    )


class LeaveStatsChartDataTests(TestCase):
    def setUp(self):
        self.employee = make_user('leave.charts@test.com', employee_id='EMPLC001', branch='Kondapur')
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)
        _leave(self.employee, 'casual', datetime.date(YEAR, 3, 4), 2, REQ_APPROVED)
        _leave(self.employee, 'sick', datetime.date(YEAR, 3, 18), 1, REQ_APPROVED)
        _leave(self.employee, 'casual', datetime.date(YEAR, 5, 6), 1, REQ_PENDING)

    def _data(self):
        response = self.client.get('/api/leave/stats/', {'year': YEAR})
        self.assertEqual(response.status_code, 200)
        return response.json()['data']

    def test_monthly_has_twelve_months_with_requests_and_approved_days(self):
        monthly = self._data()['monthly']
        self.assertEqual([m['month'] for m in monthly], list(range(1, 13)))
        self.assertEqual((monthly[2]['requests'], monthly[2]['approved_days']), (2, 3.0))
        self.assertEqual((monthly[4]['requests'], monthly[4]['approved_days']), (1, 0.0))   # pending: counted, no approved days
        self.assertEqual((monthly[0]['requests'], monthly[0]['approved_days']), (0, 0.0))

    def test_by_type_counts_approved_days_only_largest_first(self):
        self.assertEqual(self._data()['by_type'], [{'leave_type': 'casual', 'days': 2.0}, {'leave_type': 'sick', 'days': 1.0}])
