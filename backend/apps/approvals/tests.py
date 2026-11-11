"""
Phase 3 — advanced approval workflows.

- Automatic reminder / escalation of pending approvals (configurable, off by default,
  each step once per request and stage, clock restarts at the next stage).
- Approver delegation (authorisation, audit, authority, queues, notifications, revoke).
- Cancellation of an approved leave (request → approve / reject; balance and planned
  attendance restored on approval).
- Leave balance change notifications.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.accounts.tests import _login
from apps.approvals.escalation import run_escalations, working_days_between
from apps.approvals.models import ApprovalDelegation, ApprovalEscalation, ApprovalEscalationSettings
from apps.approvals.services import DelegationError, acts_for, create_delegation, revoke_delegation
from apps.attendance.models import AttendanceCorrection, AttendanceRecord
from apps.hrms.models import LeaveBalance, LeaveCreditTransaction, LeaveRequest
from apps.hrms.views.leave import _approval_scope_filter, _can_approve_at_stage
from apps.notifications.models import Notification

MON = datetime.date(2026, 11, 2)
TODAY = timezone.localdate()


def _at(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(10, 0)))


class Base(TestCase):
    def setUp(self):
        cache.clear()
        mgr_role = make_role('p3_mgr', can_manage_team=True,
                             permission_codenames=['leave.approve', 'attendance.create', 'attendance.edit'])
        hr_role = make_role('p3_hr', permission_codenames=['leave.approve', 'attendance.view', 'attendance.create',
                                                          'attendance.edit'])
        emp_role = make_role('p3_emp', permission_codenames=['attendance.view', 'attendance.create'])
        self.admin_role = make_role('p3_admin', permission_codenames=['settings.view', 'settings.edit',
                                                                      'leave.approve'])
        self.senior = make_user('p3.senior@test.com', role=mgr_role, full_name='Senior Mgr', branch='North',
                                employee_id='P3S')
        self.mgr = make_user('p3.mgr@test.com', role=mgr_role, full_name='Mgr', branch='North', employee_id='P3M',
                             reporting_manager=self.senior)
        self.mgr2 = make_user('p3.mgr2@test.com', role=mgr_role, full_name='Mgr Two', branch='North',
                              employee_id='P3M2')
        self.mgr_south = make_user('p3.mgr3@test.com', role=mgr_role, full_name='South Mgr', branch='South',
                                   employee_id='P3M3')
        self.hr = make_user('p3.hr@test.com', role=hr_role, full_name='North HR', branch='North', employee_id='P3H')
        self.head = make_user('p3.head@test.com', role=hr_role, full_name='HR Head', branch='North',
                              employee_id='P3HH')
        self.admin = make_user('p3.admin@test.com', role=self.admin_role, full_name='Admin', employee_id='P3A')
        self.emp = make_user('p3.emp@test.com', role=emp_role, full_name='Emp', branch='North', employee_id='P3E',
                             reporting_manager=self.mgr, hr=self.hr)
        self.peer = make_user('p3.peer@test.com', role=emp_role, full_name='Peer', branch='North', employee_id='P3P')

    def leave(self, start=None, created=MON, **kw):
        start = start or datetime.date(2026, 12, 7)
        kw.setdefault('status', 'pending')
        kw.setdefault('l1_approver', self.mgr)
        kw.setdefault('l2_approver', self.hr)
        lr = LeaveRequest.objects.create(employee=self.emp, leave_type='casual', start_date=start, end_date=start,
                                         total_days=Decimal('1'), reason='x', **kw)
        LeaveRequest.objects.filter(pk=lr.pk).update(created_at=_at(created))
        lr.refresh_from_db()
        return lr

    def titles(self, user):
        return list(Notification.objects.filter(user=user).order_by('created_at').values_list('title', flat=True))

    def api(self, user):
        cl = APIClient()
        _login(cl, user.email)
        return cl


NO_OFFS = mock.patch('core.cache_service.WeeklyOffCacheService.get_effective_range', return_value={})
NO_HOLIDAYS = mock.patch('core.cache_service.HolidayCacheService.get_holiday_dates', return_value=set())


class EscalationTests(Base):
    def setUp(self):
        super().setUp()
        for p in (NO_OFFS, NO_HOLIDAYS):
            p.start()
            self.addCleanup(p.stop)
        self.cfg = ApprovalEscalationSettings.objects.create(is_enabled=True, escalation_head=self.head)

    def run_on(self, day):
        Notification.objects.all().delete()
        return run_escalations(today=day)

    def test_off_by_default_and_when_disabled(self):
        self.cfg.delete()
        self.assertFalse(ApprovalEscalationSettings.current().is_enabled)
        self.leave()
        self.assertTrue(run_escalations(today=MON + datetime.timedelta(days=10))['skipped'])
        ApprovalEscalationSettings.objects.create(is_enabled=False)
        self.assertTrue(run_escalations(today=MON + datetime.timedelta(days=10))['skipped'])
        self.assertFalse(ApprovalEscalation.objects.exists())

    def test_default_timeline_reminder_then_two_escalations_each_once(self):
        lr = self.leave()
        self.run_on(MON)                                           # same day: nothing
        self.assertFalse(Notification.objects.exists())
        self.run_on(MON + datetime.timedelta(days=1))              # 1 working day -> reminder
        self.assertEqual(self.titles(self.mgr), ['Approval Reminder'])
        self.run_on(MON + datetime.timedelta(days=1))              # re-run same day -> nothing repeated
        self.assertFalse(Notification.objects.exists())
        self.run_on(MON + datetime.timedelta(days=2))              # 2 days -> next higher approver
        self.assertEqual(self.titles(self.senior), ['Request Escalated To You'])
        self.assertEqual(self.titles(self.mgr), ['Request Escalated'])
        self.assertEqual(self.titles(self.head), [])
        self.run_on(MON + datetime.timedelta(days=4))              # 4 < 2+3: nothing
        self.assertFalse(Notification.objects.exists())
        self.run_on(MON + datetime.timedelta(days=5))              # 5 = 2+3 -> HR head
        self.assertEqual(self.titles(self.head), ['Request Escalated To You'])
        self.run_on(MON + datetime.timedelta(days=9))              # all steps done -> never again
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(sorted(ApprovalEscalation.objects.filter(request_id=lr.pk).values_list('level', flat=True)),
                         [0, 1, 2])

    def test_escalation_target_gains_authority_at_that_stage_only(self):
        lr = self.leave()
        self.assertFalse(_can_approve_at_stage(self.senior, lr, 'l1'))
        self.assertFalse(LeaveRequest.objects.filter(_approval_scope_filter(self.senior), pk=lr.pk).exists())
        self.run_on(MON + datetime.timedelta(days=2))
        self.assertTrue(_can_approve_at_stage(self.senior, lr, 'l1'))
        self.assertFalse(_can_approve_at_stage(self.senior, lr, 'l2'))
        self.assertTrue(LeaveRequest.objects.filter(_approval_scope_filter(self.senior), pk=lr.pk).exists())
        resp = self.api(self.senior).post(reverse('leave-request-approve', args=[lr.pk]), {'action': 'approve'},
                                          format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lr.refresh_from_db()
        self.assertEqual(lr.status, 'l2_pending')

    def test_clock_restarts_at_next_stage(self):
        lr = self.leave()
        self.run_on(MON + datetime.timedelta(days=2))              # l1 reminder + escalation
        LeaveRequest.objects.filter(pk=lr.pk).update(status='l2_pending',
                                                     l1_actioned_at=_at(MON + datetime.timedelta(days=3)))
        self.run_on(MON + datetime.timedelta(days=3))              # 0 days at l2: nothing
        self.assertFalse(Notification.objects.exists())
        self.run_on(MON + datetime.timedelta(days=4))              # 1 day at l2 -> reminder to HR
        self.assertEqual(self.titles(self.hr), ['Approval Reminder'])
        self.assertEqual(ApprovalEscalation.objects.filter(request_id=lr.pk, stage='l2').count(), 1)

    def test_no_higher_approver_is_logged_not_notified(self):
        self.mgr.reporting_manager = None
        self.mgr.save(update_fields=['reporting_manager'])
        lr = self.leave(l2_approver=None)
        self.cfg.reminder_after_days = 0
        self.cfg.save()
        self.run_on(MON + datetime.timedelta(days=2))
        self.assertFalse(Notification.objects.exists())
        step = ApprovalEscalation.objects.get(request_id=lr.pk, level=1)
        self.assertEqual(step.action, ApprovalEscalation.ACTION_SKIPPED)
        self.assertIsNone(step.target)

    def test_head_skipped_when_unset(self):
        self.cfg.escalation_head = None
        self.cfg.save()
        lr = self.leave()
        self.run_on(MON + datetime.timedelta(days=6))
        self.assertEqual(ApprovalEscalation.objects.get(request_id=lr.pk, level=2).action,
                         ApprovalEscalation.ACTION_SKIPPED)
        self.assertEqual(self.titles(self.head), [])

    def test_configurable_timeline(self):
        self.cfg.reminder_after_days, self.cfg.first_escalation_after_days = 2, 4
        self.cfg.save()
        self.leave()
        self.run_on(MON + datetime.timedelta(days=1))
        self.assertFalse(Notification.objects.exists())
        self.run_on(MON + datetime.timedelta(days=3))
        self.assertEqual(self.titles(self.mgr), ['Approval Reminder'])
        self.assertEqual(self.titles(self.senior), [])

    def test_attendance_corrections_escalate_too_and_can_be_excluded(self):
        c = AttendanceCorrection.objects.create(employee=self.emp, date=MON, punch_type='IN',
                                                requested_in_time=datetime.time(9, 0), reason='forgot_to_punch',
                                                status='pending', l1_approver=self.mgr, l2_approver=self.hr)
        AttendanceCorrection.objects.filter(pk=c.pk).update(created_at=_at(MON))
        self.run_on(MON + datetime.timedelta(days=2))
        self.assertEqual(self.titles(self.senior), ['Request Escalated To You'])
        from apps.attendance.services_hr_corrections import _can_approve_at_stage as att_can
        c.refresh_from_db()
        self.assertTrue(att_can(self.senior, c, 'l1'))

        ApprovalEscalation.objects.all().delete()
        self.cfg.applies_to_attendance = False
        self.cfg.save()
        self.run_on(MON + datetime.timedelta(days=2))
        self.assertFalse(Notification.objects.exists())

    def test_closed_requests_are_ignored(self):
        self.leave(status='approved')
        self.leave(status='rejected')
        self.assertEqual(self.run_on(MON + datetime.timedelta(days=9))['checked'], 0)


class WorkingDaysTests(TestCase):
    def test_week_offs_and_holidays_skipped(self):
        offs = {MON + datetime.timedelta(days=i): {'sunday'} for i in range(14)}
        holiday = MON + datetime.timedelta(days=2)                 # Wednesday
        with mock.patch('core.cache_service.WeeklyOffCacheService.get_effective_range', return_value=offs), \
                mock.patch('core.cache_service.HolidayCacheService.get_holiday_dates', return_value={holiday}):
            # Tue..next Mon = 7 days, minus the Wednesday holiday (and Sunday, for a user with that week-off)
            self.assertEqual(working_days_between(MON, MON + datetime.timedelta(days=7), None), 6)
            u = make_user('p3.wd@test.com', role=make_role('p3_wd'))
            self.assertEqual(working_days_between(MON, MON + datetime.timedelta(days=7), u), 5)
            self.assertEqual(working_days_between(MON, MON, u), 0)


class DelegationTests(Base):
    def delegate(self, **kw):
        args = dict(actor=self.mgr, delegator=self.mgr, delegate=self.mgr2, start_date=TODAY,
                    end_date=TODAY + datetime.timedelta(days=7), workflows=['leave'], reason='Annual leave')
        args.update(kw)
        return create_delegation(**args)

    def test_api_create_audits_and_notifies(self):
        resp = self.api(self.mgr).post(reverse('approvals-delegations'), {
            'delegate': str(self.mgr2.pk), 'start_date': TODAY.isoformat(),
            'end_date': (TODAY + datetime.timedelta(days=3)).isoformat(), 'workflows': ['leave', 'attendance'],
            'reason': 'Travel'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['data']['active'])
        self.assertTrue(AuditLog.objects.filter(action='approval_delegation_created', user=self.mgr).exists())
        self.assertEqual(len([t for t in self.titles(self.mgr2) if 'Delegat' in t]), 1)
        listed = self.api(self.mgr2).get(reverse('approvals-delegations'))
        self.assertEqual(len(listed.data['data']), 1)
        self.assertEqual((listed.data['data'][0]['received'], listed.data['data'][0]['given']), (True, False))
        self.assertEqual(len(self.api(self.peer).get(reverse('approvals-delegations')).data['data']), 0)

    def test_delegate_can_act_for_approver_while_active(self):
        lr = self.leave()
        self.assertFalse(_can_approve_at_stage(self.mgr2, lr, 'l1'))
        self.delegate()
        self.assertTrue(acts_for(self.mgr2, lr, 'l1', 'leave'))
        self.assertTrue(_can_approve_at_stage(self.mgr2, lr, 'l1'))
        self.assertFalse(acts_for(self.mgr2, lr, 'l1', 'attendance'))   # workflow not delegated
        self.assertTrue(LeaveRequest.objects.filter(_approval_scope_filter(self.mgr2), pk=lr.pk).exists())

    def test_delegate_never_acts_on_own_request(self):
        self.delegate()
        own = LeaveRequest.objects.create(employee=self.mgr2, leave_type='casual', start_date=datetime.date(2026, 12, 7),
                                          end_date=datetime.date(2026, 12, 7), total_days=Decimal('1'), reason='x',
                                          status='pending', l1_approver=self.mgr)
        self.assertFalse(acts_for(self.mgr2, own, 'l1', 'leave'))

    def test_future_delegation_not_active_yet(self):
        lr = self.leave()
        self.delegate(start_date=TODAY + datetime.timedelta(days=2), end_date=TODAY + datetime.timedelta(days=5))
        self.assertFalse(acts_for(self.mgr2, lr, 'l1', 'leave'))

    def test_new_request_notifies_active_delegate_once(self):
        self.delegate()
        self.leave()
        self.assertEqual(self.titles(self.mgr), ['New Leave Request'])
        self.assertEqual(self.titles(self.mgr2).count('New Leave Request'), 1)

    def test_validation_rules(self):
        cases = [
            (dict(actor=self.peer, delegator=self.mgr), 'own approvals'),
            (dict(delegate=self.mgr), 'someone other'),
            (dict(delegate=self.peer), None),                         # no approval permission
            (dict(delegate=self.mgr_south), None),                    # other branch
            (dict(end_date=TODAY - datetime.timedelta(days=1), start_date=TODAY - datetime.timedelta(days=3)), 'past'),
            (dict(end_date=TODAY + datetime.timedelta(days=400)), None),
            (dict(workflows=[]), None),
        ]
        for kw, needle in cases:
            with self.subTest(kw=list(kw)):
                with self.assertRaises(DelegationError) as ctx:
                    self.delegate(**kw)
                if needle:
                    self.assertIn(needle, str(ctx.exception))
        self.assertFalse(ApprovalDelegation.objects.exists())

    def test_no_overlap_and_admin_may_delegate_for_others(self):
        self.delegate(actor=self.admin)
        self.assertTrue(AuditLog.objects.filter(action='approval_delegation_created', user=self.admin).exists())
        with self.assertRaises(DelegationError):
            self.delegate(delegate=self.hr)

    def test_revoke_ends_authority_and_is_audited(self):
        lr = self.leave()
        d = self.delegate()
        resp = self.api(self.peer).post(reverse('approvals-delegation-revoke', args=[d.pk]))
        self.assertEqual(resp.status_code, 404)
        resp = self.api(self.mgr).post(reverse('approvals-delegation-revoke', args=[d.pk]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(acts_for(self.mgr2, lr, 'l1', 'leave'))
        self.assertTrue(AuditLog.objects.filter(action='approval_delegation_revoked').exists())
        d.refresh_from_db()
        with self.assertRaises(DelegationError):
            revoke_delegation(actor=self.mgr, delegation=d)

    def test_eligible_delegates_same_branch_with_permission(self):
        resp = self.api(self.mgr).get(reverse('approvals-delegations-eligible'), {'workflow': 'leave'})
        ids = {p['id'] for p in resp.data['data']}
        self.assertIn(str(self.mgr2.pk), ids)
        self.assertNotIn(str(self.mgr_south.pk), ids)
        self.assertNotIn(str(self.peer.pk), ids)
        self.assertNotIn(str(self.mgr.pk), ids)
        self.assertEqual(self.api(self.peer).get(reverse('approvals-delegations-eligible')).data['data'], [])


class EscalationSettingsApiTests(Base):
    def test_permissions_validation_and_audit(self):
        url = reverse('approvals-escalation-settings')
        self.assertEqual(self.api(self.emp).get(url).status_code, 403)
        got = self.api(self.admin).get(url)
        self.assertEqual(got.status_code, 200)
        self.assertEqual((got.data['data']['is_enabled'], got.data['data']['reminder_after_days'],
                          got.data['data']['first_escalation_after_days'],
                          got.data['data']['second_escalation_after_days']), (False, 1, 2, 3))
        body = {'is_enabled': True, 'reminder_after_days': 2, 'first_escalation_after_days': 2,
                'second_escalation_after_days': 3, 'escalation_head': str(self.head.pk),
                'applies_to_leave': True, 'applies_to_attendance': False}
        self.assertEqual(self.api(self.admin).put(url, body, format='json').status_code, 400)
        body['reminder_after_days'] = 1
        self.assertEqual(self.api(self.mgr).put(url, body, format='json').status_code, 403)
        resp = self.api(self.admin).put(url, body, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = ApprovalEscalationSettings.current()
        self.assertTrue(cfg.is_enabled)
        self.assertEqual(cfg.escalation_head_id, self.head.pk)
        self.assertFalse(cfg.applies_to_attendance)
        self.assertTrue(AuditLog.objects.filter(action='approval_escalation_settings_updated').exists())

    def test_head_candidates_are_approvers_admin_only(self):
        url = reverse('approvals-escalation-head-candidates')
        self.assertEqual(self.api(self.mgr).get(url).status_code, 403)
        ids = {p['id'] for p in self.api(self.admin).get(url).data['data']}
        self.assertTrue({str(self.head.pk), str(self.hr.pk), str(self.mgr.pk)} <= ids)
        self.assertNotIn(str(self.peer.pk), ids)


class LeaveCancellationTests(Base):
    def setUp(self):
        super().setUp()
        self.start = TODAY + datetime.timedelta(days=10)
        self.balance = LeaveBalance.objects.create(employee=self.emp, leave_type='casual', year=self.start.year,
                                                   total_days=Decimal('12'), used_days=Decimal('3'))
        self.lr = self.leave(start=self.start, status='approved')
        AttendanceRecord.objects.create(employee=self.emp, date=self.start, status=AttendanceRecord.STATUS_ON_LEAVE)
        Notification.objects.all().delete()

    def request_cancel(self, user=None, reason='Plans changed'):
        return self.api(user or self.emp).post(reverse('leave-cancellation-request', args=[self.lr.pk]),
                                               {'reason': reason}, format='json')

    def decide(self, user, action, remarks=''):
        return self.api(user).post(reverse('leave-cancellation-decision', args=[self.lr.pk]),
                                   {'action': action, 'remarks': remarks}, format='json')

    def test_request_then_approve_restores_balance_and_attendance(self):
        resp = self.request_cancel()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['cancellation_status'], 'requested')
        self.assertEqual(self.titles(self.emp), ['Leave Cancellation Requested'])
        self.assertEqual(self.titles(self.hr), ['Leave Cancellation Pending'])      # final approver (L2)
        self.assertEqual(self.titles(self.mgr), [])
        listed = self.api(self.hr).get(reverse('leave-cancellation-list')).data['data']
        self.assertEqual([r['id'] for r in listed], [str(self.lr.pk)])
        self.assertTrue(listed[0]['can_decide_cancellation'])
        self.assertEqual(self.request_cancel().status_code, 400)                    # already waiting

        Notification.objects.all().delete()
        resp = self.decide(self.hr, 'approve')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lr.refresh_from_db()
        self.balance.refresh_from_db()
        self.assertEqual((self.lr.status, self.lr.cancellation_status), ('cancelled', 'approved'))
        self.assertEqual(self.balance.used_days, Decimal('2'))
        self.assertFalse(AttendanceRecord.objects.filter(employee=self.emp, date=self.start).exists())
        self.assertEqual(self.titles(self.emp), ['Leave Cancellation Approved'])
        self.assertTrue(AuditLog.objects.filter(action='leave_cancellation_approved').exists())
        self.assertEqual(self.decide(self.hr, 'approve').status_code, 404)          # nothing waiting now

    def test_reject_needs_remarks_and_keeps_leave(self):
        self.request_cancel()
        Notification.objects.all().delete()
        self.assertEqual(self.decide(self.hr, 'reject').status_code, 400)
        resp = self.decide(self.hr, 'reject', 'Peak season')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lr.refresh_from_db()
        self.balance.refresh_from_db()
        self.assertEqual((self.lr.status, self.lr.cancellation_status), ('approved', 'rejected'))
        self.assertEqual(self.balance.used_days, Decimal('3'))
        self.assertEqual(self.titles(self.emp), ['Leave Cancellation Rejected'])
        self.assertEqual(self.request_cancel().status_code, 200)                    # may ask again

    def test_l1_decides_when_no_l2(self):
        LeaveRequest.objects.filter(pk=self.lr.pk).update(l2_approver=None)
        self.request_cancel()
        self.assertEqual(self.titles(self.mgr), ['Leave Cancellation Pending'])
        self.assertEqual(self.decide(self.mgr2, 'approve').status_code, 403)
        self.assertEqual(self.decide(self.mgr, 'approve').status_code, 200)

    def test_only_owner_only_future_only_approved(self):
        self.assertEqual(self.request_cancel(user=self.peer).status_code, 404)
        self.assertEqual(self.request_cancel(reason='no').status_code, 400)
        LeaveRequest.objects.filter(pk=self.lr.pk).update(start_date=TODAY, end_date=TODAY)
        self.assertEqual(self.request_cancel().status_code, 400)
        LeaveRequest.objects.filter(pk=self.lr.pk).update(start_date=self.start, end_date=self.start,
                                                          status='pending')
        self.assertEqual(self.request_cancel().status_code, 400)

    def test_unauthorised_deciders(self):
        self.request_cancel()
        for u in (self.emp, self.peer, self.mgr_south):
            with self.subTest(user=u.full_name):
                self.assertIn(self.decide(u, 'approve').status_code, (403, 404))
        self.assertEqual(self.api(self.peer).get(reverse('leave-cancellation-list')).data['data'], [])
        self.lr.refresh_from_db()
        self.assertEqual(self.lr.status, 'approved')

    def test_delegate_of_final_approver_can_decide(self):
        create_delegation(actor=self.hr, delegator=self.hr, delegate=self.head, start_date=TODAY,
                          end_date=TODAY + datetime.timedelta(days=3), workflows=['leave'])
        Notification.objects.all().delete()
        self.request_cancel()
        self.assertEqual(self.titles(self.head), ['Leave Cancellation Pending'])
        self.assertEqual(self.decide(self.head, 'approve').status_code, 200)


class BalanceNotificationTests(Base):
    def test_credit_transaction_notifies_employee(self):
        bal = LeaveBalance.objects.create(employee=self.emp, leave_type='casual', year=2026,
                                          total_days=Decimal('12'), used_days=Decimal('0'))
        Notification.objects.all().delete()
        LeaveCreditTransaction.objects.create(balance=bal, employee=self.emp, leave_type='casual', year=2026,
                                              txn_type='adjustment', amount=Decimal('2'), total_before=Decimal('12'),
                                              total_after=Decimal('14'), reason='Comp', idempotency_key='k1')
        LeaveCreditTransaction.objects.create(balance=bal, employee=self.emp, leave_type='casual', year=2026, month=3,
                                              txn_type='monthly_credit', amount=Decimal('1'),
                                              total_before=Decimal('14'), total_after=Decimal('15'), reason='m',
                                              idempotency_key='k2')
        msgs = list(Notification.objects.filter(user=self.emp, title='Leave Balance Updated')
                    .order_by('created_at').values_list('message', flat=True))
        self.assertEqual(len(msgs), 2)
        self.assertIn('+2', msgs[0])
        self.assertIn('14', msgs[0])
        self.assertIn('March 2026', msgs[1])
        self.assertFalse(Notification.objects.exclude(user=self.emp).exists())
