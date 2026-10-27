"""
UAT-012 — locks in _resolve_separation_chain()'s existing, intentional
behavior: unlike apps.accounts.views.shared._auto_assign_managers (hire-time
reporting_manager assignment, which requires the resolved org-chart chief to
be in the EXACT SAME branch as the employee), the separation Manager-approval
stage resolves the nearest org-unit chief with NO branch-match requirement.

This is deliberate, not a bug — a separation request must always have
somewhere to route (see the function's own docstring on the HR fallback for
an unresolved stage) — but it is the reason a separation request's Approval
section can show a real approver name for an employee whose own recorded
`reporting_manager` is still null (QA read this as inconsistent data; the
actual fix was a frontend display clarification, not a change to this
resolver — see ApprovalSection.tsx's showOrgChartNote).
"""
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import OrgUnit, Placement, Position
from apps.hrms.models import SEP_STAGE_HR, SEP_STAGE_MANAGER
from apps.hrms.views.separation import _resolve_separation_chain


class SeparationChainOrgChartFallbackTests(TestCase):
    def setUp(self):
        self.unit = OrgUnit.objects.create(name='Platform Engineering')
        self.chief_position = Position.objects.create(org_unit=self.unit, title='Head of Platform', is_chief=True)
        self.member_position = Position.objects.create(org_unit=self.unit, title='Engineer')

    def test_resolves_chief_even_in_a_different_branch_than_the_employee(self):
        chief = make_user('sep-chief@test.com', employee_id='EMP-SEPC-01', branch='Hyderabad Office')
        Placement.objects.create(position=self.chief_position, employee=chief, effective_from='2024-01-01')

        employee = make_user('sep-employee@test.com', employee_id='EMP-SEPC-02', branch='Chennai Office', department='Engineering')
        Placement.objects.create(position=self.member_position, employee=employee, effective_from='2024-01-01')
        # Confirms the premise: hire-time auto-assign would have left this
        # null (different branch), yet the separation chain still finds the
        # chief — these are two different, both-correct resolutions.
        self.assertIsNone(employee.reporting_manager_id)

        chain = _resolve_separation_chain(employee)

        stages = dict(chain)
        self.assertEqual(stages[SEP_STAGE_MANAGER], chief)
        self.assertEqual(stages[SEP_STAGE_HR], employee.hr)

    def test_no_chief_anywhere_in_chain_leaves_manager_stage_unresolved(self):
        employee = make_user('sep-orphan@test.com', employee_id='EMP-SEPC-03', branch='Chennai Office', department='Engineering')
        Placement.objects.create(position=self.member_position, employee=employee, effective_from='2024-01-01')

        chain = _resolve_separation_chain(employee)

        stages = dict(chain)
        self.assertIsNone(stages[SEP_STAGE_MANAGER])
