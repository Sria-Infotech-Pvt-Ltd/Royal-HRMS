"""
Regression tests for the pending-approval ("maker-checker") personnel actions:
who may raise, who may decide each step, that the maker can never be a checker,
that nothing changes until the LAST approval, and that the approved change is
applied through the same views the direct path uses.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.accounts.models_personnel_action import PersonnelActionRequest as PAR
from apps.payroll.models import EmployeeSalaryConfig

TODAY = datetime.date.today().isoformat()
BRANCH = 'Test Branch'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class PersonnelActionPipelineTests(TestCase):
    def setUp(self):
        cache.clear()
        self.manager_role = make_role(
            'par_manager', can_manage_team=True,
            permission_codenames=['employees.view', 'employees.raise_action'],
        )
        self.hr_role = make_role(
            'par_hr', permission_codenames=[
                'employees.view', 'employees.edit', 'employees.approve', 'employees.confirm', 'payroll.view',
            ],
        )
        self.payroll_role = make_role('par_payroll', permission_codenames=['employees.view', 'payroll.view', 'payroll.edit'])
        self.employee_role = make_role('par_employee')

        self.manager = make_user('par_mgr@test.com', role=self.manager_role, full_name='Mgr', employee_id='PM1', branch=BRANCH)
        self.hr = make_user('par_hr@test.com', role=self.hr_role, full_name='HR', employee_id='PH1', branch=BRANCH)
        self.payroll = make_user('par_pay@test.com', role=self.payroll_role, full_name='Payroll', employee_id='PP1', branch=BRANCH)
        self.employee = make_user(
            'par_emp@test.com', role=self.employee_role, full_name='Emp', employee_id='PE1', branch=BRANCH,
            reporting_manager=self.manager,
        )
        self.url = f'/api/employees/{self.employee.employee_id}/action-requests/'

    def _raise(self, user=None, **overrides):
        body = {'action_type': 'org_assignment', 'reason': 'location_transfer', 'effective_from': TODAY,
                'work_location': 'Pune'}
        body.update(overrides)
        return _api(user or self.manager).post(self.url, body, format='json')

    # ── raising ──────────────────────────────────────────────────────────
    def test_only_holders_of_raise_action_can_raise(self):
        self.assertEqual(self._raise(self.employee).status_code, 403)
        self.assertEqual(self._raise(self.payroll).status_code, 403)
        self.assertEqual(self._raise(self.manager).status_code, 201)

    def test_manager_cannot_raise_for_someone_who_is_not_their_report(self):
        outsider = make_user('par_out@test.com', role=self.employee_role, employee_id='PO1', branch=BRANCH)
        resp = _api(self.manager).post(f'/api/employees/{outsider.employee_id}/action-requests/', {
            'action_type': 'confirmation', 'reason': 'probation_completed', 'effective_from': TODAY,
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_managers_own_step_is_satisfied_by_raising(self):
        data = self._raise().data['data']
        self.assertEqual([(s['key'], s['status']) for s in data['steps']], [('manager', 'approved'), ('hr', 'pending')])
        self.assertEqual(data['current_step_label'], 'HR Business Partner')

    def test_pay_change_route_skips_manager_and_ends_with_payroll(self):
        data = self._raise(action_type='pay_change', reason='increment', annual_ctc='900000').data['data']
        self.assertEqual([s['key'] for s in data['steps']], ['hr', 'payroll'])

    def test_current_pay_is_hidden_from_a_viewer_without_payroll_access(self):
        EmployeeSalaryConfig.objects.create(
            employee=self.employee, annual_ctc=Decimal('500000'), effective_from=datetime.date(2024, 1, 1), is_active=True,
        )
        raised = self._raise(action_type='pay_change', reason='increment', annual_ctc='900000').data['data']
        self.assertIsNone(raised['before']['annual_ctc'])
        self.assertEqual(raised['after']['annual_ctc'], '900000')
        as_payroll = _api(self.payroll).get(self.url).data['data']['results'][0]
        self.assertEqual(as_payroll['before']['annual_ctc'], '500000.00')

    def test_promotion_with_ctc_adds_a_payroll_step(self):
        from apps.accounts.models import OrgUnit, Position
        unit = OrgUnit.objects.create(name='U')
        position = Position.objects.create(org_unit=unit, title='Lead')
        data = self._raise(action_type='promotion', reason='performance_based', position=str(position.id),
                           annual_ctc='1200000').data['data']
        self.assertEqual([s['key'] for s in data['steps']], ['manager', 'hr', 'payroll'])

    def test_invalid_input_is_rejected_at_raise_time(self):
        self.assertEqual(self._raise(reason='nonsense').status_code, 400)
        self.assertEqual(self._raise(action_type='pay_change', reason='increment', annual_ctc='-5').status_code, 400)
        self.assertEqual(self._raise(work_location='').status_code, 400)

    def test_second_pending_request_of_same_type_is_a_conflict(self):
        self.assertEqual(self._raise().status_code, 201)
        self.assertEqual(self._raise(work_location='Delhi').status_code, 409)

    # ── deciding ─────────────────────────────────────────────────────────
    def test_maker_can_never_decide_their_own_request(self):
        rid = self._raise().data['data']['id']
        resp = _api(self.manager).post(f'/api/action-requests/{rid}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_wrong_role_cannot_decide_a_step(self):
        rid = self._raise().data['data']['id']
        self.assertEqual(_api(self.payroll).post(f'/api/action-requests/{rid}/approve/', {}, format='json').status_code, 403)
        self.assertEqual(_api(self.employee).post(f'/api/action-requests/{rid}/approve/', {}, format='json').status_code, 403)

    def test_hr_in_another_branch_cannot_decide(self):
        rid = self._raise().data['data']['id']
        far_hr = make_user('par_hr2@test.com', role=self.hr_role, employee_id='PH2', branch='Elsewhere')
        self.assertEqual(_api(far_hr).post(f'/api/action-requests/{rid}/approve/', {}, format='json').status_code, 403)

    def test_rejecting_requires_a_reason_and_changes_nothing(self):
        rid = self._raise().data['data']['id']
        self.assertEqual(_api(self.hr).post(f'/api/action-requests/{rid}/reject/', {}, format='json').status_code, 400)
        resp = _api(self.hr).post(f'/api/action-requests/{rid}/reject/', {'note': 'Not now'}, format='json')
        self.assertEqual(resp.data['data']['status'], 'rejected')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.work_location, '')

    # ── applying ─────────────────────────────────────────────────────────
    def test_approval_applies_the_org_assignment(self):
        rid = self._raise().data['data']['id']
        resp = _api(self.hr).post(f'/api/action-requests/{rid}/approve/', {}, format='json')
        self.assertEqual(resp.data['data']['status'], 'applied', resp.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.work_location, 'Pune')

    def test_nothing_changes_until_the_last_step_is_approved(self):
        rid = self._raise(action_type='pay_change', reason='increment', annual_ctc='900000').data['data']['id']
        step1 = _api(self.hr).post(f'/api/action-requests/{rid}/approve/', {}, format='json').data['data']
        self.assertEqual(step1['status'], 'pending')
        self.assertEqual(step1['current_step_label'], 'Payroll Admin')
        self.assertFalse(EmployeeSalaryConfig.objects.filter(employee=self.employee).exists())
        step2 = _api(self.payroll).post(f'/api/action-requests/{rid}/approve/', {}, format='json').data['data']
        self.assertEqual(step2['status'], 'applied', step2)
        self.assertTrue(EmployeeSalaryConfig.objects.filter(employee=self.employee, annual_ctc=900000, is_active=True).exists())

    def test_confirmation_is_applied_by_the_hr_approver(self):
        rid = self._raise(action_type='confirmation', reason='probation_completed').data['data']['id']
        _api(self.hr).post(f'/api/action-requests/{rid}/approve/', {}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, User.EMPLOYMENT_STATUS_CONFIRMED)

    # ── inbox / cancel ───────────────────────────────────────────────────
    def test_inbox_only_shows_requests_the_user_may_decide_now(self):
        self._raise(action_type='pay_change', reason='increment', annual_ctc='900000')
        self.assertEqual(_api(self.hr).get('/api/action-requests/').data['data']['count'], 1)
        self.assertEqual(_api(self.payroll).get('/api/action-requests/').data['data']['count'], 0)   # HR step first
        self.assertEqual(_api(self.employee).get('/api/action-requests/').data['data']['count'], 0)

    def test_only_the_raiser_can_cancel_a_pending_request(self):
        rid = self._raise().data['data']['id']
        self.assertEqual(_api(self.hr).post(f'/api/action-requests/{rid}/cancel/', {}, format='json').status_code, 403)
        resp = _api(self.manager).post(f'/api/action-requests/{rid}/cancel/', {}, format='json')
        self.assertEqual(resp.data['data']['status'], 'cancelled')
        self.assertEqual(PAR.objects.get(pk=rid).status, PAR.STATUS_CANCELLED)


class LeaveBalanceScopeTests(TestCase):
    """GET /leave/balance/?employee_id= used to expose every employee's
    balances to anyone with employees.view."""

    def setUp(self):
        cache.clear()
        manager_role = make_role('lb_manager', can_manage_team=True, permission_codenames=['employees.view', 'leave.view'])
        self.manager = make_user('lb_mgr@test.com', role=manager_role, employee_id='LM1', branch=BRANCH)
        employee_role = make_role('lb_employee')
        self.report = make_user('lb_rep@test.com', role=employee_role, employee_id='LR1', branch=BRANCH, reporting_manager=self.manager)
        self.other = make_user('lb_oth@test.com', role=employee_role, employee_id='LO1', branch=BRANCH)

    def test_manager_sees_direct_reports_but_not_other_employees(self):
        client = _api(self.manager)
        self.assertEqual(client.get('/api/leave/balance/?employee_id=LR1').status_code, 200)
        self.assertEqual(client.get('/api/leave/balance/?employee_id=LO1').status_code, 404)
