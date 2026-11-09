"""
Payroll with rehires, extensions and several historical separations. The latest approved last working day of the CURRENT
employment is what counts: a separation from before a rehire is history, a later approved separation (an extension) replaces an
earlier one, and old separations never end new employment.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from apps.payroll.engine.legacy import _approved_last_working_days, _eligible_employees_qs, _proration_windows
from apps.payroll.tests_lifecycle_eligibility import CYCLE, _employee, _leave

D = datetime.date


class PayrollRehireAndMultipleSeparationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        e = _employee
        # Rehired: previous employment ended long ago, the new one began before the cycle.
        cls.rehired = e('rehired', 21, D(2026, 1, 1))
        _leave(cls.rehired, D(2025, 6, 30))
        # Rehired in the middle of the cycle.
        cls.rehired_mid = e('rehiredmid', 22, D(2026, 11, 10))
        _leave(cls.rehired_mid, D(2026, 6, 30))
        # Rehired mid-cycle and leaving again inside the same cycle.
        cls.rehired_leaves = e('rehiredleaves', 23, D(2026, 11, 10))
        _leave(cls.rehired_leaves, D(2026, 6, 30))
        _leave(cls.rehired_leaves, D(2026, 11, 20))
        # Extension: first last day before the cycle, extended to a day inside it.
        cls.extended = e('extended', 24, D(2020, 1, 1))
        _leave(cls.extended, D(2026, 10, 15))
        _leave(cls.extended, D(2026, 11, 20))
        # Extension that still ends before the cycle starts.
        cls.extended_past = e('extpast', 25, D(2020, 1, 1))
        _leave(cls.extended_past, D(2026, 9, 30))
        _leave(cls.extended_past, D(2026, 10, 20))
        # Several historical separations, none applying to the current employment.
        cls.history = e('history', 26, D(2024, 1, 1))
        _leave(cls.history, D(2020, 12, 31))
        _leave(cls.history, D(2022, 6, 30))
        # ... and the same history plus one that does apply, inside the cycle.
        cls.history_leaves = e('histleaves', 27, D(2024, 1, 1))
        _leave(cls.history_leaves, D(2020, 12, 31))
        _leave(cls.history_leaves, D(2022, 6, 30))
        _leave(cls.history_leaves, D(2026, 11, 14))
        # Documented edge: a joining date equal to the old last day leaves that separation applicable.
        cls.same_day = e('sameday', 28, D(2026, 1, 1))
        _leave(cls.same_day, D(2026, 1, 1))
        cls.everyone = [cls.rehired, cls.rehired_mid, cls.rehired_leaves, cls.extended, cls.extended_past, cls.history,
                        cls.history_leaves, cls.same_day]

    def test_who_is_paid(self):
        ids = set(_eligible_employees_qs(CYCLE).values_list('employee_id', flat=True))
        for employee in (self.rehired, self.rehired_mid, self.rehired_leaves, self.extended, self.history, self.history_leaves):
            self.assertIn(employee.employee_id, ids, employee.email)
        for employee in (self.extended_past, self.same_day):
            self.assertNotIn(employee.employee_id, ids, employee.email)

    def test_old_separations_are_not_used_for_the_last_working_day(self):
        found = _approved_last_working_days([e.id for e in self.everyone])
        self.assertNotIn(self.rehired.id, found)                                  # only history
        self.assertNotIn(self.rehired_mid.id, found)
        self.assertNotIn(self.history.id, found)                                  # several historical separations, none current
        self.assertEqual(found[self.rehired_leaves.id], D(2026, 11, 20))          # the current one, not the June one
        self.assertEqual(found[self.extended.id], D(2026, 11, 20))                # the extension replaces October
        self.assertEqual(found[self.history_leaves.id], D(2026, 11, 14))

    def test_windows_and_fractions(self):
        people = [self.rehired, self.rehired_mid, self.rehired_leaves, self.extended, self.history, self.history_leaves]
        windows, factors = _proration_windows(people, CYCLE, {}, _approved_last_working_days([p.id for p in people]))
        expected = {
            self.rehired: (D(2026, 11, 1), D(2026, 11, 30), 30),            # the old separation does not cut the new employment
            self.rehired_mid: (D(2026, 11, 10), D(2026, 11, 30), 21),       # rehired mid-cycle: from the new joining date
            self.rehired_leaves: (D(2026, 11, 10), D(2026, 11, 20), 11),    # ... until the new last working day
            self.extended: (D(2026, 11, 1), D(2026, 11, 20), 20),           # paid to the EXTENDED day, not the first one
            self.history: (D(2026, 11, 1), D(2026, 11, 30), 30),            # several old separations: ignored
            self.history_leaves: (D(2026, 11, 1), D(2026, 11, 14), 14),
        }
        for employee, (start, end, days) in expected.items():
            self.assertEqual(windows[employee.id], (start, end), employee.email)
            self.assertEqual(factors[employee.id], Decimal(days) / Decimal(30), employee.email)
