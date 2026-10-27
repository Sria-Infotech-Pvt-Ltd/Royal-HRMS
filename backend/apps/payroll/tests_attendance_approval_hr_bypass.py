"""
Regression tests for the "Attendance Approval" HR/Admin bypass bug.

With PayrollSettings.approval_levels = L1_L2 but no employee having a
reporting_manager with can_manage_team rights, a payroll cycle's
attendance_pending status was permanently stuck: GET
/payroll/cycles/pending-approval/ returned [] even for Admin/HR, because
the view only matched cycles where the LOGGED-IN user had an assigned,
unapproved ManagerAttendanceApproval row — a superuser/HR account never
has one of those, so nobody could ever see the cycle to approve it.

Covers both halves of the acceptance criteria: (a) no managers configured
-> Admin/HR sees the cycle, can approve both L1 and L2, cycle unlocks;
(b) managers ARE configured -> the existing per-manager approval flow is
unchanged.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.branch.models import Branch, City, State
from apps.payroll.models import ManagerAttendanceApproval, PayrollCycle, PayrollSettings


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data
    return resp


def _make_branch(code: str, name: str) -> Branch:
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(
        branch_code=code, branch_name=name, address='Test Address',
        state=state, city=city,
        latitude=Decimal('17.4'), longitude=Decimal('78.4'),
        allowed_radius_meters=150, geofencing_enabled=True,
    )


class NoManagersConfiguredHrBypassTests(TestCase):
    """Acceptance case 1: no managers configured -> Admin sees the cycle,
    can approve it, and the cycle unlocks (status -> attendance_approved)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        PayrollSettings.objects.update_or_create(
            pk=1, defaults={'approval_levels': PayrollSettings.APPROVAL_L1_L2},
        )
        self.branch = _make_branch('NOMGR1', 'No Manager Branch')
        hr_role = make_role('hr_nomgr_test', permission_codenames=['payroll.create', 'payroll.view', 'payroll.edit'])
        self.hr_user = make_user(
            'hr-nomgr@test.com', role=hr_role, password='TestPass123!', branch=self.branch.branch_name,
        )
        # A payroll-eligible employee with NO reporting_manager at all --
        # _cycle_attendance_managers() seeds zero ManagerAttendanceApproval
        # rows for this cycle, the exact "no managers configured" case.
        make_user(
            'employee-nomgr@test.com', role=make_role('employee_nomgr_test'), password='TestPass123!',
            branch=self.branch.branch_name, employee_id='NOMGR001',
        )
        _login(self.client, 'hr-nomgr@test.com')

        resp = self.client.post(
            reverse('payroll-cycle-list'),
            {'cycle_start': '2026-03-01', 'cycle_end': '2026-03-31', 'pay_date': '2026-04-01'},
            format='json',
        )
        assert resp.status_code == 201, resp.data
        self.cycle_id = resp.data['data']['id']

    def test_cycle_has_zero_manager_rows(self):
        self.assertEqual(
            ManagerAttendanceApproval.objects.filter(cycle_id=self.cycle_id).count(), 0,
        )

    def test_hr_sees_cycle_in_pending_approval_list(self):
        resp = self.client.get(reverse('payroll-pending-approval'))
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [c['id'] for c in resp.data['data']]
        self.assertIn(str(self.cycle_id), ids)

    def test_superuser_also_sees_cycle_in_pending_approval_list(self):
        # The actual reported bug: a superuser satisfies _is_manager() too
        # (is_superuser check), which previously routed them into the
        # manager-only branch that never matches them.
        admin = make_user(
            'admin-nomgr@test.com', role=make_role('admin_nomgr_test'), password='TestPass123!',
            is_superuser=True, is_staff=True,
        )
        client = APIClient()
        _login(client, 'admin-nomgr@test.com')
        resp = client.get(reverse('payroll-pending-approval'))
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [c['id'] for c in resp.data['data']]
        self.assertIn(str(self.cycle_id), ids)

    def test_hr_can_approve_l1_directly_with_no_managers(self):
        resp = self.client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]),
            {'level': 'L1', 'comment': 'No managers configured'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        cycle = PayrollCycle.objects.get(pk=self.cycle_id)
        self.assertIsNotNone(cycle.attendance_approved_by_l1_id)
        self.assertIsNotNone(cycle.attendance_l1_approved_at)
        # L1_L2 is configured, so status must NOT jump straight to approved.
        self.assertEqual(cycle.status, PayrollCycle.STATUS_ATTENDANCE_PENDING)
        self.assertIsNotNone(cycle.hr_self_approved_at, 'HR standing in for a non-existent L1 should be recorded as a self-approval.')
        self.assertTrue(
            AuditLog.objects.filter(
                action='payroll_attendance_l1_approved', object_id=str(self.cycle_id),
                changes__method='hr_direct_no_managers',
            ).exists(),
        )

    def test_full_hr_approval_unlocks_cycle(self):
        l1 = self.client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]), {'level': 'L1'}, format='json',
        )
        self.assertEqual(l1.status_code, 200, l1.data)
        l2 = self.client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]),
            {'level': 'L2', 'self_approve': True}, format='json',
        )
        self.assertEqual(l2.status_code, 200, l2.data)
        cycle = PayrollCycle.objects.get(pk=self.cycle_id)
        self.assertEqual(cycle.status, PayrollCycle.STATUS_ATTENDANCE_APPROVED)
        self.assertIsNotNone(cycle.hr_self_approved_at)

    def test_non_hr_non_manager_still_cannot_approve(self):
        employee = make_user(
            'plain-nomgr@test.com', role=make_role('plain_nomgr_test'), password='TestPass123!',
        )
        client = APIClient()
        _login(client, 'plain-nomgr@test.com')
        resp = client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]), {'level': 'L1'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)


