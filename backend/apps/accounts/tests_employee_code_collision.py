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
        # Note: since the 2026-11 move to disjoint 8-digit numeric ranges per
        # employment type, EmployeeCodeSeries and EmployeeCodeSettings can no
        # longer collide with each other at all — their ID spaces don't
        # overlap (EMP00046 vs. 10000046). This test now only covers a
        # collision WITHIN one series' own range, which the same skip-forward
        # guard still protects against (e.g. a manually-assigned employee_id
        # landing exactly on next_sequence before the series catches up).
        series, _ = EmployeeCodeSeries.objects.get_or_create(
            employment_type='Permanent',
            defaults={'range_start': 10000000, 'range_end': 10000100, 'next_sequence': 10000046},
        )
        series.next_sequence = 10000046
        series.save(update_fields=['next_sequence'])
        make_user('already.has.the.numeric.one@test.com', role=make_role('code_collision_role3'), employee_id='10000046')
        emp_id = EmployeeCodeSeries.generate_employee_id_for_type('Permanent')
        self.assertNotEqual(emp_id, '10000046')
