"""UAT-048: days asked for by pending requests are reserved: available = entitlement - used - pending, released on reject/cancel."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.hrms.models import REQ_CANCELLED, REQ_PENDING, REQ_REJECTED, LeaveBalance, LeavePolicy, LeaveRequest
from apps.hrms.services_leave_ledger import pending_leave_days


def _first_monday(year, month):
    day = datetime.date(year, month, 1)
    while day.weekday() != 0:
        day += datetime.timedelta(days=1)
    return day


YEAR = 2030  # far from the seeded holiday calendar, so every Monday-Thursday is a plain working day
MONDAY = _first_monday(YEAR, 3)


class PendingLeaveReservationTests(TestCase):
    def setUp(self):
        cache.clear()
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={
                'annual_days': 4, 'is_active': True, 'convert_to_lop': False, 'allow_negative_balance': False,
                'minimum_notice_period': 0, 'maximum_consecutive_days': 0, 'minimum_service_period': 0, 'applicable_gender': 'all',
            },
        )
        self.employee = make_user('leave.pending@test.com', employee_id='EMPLP001', branch='Kondapur')
        LeaveBalance.objects.create(employee=self.employee, leave_type='casual', year=YEAR, total_days=4, used_days=0)
        self.client = APIClient()
        self.client.force_authenticate(user=self.employee)

    def _apply(self, start, days=1, duration='full_day'):
        end = start + datetime.timedelta(days=days - 1)
        return self.client.post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': duration, 'start_date': start.isoformat(), 'end_date': end.isoformat(), 'reason': 'Personal family work',
        }, format='json')

    def _balance(self):
        rows = self.client.get(reverse('leave-balance'), {'year': YEAR}).json()['data']
        rows = rows['results'] if isinstance(rows, dict) and 'results' in rows else rows
        return next(row for row in rows if row['leave_type'] == 'casual')

    def test_the_reported_overbooking_is_rejected(self):
        self.assertEqual(self._apply(MONDAY, 1).status_code, 201)                                  # 1 day: 3 left
        refused = self._apply(MONDAY + datetime.timedelta(days=7), 4)                              # 4 days: only 3 free
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Insufficient balance. You have 3 day(s) available', refused.json()['message'])
        self.assertIn('1 more day(s) are held by your pending requests', refused.json()['message'])
        self.assertEqual(self._apply(MONDAY + datetime.timedelta(days=7), 3).status_code, 201)     # 3 days fits exactly
        self.assertEqual(self._apply(MONDAY + datetime.timedelta(days=3), 1, 'half_morning').status_code, 400)  # nothing left

    def test_balance_card_shows_pending_and_the_reduced_available(self):
        self._apply(MONDAY, 3)
        row = self._balance()
        self.assertEqual((row['pending_days'], row['available_days'], float(row['used_days'])), (3.0, 1.0, 0.0))

    def test_rejecting_or_cancelling_releases_the_days(self):
        first = self._apply(MONDAY, 2).json()['data']['id']
        second = self._apply(MONDAY + datetime.timedelta(days=7), 2).json()['data']['id']
        self.assertEqual(self._apply(MONDAY + datetime.timedelta(days=14), 1).status_code, 400)   # all 4 held
        LeaveRequest.objects.filter(pk=first).update(status=REQ_REJECTED)
        self.assertEqual(pending_leave_days(self.employee, 'casual', YEAR), 2.0)
        LeaveRequest.objects.filter(pk=second).update(status=REQ_CANCELLED)
        self.assertEqual(pending_leave_days(self.employee, 'casual', YEAR), 0.0)
        self.assertEqual(self._apply(MONDAY + datetime.timedelta(days=14), 4).status_code, 201)  # the whole balance is free again

    def test_preview_includes_pending_days(self):
        self._apply(MONDAY, 2)
        preview = self.client.get(reverse('leave-request-list'), {
            'action': 'preview', 'leave_type': 'casual', 'duration': 'full_day',
            'start_date': (MONDAY + datetime.timedelta(days=7)).isoformat(), 'end_date': (MONDAY + datetime.timedelta(days=9)).isoformat(),
        }).json()['data']
        self.assertEqual((preview['available_balance'], preview['pending_days']), (2.0, 2.0))
        self.assertFalse(preview['sufficient_balance'])  # 3 days asked, 2 free

    def test_only_waiting_requests_count(self):
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', duration='full_day', start_date=MONDAY, end_date=MONDAY, total_days=1,
            status=REQ_REJECTED,
        )
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='casual', duration='full_day', start_date=MONDAY + datetime.timedelta(days=7),
            end_date=MONDAY + datetime.timedelta(days=7), total_days=1, status=REQ_PENDING,
        )
        self.assertEqual(pending_leave_days(self.employee, 'casual', YEAR), 1.0)
        self.assertEqual(pending_leave_days(self.employee, 'sick', YEAR), 0.0)
