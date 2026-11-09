"""
Sensitive-assignment guard on the personnel-action engines, and the scan that keeps every assign_position() call guarded.

  * maker-checker personnel actions (services_personnel_actions): the RAISER is checked when the request is raised, the HR
    APPROVER (the one who applies it) when they decide, and the application itself dispatches the employee-edit view as that
    approver, so the edit door re-checks at application time;
  * employment-action engine (services_actions._handle_set_placement): re-checks the person who created and the one who
    applied the action.
"""
from __future__ import annotations

import ast
import datetime
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Permission, Placement, Position, PositionPermission, User
from apps.accounts.models_actions import ActionType, EmploymentAction
from apps.accounts.models_personnel_action import PersonnelActionRequest as PAR
from apps.accounts.services_actions import ActionConflictError, apply_employment_action
from apps.accounts.services_personnel_actions import _apply

TODAY = datetime.date.today().isoformat()
BRANCH = 'Guard Action Branch'
SENSITIVE_PAYROLL = ['payroll.view', 'payroll.edit']


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _seat(unit: OrgUnit, title: str, keys: list[str]) -> Position:
    position = Position.objects.create(org_unit=unit, title=title, grade='L3')
    for key in keys:
        PositionPermission.objects.create(position=position, permission=Permission.objects.get(codename=key))
    return position


