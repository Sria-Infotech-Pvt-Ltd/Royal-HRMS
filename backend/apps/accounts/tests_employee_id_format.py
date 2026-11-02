"""
Per-company Employee ID format (EmployeeCodeSettings.id_format).

date_initials (default, unchanged):   prefix + DDMM + first + last initial  -> RSS0308TG
first_date_last (chosen per company): prefix + first initial + DDMM + last initial -> RIST0308G

New-employee generation and convert_employee_ids share build_base_id, so
converted and newly created ids can't differ; --revert puts the previous
prefix and format back. A company that never chooses keeps the old format.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.management.commands.convert_employee_ids import Candidate, Command, plan_conversion
from apps.accounts.models import AuditLog, EmployeeCodeSettings, User
from apps.accounts.tests import _login
from apps.tenants.models import Client
from config.test_runner import TEST_COMPANY_CODE

FIRST_DATE_LAST = EmployeeCodeSettings.FORMAT_FIRST_DATE_LAST
DATE_INITIALS = EmployeeCodeSettings.FORMAT_DATE_INITIALS


def _settings(prefix, id_format=DATE_INITIALS):
    EmployeeCodeSettings.objects.update_or_create(
        pk=1, defaults={'prefix': prefix, 'id_format': id_format, 'padding': 5, 'next_sequence': 1},
    )


class GenerationFormatTests(TestCase):
    def gen(self, first, last, doj=date(2026, 8, 3)):
        return EmployeeCodeSettings.generate_employee_id(first_name=first, last_name=last, date_of_joining=doj)

    def test_default_format_is_unchanged(self):
        EmployeeCodeSettings.objects.filter(pk=1).delete()
        self.assertEqual(EmployeeCodeSettings.get().id_format, DATE_INITIALS)
        _settings('RSS')
        self.assertEqual(self.gen('Teerdaveni', 'Gedela'), 'RSS0308TG')

    def test_first_date_last(self):
        _settings('RIS', FIRST_DATE_LAST)
        self.assertEqual(self.gen('Teerdaveni', 'Gedela'), 'RIST0308G')
        self.assertEqual(self.gen('Mary Jane', 'Smith', date(2026, 12, 25)), 'RISM2512S')   # middle name ignored
        self.assertEqual(self.gen('Madonna', ''), 'RISM0308M')                              # one-word name

    def test_first_date_last_collision_gets_suffix(self):
        _settings('RIS', FIRST_DATE_LAST)
        make_user('taken@test.com', role=make_role('fmt_taken'), employee_id='RIST0308G', full_name='Taken')
        self.assertEqual(self.gen('Tara', 'Gupta'), 'RIST0308G2')

    def test_string_date_accepted(self):
        _settings('RIS', FIRST_DATE_LAST)
        self.assertEqual(self.gen('Ravi', 'Kumar', '2026-09-15'), 'RISR1509K')


class SettingsApiTests(TestCase):
    def setUp(self):
        _settings('RSS')
        admin = make_user('fmt.admin@test.com', role=make_role('fmt_admin', permission_codenames=['settings.edit']),
                          full_name='Fmt Admin')
        self.client_api = APIClient()
        _login(self.client_api, admin.email)
        self.url = reverse('employee-code-settings')

    def put(self, data):
        return self.client_api.put(self.url, data, format='json')

    def test_get_returns_format(self):
        data = self.client_api.get(self.url).data['data']
        self.assertEqual(data['id_format'], DATE_INITIALS)

    def test_change_format_is_saved_and_audited(self):
        resp = self.put({'prefix': 'ris', 'id_format': FIRST_DATE_LAST, 'padding': 5, 'next_sequence': 1})
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = EmployeeCodeSettings.get()
        self.assertEqual((cfg.prefix, cfg.id_format), ('RIS', FIRST_DATE_LAST))
        log = AuditLog.objects.filter(action='employee_code_settings_updated').latest('created_at')
        self.assertEqual(log.changes['id_format'], FIRST_DATE_LAST)

    def test_save_without_format_keeps_it(self):
        _settings('RIS', FIRST_DATE_LAST)
        resp = self.put({'prefix': 'RIS', 'padding': 5, 'next_sequence': 1})    # older client
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(EmployeeCodeSettings.get().id_format, FIRST_DATE_LAST)

    def test_invalid_format_rejected(self):
        resp = self.put({'prefix': 'RIS', 'id_format': 'nope', 'padding': 5, 'next_sequence': 1})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(EmployeeCodeSettings.get().id_format, DATE_INITIALS)


class ConversionFormatTests(TestCase):
    def setUp(self):
        _settings('RSS')
        role = make_role('fmt_convert')
        self.t = make_user('fmt.t@test.com', role=role, employee_id='RSS0308TG',
                           full_name='Teerdaveni Gedela', date_of_joining=date(2026, 8, 3))
        self.r = make_user('fmt.r@test.com', role=role, employee_id='RSS1509RK',
                           full_name='Ravi Kumar', date_of_joining=date(2026, 9, 15))
        self.pending = make_user('fmt.p@test.com', role=role, employee_id='', full_name='Not Yet Approved')
        self.tmp = tempfile.mkdtemp()

    def run_cmd(self, **opts):
        # handle_tenant directly: call_command's TenantCommand wrapper closes
        # the DB connection this TestCase still needs (see tests.py).
        client = Client.objects.get(company_code=TEST_COMPANY_CODE)
        out = io.StringIO()
        defaults = {'prefix': None, 'id_format': None, 'skip': [], 'apply': False,
                    'mapping_file': None, 'revert': None}
        Command(stdout=out).handle_tenant(client, **(defaults | opts))
        return out.getvalue()

    def test_plan_reorders_without_collisions(self):
        cands = [Candidate(u.pk, u.employee_id, u.full_name, u.date_of_joining, u.date_joined, u.is_active)
                 for u in (self.t, self.r)]
        mapping, skipped, invalid = plan_conversion(cands, 'RIS', [], FIRST_DATE_LAST)
        self.assertEqual({m['old_id']: m['new_id'] for m in mapping},
                         {'RSS0308TG': 'RIST0308G', 'RSS1509RK': 'RISR1509K'})
        self.assertFalse(any(m['suffixed'] for m in mapping))

    def test_plan_default_format_unchanged(self):
        cands = [Candidate(self.t.pk, 'X1', self.t.full_name, self.t.date_of_joining, self.t.date_joined, True)]
        mapping, _, _ = plan_conversion(cands, 'RSS', [])
        self.assertEqual(mapping[0]['new_id'], 'RSS0308TG')

    def test_preview_writes_nothing(self):
        out = self.run_cmd(prefix='RIS', id_format=FIRST_DATE_LAST)
        self.assertIn('RIST0308G', out)
        self.t.refresh_from_db()
        self.assertEqual(self.t.employee_id, 'RSS0308TG')
        self.assertEqual(EmployeeCodeSettings.get().id_format, DATE_INITIALS)

    def test_apply_then_revert(self):
        path = os.path.join(self.tmp, 'map.csv')
        self.run_cmd(prefix='RIS', id_format=FIRST_DATE_LAST, apply=True, mapping_file=path)

        self.assertEqual(set(User.objects.exclude(employee_id='').values_list('employee_id', flat=True)),
                         {'RIST0308G', 'RISR1509K'})
        cfg = EmployeeCodeSettings.get()
        self.assertEqual((cfg.prefix, cfg.id_format), ('RIS', FIRST_DATE_LAST))
        log = AuditLog.objects.get(action='employee_id_bulk_conversion')
        self.assertEqual((log.changes['old_format'], log.changes['new_format']), (DATE_INITIALS, FIRST_DATE_LAST))
        with open(path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual({r['old_format'] for r in rows}, {DATE_INITIALS})

        # The employee still in onboarding gets the new format on approval.
        self.assertEqual(EmployeeCodeSettings.generate_employee_id('Not Yet', 'Approved', date(2026, 11, 2)),
                         'RISN0211A')

        self.run_cmd(revert=path, apply=True)
        self.t.refresh_from_db(); self.r.refresh_from_db()
        self.assertEqual((self.t.employee_id, self.r.employee_id), ('RSS0308TG', 'RSS1509RK'))
        cfg = EmployeeCodeSettings.get()
        self.assertEqual((cfg.prefix, cfg.id_format), ('RSS', DATE_INITIALS))

    def test_revert_of_old_csv_without_format_keeps_format(self):
        path = os.path.join(self.tmp, 'old.csv')
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['user_id', 'old_employee_id', 'new_employee_id', 'old_prefix', 'new_prefix'])
            w.writerow([self.t.pk, 'RIS00049', 'RSS0308TG', 'RIS', 'RSS'])
        _settings('RSS', FIRST_DATE_LAST)
        self.run_cmd(revert=path, apply=True)
        self.t.refresh_from_db()
        self.assertEqual(self.t.employee_id, 'RIS00049')
        cfg = EmployeeCodeSettings.get()
        self.assertEqual((cfg.prefix, cfg.id_format), ('RIS', FIRST_DATE_LAST))
