"""
Bulk import when several seats share one org unit and title ("Software Developer" x 3 in the same unit).

Each row gets the FIRST vacant seat of its exact (org unit, title) pair, in a fixed order; a seat is never given to two rows,
nothing similar is substituted, and when the seats run out the rows that cannot be placed fail (the whole import then
creates nobody). The commit locks the candidate seats and checks again, so repeats and racing imports cannot double-book.

The real-thread race test at the bottom is OPT-IN (it flushes the whole test database, see its docstring).
"""
from __future__ import annotations

import os
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase

from apps.accounts import services_employee_import_commit as commit_module
from apps.accounts.factories import make_user
from apps.accounts.models import AuditLog, OrgUnit, Permission, Placement, Position, PositionPermission, User
from apps.accounts.services_employee_import import file_sha256
from apps.accounts.services_employee_import_commit import ImportRejected, commit_import
from apps.accounts.tests_employee_bulk_import import INVITE, _ImportCase, _workbook
from apps.accounts.tests_employee_scope import make_branch

TITLE = 'Software Developer'


def _seat(unit, title=TITLE, **fields) -> Position:
    """A seat exactly as the approved master-data change creates them: blank grade, no permissions, no flags."""
    return Position.objects.create(org_unit=unit, title=title, grade='', **fields)


