"""Moving several employees to seats in another org unit at once: each old seat turns vacant, and what cannot be moved is skipped with a reason."""
from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, OrgUnit, Placement, Position
from apps.accounts.services_placement import assign_position, current_placement

START = timezone.localdate() - timedelta(days=60)


class BulkMoveOrgUnitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.old_unit = OrgUnit.objects.create(name='Old Unit')
        self.new_unit = OrgUnit.objects.create(name='New Unit')
        self.hr = make_user('hr-move@test.com', role=make_role('hr_move', permission_codenames=['employees.edit', 'employees.view']))
        self.viewer = make_user('viewer-move@test.com', role=make_role('viewer_move', permission_codenames=['employees.view']))
        self.people, self.old_seats, self.new_seats = [], [], []
        for number in range(3):
            person = make_user(f'mover{number}@test.com', employee_id=f'3000000{number}', full_name=f'Mover {number}')
            old_seat = Position.objects.create(org_unit=self.old_unit, title=f'Analyst {number}', grade='L3')
            assign_position(person, old_seat, effective_from=START)
            self.people.append(person)
            self.old_seats.append(old_seat)
            self.new_seats.append(Position.objects.create(org_unit=self.new_unit, title=f'Analyst {number}', grade='L3'))

    def _post(self, moves, actor=None, **extra):
        client = APIClient()
        client.force_authenticate(user=actor or self.hr)
        return client.post(reverse('employee-bulk-move-org-unit'), {'moves': moves, **extra}, format='json')

    def _moves(self, count=3):
        return [{'employee_id': self.people[i].employee_id, 'position_id': str(self.new_seats[i].pk)} for i in range(count)]

    def test_everyone_moves_and_their_old_seats_turn_vacant(self):
        response = self._post(self._moves(), reason='Team restructure')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()['data']['moved']), 3)
        today = timezone.localdate()
        for i in range(3):
            self.assertIsNone(current_placement(self.old_seats[i], today), f'old seat {i} should be vacant')
            self.assertEqual(current_placement(self.new_seats[i], today).employee_id, self.people[i].pk)
        self.assertEqual(AuditLog.objects.filter(changes__via='bulk_move_org_unit').count(), 3)

    def test_a_taken_seat_a_duplicate_seat_and_an_unknown_employee_are_skipped_the_rest_still_move(self):
        other = make_user('occupant@test.com', employee_id='30000099')
        assign_position(other, self.new_seats[0], effective_from=START)
        moves = self._moves()
        moves[2]['position_id'] = str(self.new_seats[1].pk)   # the same seat twice in one request
        moves.append({'employee_id': 'NOPE', 'position_id': str(self.new_seats[2].pk)})
        data = self._post(moves).json()['data']
        reasons = {row['employee_id']: row['reason'] for row in data['skipped']}
        self.assertEqual([row['employee_id'] for row in data['moved']], [self.people[1].employee_id])
        self.assertIn('not vacant', reasons[self.people[0].employee_id])
        self.assertIn('already taken', reasons[self.people[2].employee_id])
        self.assertEqual(reasons['NOPE'], 'Employee not found.')
        self.assertIsNotNone(current_placement(self.old_seats[0], timezone.localdate()))   # skipped people stay where they are

    def test_moving_into_the_seat_already_held_is_skipped(self):
        data = self._post([{'employee_id': self.people[0].employee_id, 'position_id': str(self.old_seats[0].pk)}]).json()['data']
        self.assertEqual(data['skipped'][0]['reason'], 'Already in this position.')

    def test_a_future_date_keeps_the_old_seat_until_then(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.assertEqual(self._post(self._moves(1), effective_date=tomorrow.isoformat()).status_code, 200)
        self.assertEqual(current_placement(self.old_seats[0], timezone.localdate()).employee_id, self.people[0].pk)
        self.assertIsNone(current_placement(self.old_seats[0], tomorrow))
        self.assertEqual(Placement.objects.filter(employee=self.people[0]).count(), 2)

    def test_bad_requests_are_refused(self):
        self.assertEqual(self._post([]).status_code, 400)
        self.assertEqual(self._post(self._moves(1), effective_date='not-a-date').status_code, 400)
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self._post(self._moves(1), effective_date=yesterday).status_code, 400)
        self.assertEqual(self._post(self._moves(1), actor=self.viewer).status_code, 403)
        self.assertIsNone(current_placement(self.new_seats[0], timezone.localdate()))
