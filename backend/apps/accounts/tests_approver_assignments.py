"""
Employee approver assignments: who may be an employee's reporting manager, L1 approver and L2 HR approver, how an HR user
assigns them, what the employee sees (read-only), and how the leave request uses them.

Rules under test:
  - an approver must be active, an employee, not the employee themselves, and (for L1 / L2) able to approve leave;
  - only HR with employees.edit, inside their own scope, assigns; nobody changes their own approvers;
  - L1 and L2 are resolved one at a time (an override for one level must not blank the other);
  - an inactive approver counts as nobody, and a request is never submitted into a chain that cannot finish.
"""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule, AuditLog, EmployeeApprovalOverride, User
from apps.accounts.services_approval import resolve_approval_chain
from apps.accounts.services_approval_chain import describe_chain
from apps.hrms.models import REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING, LeaveBalance, LeavePolicy, LeaveRequest
from core.cache_service import ApprovalWorkflowCacheService

BRANCH = 'Approver Test Branch'
LEAVE = 'leave'
APPROVE = ['leave.approve', 'leave.view']


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class _ApproverFixtures(TestCase):
    def setUp(self):
        cache.clear()
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type=LEAVE, defaults={'l1_approver_kind': 'reporting_manager', 'l2_approver_kind': 'hr'},
        )
        ApprovalWorkflowCacheService.invalidate(LEAVE)
        self.hr = self._person('aa_hr@test.com', 'AA001', ['employees.view', 'employees.edit', 'employees.create', *APPROVE], 'HR Business Partner')
        self.manager = self._person('aa_manager@test.com', 'AA002', APPROVE, 'Engineering Manager', team=True)
        self.other_manager = self._person('aa_manager2@test.com', 'AA003', APPROVE, 'Delivery Manager', team=True)
        self.manager_without_permission = self._person('aa_manager3@test.com', 'AA004', ['leave.view'], 'Team Lead', team=True)
        self.inactive_manager = self._person('aa_gone@test.com', 'AA005', APPROVE, 'Former Manager', team=True, is_active=False)
        self.employee = self._person('aa_emp@test.com', 'AA010', [], 'Software Engineer', reporting_manager=self.manager, hr=self.hr,
                                     reporting_manager_from_org_chart=False)
        self.elsewhere = self._person('aa_far@test.com', 'AA011', APPROVE, 'Remote Manager', team=True, branch='Elsewhere Branch')

    def _person(self, email: str, employee_id: str, permissions: list[str], designation: str, *, team: bool = False,
                branch: str = BRANCH, **extra) -> User:
        role = make_role(f'role_{employee_id}', permission_codenames=permissions, can_manage_team=team)
        return make_user(email, role=role, employee_id=employee_id, branch=branch, designation=designation, **extra)

    def _assign(self, actor: User, employee: User, body: dict):
        return _client(actor).put(reverse('employee-approver-assignments', args=[employee.employee_id]), body, format='json')

    def _options(self, actor: User, kind: str, **params):
        response = _client(actor).get(reverse('approver-options'), {'kind': kind, **params})
        return response, [row['employee_id'] for row in (response.json().get('data') or {}).get('results', [])]


class ApproverOptionsTests(_ApproverFixtures):
    def test_l1_and_l2_options_are_only_active_people_who_can_approve_leave_inside_the_callers_scope(self):
        response, ids = self._options(self.hr, 'l1', employee_id=self.employee.employee_id)
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(set(ids), {'AA001', 'AA002', 'AA003'})  # not the employee, inactive, no permission, or another branch
        self.assertEqual(set(self._options(self.hr, 'l2', employee_id=self.employee.employee_id)[1]), {'AA001', 'AA002', 'AA003'})

    def test_reporting_manager_options_skip_the_employee_themselves_and_inactive_people(self):
        _response, ids = self._options(self.hr, 'reporting_manager', employee_id=self.employee.employee_id)
        self.assertNotIn('AA010', ids)
        self.assertNotIn('AA005', ids)
        self.assertIn('AA004', ids)  # a reporting manager needs no approval permission

    def test_each_option_shows_name_role_branch_and_department(self):
        response, _ids = self._options(self.hr, 'l1', q='AA003')
        row = response.json()['data']['results'][0]
        self.assertEqual((row['role'], row['branch']), ('Delivery Manager', BRANCH))
        self.assertIn('department', row)
        self.assertIn('full_name', row)

    def test_search_filters_by_name_or_employee_id(self):
        self.assertEqual(self._options(self.hr, 'l1', q='AA003')[1], ['AA003'])

    def test_an_employee_without_hr_permissions_cannot_list_options(self):
        self.assertEqual(self._options(self.employee, 'l1')[0].status_code, 403)

    def test_an_unknown_kind_is_refused(self):
        self.assertEqual(self._options(self.hr, 'ceo')[0].status_code, 400)


