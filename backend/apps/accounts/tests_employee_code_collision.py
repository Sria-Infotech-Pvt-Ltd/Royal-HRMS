"""Regression test for a real production incident: EmployeeCodeSettings
(the old global counter — plain create/bulk-import/portal-conversion) and
EmployeeCodeSeries (the newer per-employment-type counter — Hire wizard)
share the same default prefix ('EMP') but increment completely
independently of each other, so they eventually generate the same
employee_id from two unrelated code paths — which is exactly what happened
(two real employees both ended up as "EMP00046", breaking every
_get_employee() lookup for that code with a MultipleObjectsReturned 500).

Both generators now skip forward past any sequence number already claimed
by a real User, regardless of how out of sync the two counters get with
each other.
"""
from __future__ import annotations

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeCodeSeries, EmployeeCodeSettings


class EmployeeCodeCollisionTests(TestCase):
    def setUp(self):
        # Force both counters to the exact same next value — the scenario
        # that actually caused the collision.
        cfg = EmployeeCodeSettings.get()
        cfg.next_sequence = 46
        cfg.save(update_fields=['next_sequence'])
        role = make_role('code_collision_role')
        # A real employee already holds the number both counters are about
        # to reach — simulates the seed_dummy_employees/bulk-import path
        # having already claimed it independently of the Hire wizard.
        make_user('already.has.it@test.com', role=role, employee_id='EMP00046')

    def test_global_generator_skips_an_already_claimed_id(self):
        emp_id = EmployeeCodeSettings.generate_employee_id('Test', 'User')
        self.assertNotEqual(emp_id, 'EMP00046')

    def test_per_type_series_skips_an_already_claimed_id(self):
        series, _ = EmployeeCodeSeries.objects.get_or_create(
            employment_type='Permanent',
            defaults={'prefix': 'EMP', 'padding': 5, 'next_sequence': 46},
        )
        series.next_sequence = 46
        series.save(update_fields=['next_sequence'])
        emp_id = EmployeeCodeSeries.generate_employee_id_for_type('Permanent')
        self.assertNotEqual(emp_id, 'EMP00046')

    def test_second_generator_skips_an_id_the_first_one_just_committed(self):
        # The actual incident this guards against: one path (e.g. the old
        # bulk-import/seed-data flow via EmployeeCodeSettings) already
        # created a real, saved User with a given ID before the OTHER path
        # (the Hire wizard's EmployeeCodeSeries) generates its own next
        # number — this is the case the guard can fully close, since the
        # first ID is a real, queryable User row by the time the second
        # generator runs. Two calls racing in the SAME instant, before
        # either has committed a User row yet, remain a narrower residual
        # race this fix doesn't fully close — flagged, not silently assumed
        # fixed.
        series, _ = EmployeeCodeSeries.objects.get_or_create(
            employment_type='Contract',
            defaults={'prefix': 'EMP', 'padding': 5, 'next_sequence': 46},
        )
        series.next_sequence = 46
        series.save(update_fields=['next_sequence'])

        from_global = EmployeeCodeSettings.generate_employee_id('A', 'B')
        make_user('holder.of.the.global.one@test.com', role=make_role('code_collision_role2'), employee_id=from_global)
        from_series = EmployeeCodeSeries.generate_employee_id_for_type('Contract')
        self.assertNotEqual(from_global, from_series)
