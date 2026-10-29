"""
Tests for the per-worker-type employee ID series admin API
(EmployeeCodeSeriesListView/EmployeeCodeSeriesDetailView, backend/apps/
accounts/views/employees_actions.py) — lets an admin configure a separate
auto-generated ID series (prefix/digit count/starting number) per
employment type (Permanent -> EMP, Contract -> CON, Freelancer -> FRL, ...),
each with its own independent, concurrency-safe counter
(EmployeeCodeSeries.generate_employee_id_for_type).
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeCodeSeries, User


class EmployeeCodeSeriesListViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin_role = make_role('code_series_admin', permission_codenames=['settings.edit'])
        self.admin = make_user('code-series-admin@test.com', role=self.admin_role)
        self.client.force_authenticate(user=self.admin)
        self.url = reverse('employee-code-series-list')

    def test_list_auto_creates_one_row_per_employment_type(self):
        # Migration 0155 already seeds one row per type on a real/migrated
        # DB — delete them first so this test genuinely exercises the view's
        # own on-demand auto-create path, not just the migration's seeding.
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

    def test_updates_prefix_padding_and_start_for_one_type_only(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Contract']),
            {'prefix': 'con', 'padding': 4, 'next_sequence': 7},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['prefix'], 'CON')
        self.assertEqual(resp.data['data']['padding'], 4)
        self.assertEqual(resp.data['data']['next_sequence'], 7)

        other = EmployeeCodeSeries.objects.filter(employment_type='Permanent').first()
        self.assertTrue(other is None or other.prefix != 'CON')

        series = EmployeeCodeSeries.objects.get(employment_type='Contract')
        self.assertEqual(series.prefix, 'CON')
        self.assertEqual(series.padding, 4)

        self.assertTrue(AuditLog.objects.filter(action='employee_code_series_updated', object_id='Contract').exists())

    def test_invalid_prefix_rejected(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Freelancer']),
            {'prefix': 'FR L!', 'padding': 5, 'next_sequence': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_unknown_employment_type_404s(self):
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['NotARealType']),
            {'prefix': 'ABC', 'padding': 5, 'next_sequence': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_generated_ids_use_the_configured_series_and_never_collide_across_types(self):
        self.client.put(
            reverse('employee-code-series-detail', args=['Permanent']),
            {'prefix': 'EMP', 'padding': 4, 'next_sequence': 1}, format='json',
        )
        self.client.put(
            reverse('employee-code-series-detail', args=['Contract']),
            {'prefix': 'CON', 'padding': 4, 'next_sequence': 1}, format='json',
        )
        self.client.put(
            reverse('employee-code-series-detail', args=['Freelancer']),
            {'prefix': 'FRL', 'padding': 4, 'next_sequence': 1}, format='json',
        )

        emp_id = EmployeeCodeSeries.generate_employee_id_for_type('Permanent')
        con_id = EmployeeCodeSeries.generate_employee_id_for_type('Contract')
        frl_id = EmployeeCodeSeries.generate_employee_id_for_type('Freelancer')
        self.assertEqual(emp_id, 'EMP0001')
        self.assertEqual(con_id, 'CON0001')
        self.assertEqual(frl_id, 'FRL0001')

        # Each series increments independently.
        self.assertEqual(EmployeeCodeSeries.generate_employee_id_for_type('Permanent'), 'EMP0002')
        self.assertEqual(EmployeeCodeSeries.generate_employee_id_for_type('Contract'), 'CON0002')

    def test_without_permission_403s(self):
        plain = make_user('code-series-plain2@test.com', role=make_role('code_series_plain2'))
        self.client.force_authenticate(user=plain)
        resp = self.client.put(
            reverse('employee-code-series-detail', args=['Permanent']),
            {'prefix': 'EMP', 'padding': 5, 'next_sequence': 1}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