class AssignmentSaveTests(_ApproverFixtures):
    def test_hr_assigns_reporting_manager_l1_and_l2_and_the_change_is_audited(self):
        response = self._assign(self.hr, self.employee, {
            'reporting_manager_id': str(self.manager.pk), 'l1_approver_id': str(self.other_manager.pk), 'hr_id': str(self.hr.pk),
        })
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()['data']
        self.assertEqual(data['l1_approver']['assigned']['full_name'], self.other_manager.full_name)
        self.assertEqual(data['l2_hr_approver']['assigned']['full_name'], self.hr.full_name)
        self.assertEqual(data['reporting_manager']['assigned']['full_name'], self.manager.full_name)

        self.employee.refresh_from_db()
        self.assertEqual((self.employee.reporting_manager_id, self.employee.hr_id), (self.manager.pk, self.hr.pk))
        override = EmployeeApprovalOverride.objects.get(employee=self.employee, workflow_type=LEAVE)
        self.assertEqual((override.l1_override_id, override.l2_override_id), (self.other_manager.pk, None))

    def test_the_audit_log_records_who_changed_what(self):
        self._assign(self.hr, self.employee, {'l1_approver_id': str(self.other_manager.pk)})
        entry = AuditLog.objects.get(action='approver_assignment_changed', object_id=str(self.employee.pk))
        self.assertEqual(entry.user_id, self.hr.pk)
        self.assertEqual(entry.changes['l1_approver_id'], {'from': None, 'to': self.other_manager.full_name})

    def test_an_unchanged_save_writes_no_audit_entry(self):
        self._assign(self.hr, self.employee, {'hr_id': str(self.hr.pk)})
        self.assertFalse(AuditLog.objects.filter(action='approver_assignment_changed').exists())

    def test_only_the_keys_sent_are_changed(self):
        self._assign(self.hr, self.employee, {'l1_approver_id': str(self.other_manager.pk)})
        self.employee.refresh_from_db()
        self.assertEqual((self.employee.reporting_manager_id, self.employee.hr_id), (self.manager.pk, self.hr.pk))

    def test_clearing_l1_returns_to_the_approval_rule_and_removes_the_override(self):
        self._assign(self.hr, self.employee, {'l1_approver_id': str(self.other_manager.pk)})
        self._assign(self.hr, self.employee, {'l1_approver_id': None})
        self.assertFalse(EmployeeApprovalOverride.objects.filter(employee=self.employee).exists())
        self.assertEqual(resolve_approval_chain(self.employee, LEAVE)[0], self.manager)  # the rule: reporting manager