class SharedTitleTests(_ImportCase):
    def setUp(self):
        super().setUp()
        self.shared = [_seat(self.unit) for _ in range(3)]          # oldest first: this is the allocation order

    def rows(self, count, **overrides):
        return [self.row(n, position=TITLE, **overrides) for n in range(1, count + 1)]

    def errors(self, rows, user=None):
        data = self.preview(user or self.hr, rows).json()['data']
        return [' '.join(r['errors']) for r in data['rows']], data

    def seats_held(self):
        return {p.employee.email: p.position_id for p in Placement.objects.filter(position__title=TITLE, effective_to__isnull=True).select_related('employee')}

    def test_rows_sharing_a_title_each_get_their_own_seat_in_order(self):
        errors, data = self.errors(self.rows(3))
        self.assertEqual(errors, ['', '', ''])
        self.assertTrue(data['can_import'])
        with mock.patch(INVITE):
            self.assertEqual(self.commit(self.hr, self.rows(3)).status_code, 201)
        held = self.seats_held()
        self.assertEqual([held[f'asha{n}@import.test'] for n in (1, 2, 3)], [seat.pk for seat in self.shared])
        self.assertEqual(len(set(held.values())), 3)                                  # no seat has two people
        for n in (1, 2, 3):
            self.assertEqual(User.objects.get(email=f'asha{n}@import.test').designation, TITLE)   # the original designation, unchanged

    def test_blank_grade_seats_work_end_to_end(self):
        with mock.patch(INVITE):
            self.assertEqual(self.commit(self.hr, self.rows(1)).status_code, 201)
        user = User.objects.get(email='asha1@import.test')
        self.assertEqual(user.designation, TITLE)
        self.assertEqual(Position.objects.get(pk=self.shared[0].pk).grade, '')

    def test_not_enough_seats_fails_the_extra_rows_and_creates_nobody(self):
        errors, data = self.errors(self.rows(4))
        self.assertEqual(errors[:3], ['', '', ''])
        self.assertIn(f'No vacant "{TITLE}" position is left in org unit "Import Unit"', errors[3])
        self.assertFalse(data['can_import'])
        before = User.objects.count()
        response = self.commit(self.hr, self.rows(4))
        self.assertEqual((response.status_code, User.objects.count()), (400, before))
        self.assertFalse(Placement.objects.filter(position__in=self.shared).exists())

    def test_occupied_seats_are_skipped(self):
        holder = make_user('holder2@test.com', employee_id='IH901', branch=self.hyd.branch_name)
        Placement.objects.create(position=self.shared[0], employee=holder, effective_from='2020-01-01')
        errors, _data = self.errors(self.rows(3))
        self.assertEqual(errors[:2], ['', ''])
        self.assertIn('No vacant', errors[2])                                           # 3 seats, 1 occupied: only 2 free
        with mock.patch(INVITE):
            self.assertEqual(self.commit(self.hr, self.rows(2)).status_code, 201)
        self.assertEqual(set(self.seats_held().values()) - {self.shared[0].pk}, {self.shared[1].pk, self.shared[2].pk})

    def test_inactive_seats_are_not_used(self):
        Position.objects.filter(pk=self.shared[0].pk).update(is_active=False)
        errors, _data = self.errors(self.rows(3))
        self.assertEqual(errors[:2], ['', ''])
        self.assertIn('No vacant', errors[2])

    def test_matching_is_exact_on_org_unit_and_title(self):
        other_unit = OrgUnit.objects.create(name='Other Unit')
        _seat(other_unit)                                                                # same title, different unit: never used
        rows = [self.row(1, position=TITLE.lower() + '  '),                              # case / spaces are tolerated
                self.row(2, position='Software Developer Trainee'),                      # a similar title is NOT substituted
                self.row(3, position=TITLE, org_unit='Other Unit')]
        errors, _data = self.errors(rows)
        self.assertEqual(errors[0], '')
        self.assertIn('No active position "Software Developer Trainee"', errors[1])
        self.assertEqual(errors[2], '')
        with mock.patch(INVITE):
            self.assertEqual(self.commit(self.hr, [rows[0], rows[2]]).status_code, 201)
        self.assertEqual(Placement.objects.get(employee__email='asha3@import.test').position.org_unit.name, 'Other Unit')
        self.assertEqual(Placement.objects.get(employee__email='asha1@import.test').position.org_unit_id, self.unit.pk)

    def test_a_full_access_seat_among_the_candidates_is_skipped_and_never_filled(self):
        PositionPermission.objects.create(position=self.shared[0], permission=Permission.objects.get_or_create(
            codename='settings.edit', defaults={'module': 'settings', 'action': 'edit'})[0])
        errors, _data = self.errors(self.rows(3))
        self.assertEqual(errors[:2], ['', ''])                                           # seats 2 and 3 are used, seat 1 is refused
        self.assertIn('No vacant', errors[2]) if 'full access' not in errors[2] else self.assertIn('full access', errors[2])
        with mock.patch(INVITE):
            self.assertEqual(self.commit(self.hr, self.rows(2)).status_code, 201)
        self.assertNotIn(self.shared[0].pk, self.seats_held().values())

    def test_committing_the_same_batch_again_creates_nobody_twice(self):
        content, batch = _workbook(self.rows(2)), str(uuid.uuid4())
        with mock.patch(INVITE):
            first = self.commit(self.hr, None, batch=batch, content=content)
            again = self.commit(self.hr, None, batch=batch, content=content)
        self.assertEqual((first.status_code, again.status_code), (201, 200))            # the retry is answered 200 with the earlier result
        self.assertTrue(again.json()['data']['already_committed'])
        self.assertEqual(User.objects.filter(email__endswith='@import.test').count(), 2)
        self.assertEqual(Placement.objects.filter(position__in=self.shared).count(), 2)
        self.assertEqual(AuditLog.objects.filter(action='employee_bulk_import_committed').count(), 1)

    def test_a_second_import_takes_the_next_free_seats_or_fails_whole(self):
        with mock.patch(INVITE):
            self.assertEqual(self.commit(self.hr, self.rows(2)).status_code, 201)       # seats 1 and 2
            later = [self.row(5, position=TITLE), self.row(6, position=TITLE)]          # only seat 3 is left for two people
            before = User.objects.count()
            self.assertEqual(self.commit(self.hr, later).status_code, 400)
            self.assertEqual(User.objects.count(), before)                               # all-or-nothing: neither was created
            self.assertEqual(self.commit(self.hr, later[:1]).status_code, 201)
        self.assertEqual(self.seats_held()['asha5@import.test'], self.shared[2].pk)

    def test_commit_checks_again_after_the_preview(self):
        rows = self.rows(3)
        self.assertTrue(self.preview(self.hr, rows).json()['data']['can_import'])
        taker = make_user('taker@test.com', employee_id='IH902', branch=self.hyd.branch_name)
        Placement.objects.create(position=self.shared[1], employee=taker, effective_from='2020-01-01')   # someone fills a seat meanwhile
        before = User.objects.count()
        self.assertEqual(self.commit(self.hr, rows).status_code, 400)
        self.assertEqual(User.objects.count(), before)

    def test_failure_midway_rolls_back_and_the_seats_stay_free(self):
        content = _workbook(self.rows(3))
        original, calls = commit_module._save_profile, {'n': 0}

        def explode(user, result):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('boom')
            original(user, result)
        before = (User.objects.count(), Placement.objects.count())
        with mock.patch.object(commit_module, '_save_profile', explode), mock.patch(INVITE), self.assertRaises(RuntimeError):
            commit_import(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))
        self.assertEqual((User.objects.count(), Placement.objects.count()), before)
        with mock.patch(INVITE):                                                          # the same file now succeeds: seats were never consumed
            self.assertEqual(self.commit(self.hr, self.rows(3)).status_code, 201)

    def test_database_rule_is_the_last_line_of_defence(self):
        """If a seat is double-booked despite the checks, the database refuses and the import ends cleanly with nothing created."""
        from django.core.exceptions import ValidationError

        content = _workbook(self.rows(2))
        with mock.patch.object(commit_module, 'assign_position', side_effect=ValidationError('overlap')), mock.patch(INVITE):
            with self.assertRaises(ImportRejected):
                commit_import(self.hr, content, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(content))
        self.assertFalse(User.objects.filter(email__endswith='@import.test').exists())


