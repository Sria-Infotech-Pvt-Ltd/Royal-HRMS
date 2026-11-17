"""On-request leave (maternity, paternity): never credited to everyone each year; granted per case when an eligible employee applies."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, LeaveBalance, LeavePolicy, LeaveRequest
from apps.hrms.services_leave_event import days_taken_recently, ensure_event_balance, hide_unused_event_balances
from apps.hrms.views.leave_shared import _allocate_leaves_for_employee

YEAR = 2030  # far from the seeded holiday calendar, so every Monday-Thursday is a plain working day


def _first_monday(year, month):
    day = datetime.date(year, month, 1)
    while day.weekday() != 0:
        day += datetime.timedelta(days=1)
    return day


MONDAY = _first_monday(YEAR, 3)


def _policy(leave_type, **overrides):
    defaults = {
        'annual_days': 10, 'is_active': True, 'convert_to_lop': False, 'allow_negative_balance': False, 'minimum_notice_period': 0,
        'maximum_consecutive_days': 0, 'minimum_service_period': 0, 'applicable_gender': 'all', 'grant_mode': 'annual',
        'allow_probation_leave': True,
    }
    return LeavePolicy.objects.update_or_create(leave_type=leave_type, defaults={**defaults, **overrides})[0]


def _person(email, employee_id, gender):
    user = make_user(email, employee_id=employee_id, branch='Kondapur', date_of_joining=datetime.date(2020, 1, 1))
    EmployeeProfile.objects.update_or_create(user=user, defaults={'gender': gender})
    return user


class OnRequestLeaveTests(TestCase):
    def setUp(self):
        cache.clear()
        _policy('casual', annual_days=12)
        _policy('maternity', annual_days=10, applicable_gender='female', grant_mode='on_request')
        _policy('paternity', annual_days=5, applicable_gender='male', grant_mode='on_request')
        # Someone who can decide leave, so a request has an approver to be routed to.
        make_user('mat-hr@test.com', role=make_role('mat_hr', permission_codenames=['leave.approve']), employee_id='EMPMATHR', branch='Kondapur')
        self.mother = _person('mat-f@test.com', 'EMPMAT001', 'female')
        self.father = _person('mat-m@test.com', 'EMPMAT002', 'male')

    def _apply(self, user, leave_type='maternity', days=3, start=MONDAY):
        client = APIClient()
        client.force_authenticate(user=user)
        end = start + datetime.timedelta(days=days - 1)
        return client.post(reverse('leave-request-list'), {
            'leave_type': leave_type, 'duration': 'full_day', 'start_date': start.isoformat(), 'end_date': end.isoformat(), 'reason': 'Expected delivery in the month',
        }, format='json')

    # ── never given to everyone ─────────────────────────────────────────────────────────────────────
    def test_joining_credit_gives_the_normal_leave_but_not_maternity_or_paternity(self):
        _allocate_leaves_for_employee(self.mother, datetime.date(YEAR, 1, 2))
        types = set(LeaveBalance.objects.filter(employee=self.mother, year=YEAR).values_list('leave_type', flat=True))
        self.assertIn('casual', types)
        self.assertNotIn('maternity', types)
        self.assertNotIn('paternity', types)

    def test_the_policy_list_carries_the_grant_mode(self):
        client = APIClient()
        client.force_authenticate(user=self.mother)
        rows = client.get(reverse('leave-policy-list')).json()['data']
        modes = {row['leave_type']: row['grant_mode'] for row in rows}
        self.assertEqual((modes['casual'], modes['maternity'], modes['paternity']), ('annual', 'on_request', 'on_request'))

    # ── created when an eligible employee applies ──────────────────────────────────────────────────
    def test_an_eligible_employee_gets_the_balance_when_she_applies(self):
        self.assertFalse(LeaveBalance.objects.filter(employee=self.mother, leave_type='maternity').exists())
        response = self._apply(self.mother, days=3)
        self.assertEqual(response.status_code, 201, response.json())
        balance = LeaveBalance.objects.get(employee=self.mother, leave_type='maternity', year=YEAR)
        self.assertEqual(float(balance.total_days), 10.0)

    def test_the_wrong_gender_cannot_apply_and_gets_no_balance(self):
        response = self._apply(self.father, leave_type='maternity')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LeaveBalance.objects.filter(employee=self.father, leave_type='maternity').exists())

    def test_the_case_entitlement_is_the_limit(self):
        _policy('maternity', annual_days=2, applicable_gender='female', grant_mode='on_request')   # two working days for the case
        self.assertEqual(self._apply(self.mother, days=2).status_code, 201)                      # Monday and Tuesday: all of it
        refused = self._apply(self.mother, days=1, start=MONDAY + datetime.timedelta(days=14))
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Insufficient balance', refused.json()['message'])

    def test_minimum_service_is_required(self):
        _policy('maternity', annual_days=10, applicable_gender='female', grant_mode='on_request', minimum_service_period=240)
        self.assertIsNone(ensure_event_balance(self.mother, 'maternity', YEAR, MONDAY))
        self.assertEqual(self._apply(self.mother).status_code, 400)

    def test_a_normal_leave_type_is_untouched_by_the_helper(self):
        self.assertIsNone(ensure_event_balance(self.mother, 'casual', YEAR, MONDAY))

    def test_asking_twice_does_not_create_a_second_balance(self):
        first = ensure_event_balance(self.mother, 'maternity', YEAR, MONDAY)
        second = ensure_event_balance(self.mother, 'maternity', YEAR, MONDAY)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(LeaveBalance.objects.filter(employee=self.mother, leave_type='maternity').count(), 1)

    def test_what_was_taken_in_the_last_year_is_not_granted_again(self):
        LeaveRequest.objects.create(
            employee=self.mother, leave_type='maternity', duration='full_day', start_date=datetime.date(YEAR - 1, 11, 4),
            end_date=datetime.date(YEAR - 1, 11, 8), total_days=4, status=REQ_APPROVED,
        )
        self.assertEqual(float(days_taken_recently(self.mother, 'maternity', MONDAY)), 4.0)
        self.assertEqual(float(ensure_event_balance(self.mother, 'maternity', YEAR, MONDAY).total_days), 6.0)

    # ── what the employee sees ──────────────────────────────────────────────────────────────────────
    def test_an_untouched_on_request_balance_is_not_listed_but_a_used_or_requested_one_is(self):
        LeaveBalance.objects.create(employee=self.mother, leave_type='maternity', year=YEAR, total_days=10, used_days=0)   # e.g. credited before this change
        LeaveBalance.objects.create(employee=self.mother, leave_type='casual', year=YEAR, total_days=12, used_days=0)
        listed = lambda: {b.leave_type for b in hide_unused_event_balances(list(LeaveBalance.objects.filter(employee=self.mother, year=YEAR)), self.mother)}  # noqa: E731
        self.assertEqual(listed(), {'casual'})
        LeaveRequest.objects.create(
            employee=self.mother, leave_type='maternity', duration='full_day', start_date=MONDAY, end_date=MONDAY, total_days=1, status=REQ_PENDING,
        )
        self.assertEqual(listed(), {'casual', 'maternity'})

    def test_the_balance_list_endpoint_hides_it_too(self):
        LeaveBalance.objects.create(employee=self.mother, leave_type='maternity', year=YEAR, total_days=10, used_days=0)
        client = APIClient()
        client.force_authenticate(user=self.mother)
        data = client.get(reverse('leave-balance'), {'year': YEAR}).json()['data']
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertNotIn('maternity', {row['leave_type'] for row in rows})

    def test_the_preview_shows_the_available_days_before_anything_is_applied(self):
        client = APIClient()
        client.force_authenticate(user=self.mother)
        preview = client.get(reverse('leave-request-list'), {
            'action': 'preview', 'leave_type': 'maternity', 'duration': 'full_day',
            'start_date': MONDAY.isoformat(), 'end_date': (MONDAY + datetime.timedelta(days=2)).isoformat(),
        }).json()['data']
        self.assertEqual(preview['available_balance'], 10.0)
        self.assertTrue(preview['sufficient_balance'])