class AssignmentValidationTests(_ApproverFixtures):
    def _refused(self, field: str, person: User, expected_text: str):
        response = self._assign(self.hr, self.employee, {field: str(person.pk)})
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn(expected_text, response.json()['data'][field])
        self.employee.refresh_from_db()

    def test_an_inactive_person_cannot_be_assigned(self):
        for field in ('reporting_manager_id', 'l1_approver_id', 'hr_id'):
            self._refused(field, self.inactive_manager, 'inactive')

    def test_nobody_can_be_their_own_approver(self):
        self._refused('reporting_manager_id', self.employee, 'their own')

    def test_l1_and_l2_need_the_leave_approval_permission(self):
        self._refused('l1_approver_id', self.manager_without_permission, 'cannot approve leave requests')
        self._refused('hr_id', self.manager_without_permission, 'cannot approve leave requests')

    def test_an_unknown_person_is_refused(self):
        response = self._assign(self.hr, self.employee, {'l1_approver_id': '00000000-0000-0000-0000-000000000000'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._assign(self.hr, self.employee, {'l1_approver_id': 'not-a-uuid'}).status_code, 400)

    def test_a_reporting_cycle_is_refused(self):
        User.objects.filter(pk=self.manager.pk).update(reporting_manager=self.employee)
        self._refused('reporting_manager_id', User.objects.get(pk=self.manager.pk), 'reporting cycle')

    def test_a_manager_has_no_reporting_manager(self):
        response = self._assign(self.hr, self.manager, {'reporting_manager_id': str(self.other_manager.pk)})
        self.assertEqual(response.status_code, 400)
        self.assertIn('do not have a reporting manager', response.json()['message'])

    def test_a_rejected_choice_saves_nothing_from_the_same_request(self):
        response = self._assign(self.hr, self.employee, {'hr_id': str(self.other_manager.pk), 'l1_approver_id': str(self.inactive_manager.pk)})
        self.assertEqual(response.status_code, 400)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.hr_id, self.hr.pk)
        self.assertFalse(EmployeeApprovalOverride.objects.filter(employee=self.employee).exists())

    def test_the_approval_matrix_api_applies_the_same_rules(self):
        url = reverse('employee-approval-matrix', args=[self.employee.employee_id])
        refused = _client(self.hr).put(url, {'workflow_type': LEAVE, 'l1_override_id': str(self.manager_without_permission.pk)}, format='json')
        self.assertEqual(refused.status_code, 400)
        saved = _client(self.hr).put(url, {'workflow_type': LEAVE, 'l1_override_id': str(self.other_manager.pk)}, format='json')
        self.assertEqual(saved.status_code, 200, saved.json())
        self.assertTrue(AuditLog.objects.filter(action='approver_assignment_changed', object_id=str(self.employee.pk)).exists())


