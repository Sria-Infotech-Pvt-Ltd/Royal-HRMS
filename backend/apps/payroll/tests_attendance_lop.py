from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendanceRecord
from apps.hrms.models import LeaveRequest, REQ_APPROVED, REQ_PENDING
from apps.payroll.engine.legacy import _approved_leave_lop_by_employee
from apps.payroll.models import PayrollCycle


class PayrollApprovedLeaveLOPTests(TestCase):
    def setUp(self):
        role = make_role('payroll_lop_employee')
        self.employee = make_user(
            'payroll-lop@example.com',
            role=role,
            employee_id='LOP0001',
        )
        self.cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 11, 1),
            cycle_end=datetime.date(2026, 11, 30),
            pay_date=datetime.date(2026, 12, 5),
            created_by=self.employee,
        )

    def _leave(self, **overrides):
        values = {
            'employee': self.employee,
            'leave_type': 'lwp',
            'duration': 'full_day',
            'start_date': datetime.date(2026, 11, 3),
            'end_date': datetime.date(2026, 11, 4),
            'total_days': Decimal('2'),
            'lop_days': Decimal('0'),
            'reason': 'Test leave',
            'status': REQ_APPROVED,
            'is_lwp': True,
        }
        values.update(overrides)
        return LeaveRequest.objects.create(**values)

    def test_approved_lwp_days_are_included_in_payroll_lop(self):
        self._leave()

        result = _approved_leave_lop_by_employee([self.employee.pk], self.cycle)

        self.assertEqual(result[self.employee.pk], Decimal('2'))

    def test_approved_partial_lop_is_included_in_payroll_lop(self):
        self._leave(
            leave_type='casual',
            total_days=Decimal('2'),
            lop_days=Decimal('0.5'),
            is_lwp=False,
        )

        result = _approved_leave_lop_by_employee([self.employee.pk], self.cycle)

        self.assertEqual(result[self.employee.pk], Decimal('0.5'))

    def test_lwp_crossing_pay_period_is_prorated_by_chargeable_leave_days(self):
        self.cycle.cycle_end = datetime.date(2026, 11, 2)
        self.cycle.save(update_fields=['cycle_end'])
        self._leave(
            start_date=datetime.date(2026, 11, 2),
            end_date=datetime.date(2026, 11, 3),
        )

        result = _approved_leave_lop_by_employee([self.employee.pk], self.cycle)

        self.assertEqual(result[self.employee.pk], Decimal('1'))

    def test_unapproved_lwp_is_not_deducted(self):
        self._leave(status=REQ_PENDING)

        result = _approved_leave_lop_by_employee([self.employee.pk], self.cycle)

        self.assertNotIn(self.employee.pk, result)

    def test_payroll_processing_is_blocked_by_unresolved_incomplete_attendance(self):
        hr = make_user(
            'payroll-lop-hr@example.com',
            role=make_role(
                'payroll_lop_hr',
                permission_codenames=['payroll.edit', 'settings.edit'],
            ),
            employee_id='HRLOP001',
        )
        self.cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED
        self.cycle.save(update_fields=['status'])
        AttendanceRecord.objects.create(
            employee=self.employee,
            date=datetime.date(2026, 11, 3),
            status=AttendanceRecord.STATUS_INCOMPLETE,
        )
        client = APIClient()
        client.force_authenticate(user=hr)

        response = client.post(
            reverse('payroll-process', kwargs={'pk': self.cycle.pk}),
            {},
            format='json',
        )

        self.assertEqual(response.status_code, 409, response.data)
        self.assertIn('unresolved missing clock-out', response.data['message'])
