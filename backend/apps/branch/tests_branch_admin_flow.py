"""
End-to-end contract for the Company Code Admin section of the Edit Company Code form
(frontend/app/dashboard/branches/_components/branchAdminOptions.ts + BranchManagement.tsx).

Replays, against the real endpoints, the exact requests the form makes:
  save  : PUT  /employees/<code>/ {branch}  then  POST /org-structure/positions/<id>/placements/
  reload: GET  /org-structure/positions/?can_manage_branch=true  then  GET /employees/<holder_employee_id>/
and checks the admin is stored and found again by the same ids the frontend matches on.

Run with: python manage.py test apps.branch.tests_branch_admin_flow
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import OrgUnit, Position
from apps.branch.models import Branch, City, State


class CompanyCodeAdminEditFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='HYDT01', branch_name='Admin Flow Office', address='Plot 1, Hitech City',
            state=state, city=city, allowed_radius_meters=150,
        )
        self.actor = make_user('flow-actor@example.test', is_superuser=True, is_staff=True)
        # Probation / not-yet-onboarded, like most real staff: ?status=active would hide them.
        self.candidate = make_user(
            'flow-candidate@example.test', full_name='Flow Candidate', employee_id='90000001', account_activated_at=None,
        )
        unit = OrgUnit.objects.create(name='Admin Flow Unit')
        self.seat = Position.objects.create(org_unit=unit, title='Company Code Admin', grade='L3', can_manage_branch=True)
        self.client = APIClient()
        self.client.force_authenticate(self.actor)

    def _branch_wide_seats(self):
        resp = self.client.get('/api/org-structure/positions/', {'page_size': 500, 'can_manage_branch': 'true'})
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['data']['results']

    def _current_admin(self):
        """The frontend's findCurrentAdmin, over real responses."""
        for seat in self._branch_wide_seats():
            if not seat['holder_employee_id']:
                continue
            detail = self.client.get(f"/api/employees/{seat['holder_employee_id']}/")
            self.assertEqual(detail.status_code, 200, detail.data)
            employee = detail.data['data']
            if employee['uuid'] == seat['holder'] and employee['branch'] == self.branch.branch_name:
                return employee, seat
        return None

    def test_no_admin_before_assignment(self):
        self.assertIsNone(self._current_admin())

    def test_assignment_persists_and_edit_finds_it(self):
        code = self.candidate.employee_id
        move = self.client.put(f'/api/employees/{code}/', {'branch': self.branch.branch_name}, format='json')
        self.assertEqual(move.status_code, 200, move.data)
        place = self.client.post(
            f'/api/org-structure/positions/{self.seat.pk}/placements/',
            {'employee': str(self.candidate.pk), 'effective_from': timezone.localdate().isoformat()},
            format='json',
        )
        self.assertEqual(place.status_code, 200, place.data)

        # Persisted server-side.
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.branch, self.branch.branch_name)
        self.assertTrue(self.seat.placements.filter(employee=self.candidate, effective_to__isnull=True).exists())

        # Reopening Edit finds the same person, with every field the form shows.
        found = self._current_admin()
        self.assertIsNotNone(found)
        employee, seat = found
        self.assertEqual(seat['id'], str(self.seat.pk))
        self.assertEqual(seat['holder'], str(self.candidate.pk))
        self.assertEqual(employee['id'], code)
        self.assertEqual(employee['full_name'], 'Flow Candidate')
        self.assertEqual(employee['email'], 'flow-candidate@example.test')

    def test_holder_in_another_company_code_is_not_this_ones_admin(self):
        self.client.post(
            f'/api/org-structure/positions/{self.seat.pk}/placements/',
            {'employee': str(self.candidate.pk), 'effective_from': timezone.localdate().isoformat()},
            format='json',
        )
        self.assertIsNone(self._current_admin())  # candidate's branch is still blank
