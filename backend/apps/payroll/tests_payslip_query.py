"""
Employee payslip queries: raise (own payslip, within the window), history,
HR list / resolve within branch scope, and notifications.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City
from apps.notifications.models import Notification
from apps.payroll.models import EmployeePayslip, PayrollCycle, PayslipQuery
from apps.payroll.tests_salary_components import SalaryFixtureMixin, _login

D = Decimal


class PayslipQueryTests(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()                                   # branch A, admin HR (settings.edit), …
        city = City.objects.create(name='QueryCityB', state=self.state)
        self.branch_b = Branch.objects.create(branch_code='QBR', branch_name='QueryBranchB',
                                              status=Branch.STATUS_ACTIVE, state=self.state, city=city)
        a, b = self.branch.branch_name, self.branch_b.branch_name

        staff_role = make_role('q_staff', permission_codenames=['payroll.view_own'])
        self.emp1 = make_user('q.e1@test.com', role=staff_role, employee_id='QE1', full_name='Query One', branch=a)
        self.emp2 = make_user('q.e2@test.com', role=staff_role, employee_id='QE2', full_name='Query Two', branch=a)
        self.emp3 = make_user('q.e3@test.com', role=staff_role, employee_id='QE3', full_name='Query Three', branch=b)
        hr_role = make_role('q_branch_hr', permission_codenames=['payroll.view', 'payroll.edit', 'payroll.view_own'])
        self.hr_a = make_user('q.hra@test.com', role=hr_role, employee_id='QHA', full_name='HR A', branch=a)
        self.hr_b = make_user('q.hrb@test.com', role=hr_role, employee_id='QHB', full_name='HR B', branch=b)

        self.cycle_a = self._cycle(self.branch)
        self.cycle_b = self._cycle(self.branch_b)
        self.p1 = self._payslip(self.emp1, self.cycle_a)
        self.p2 = self._payslip(self.emp2, self.cycle_a)
        self.p3 = self._payslip(self.emp3, self.cycle_b)
        self.p_hr = self._payslip(self.hr_a, self.cycle_a)

    def _cycle(self, branch):
        return PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 9, 1), cycle_end=datetime.date(2026, 9, 30),
            pay_date=datetime.date(2026, 9, 30), created_by=self.hr, branch=branch,
            status=PayrollCycle.STATUS_QUERY_WINDOW_OPEN,
        )

    def _payslip(self, employee, cycle, **over):
        fields = dict(cycle=cycle, employee=employee, annual_ctc=D('600000'), monthly_ctc=D('50000'),
                      basic=D('20000'), gross_earnings=D('35000'), net_pay=D('32000'), total_working_days=26,
                      status=EmployeePayslip.STATUS_SENT, sent_at=timezone.now(),
                      query_deadline=timezone.now() + datetime.timedelta(hours=24))
        fields.update(over)
        return EmployeePayslip.objects.create(**fields)

    def _client(self, user):
        api = APIClient()
        _login(api, user.email)
        return api

    def _raise(self, api, payslip, text='Basic looks wrong this month.'):
        with self.captureOnCommitCallbacks(execute=True):
            return api.post(reverse('payslip-query-list'), {'payslip': str(payslip.pk), 'description': text},
                            format='json')

    def _resolve(self, api, query_id, note='Corrected in next cycle.'):
        with self.captureOnCommitCallbacks(execute=True):
            return api.post(reverse('payslip-query-resolve', kwargs={'pk': query_id}),
                            {'resolution_note': note}, format='json')

    def _notified(self, kind):
        return set(Notification.objects.filter(notification_type=kind).values_list('user__email', flat=True))

    # 1, 10 ── raise + HR notification recipients
    def test_employee_raises_query_and_branch_hr_is_notified(self):
        resp = self._raise(self._client(self.emp1), self.p1, '  Basic looks wrong this month.  ')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['description'], 'Basic looks wrong this month.')   # trimmed
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.status, EmployeePayslip.STATUS_QUERIED)
        # branch A HR + org-wide admin; not branch B HR, not the employee
        self.assertEqual(self._notified('payslip_query_raised'), {'q.hra@test.com', 'salcomp.hr@test.com'})

    # 2 ── someone else's payslip
    def test_cannot_raise_on_or_see_another_employees_payslip(self):
        self.assertEqual(self._raise(self._client(self.emp2), self.p1).status_code, 404)
        self._raise(self._client(self.emp1), self.p1)
        rows = self._client(self.emp2).get(reverse('payslip-query-list')).data['data']
        self.assertEqual(rows, [])

    # 3 ── window closed
    def test_cannot_raise_after_deadline(self):
        EmployeePayslip.objects.filter(pk=self.p1.pk).update(query_deadline=timezone.now() - datetime.timedelta(minutes=1))
        resp = self._raise(self._client(self.emp1), self.p1)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('query window', resp.data['message'])
        self.assertFalse(PayslipQuery.objects.exists())

    # 4 ── validation + duplicates
    def test_blank_long_and_duplicate_queries_rejected(self):
        api = self._client(self.emp1)
        self.assertEqual(self._raise(api, self.p1, '   ').status_code, 400)
        self.assertEqual(self._raise(api, self.p1, 'x' * 2001).status_code, 400)
        self.assertEqual(self._raise(api, self.p1).status_code, 201)
        second = self._raise(api, self.p1, 'Again')
        self.assertEqual(second.status_code, 400)                                     # payslip is now "queried"
        self.assertEqual(PayslipQuery.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(notification_type='payslip_query_raised').count(), 2)

    # 5, 7 ── history with resolution + employee notified
    def test_history_shows_resolution_and_employee_is_notified(self):
        api = self._client(self.emp1)
        qid = self._raise(api, self.p1).data['data']['id']
        resp = self._resolve(self._client(self.hr_a), qid)
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = api.get(reverse('payslip-query-list')).data['data']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['status'], row['resolution_note'], row['resolved_by_name'], str(row['payslip'])),
                         ('resolved', 'Corrected in next cycle.', 'HR A', str(self.p1.pk)))
        self.assertIsNotNone(row['resolved_at'])
        self.assertEqual(self._notified('payslip_query_resolved'), {'q.e1@test.com'})
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.status, EmployeePayslip.STATUS_RESOLVED)

    # 6 ── other branch HR
    def test_other_branch_hr_cannot_list_or_resolve(self):
        qid = self._raise(self._client(self.emp1), self.p1).data['data']['id']
        hr_b = self._client(self.hr_b)
        self.assertEqual(hr_b.get(reverse('payslip-query-list')).data['data'], [])
        resp = self._resolve(hr_b, qid)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._resolve(hr_b, qid, note='').status_code, 404)           # no hint either way
        self.assertEqual(PayslipQuery.objects.get(pk=qid).status, 'open')

    # 7, 8 ── branch HR and org-wide admin
    def test_branch_hr_sees_own_branch_and_admin_sees_all(self):
        self._raise(self._client(self.emp1), self.p1)
        self._raise(self._client(self.emp3), self.p3)
        hr_a_rows = self._client(self.hr_a).get(reverse('payslip-query-list')).data['data']
        self.assertEqual([r['employee_id_code'] for r in hr_a_rows], ['QE1'])
        admin_rows = self._client(self.hr).get(reverse('payslip-query-list')).data['data']
        self.assertEqual(sorted(r['employee_id_code'] for r in admin_rows), ['QE1', 'QE3'])

    def test_hr_mine_returns_only_own_queries(self):
        hr_api = self._client(self.hr_a)
        self._raise(hr_api, self.p_hr, 'My own payslip question')
        self._raise(self._client(self.emp1), self.p1)
        mine = hr_api.get(reverse('payslip-query-list'), {'mine': '1'}).data['data']
        self.assertEqual([r['description'] for r in mine], ['My own payslip question'])

    def test_resolve_requires_payroll_edit_and_note(self):
        qid = self._raise(self._client(self.emp1), self.p1).data['data']['id']
        self.assertEqual(self._resolve(self._client(self.emp2), qid).status_code, 403)
        self.assertEqual(self._resolve(self._client(self.hr_a), qid, note='   ').status_code, 400)

    # 11 ── notification failure does not break the operation
    def test_notification_failure_does_not_fail_raise_or_resolve(self):
        with mock.patch('apps.payroll.notifications.query_recipients', side_effect=RuntimeError('boom')):
            resp = self._raise(self._client(self.emp1), self.p1)
        self.assertEqual(resp.status_code, 201)
        with mock.patch('apps.notifications.models.Notification.objects.create', side_effect=RuntimeError('db')):
            resp = self._resolve(self._client(self.hr_a), resp.data['data']['id'])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PayslipQuery.objects.get().status, 'resolved')

    # 12 ── acknowledgement and transfer gate unchanged
    def test_acknowledge_still_works_and_open_query_still_blocks_transfer(self):
        resp = self._client(self.emp2).post(reverse('payslip-acknowledge', kwargs={'pk': self.p2.pk}))
        self.assertEqual(resp.status_code, 200, resp.data)
        self._raise(self._client(self.emp1), self.p1)
        status = self._client(self.hr_a).post(reverse('salary-transfer-confirm', kwargs={'cycle_pk': self.cycle_a.pk}))
        self.assertEqual(status.status_code, 400)
        self.assertIn('not yet acknowledged', status.data['message'])
