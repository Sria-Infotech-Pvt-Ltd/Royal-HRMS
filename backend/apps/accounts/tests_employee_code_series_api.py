"""
Tests for the per-worker-type employee ID series admin API
(EmployeeCodeSeriesListView/EmployeeCodeSeriesDetailView, backend/apps/
accounts/views/employees_actions.py) — lets an admin configure a separate
8-digit numeric ID range per employment type (Permanent -> 10000000-19999999,
Contract -> 20000000-29999999, ...), each with its own independent,
concurrency-safe counter (EmployeeCodeSeries.generate_employee_id_for_type).
"""
from __future__ import annotations

import threading

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeCodeSeries, EmployeeIdSeriesExhausted, User


class EmployeeCodeSeriesListViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin_role = make_role('code_series_admin', permission_codenames=['settings.edit'])
        self.admin = make_user('code-series-admin@test.com', role=self.admin_role)
        self.client.force_authenticate(user=self.admin)
        self.url = reverse('employee-code-series-list')

    def test_list_auto_creates_one_row_per_employment_type(self):
        EmployeeCodeSeries.objects.all().delete()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['data']
        returned_types = {r['employment_type'] for r in rows}
        expected_types = {value for value, _ in User.EMPLOYMENT_TYPE_CHOICES}
        self.assertEqual(returned_types, expected_types)
        self.assertEqual(EmployeeCodeSeries.objects.count(), len(expected_types))

    def test_list_is_idempotent_and_does_not_duplicate_rows(self):
        self.client.get(self.url)
        count_after_first = EmployeeCodeSeries.objects.count()
        self.client.get(self.url)
        self.assertEqual(EmployeeCodeSeries.objects.count(), count_after_first)

    def test_without_permission_403s(self):
        plain = make_user('code-series-plain@test.com', role=make_role('code_series_plain'))
        self.client.force_authenticate(user=plain)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)


class EmployeeCodeSeriesDetailViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin_role = make_role('code_series_admin2', permission_codenames=['settings.edit'])
        self.admin = make_user('code-series-admin2@test.com', role=self.admin_role)
        self.client.force_authenticate(user=self.admin)

    def test_updates_range_and_next_number_for_one_type_only(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Contract']),
            {'range_start': 20000000, 'range_end': 20000999, 'next_sequence': 20000007},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['range_start'], 20000000)
        self.assertEqual(resp.data['data']['range_end'], 20000999)
        self.assertEqual(resp.data['data']['next_sequence'], 20000007)

        other = EmployeeCodeSeries.objects.filter(employment_type='Permanent').first()
        self.assertTrue(other is None or other.range_start != 20000000)

        series = EmployeeCodeSeries.objects.get(employment_type='Contract')
        self.assertEqual(series.range_start, 20000000)
        self.assertEqual(series.range_end, 20000999)

        self.assertTrue(AuditLog.objects.filter(action='employee_code_series_updated', object_id='Contract').exists())

    def test_overlapping_ranges_rejected(self):
        self.client.put(
            reverse('employee-code-series-detail', args=['Permanent']),
            {'range_start': 10000000, 'range_end': 19999999, 'next_sequence': 10000001}, format='json',
        )
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Contract']),
            {'range_start': 15000000, 'range_end': 25000000, 'next_sequence': 15000001}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('range_start', resp.data.get('data', {}))

    def test_range_end_must_exceed_range_start(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Freelancer']),
            {'range_start': 40000000, 'range_end': 39999999, 'next_sequence': 40000001},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_next_sequence_must_fall_within_range(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Freelancer']),
            {'range_start': 40000000, 'range_end': 40000010, 'next_sequence': 50000000},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_cannot_shrink_range_below_already_issued_ids(self):
        User.objects.create(email='perm1@test.com', full_name='P1', employee_type='Permanent', employee_id='10005000')
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Permanent']),
            {'range_start': 10000000, 'range_end': 10001000, 'next_sequence': 10000001},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_unknown_employment_type_404s(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['NotARealType']),
            {'range_start': 90000000, 'range_end': 90999999, 'next_sequence': 90000001},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_generated_ids_use_the_configured_range_and_never_collide_across_types(self):
        self.client.put(
            reverse('employee-code-series-detail', args=['Permanent']),
            {'range_start': 10000000, 'range_end': 10000010, 'next_sequence': 10000001}, format='json',
        )
        self.client.put(
            reverse('employee-code-series-detail', args=['Contract']),
            {'range_start': 20000000, 'range_end': 20000010, 'next_sequence': 20000001}, format='json',
        )
        self.client.put(
            reverse('employee-code-series-detail', args=['Freelancer']),
            {'range_start': 40000000, 'range_end': 40000010, 'next_sequence': 40000001}, format='json',
        )

        emp_id = EmployeeCodeSeries.generate_employee_id_for_type('Permanent')
        con_id = EmployeeCodeSeries.generate_employee_id_for_type('Contract')
        frl_id = EmployeeCodeSeries.generate_employee_id_for_type('Freelancer')
        self.assertEqual(emp_id, '10000001')
        self.assertEqual(con_id, '20000001')
        self.assertEqual(frl_id, '40000001')

        # Each series increments independently.
        self.assertEqual(EmployeeCodeSeries.generate_employee_id_for_type('Permanent'), '10000002')
        self.assertEqual(EmployeeCodeSeries.generate_employee_id_for_type('Contract'), '20000002')

    def test_without_permission_403s(self):
        plain = make_user('code-series-plain2@test.com', role=make_role('code_series_plain2'))
        self.client.force_authenticate(user=plain)
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Permanent']),
            {'range_start': 10000000, 'range_end': 19999999, 'next_sequence': 10000001}, format='json',
        )
        self.assertEqual(resp.status_code, 403)


def _set_intern_series(range_start: int, range_end: int, next_sequence: int) -> EmployeeCodeSeries:
    """Migration 0155 already seeds a row for every employment type on a
    real/migrated DB — update it in place rather than create(), which would
    violate the one-row-per-type unique constraint."""
    series, _ = EmployeeCodeSeries.objects.update_or_create(
        employment_type='Intern',
        defaults={'range_start': range_start, 'range_end': range_end, 'next_sequence': next_sequence},
    )
    return series


class EmployeeCodeSeriesBoundaryTests(TestCase):
    """First/last number in a range, and range exhaustion blocking hires."""

    def test_first_id_issued_is_range_start_plus_one(self):
        _set_intern_series(50000000, 50000002, 50000001)
        self.assertEqual(EmployeeCodeSeries.generate_employee_id_for_type('Intern'), '50000001')

    def test_last_id_in_range_is_issuable(self):
        _set_intern_series(50000000, 50000001, 50000001)
        self.assertEqual(EmployeeCodeSeries.generate_employee_id_for_type('Intern'), '50000001')

    def test_exhausted_range_blocks_hiring_with_clear_error(self):
        _set_intern_series(50000000, 50000000, 50000001)
        with self.assertRaises(EmployeeIdSeriesExhausted) as ctx:
            EmployeeCodeSeries.generate_employee_id_for_type('Intern')
        self.assertIn('Intern', str(ctx.exception))
        self.assertIn('exhausted', str(ctx.exception).lower())

    def test_release_employee_id_only_takes_back_the_newest_number(self):
        series = _set_intern_series(50000000, 50000010, 50000001)
        emp_id = EmployeeCodeSeries.generate_employee_id_for_type('Intern')
        self.assertTrue(EmployeeCodeSeries.release_employee_id('Intern', emp_id))
        series.refresh_from_db()
        self.assertEqual(series.next_sequence, 50000001)

    def test_release_employee_id_refuses_a_non_newest_number(self):
        _set_intern_series(50000000, 50000010, 50000001)
        EmployeeCodeSeries.generate_employee_id_for_type('Intern')
        second = EmployeeCodeSeries.generate_employee_id_for_type('Intern')
        first_still_held = '50000001'
        self.assertFalse(EmployeeCodeSeries.release_employee_id('Intern', first_still_held))
        self.assertTrue(EmployeeCodeSeries.release_employee_id('Intern', second))


class EmployeeCodeSeriesConcurrencyTests(TransactionTestCase):
    """Two simultaneous hires of the same worker type must never receive the same ID."""

    def test_concurrent_generation_never_collides(self):
        _set_intern_series(50000000, 50000999, 50000001)

        results: list[str] = []
        errors: list[Exception] = []

        def worker():
            try:
                results.append(EmployeeCodeSeries.generate_employee_id_for_type('Intern'))
            except Exception as exc:  # pragma: no cover - surfaced via errors list
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 10)
        self.assertEqual(len(set(results)), 10, 'two concurrent hires received the same employee ID')