@unittest.skipUnless(
    os.environ.get('RUN_DB_FLUSHING_TESTS') == '1',
    'Flushes the whole test database (including migration-seeded rows). Opt in with RUN_DB_FLUSHING_TESTS=1 on a throwaway '
    'test database, run WITHOUT --keepdb so it is destroyed afterwards; see the module docstring.',
)
class ConcurrentImportTests(TransactionTestCase):
    """Two imports of the same designation, released at the same instant on real threads and real connections.

    Real threads need COMMITTED rows, hence TransactionTestCase, and that empties every table when the test ends (including the
    rows migrations seed), which is why this is opt-in:
        RUN_DB_FLUSHING_TESTS=1 python manage.py test apps.accounts.tests_employee_import_shared_titles.ConcurrentImportTests --noinput
    """

    def test_two_racing_imports_never_double_book_a_seat(self):
        branch = make_branch('RC-HYD', 'Race Hyderabad')
        unit = OrgUnit.objects.create(name='Race Unit')
        seats = [_seat(unit) for _ in range(3)]
        hr = make_user('race_hr@test.com', employee_id='RH001', is_superuser=True, branch=branch.branch_name)

        def content(tag):
            return _workbook([
                {'first_name': f'Racer{tag}{n}', 'last_name': 'Test', 'email': f'racer{tag}{n}@race.test', 'date_of_joining': '2026-11-10',
                 'branch': 'RC-HYD', 'org_unit': 'Race Unit', 'position': TITLE} for n in (1, 2)])
        barrier, outcomes = threading.Barrier(2), []

        def run(tag):
            payload = content(tag)
            try:
                barrier.wait(timeout=60)
                with mock.patch(INVITE):
                    commit_import(hr, payload, batch_id=str(uuid.uuid4()), expected_hash=file_sha256(payload))
                return 'created'
            except ImportRejected:
                return 'rejected'
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [future.result() for future in [pool.submit(run, tag) for tag in ('a', 'b')]]
        # 2 people + 2 people need 4 seats but only 3 exist: exactly one import wins whole, the other is refused whole.
        self.assertEqual(sorted(outcomes), ['created', 'rejected'])
        held = list(Placement.objects.filter(position__in=seats).values_list('position_id', flat=True))
        self.assertEqual((len(held), len(set(held))), (2, 2))
        self.assertEqual(User.objects.filter(email__endswith='@race.test').count(), 2)
