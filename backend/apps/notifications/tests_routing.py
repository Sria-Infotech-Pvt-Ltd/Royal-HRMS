"""
Notification routing (Phase 1): who is told at each approval transition.

- Regularization: the L1 manager is told on submission (not HR, whose stage
  hasn't started); on manager approval the employee and HR are told.
- HR stage with no specific HR assigned (leave, regularization): the HR who
  can act are told — branch HR first, never another branch's HR or managers.
- Existing leave notifications unchanged; no duplicates.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendanceCorrection
from apps.hrms.models import LeaveRequest
from apps.notifications.models import Notification

D = datetime.date(2026, 12, 7)


class RoutingBase(TestCase):
    def setUp(self):
        cache.clear()
        hr_role = make_role('nr_hr', permission_codenames=['leave.approve', 'attendance.view', 'attendance.create',
                                                           'attendance.edit'])
        mgr_role = make_role('nr_mgr', can_manage_team=True,
                             permission_codenames=['leave.approve', 'attendance.create', 'attendance.edit'])
        emp_role = make_role('nr_emp', permission_codenames=['attendance.view', 'attendance.create'])
        self.mgr = make_user('nr.mgr@test.com', role=mgr_role, full_name='Mgr', branch='North', employee_id='NRM')
        self.other_mgr = make_user('nr.mgr2@test.com', role=mgr_role, full_name='Other Mgr', branch='North',
                                   employee_id='NRM2')
        self.hr = make_user('nr.hr@test.com', role=hr_role, full_name='North HR', branch='North', employee_id='NRH')
        self.hr_south = make_user('nr.hr2@test.com', role=hr_role, full_name='South HR', branch='South',
                                  employee_id='NRH2')
        self.emp = make_user('nr.emp@test.com', role=emp_role, full_name='Emp', branch='North', employee_id='NRE',
                             reporting_manager=self.mgr)
        self.peer = make_user('nr.peer@test.com', role=emp_role, full_name='Peer', branch='North', employee_id='NRP')

    def titles(self, user):
        return list(Notification.objects.filter(user=user).order_by('created_at').values_list('title', flat=True))

    def clear(self):
        Notification.objects.all().delete()


class RegularizationRoutingTests(RoutingBase):
    def correction(self, **kw):
        return AttendanceCorrection.objects.create(employee=self.emp, date=D, punch_type='IN',
                                                   requested_in_time=datetime.time(9, 0), reason='forgot_to_punch',
                                                   **kw)

    def test_submission_tells_the_l1_manager_not_hr(self):
        self.correction(status='pending', l1_approver=self.mgr, l2_approver=self.hr)
        self.assertEqual(self.titles(self.emp), ['Regularization Submitted'])
        self.assertEqual(self.titles(self.mgr), ['Regularization Request Pending'])
        self.assertEqual(self.titles(self.hr), [])

    def test_forward_tells_employee_and_hr_once(self):
        c = self.correction(status='pending', l1_approver=self.mgr, l2_approver=self.hr)
        self.clear()
        c.status = 'l2_pending'
        c.save()
        self.assertEqual(self.titles(self.emp), ['Regularization Forwarded to HR'])
        self.assertEqual(self.titles(self.hr), ['Regularization Request Pending'])
        self.assertEqual(self.titles(self.mgr), [])
        c.save()                                             # saving again without a transition: nothing new
        self.assertEqual(Notification.objects.count(), 2)

    def test_unassigned_hr_stage_tells_branch_hr_only(self):
        self.correction(status='l2_pending', l1_approver=None, l2_approver=None)
        self.assertEqual(self.titles(self.hr), ['Regularization Request Pending'])
        for u in (self.hr_south, self.mgr, self.other_mgr, self.peer):
            self.assertEqual(self.titles(u), [], u.full_name)

    def test_final_decision_unchanged(self):
        c = self.correction(status='l2_pending', l1_approver=self.mgr, l2_approver=self.hr)
        self.clear()
        c.status = 'approved'
        c.save()
        self.assertEqual(self.titles(self.emp), ['Regularization Approved'])
        self.assertEqual(Notification.objects.count(), 1)


class LeaveRoutingTests(RoutingBase):
    def leave(self, **kw):
        return LeaveRequest.objects.create(employee=self.emp, leave_type='casual', start_date=D, end_date=D,
                                           total_days=Decimal('1'), reason='x', **kw)

    def test_assigned_chain_unchanged(self):
        lr = self.leave(status='pending', l1_approver=self.mgr, l2_approver=self.hr)
        self.assertEqual((self.titles(self.emp), self.titles(self.mgr), self.titles(self.hr)),
                         (['Leave Request Submitted'], ['New Leave Request'], []))
        self.clear()
        lr.status = 'l2_pending'
        lr.save()
        self.assertEqual((self.titles(self.emp), self.titles(self.hr)),
                         (['Leave Forwarded to HR'], ['Leave Awaiting Approval']))
        self.assertEqual(self.titles(self.hr_south), [])

    def test_unassigned_hr_stage_on_submission(self):
        self.leave(status='l2_pending', l1_approver=None, l2_approver=None)
        self.assertEqual(self.titles(self.hr), ['New Leave Request'])
        for u in (self.hr_south, self.mgr, self.other_mgr, self.peer):
            self.assertEqual(self.titles(u), [], u.full_name)

    def test_unassigned_hr_stage_on_forward(self):
        lr = self.leave(status='pending', l1_approver=self.mgr, l2_approver=None)
        self.clear()
        lr.status = 'l2_pending'
        lr.save()
        self.assertEqual(self.titles(self.hr), ['Leave Awaiting Approval'])
        self.assertEqual(self.titles(self.hr_south), [])

    def test_branch_admin_when_branch_has_no_hr(self):
        self.hr.branch = 'Elsewhere'
        self.hr.save(update_fields=['branch'])
        admin = make_user('nr.ba@test.com', role=make_role('nr_branch_admin'), full_name='Branch Admin',
                          branch='North', employee_id='NRBA')
        admin.role.can_manage_branch = True
        admin.role.save(update_fields=['can_manage_branch'])
        self.leave(status='l2_pending', l1_approver=None, l2_approver=None)
        self.assertEqual(self.titles(admin), ['New Leave Request'])
        self.assertEqual(self.titles(self.hr), [])
