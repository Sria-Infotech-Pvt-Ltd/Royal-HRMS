"""UAT-033 follow-up: leave balances are credited by eligibility, not by a per-employee "leave plan". Gender is enforced; probation is NOT (see TEAM_CONTEXT section 23)."""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import EmployeeProfile
from apps.hrms.models import LeaveBalance, LeavePolicy
from apps.hrms.services_leave_ledger import employee_matches_policy_gender
from apps.hrms.views.leave_shared import _allocate_leaves_for_employee


def _employee(email, code, gender):
    employee = make_user(email, employee_id=code)
    EmployeeProfile.objects.create(user=employee, gender=gender)
    return employee


class LeaveAllocationEligibilityTests(TestCase):
    def setUp(self):
        for leave_type, gender in (('casual', 'all'), ('maternity', 'female'), ('paternity', 'male')):
            LeavePolicy.objects.update_or_create(
                leave_type=leave_type,
                defaults={'annual_days': 10, 'applicable_gender': gender, 'is_active': True, 'minimum_service_period': 0},
            )
        self.joining = datetime.date(2026, 1, 5)

    def _types(self, employee):
        return set(LeaveBalance.objects.filter(employee=employee).values_list('leave_type', flat=True))

    def test_a_woman_gets_maternity_and_not_paternity(self):
        employee = _employee('she@test.com', 'EMPLV001', 'female')
        _allocate_leaves_for_employee(employee, self.joining)
        self.assertEqual(self._types(employee), {'casual', 'maternity'})

    def test_a_man_gets_paternity_and_not_maternity(self):
        employee = _employee('he@test.com', 'EMPLV002', 'male')
        _allocate_leaves_for_employee(employee, self.joining)
        self.assertEqual(self._types(employee), {'casual', 'paternity'})

    def test_a_blank_profile_gender_gets_neither_restricted_type(self):
        employee = _employee('blank@test.com', 'EMPLV003', '')
        _allocate_leaves_for_employee(employee, self.joining)
        self.assertEqual(self._types(employee), {'casual'})

    def test_matcher_follows_the_policy_value(self):
        woman = _employee('she2@test.com', 'EMPLV004', 'female')
        self.assertTrue(employee_matches_policy_gender(woman, LeavePolicy.objects.get(leave_type='maternity')))
        self.assertFalse(employee_matches_policy_gender(woman, LeavePolicy.objects.get(leave_type='paternity')))
        self.assertTrue(employee_matches_policy_gender(woman, LeavePolicy.objects.get(leave_type='casual')))
