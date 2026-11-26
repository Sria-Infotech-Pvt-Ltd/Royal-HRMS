"""Perform Action > Org assignment can move one employee to a vacant position in another org unit: applied directly by HR, or
raised by the reporting manager and applied on HR approval. A seat someone else holds is never taken."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Position
from apps.accounts.models_personnel_action import PersonnelActionRequest as PAR
from apps.accounts.services_placement import assign_position, current_placement

TODAY = datetime.date.today()
BRANCH = 'Move Branch'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class OrgAssignmentMoveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.hr = make_user('oam_hr@test.com', full_name='HR', employee_id='OH1', branch=BRANCH, role=make_role(
            'oam_hr', permission_codenames=['employees.view', 'employees.edit', 'employees.approve']))
        self.manager = make_user('oam_mgr@test.com', full_name='Mgr', employee_id='OM1', branch=BRANCH, role=make_role(
            'oam_mgr', can_manage_team=True, permission_codenames=['employees.view', 'employees.raise_action']))
        self.employee = make_user('oam_emp@test.com', full_name='Emp', employee_id='OE1', branch=BRANCH, reporting_manager=self.manager)
        old_unit, self.new_unit = OrgUnit.objects.create(name='Old Unit'), OrgUnit.objects.create(name='New Unit')
        self.old_seat = Position.objects.create(org_unit=old_unit, title='Analyst', grade='L3')
        self.new_seat = Position.objects.create(org_unit=self.new_unit, title='Analyst', grade='L3')
        self.taken_seat = Position.objects.create(org_unit=self.new_unit, title='Lead', grade='L4')
        assign_position(self.employee, self.old_seat, effective_from=TODAY - datetime.timedelta(days=30))
        assign_position(make_user('oam_other@test.com', employee_id='OX1', branch=BRANCH), self.taken_seat, effective_from=TODAY - datetime.timedelta(days=30))

    def _direct(self, seat):
        return _api(self.hr).put(f'/api/employees/{self.employee.employee_id}/', {
            'position': str(seat.pk), 'position_must_be_vacant': True, 'effective_date': TODAY.isoformat(), 'reason': 'restructuring',
        }, format='json')

    def test_hr_moves_the_employee_into_a_vacant_seat_and_the_old_one_turns_vacant(self):
        self.assertEqual(self._direct(self.new_seat).status_code, 200)
        self.assertEqual(current_placement(self.new_seat, TODAY).employee_id, self.employee.pk)
        self.assertIsNone(current_placement(self.old_seat, TODAY))

    def test_a_seat_someone_else_holds_is_refused_and_nothing_changes(self):
        response = self._direct(self.taken_seat)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Choose a vacant position', response.json()['message'])
        self.assertEqual(current_placement(self.old_seat, TODAY).employee_id, self.employee.pk)

    def test_a_manager_raises_it_and_hr_approval_applies_the_move(self):
        response = _api(self.manager).post(f'/api/employees/{self.employee.employee_id}/action-requests/', {
            'action_type': 'org_assignment', 'reason': 'restructuring', 'effective_from': TODAY.isoformat(), 'position': str(self.new_seat.pk),
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(current_placement(self.new_seat, TODAY))   # nothing changes before approval
        request_id = response.json()['data']['id']
        self.assertEqual(_api(self.hr).post(f'/api/action-requests/{request_id}/approve/', {}, format='json').status_code, 200)
        self.assertEqual(PAR.objects.get(pk=request_id).status, PAR.STATUS_APPLIED)
        self.assertEqual(current_placement(self.new_seat, TODAY).employee_id, self.employee.pk)

    def test_raising_a_move_into_a_taken_seat_is_refused(self):
        response = _api(self.manager).post(f'/api/employees/{self.employee.employee_id}/action-requests/', {
            'action_type': 'org_assignment', 'reason': 'restructuring', 'effective_from': TODAY.isoformat(), 'position': str(self.taken_seat.pk),
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Choose a vacant position', response.json()['message'])
