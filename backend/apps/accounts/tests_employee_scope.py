"""
core.access.employee_in_scope / employees_in_scope — the rules every employee-data endpoint relies on:

  1. unusable actor (missing / unsaved / inactive) -> no
  2. superuser -> yes (settings.edit does NOT grant company-wide employee scope)
  3. seat with can_manage_team -> direct reports only, even if the seat also manages a branch
  4. same branch (branch_fk; legacy name only when an FK is null and both names are non-blank)
  5. anything else, including an actor with no branch -> no

build_world() is shared with tests_employee_scope_endpoints.py.
"""
from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.branch.models import Branch, City, State
from apps.recruitment.models import Candidate
from core.access import employee_in_scope, employees_in_scope

HR_PERMISSIONS = ['employees.view', 'employees.edit', 'onboarding.approve', 'audit.view']


def make_branch(code: str, name: str) -> Branch:
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.get_or_create(
        branch_code=code, defaults={'branch_name': name, 'state': state, 'city': city},
    )[0]


def build_world() -> SimpleNamespace:
    """Two branches and one user of every kind the scope rules distinguish. Every attribute is a freshly loaded User
    (a signal may fill branch_fk after create, so the in-memory objects are refreshed)."""
    world = SimpleNamespace()
    world.hyd = make_branch('SCP-HYD', 'Scope Hyderabad')
    world.blr = make_branch('SCP-BLR', 'Scope Bengaluru')
    hr = make_role('scope_hr', permission_codenames=HR_PERMISSIONS)
    team = make_role('scope_team', permission_codenames=HR_PERMISSIONS, can_manage_team=True)
    team_branch = make_role('scope_team_branch', permission_codenames=HR_PERMISSIONS, can_manage_team=True, can_manage_branch=True)
    settings_edit = make_role('scope_settings', permission_codenames=['settings.edit', *HR_PERMISSIONS])
    counter = iter(range(1, 100))

    def build(role=None, **extra) -> User:
        number = next(counter)
        return make_user(f'scope{number}@test.com', role=role, employee_id=f'SC{number:03d}', **extra)

    hyd, blr = world.hyd.branch_name, world.blr.branch_name
    world.root = build(is_superuser=True)
    world.hr_hyd, world.hr_blr, world.hr_none = build(hr, branch=hyd), build(hr, branch=blr), build(hr, branch='')
    world.settings_blr = build(settings_edit, branch=blr)
    world.inactive_hr = build(hr, branch=hyd, is_active=False)
    world.legacy_hr = build(hr, branch='Legacy Wing')  # no Branch row has this name -> branch_fk stays null
    world.mgr, world.mgr_branch, world.mgr_nobranch = build(team, branch=hyd), build(team_branch, branch=hyd), build(team, branch='')
    world.report, world.report_branch = build(branch=hyd, reporting_manager=world.mgr), build(branch=hyd, reporting_manager=world.mgr_branch)
    world.report_nobranch = build(branch=hyd, reporting_manager=world.mgr_nobranch)
    world.emp_hyd, world.emp_blr, world.emp_blank = build(branch=hyd), build(branch=blr), build(branch='')
    world.legacy_emp = build(branch='Legacy Wing')
    world.pending = build(branch='')  # onboarding candidate: no branch of its own yet
    Candidate.objects.create(name='Pending', email='pending@test.com', position_applied='Tester', branch=world.hyd, portal_user=world.pending)
    for name, value in vars(world).items():
        if isinstance(value, User):
            value.refresh_from_db()
    return world


class EmployeeInScopeRuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()

    def test_superuser_is_in_scope_for_everyone(self):
        for employee in (self.w.emp_hyd, self.w.emp_blr, self.w.emp_blank, self.w.pending):
            self.assertTrue(employee_in_scope(self.w.root, employee))

    def test_settings_edit_does_not_grant_company_wide_scope(self):
        self.assertTrue(employee_in_scope(self.w.settings_blr, self.w.emp_blr))
        self.assertFalse(employee_in_scope(self.w.settings_blr, self.w.emp_hyd))

    def test_unusable_actor_or_missing_employee_is_denied(self):
        self.assertFalse(employee_in_scope(self.w.inactive_hr, self.w.emp_hyd))
        self.assertFalse(employee_in_scope(None, self.w.emp_hyd))
        self.assertFalse(employee_in_scope(User(email='unsaved@test.com'), self.w.emp_hyd))
        self.assertFalse(employee_in_scope(self.w.root, None))

    def test_team_manager_is_limited_to_direct_reports(self):
        self.assertTrue(employee_in_scope(self.w.mgr, self.w.report))
        self.assertFalse(employee_in_scope(self.w.mgr, self.w.emp_hyd))  # same branch, not a report
        self.assertFalse(employee_in_scope(self.w.mgr, self.w.report_branch))  # someone else's report

    def test_team_flag_wins_over_branch_flag(self):
        self.assertTrue(employee_in_scope(self.w.mgr_branch, self.w.report_branch))
        self.assertFalse(employee_in_scope(self.w.mgr_branch, self.w.emp_hyd))

    def test_team_manager_needs_no_branch_for_direct_reports(self):
        self.assertTrue(employee_in_scope(self.w.mgr_nobranch, self.w.report_nobranch))
        self.assertFalse(employee_in_scope(self.w.mgr_nobranch, self.w.emp_blank))

    def test_branch_user_sees_only_their_branch(self):
        self.assertTrue(employee_in_scope(self.w.hr_hyd, self.w.emp_hyd))
        self.assertFalse(employee_in_scope(self.w.hr_hyd, self.w.emp_blr))
        self.assertFalse(employee_in_scope(self.w.hr_hyd, self.w.emp_blank))

    def test_actor_without_a_branch_is_denied_everywhere(self):
        for employee in (self.w.emp_hyd, self.w.emp_blr, self.w.emp_blank, self.w.pending):
            self.assertFalse(employee_in_scope(self.w.hr_none, employee))

    def test_legacy_name_fallback_only_when_an_fk_is_null(self):
        self.assertIsNone(self.w.legacy_hr.branch_fk_id)
        self.assertTrue(employee_in_scope(self.w.legacy_hr, self.w.legacy_emp))
        self.assertFalse(employee_in_scope(self.w.legacy_hr, self.w.emp_hyd))
        self.assertFalse(employee_in_scope(self.w.hr_hyd, self.w.legacy_emp))

    def test_pending_onboarding_user_follows_the_candidates_branch(self):
        self.assertTrue(employee_in_scope(self.w.hr_hyd, self.w.pending))
        self.assertFalse(employee_in_scope(self.w.hr_blr, self.w.pending))

    def test_queryset_form_agrees_with_the_function_for_every_actor_and_employee(self):
        everyone = list(User.objects.all())
        for actor in everyone:
            allowed = set(User.objects.filter(employees_in_scope(actor)).distinct().values_list('pk', flat=True))
            for employee in everyone:
                self.assertEqual(
                    employee_in_scope(actor, employee), employee.pk in allowed,
                    f'{actor.employee_id} -> {employee.employee_id}',
                )