class AssignmentPermissionTests(_ApproverFixtures):
    def test_an_employee_cannot_change_their_own_approvers(self):
        response = self._assign(self.employee, self.employee, {'hr_id': str(self.other_manager.pk)})
        self.assertEqual(response.status_code, 403)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.hr_id, self.hr.pk)

    def test_an_hr_user_cannot_change_their_own_approvers_either(self):
        self.assertEqual(self._assign(self.hr, self.hr, {'hr_id': str(self.other_manager.pk)}).status_code, 403)

    def test_a_manager_without_employees_edit_cannot_assign(self):
        self.assertEqual(self._assign(self.manager, self.employee, {'hr_id': str(self.hr.pk)}).status_code, 403)

    def test_an_employee_cannot_read_anyone_elses_assignments(self):
        url = reverse('employee-approver-assignments', args=[self.manager.employee_id])
        self.assertEqual(_client(self.employee).get(url).status_code, 403)

    def test_hr_cannot_reach_an_employee_outside_their_branch(self):
        outsider = self._person('aa_out@test.com', 'AA012', [], 'Analyst', branch='Elsewhere Branch')
        self.assertEqual(self._assign(self.hr, outsider, {'hr_id': str(self.hr.pk)}).status_code, 404)
        self.assertEqual(_client(self.hr).get(reverse('employee-approver-assignments', args=[outsider.employee_id])).status_code, 404)

    def test_hr_can_read_assignments_with_the_rule_and_the_effective_chain(self):
        response = _client(self.hr).get(reverse('employee-approver-assignments', args=[self.employee.employee_id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertTrue(data['can_edit'])
        self.assertEqual(data['rule']['l1_kind'], 'reporting_manager')
        self.assertEqual(data['l1_approver']['effective']['full_name'], self.manager.full_name)

    def test_the_employee_view_is_read_only(self):
        response = _client(self.employee).get(reverse('my-approvals'))
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(_client(self.employee).put(reverse('my-approvals'), {}, format='json').status_code, 405)


class ChainResolutionTests(_ApproverFixtures):
    def test_an_employee_with_both_levels_assigned_gets_both(self):
        EmployeeApprovalOverride.objects.create(employee=self.employee, workflow_type=LEAVE, l1_override=self.other_manager)
        self.assertEqual(resolve_approval_chain(self.employee, LEAVE), (self.other_manager, self.hr))

    def test_an_override_for_one_level_does_not_blank_the_other(self):
        EmployeeApprovalOverride.objects.create(employee=self.employee, workflow_type=LEAVE, l1_override=self.other_manager)
        l1, l2 = resolve_approval_chain(self.employee, LEAVE)
        self.assertEqual((l1, l2), (self.other_manager, self.hr))  # L2 still follows the rule (the HR partner)

    def test_an_inactive_override_is_ignored(self):
        EmployeeApprovalOverride.objects.create(employee=self.employee, workflow_type=LEAVE, l1_override=self.inactive_manager)
        self.assertEqual(resolve_approval_chain(self.employee, LEAVE)[0], self.manager)

    def test_an_inactive_hr_partner_is_not_used(self):
        User.objects.filter(pk=self.hr.pk).update(is_active=False)
        self.employee.refresh_from_db()
        self.assertNotEqual(resolve_approval_chain(self.employee, LEAVE)[1], self.hr)

    def test_the_description_names_both_approvers_for_a_complete_chain(self):
        chain = describe_chain(self.employee, LEAVE)
        self.assertTrue(chain['can_submit'])
        self.assertEqual(chain['warnings'], [])
        self.assertEqual([stage['status'] for stage in chain['stages']], ['assigned', 'assigned'])
        self.assertEqual(chain['stages'][0]['user']['full_name'], self.manager.full_name)
        self.assertEqual(chain['reporting_manager']['full_name'], self.manager.full_name)

    def test_the_employee_form_has_names_and_roles_but_no_ids(self):
        stage = describe_chain(self.employee, LEAVE, detail=False)['stages'][0]['user']
        self.assertEqual(set(stage), {'full_name', 'role'})

    def test_a_missing_l1_is_a_warning_but_the_request_still_has_an_approver(self):
        loner = self._person('aa_loner@test.com', 'AA020', [], 'Analyst', hr=self.hr)
        chain = describe_chain(loner, LEAVE)
        self.assertEqual(chain['stages'][0]['status'], 'missing')
        self.assertTrue(any('L1 approver' in warning for warning in chain['warnings']))
        self.assertTrue(chain['can_submit'])

    def test_with_no_named_hr_the_branch_fallback_decides_so_submission_is_allowed(self):
        loner = self._person('aa_loner2@test.com', 'AA023', [], 'Analyst')   # same branch as the HR and managers, nobody assigned
        chain = describe_chain(loner, LEAVE)
        self.assertTrue(chain['can_submit'])
        self.assertEqual(chain['stages'][1]['status'], 'assigned')   # the existing fallback finds an HR in the branch
        self.assertTrue(any(warning.startswith('L1 approver') for warning in chain['warnings']))

    def test_an_inactive_assigned_approver_is_called_out(self):
        EmployeeApprovalOverride.objects.create(employee=self.employee, workflow_type=LEAVE, l1_override=self.inactive_manager)
        warnings = describe_chain(self.employee, LEAVE)['warnings']
        self.assertTrue(any('inactive' in warning and self.inactive_manager.full_name in warning for warning in warnings), warnings)

    def test_nobody_available_blocks_submission(self):
        orphan = self._person('aa_orphan@test.com', 'AA021', [], 'Analyst', branch='A Branch With Nobody')
        chain = describe_chain(orphan, LEAVE)
        self.assertFalse(chain['can_submit'])
        self.assertTrue(any('Nobody is available' in text for text in chain['blocking']))

    def test_a_named_approver_who_cannot_approve_leave_blocks_submission(self):
        User.objects.filter(pk=self.employee.pk).update(reporting_manager=self.manager_without_permission)
        self.employee.refresh_from_db()
        chain = describe_chain(self.employee, LEAVE)
        self.assertFalse(chain['can_submit'])
        self.assertTrue(any('cannot approve leave requests' in text for text in chain['blocking']))


class LeaveRequestApprovalChainTests(_ApproverFixtures):
    def setUp(self):
        super().setUp()
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'annual_days': 8, 'is_active': True, 'minimum_notice_period': 0, 'maximum_consecutive_days': 0,
                      'minimum_service_period': 0, 'applicable_gender': 'all', 'allow_probation_leave': True},
        )
        day = datetime.date.today() + datetime.timedelta(days=1)
        while day.weekday() >= 5:
            day += datetime.timedelta(days=1)
        self.day = day
        self._balance(self.employee)

    def _balance(self, employee: User) -> None:
        LeaveBalance.objects.update_or_create(employee=employee, leave_type='casual', year=self.day.year,
                                              defaults={'total_days': 8, 'used_days': 0})

    def _apply(self, employee: User):
        return _client(employee).post(reverse('leave-request-list'), {
            'leave_type': 'casual', 'duration': 'full_day', 'start_date': self.day.isoformat(), 'end_date': self.day.isoformat(),
            'reason': 'Family function',
        }, format='json')

    def _decide(self, approver: User, request_id: str, action: str = 'approve'):
        return _client(approver).post(reverse('leave-request-approve', args=[request_id]), {'action': action}, format='json')

    def test_a_request_goes_to_l1_then_l2_and_is_approved(self):
        created = self._apply(self.employee)
        self.assertEqual(created.status_code, 201, created.json())
        request_id = created.json()['data']['id']
        leave = LeaveRequest.objects.get(pk=request_id)
        self.assertEqual((leave.status, leave.l1_approver_id, leave.l2_approver_id), (REQ_PENDING, self.manager.pk, self.hr.pk))

        self.assertEqual(self._decide(self.manager, request_id).status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_L2_PENDING)
        self.assertEqual(self._decide(self.hr, request_id).status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).status, REQ_APPROVED)

    def test_an_assigned_l1_who_is_not_the_reporting_manager_is_the_one_who_decides(self):
        self._assign(self.hr, self.employee, {'l1_approver_id': str(self.other_manager.pk)})
        request_id = self._apply(self.employee).json()['data']['id']
        self.assertEqual(LeaveRequest.objects.get(pk=request_id).l1_approver_id, self.other_manager.pk)
        self.assertEqual(self._decide(self.manager, request_id).status_code, 403)  # still the reporting manager, no longer L1
        self.assertEqual(self._decide(self.other_manager, request_id).status_code, 200)

    def test_submission_is_refused_when_nobody_can_decide_it(self):
        orphan = self._person('aa_orphan2@test.com', 'AA022', [], 'Analyst', branch='A Branch With Nobody')
        self._balance(orphan)
        response = self._apply(orphan)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Nobody is available', response.json()['message'])
        self.assertFalse(LeaveRequest.objects.filter(employee=orphan).exists())

    def test_submission_is_refused_when_the_l1_cannot_approve_leave(self):
        User.objects.filter(pk=self.employee.pk).update(reporting_manager=self.manager_without_permission)
        response = self._apply(User.objects.get(pk=self.employee.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn('cannot approve leave requests', response.json()['message'])
        self.assertFalse(LeaveRequest.objects.filter(employee=self.employee).exists())

    def test_with_an_inactive_l1_the_request_is_routed_to_the_fallback_not_the_inactive_person(self):
        EmployeeApprovalOverride.objects.create(employee=self.employee, workflow_type=LEAVE, l1_override=self.inactive_manager)
        created = self._apply(self.employee)
        self.assertEqual(created.status_code, 201, created.json())
        self.assertEqual(LeaveRequest.objects.get(pk=created.json()['data']['id']).l1_approver_id, self.manager.pk)

    def test_the_employee_can_see_the_chain_before_submitting(self):
        data = _client(self.employee).get(reverse('my-approvals')).json()['data']
        self.assertTrue(data['can_submit'])
        self.assertEqual([stage['user']['full_name'] for stage in data['stages']], [self.manager.full_name, self.hr.full_name])