class _ActionFixtures(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = OrgUnit.objects.create(name='Guard Action Unit')
        self.ordinary = _seat(self.unit, 'Senior Analyst', ['leave.view'])
        self.payroll_seat = _seat(self.unit, 'Payroll Executive', SENSITIVE_PAYROLL)
        raise_keys = ['employees.view', 'employees.raise_action']
        hr_keys = ['employees.view', 'employees.edit', 'employees.approve']
        self.weak_manager = self._user('ga_weak_mgr@test.com', 'GA001', raise_keys, team=True)
        self.strong_manager = self._user('ga_strong_mgr@test.com', 'GA002', raise_keys + SENSITIVE_PAYROLL, team=True)
        self.admin_manager = self._user('ga_admin_mgr@test.com', 'GA003', raise_keys + ['settings.edit'], team=True)
        self.weak_hr = self._user('ga_weak_hr@test.com', 'GA004', hr_keys)
        self.strong_hr = self._user('ga_strong_hr@test.com', 'GA005', hr_keys + SENSITIVE_PAYROLL)
        self.admin_hr = self._user('ga_admin_hr@test.com', 'GA006', hr_keys + ['settings.edit'])

    def _user(self, email: str, employee_id: str, keys: list[str], team: bool = False, **extra) -> User:
        return make_user(email, role=make_role(f'role_{employee_id}', permission_codenames=keys, can_manage_team=team), employee_id=employee_id, branch=BRANCH, **extra)

    def _employee(self, n: int, manager: User) -> User:
        return make_user(f'ga_emp{n}@test.com', employee_id=f'GA10{n}', branch=BRANCH, reporting_manager=manager)

    def _raise(self, actor: User, employee: User, position: Position):
        return _api(actor).post(
            f'/api/employees/{employee.employee_id}/action-requests/',
            {'action_type': 'promotion', 'reason': 'performance_based', 'effective_from': TODAY, 'position': str(position.pk)}, format='json',
        )

    def _approve(self, actor: User, request_id: str):
        return _api(actor).post(f'/api/action-requests/{request_id}/approve/', {}, format='json')


class PersonnelActionPositionTests(_ActionFixtures):
    def test_an_everyday_promotion_is_raised_approved_and_applied(self):
        employee = self._employee(1, self.weak_manager)
        raised = self._raise(self.weak_manager, employee, self.ordinary)
        self.assertEqual(raised.status_code, 201, raised.json())
        approved = self._approve(self.weak_hr, raised.json()['data']['id'])
        self.assertEqual(approved.status_code, 200, approved.json())
        self.assertEqual(PAR.objects.get(pk=raised.json()['data']['id']).status, PAR.STATUS_APPLIED)
        self.assertTrue(Placement.objects.filter(employee=employee, position=self.ordinary).exists())

    def test_a_raiser_without_authority_cannot_raise_a_promotion_into_a_sensitive_seat(self):
        employee = self._employee(2, self.weak_manager)
        response = self._raise(self.weak_manager, employee, self.payroll_seat)
        self.assertEqual(response.status_code, 403)
        self.assertIn('sensitive permissions', response.json()['message'])
        self.assertFalse(PAR.objects.filter(employee=employee).exists())

    def test_an_hr_approver_without_authority_cannot_approve_and_the_request_stays_pending(self):
        employee = self._employee(3, self.strong_manager)
        request_id = self._raise(self.strong_manager, employee, self.payroll_seat).json()['data']['id']
        refused = self._approve(self.weak_hr, request_id)
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(PAR.objects.get(pk=request_id).status, PAR.STATUS_PENDING)
        self.assertFalse(Placement.objects.filter(employee=employee, position=self.payroll_seat).exists())
        approved = self._approve(self.strong_hr, request_id)  # an approver whose own seat holds the permissions may
        self.assertEqual(approved.status_code, 200, approved.json())
        self.assertTrue(Placement.objects.filter(employee=employee, position=self.payroll_seat).exists())

    def test_full_access_raiser_and_approver_may_administer_a_sensitive_seat(self):
        employee = self._employee(4, self.admin_manager)
        raised = self._raise(self.admin_manager, employee, self.payroll_seat)
        self.assertEqual(raised.status_code, 201, raised.json())
        self.assertEqual(self._approve(self.admin_hr, raised.json()['data']['id']).status_code, 200)
        self.assertTrue(Placement.objects.filter(employee=employee, position=self.payroll_seat).exists())

    def test_the_application_step_re_checks_the_approver_even_if_a_weak_approver_was_recorded(self):
        employee = self._employee(5, self.strong_manager)
        request = PAR.objects.get(pk=self._raise(self.strong_manager, employee, self.payroll_seat).json()['data']['id'])
        steps = list(request.steps)
        for step in steps:
            step.update(status='approved', decided_by_id=str(self.weak_hr.id) if step['key'] == 'hr' else step.get('decided_by_id'))
        request.steps, request.current_step = steps, len(steps)
        request.save()
        _apply(request)  # what decide() calls after the last approval
        request.refresh_from_db()
        self.assertEqual(request.status, PAR.STATUS_FAILED)
        self.assertIn('sensitive permissions', request.apply_error)
        self.assertFalse(Placement.objects.filter(employee=employee, position=self.payroll_seat).exists())


class EmploymentActionEngineTests(_ActionFixtures):
    def setUp(self):
        super().setUp()
        self.action_type = ActionType.objects.create(code='GUARD_PROMOTION', name='Guard promotion', category='movement', effects=[{'handler': 'set_placement'}])
        self.employee = self._employee(6, self.weak_manager)

    def _action(self, position: Position, created_by=None, applied_by=None) -> EmploymentAction:
        return EmploymentAction.objects.create(
            employee=self.employee, action_type=self.action_type, effective_date=datetime.date.today(),
            payload={'position_id': str(position.pk)}, created_by=created_by, applied_by=applied_by,
        )

    def _holds(self, position: Position) -> bool:
        return Placement.objects.filter(employee=self.employee, position=position).exists()

    def test_an_everyday_action_applies(self):
        apply_employment_action(self._action(self.ordinary, created_by=self.weak_hr, applied_by=self.weak_hr))
        self.assertTrue(self._holds(self.ordinary))

    def test_an_action_created_by_someone_without_authority_is_refused_at_application(self):
        with self.assertRaises(ActionConflictError):
            apply_employment_action(self._action(self.payroll_seat, created_by=self.weak_hr))
        self.assertFalse(self._holds(self.payroll_seat))

    def test_an_action_applied_by_someone_without_authority_is_refused_even_if_the_creator_had_it(self):
        with self.assertRaises(ActionConflictError):
            apply_employment_action(self._action(self.payroll_seat, created_by=self.strong_hr, applied_by=self.weak_hr))
        self.assertFalse(self._holds(self.payroll_seat))

    def test_an_action_with_nobody_on_record_applies_on_an_everyday_seat_but_never_on_a_sensitive_one(self):
        apply_employment_action(self._action(self.ordinary))  # existing behaviour: a system-made action on an everyday seat
        self.assertTrue(self._holds(self.ordinary))
        with self.assertRaises(ActionConflictError) as refused:
            apply_employment_action(self._action(self.payroll_seat))
        self.assertIn('no recorded creator or applier', str(refused.exception))
        self.assertFalse(self._holds(self.payroll_seat))

    def test_an_action_with_nobody_on_record_cannot_fill_a_full_access_or_branch_seat_either(self):
        top = _seat(self.unit, 'Backup Administrator', ['settings.edit'])
        branch = _seat(self.unit, 'Branch Lead', ['leave.approve'])
        Position.objects.filter(pk=branch.pk).update(can_manage_branch=True)
        for seat in (top, Position.objects.get(pk=branch.pk)):
            with self.assertRaises(ActionConflictError):
                apply_employment_action(self._action(seat))
        self.assertEqual(Placement.objects.filter(employee=self.employee).count(), 0)

    def test_creator_and_applier_with_authority_or_full_access_apply_it(self):
        apply_employment_action(self._action(self.payroll_seat, created_by=self.strong_hr, applied_by=self.admin_hr))
        self.assertTrue(self._holds(self.payroll_seat))


class EveryAssignmentCallSiteIsGuardedTests(TestCase):
    """A new door that calls assign_position() without a guard fails this test."""

    GUARDS = {'assignment_refusal', 'placement_refusal', '_check_position_authority'}
    EXEMPT = {('accounts/services_actions.py', 'reverse_employment_action'): 'restores the seat the person already held before the action'}
    SKIPPED_PARTS = {'migrations', 'management', 'tests'}

    def _functions_calling(self, name: str):
        apps_dir = Path(__file__).resolve().parents[1]
        for path in apps_dir.rglob('*.py'):
            relative = path.relative_to(apps_dir).as_posix()
            if self.SKIPPED_PARTS & set(path.parts) or path.name.startswith('tests') or relative == 'accounts/services_placement.py':
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    called = {call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, 'attr', '')
                              for call in ast.walk(node) if isinstance(call, ast.Call)}
                    if name in called:
                        yield relative, node.name, called

    def test_every_function_that_calls_assign_position_calls_a_guard_or_is_a_listed_exemption(self):
        unguarded = [(file, function) for file, function, called in self._functions_calling('assign_position')
                     if not (called & self.GUARDS) and (file, function) not in self.EXEMPT]
        self.assertEqual(unguarded, [], 'assign_position() called without a guard: add assignment_refusal() or a documented exemption')

    def test_the_known_doors_are_all_found_so_the_scan_cannot_pass_by_finding_nothing(self):
        found = {file for file, _function, _called in self._functions_calling('assign_position')}
        expected = {
            'accounts/views_hire_complete.py', 'accounts/views/employees_list.py', 'accounts/views/employees_detail.py',
            'accounts/views/bulk_import.py', 'accounts/views/onboarding_approval.py', 'accounts/views/org_structure.py',
            'accounts/services_actions.py',
        }
        self.assertTrue(expected <= found, expected - found)

    def test_the_exemptions_are_real_and_the_personnel_action_checks_are_in_place(self):
        calling = {(file, function) for file, function, _called in self._functions_calling('assign_position')}
        for exempt in self.EXEMPT:
            self.assertIn(exempt, calling, f'stale exemption {exempt}')
        checkers = {function for _file, function, _called in self._functions_calling('_check_position_authority')}
        self.assertEqual(checkers, {'raise_request', 'decide'})