class ManagersConfiguredExistingFlowTests(TestCase):
    """Acceptance case 2: managers ARE configured -> existing per-manager
    approval flow is unaffected by the HR-bypass changes."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        PayrollSettings.objects.update_or_create(
            pk=1, defaults={'approval_levels': PayrollSettings.APPROVAL_L1_L2},
        )
        self.branch = _make_branch('MGR1', 'Has Manager Branch')
        hr_role = make_role('hr_mgr_test', permission_codenames=['payroll.create', 'payroll.view', 'payroll.edit'])
        manager_role = make_role('manager_mgr_test', can_manage_team=True)
        self.hr_user = make_user(
            'hr-mgr@test.com', role=hr_role, password='TestPass123!', branch=self.branch.branch_name,
        )
        self.manager = make_user(
            'manager-mgr@test.com', role=manager_role, password='TestPass123!', branch=self.branch.branch_name,
        )
        make_user(
            'report-mgr@test.com', role=make_role('employee_mgr_test'), password='TestPass123!',
            branch=self.branch.branch_name, employee_id='MGR001', reporting_manager=self.manager,
        )
        _login(self.client, 'hr-mgr@test.com')
        resp = self.client.post(
            reverse('payroll-cycle-list'),
            {'cycle_start': '2026-03-01', 'cycle_end': '2026-03-31', 'pay_date': '2026-04-01'},
            format='json',
        )
        assert resp.status_code == 201, resp.data
        self.cycle_id = resp.data['data']['id']

    def test_cycle_has_a_manager_row(self):
        self.assertEqual(
            ManagerAttendanceApproval.objects.filter(cycle_id=self.cycle_id).count(), 1,
        )

    def test_manager_sees_only_their_own_pending_cycle(self):
        client = APIClient()
        _login(client, 'manager-mgr@test.com')
        resp = client.get(reverse('payroll-pending-approval'))
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [c['id'] for c in resp.data['data']]
        self.assertIn(str(self.cycle_id), ids)

    def test_hr_still_sees_cycle_alongside_manager(self):
        # HR's own visibility must still include cycles that DO have real
        # manager rows -- the fix must not narrow existing HR visibility.
        resp = self.client.get(reverse('payroll-pending-approval'))
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [c['id'] for c in resp.data['data']]
        self.assertIn(str(self.cycle_id), ids)

    def test_hr_cannot_bypass_l1_when_a_manager_row_exists(self):
        # The HR-direct-L1 fallback must only fire when there are ZERO
        # manager rows -- with one configured, HR has no row of their own
        # and must be refused, not silently approve on the manager's behalf.
        resp = self.client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]), {'level': 'L1'}, format='json',
        )
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_manager_approval_completes_l1_normally(self):
        client = APIClient()
        _login(client, 'manager-mgr@test.com')
        resp = client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]), {'level': 'L1'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        cycle = PayrollCycle.objects.get(pk=self.cycle_id)
        self.assertIsNotNone(cycle.attendance_approved_by_l1_id)
        self.assertIsNone(cycle.hr_self_approved_at, 'A real manager approving their own row is not an HR self-approval.')
        self.assertEqual(cycle.status, PayrollCycle.STATUS_ATTENDANCE_PENDING)

        l2 = self.client.post(
            reverse('payroll-approve-attendance', args=[self.cycle_id]), {'level': 'L2'}, format='json',
        )
        self.assertEqual(l2.status_code, 200, l2.data)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, PayrollCycle.STATUS_ATTENDANCE_APPROVED)
        self.assertIsNone(cycle.hr_self_approved_at, 'A normal L2 approval without self_approve must not set hr_self_approved_at.')
