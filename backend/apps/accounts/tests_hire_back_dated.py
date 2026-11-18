"""
The whole Hire flow with a joining date in the past (a back-dated hire: months or years ago).

Every record that depends on the date must carry it, and the new employee must be usable TODAY: in particular they must have a leave
balance for the CURRENT year. Allocation used to create only the joining year's balance, so someone who joined two years ago had no
balance for this year (the yearly reset ran on 1 January and the monthly accrual only touches monthly policies).

Dates are taken from today so the tests do not age.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from apps.accounts.models import Placement, Position, User
from apps.accounts.tests_hire_wizard import HireWizardTestCase
from apps.attendance.models import EmployeeWeeklyOffAssignment
from apps.hrms.models import LeaveBalance, LeavePolicy
from apps.payroll.models import EmployeeSalaryConfig

ANNUAL_DAYS = 12   # so a joining month m is worth exactly 13 - m days (joining month counts in full)


class BackDatedHireFlowTests(HireWizardTestCase):
    def setUp(self):
        super().setUp()
        LeavePolicy.objects.create(leave_type='casual', annual_days=Decimal(ANNUAL_DAYS), is_active=True)
        self.counter = 0

    def _hire(self, joining: datetime.date) -> User:
        """A wizard-style hire (create, autosave the whole form, upload the required documents, complete)."""
        self.counter += 1
        n = self.counter
        position = Position.objects.create(org_unit=self.unit, title=f'Back-dated Role {n}', grade='L2')
        action = self._create_draft(effective_from=joining.isoformat(), position=str(position.id))
        self._set_employment_type(action, 'Permanent')
        draft = self._valid_full_draft()
        draft.update({
            'email': f'back.dated.{n}@test.com', 'phone': f'+91 98765432{n:02d}', 'pan_number': f'ABCDE{1000 + n}F',
            'aadhaar_number': f'12345678{n:04d}', 'account_number': f'12345678{n:02d}', 'annual_ctc': '600000',
        })
        self.assertEqual(self._patch(action, draft).status_code, 200)
        self._upload_all_required_docs(action)
        response = self._complete(action)
        self.assertEqual(response.status_code, 201, response.data)
        action.refresh_from_db()
        return User.objects.get(pk=action.created_employee_id)

    def _balances(self, employee: User) -> dict:
        return {row.year: row.total_days for row in LeaveBalance.objects.filter(employee=employee, leave_type='casual')}

    def _assert_date_carried_everywhere(self, employee: User, joining: datetime.date):
        self.assertEqual(employee.date_of_joining, joining)
        placement = Placement.objects.get(employee=employee)
        self.assertEqual((placement.effective_from, placement.effective_to), (joining, None))
        weekly_off = EmployeeWeeklyOffAssignment.objects.get(employee=employee)
        self.assertEqual((weekly_off.effective_from, weekly_off.effective_to), (joining, None))
        salary = EmployeeSalaryConfig.objects.get(employee=employee)
        self.assertEqual((salary.effective_from, salary.annual_ctc), (joining, Decimal('600000.00')))
        self.assertEqual(employee.onboarding_status, User.ONBOARDING_COMPLETE)

    def test_control_joining_today(self):
        today = datetime.date.today()
        employee = self._hire(today)
        self._assert_date_carried_everywhere(employee, today)
        self.assertEqual(self._balances(employee), {today.year: Decimal(13 - today.month)})

    def test_joined_earlier_this_year(self):
        today = datetime.date.today()
        joining = today.replace(month=1, day=1) if today.month > 1 else today
        employee = self._hire(joining)
        self._assert_date_carried_everywhere(employee, joining)
        self.assertEqual(self._balances(employee), {today.year: Decimal(12)})   # January joiner: all 12 months

    def test_joined_two_years_and_three_months_ago_has_a_balance_for_this_year(self):
        today = datetime.date.today()
        joining = today - datetime.timedelta(days=2 * 365 + 90)
        employee = self._hire(joining)
        self._assert_date_carried_everywhere(employee, joining)
        balances = self._balances(employee)
        self.assertEqual(balances[joining.year], Decimal(13 - joining.month))   # the joining year, pro-rated as before
        self.assertEqual(balances[today.year], Decimal(ANNUAL_DAYS))            # this year, in full: the employee can apply for leave now

    def test_joined_last_year(self):
        today = datetime.date.today()
        joining = datetime.date(today.year - 1, 7, 1)
        employee = self._hire(joining)
        self._assert_date_carried_everywhere(employee, joining)
        self.assertEqual(self._balances(employee), {today.year - 1: Decimal(6), today.year: Decimal(ANNUAL_DAYS)})

    def test_allocation_is_idempotent_so_a_second_run_changes_nothing(self):
        from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
        today = datetime.date.today()
        joining = today - datetime.timedelta(days=2 * 365 + 90)
        employee = self._hire(joining)
        before = self._balances(employee)
        self.assertEqual(_allocate_leaves_for_employee(employee, joining), 0)
        self.assertEqual(self._balances(employee), before)

    def test_a_future_joiner_is_unchanged_and_gets_only_the_joining_year(self):
        from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
        today = datetime.date.today()
        employee = self._hire(today)
        LeaveBalance.objects.filter(employee=employee).delete()
        next_january = datetime.date(today.year + 1, 1, 1)
        _allocate_leaves_for_employee(employee, next_january)
        self.assertEqual(self._balances(employee), {today.year + 1: Decimal(12)})
