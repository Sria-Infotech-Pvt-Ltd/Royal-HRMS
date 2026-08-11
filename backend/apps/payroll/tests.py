"""Regression tests for the bugs fixed in the 2026-07-22 engineering audit.

Prior to this file, apps/payroll/tests.py was the unmodified Django
`startapp` stub — this app (and this repo) had zero real test coverage.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendanceRecord
from apps.branch.models import Branch, City, State
from apps.notifications.models import Notification
from apps.payroll.models import EmployeePayslip, PayrollCycle, PayrollSettings


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


class CycleEmployeeDailyScopingTests(TestCase):
    """Regression test for the 'manager' vs 'manager__team_lead' role-name
    bug in CycleEmployeeDailyView — a manager could previously view ANY
    employee's daily attendance, not just their own direct reports, because
    the scoping check compared against a role name nobody actually has.
    """

    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        manager_role = make_role(
            'manager__team_lead', permission_codenames=['payroll.view'], can_manage_team=True,
        )
        employee_role = make_role('employee')

        self.manager = make_user('manager@test.com', role=manager_role, password='TestPass123!')
        self.own_report = make_user(
            'report@test.com', role=employee_role, password='TestPass123!',
            reporting_manager=self.manager,
        )
        self.other_employee = make_user(
            'other@test.com', role=employee_role, password='TestPass123!',
        )

        self.cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 1, 1),
            cycle_end=datetime.date(2026, 1, 31),
            pay_date=datetime.date(2026, 2, 1),
            created_by=self.manager,
        )
        for emp in (self.own_report, self.other_employee):
            AttendanceRecord.objects.create(
                employee=emp, date=datetime.date(2026, 1, 15),
                status=AttendanceRecord.STATUS_PRESENT,
            )

        _login(self.client, 'manager@test.com')

    def _daily_url(self, employee):
        return reverse(
            'payroll-employee-daily',
            kwargs={'pk': self.cycle.pk, 'employee_pk': str(employee.pk)},
        )

    def test_manager_can_view_own_direct_report(self):
        resp = self.client.get(self._daily_url(self.own_report))
        self.assertEqual(resp.status_code, 200)

    def test_manager_cannot_view_non_report_employee(self):
        resp = self.client.get(self._daily_url(self.other_employee))
        self.assertEqual(resp.status_code, 403)


class PayrollCycleCreationNotifiesManagersTests(TestCase):
    """Regression test: creating a payroll cycle must notify active
    manager__team_lead users. Previously the notification query filtered on
    role__name='manager', which never matched any real user.
    """

    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        branch = Branch.objects.create(
            branch_code='HYD02', branch_name='Notify Test Branch', address='Test Address',
            state=state, city=city,
            latitude=Decimal('17.4'), longitude=Decimal('78.4'),
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        hr_role = make_role('hr', permission_codenames=['payroll.create', 'payroll.view'])
        manager_role = make_role('manager__team_lead', can_manage_team=True)

        self.hr_user = make_user(
            'hr@test.com', role=hr_role, password='TestPass123!', branch=branch.branch_name,
        )
        self.manager = make_user(
            'manager2@test.com', role=manager_role, password='TestPass123!', branch=branch.branch_name,
        )

        _login(self.client, 'hr@test.com')

    def test_cycle_creation_notifies_active_managers(self):
        resp = self.client.post(
            reverse('payroll-cycle-list'),
            {
                'cycle_start': '2026-02-01',
                'cycle_end': '2026-02-28',
                'pay_date': '2026-03-01',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            Notification.objects.filter(user=self.manager, module='payroll').exists(),
            'Manager was not notified of the new payroll cycle awaiting attendance sign-off.',
        )


class UpdatePayslipReimbBonusDecimalTests(TestCase):
    """Regression test: the Decimal/float TypeError fix in the last commit
    only covered the bonus_breakdown path. reimbursements, flat bonus, and
    lop_days all had the identical unguarded assignment and would throw the
    same error the moment a flat JSON number came in from the frontend.
    """

    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()
        hr_role = make_role('hr', permission_codenames=['payroll.view', 'payroll.edit'])
        self.hr_user = make_user('hrpay@test.com', role=hr_role, password='TestPass123!')
        employee_role = make_role('employee')
        self.employee = make_user('payee@test.com', role=employee_role, password='TestPass123!')

        PayrollSettings.objects.create(
            id='00000000-0000-0000-0000-000000000001',
            enable_reimbursements=True,
            enable_bonuses=True,
        )
        cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 1, 1),
            cycle_end=datetime.date(2026, 1, 31),
            pay_date=datetime.date(2026, 2, 1),
            created_by=self.hr_user,
        )
        self.payslip = EmployeePayslip.objects.create(
            cycle=cycle, employee=self.employee,
            annual_ctc=Decimal('600000.00'), monthly_ctc=Decimal('50000.00'),
            basic=Decimal('20000.00'), hra=Decimal('8000.00'),
            special_allowance=Decimal('2000.00'),
            total_working_days=26,
        )
        _login(self.client, 'hrpay@test.com')

    def _url(self):
        return reverse('payslip-reimb-bonus', kwargs={'pk': self.payslip.pk})

    def test_flat_reimbursements_as_json_float_does_not_crash(self):
        resp = self.client.patch(self._url(), {'reimbursements': 1500.50}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.payslip.refresh_from_db()
        self.assertEqual(self.payslip.reimbursements, Decimal('1500.50'))
        self.assertEqual(
            self.payslip.gross_earnings,
            Decimal('20000.00') + Decimal('8000.00') + Decimal('2000.00') + Decimal('1500.50'),
        )

    def test_flat_bonus_as_json_float_does_not_crash(self):
        resp = self.client.patch(self._url(), {'bonus': 999.99}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.payslip.refresh_from_db()
        self.assertEqual(self.payslip.bonus, Decimal('999.99'))

    def test_lop_days_as_json_float_does_not_crash(self):
        resp = self.client.patch(self._url(), {'lop_days': 1.5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.payslip.refresh_from_db()
        self.assertEqual(self.payslip.lop_days, Decimal('1.5'))

    def test_invalid_reimbursements_returns_clean_validation_error_not_500(self):
        resp = self.client.patch(self._url(), {'reimbursements': 'not-a-number'}, format='json')
        self.assertEqual(resp.status_code, 400)
