"""
Salary setup import (Payroll → Salary Setup → Import salaries): sample CSV /
Excel, preview that saves nothing, row-specific validation, duplicates,
same-date replacement only when asked, revision history kept, shared
structures untouched, branch scope, and payroll using the imported amounts.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.branch.models import Branch, City
from apps.payroll.models import EmployeeSalaryConfig, SalaryComponent, SalaryStructure
from apps.payroll.tests_salary_components import SalaryFixtureMixin, _login
from apps.payroll.views.cycles import process_payroll_cycle

D = Decimal
HEADER = 'Employee Code,Employee Name,Structure Name,Effective From,Basic,HRA,Special Allowance,Annual CTC,PF Eligible'


def _csv(*rows, header=HEADER):
    return SimpleUploadedFile('salaries.csv', ('\n'.join([header, *rows]) + '\n').encode(), content_type='text/csv')


class Fixture(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()

    def send(self, *rows, dry_run=False, replace=False, client=None, header=HEADER):
        body = {'file': _csv(*rows, header=header)}
        if dry_run:
            body['dry_run'] = 'true'
        if replace:
            body['replace_same_date'] = 'true'
        return (client or self.api).post(reverse('salary-import'), body, format='multipart')

    def rows(self, resp):
        return {r['row']: r for r in resp.data['data']['rows']}

    def current(self, employee):
        return EmployeeSalaryConfig.objects.get(employee=employee, is_active=True)


A = 'SCA,Emp A,,2026-03-01,20000,8000,4000,,'
B = 'SCB,Emp B,Standard,2026-03-01,15000,6000,,,no'


class SampleTests(Fixture):
    def test_sample_uses_default_structure_components(self):
        url = reverse('salary-import-sample')
        csv = self.api.get(url, {'format': 'csv'})
        self.assertEqual(csv.status_code, 200)
        header = csv.content.decode('utf-8-sig').splitlines()[0]
        self.assertEqual(header, 'Employee Code,Employee Name,Structure Name,Effective From,Basic,HRA,'
                                 'Special Allowance,Annual CTC,PF Eligible,ESI Eligible,PT Applicable')
        xlsx = self.api.get(url, {'format': 'xlsx'})
        self.assertEqual(xlsx.status_code, 200)
        self.assertIn('spreadsheetml', xlsx['Content-Type'])


class PreviewAndSaveTests(Fixture):
    def test_preview_saves_nothing(self):
        resp = self.send(A, B, dry_run=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['summary'], {'create': 2, 'update': 0, 'no_change': 0, 'error': 0, 'total': 2})
        a = self.rows(resp)[2]
        self.assertEqual((a['structure'], a['annual_ctc'], a['monthly_earnings']), ('Standard', '384000.00', '32000.00'))
        self.assertEqual(EmployeeSalaryConfig.objects.count(), 0)

    def test_confirm_saves_revisions_with_fixed_amounts(self):
        resp = self.send(A, B)
        self.assertEqual(resp.status_code, 200, resp.data)
        a = self.current(self.emp_a)
        self.assertEqual((a.annual_ctc, a.effective_from), (D('384000.00'), datetime.date(2026, 3, 1)))
        comps = {c.name: (c.calculation_type, c.value, c.is_enabled) for c in a.components.all()}
        self.assertEqual(comps['Basic'], ('fixed', D('20000.0000'), True))
        self.assertEqual(comps['Special Allowance'], ('fixed', D('4000.0000'), True))
        b = self.current(self.emp_b)
        self.assertEqual(b.annual_ctc, D('252000.00'))
        self.assertFalse(b.components.get(name='Special Allowance').is_enabled)       # blank → switched off
        self.assertIs(b.pf_eligible, False)
        self.assertEqual(b.salary_structure.name, 'Standard')                          # named explicitly
        self.assertIsNone(a.salary_structure)                                          # resolved, like Assign CTC
        self.assertTrue(AuditLog.objects.filter(action='salary_revision_created',
                                                changes__source='salary_import').exists())

    def test_shared_structure_is_not_changed(self):
        before = list(SalaryComponent.objects.filter(structure__name='Standard')
                      .values_list('name', 'calculation_type', 'value', 'is_active'))
        self.send(A)
        after = list(SalaryComponent.objects.filter(structure__name='Standard')
                     .values_list('name', 'calculation_type', 'value', 'is_active'))
        self.assertEqual(before, after)

    def test_payroll_uses_imported_amounts(self):
        self.send('SCA,Emp A,,2026-01-01,20000,8000,4000,,')
        cycle = self.cycle(1)
        process_payroll_cycle(cycle)
        p = self.payslip(cycle, self.emp_a)
        self.assertEqual((p.basic, p.hra, p.special_allowance, p.gross_earnings),
                         (D('20000.00'), D('8000.00'), D('4000.00'), D('32000.00')))


class HistoryAndDuplicateTests(Fixture):
    def test_new_revision_keeps_history(self):
        self.assertEqual(self.assign(self.emp_a, effective='2026-01-01').status_code, 201)
        self.assertEqual(self.send(A).status_code, 200)
        revs = EmployeeSalaryConfig.objects.filter(employee=self.emp_a).order_by('effective_from')
        self.assertEqual([(r.effective_from.month, r.is_active) for r in revs], [(1, False), (3, True)])

    def test_same_date_needs_explicit_replace_and_identical_is_no_change(self):
        self.assertEqual(self.send(A).status_code, 200)
        again = self.send(A, dry_run=True)
        self.assertEqual(self.rows(again)[2]['status'], 'no_change')
        changed = 'SCA,Emp A,,2026-03-01,21000,8000,4000,,'
        refused = self.send(changed)
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Replace revisions with the same Effective From', self.rows(refused)[2]['message'])
        self.assertEqual(self.current(self.emp_a).annual_ctc, D('384000.00'))
        ok = self.send(changed, replace=True)
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(self.rows(ok)[2]['status'], 'updated')
        self.assertEqual(self.current(self.emp_a).annual_ctc, D('396000.00'))
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).count(), 2)

    def test_same_employee_twice_in_file(self):
        resp = self.send(A, 'sca,,,2026-04-01,1,1,1,,', dry_run=True)
        for r in (2, 3):
            self.assertIn('appears more than once', self.rows(resp)[r]['message'])

    def test_back_dated_revision_is_refused(self):
        self.assertEqual(self.send(A).status_code, 200)
        resp = self.send('SCA,,,2026-02-01,20000,8000,4000,,', dry_run=True)
        self.assertIn("can't be before the current revision", self.rows(resp)[2]['message'])


class ValidationTests(Fixture):
    def test_row_specific_errors_and_nothing_saved(self):
        resp = self.send(
            A,
            'NOPE,,,2026-03-01,1000,,,,',
            'SCB,,,03/2026,abc,-5,1.234,,maybe',
            'SCHR,,Ghost,2026-03-01,1000,,,,',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Nothing was saved', resp.data['message'])
        self.assertEqual(EmployeeSalaryConfig.objects.count(), 0)
        rows = self.rows(resp)
        self.assertIn('"NOPE" doesn\'t match any employee', rows[3]['message'])
        for text in ('is not a date', 'Basic: "abc" is not a number', 'HRA: cannot be negative',
                     'at most 2 decimal places', 'PF Eligible: must be yes, no or blank'):
            self.assertIn(text, rows[4]['message'])
        self.assertIn('Structure Name: "Ghost" not found', rows[5]['message'])

    def test_amount_errors_shown_even_when_employee_unknown(self):
        msg = self.rows(self.send('NOPE,,,2026-03-01,abc,,,,', dry_run=True))[2]['message']
        self.assertIn("doesn't match any employee", msg)
        self.assertIn('Basic: "abc" is not a number', msg)

    def test_basic_required_and_unknown_component_column(self):
        resp = self.send('SCA,,,2026-03-01,,8000,,,,500', dry_run=True,
                         header=HEADER + ',Performance Allowance')
        msg = self.rows(resp)[2]['message']
        self.assertIn('Basic: required', msg)
        self.assertIn('Column "Performance Allowance": not a component of salary structure "Standard"', msg)

    def test_blank_column_from_another_structure_is_ignored(self):
        resp = self.send('SCA,,,2026-03-01,20000,,,,,', dry_run=True, header=HEADER + ',Performance Allowance')
        self.assertEqual(self.rows(resp)[2]['status'], 'create')

    def test_annual_ctc_must_match_components(self):
        resp = self.send('SCA,,,2026-03-01,20000,8000,4000,"400,000",', dry_run=True)
        self.assertIn("Annual CTC: 400,000 doesn't match the components", self.rows(resp)[2]['message'])
        ok = self.send('SCA,,,2026-03-01,20000,8000,4000,384000,', dry_run=True)
        self.assertEqual(self.rows(ok)[2]['status'], 'create')

    def test_name_mismatch_is_a_note_not_an_error(self):
        resp = self.send('SCA,Someone Else,,2026-03-01,20000,,,,', dry_run=True)
        row = self.rows(resp)[2]
        self.assertEqual(row['status'], 'create')
        self.assertIn('differs from the employee record', row['message'])

    def test_missing_required_column(self):
        resp = self.send('SCA,20000', header='Employee Code,Basic')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('"Effective From" column', resp.data['message'])


class ScopeTests(Fixture):
    def test_branch_hr_only_their_branch(self):
        other = Branch.objects.create(branch_code='SIOT', branch_name='SalImpOther', status=Branch.STATUS_ACTIVE,
                                      state=self.state, city=City.objects.first())
        make_user('si.other@test.com', role=make_role('si_emp'), employee_id='SIO1', full_name='Other',
                  branch=other.branch_name)
        hr = make_user('si.bhr@test.com', role=make_role('si_bhr', permission_codenames=[
            'payroll.view', 'payroll.edit']), employee_id='SIBHR', full_name='Branch HR', branch=self.branch.branch_name)
        client = APIClient()
        _login(client, hr.email)
        resp = self.send(A, 'SIO1,,Standard,2026-03-01,1000,,,,', dry_run=True, client=client)
        self.assertEqual(self.rows(resp)[2]['status'], 'create')
        self.assertIn("doesn't match any employee you can manage", self.rows(resp)[3]['message'])

    def test_view_only_permission_refused(self):
        viewer = make_user('si.view@test.com', role=make_role('si_view', permission_codenames=['payroll.view']),
                           employee_id='SIV', full_name='Viewer', branch=self.branch.branch_name)
        client = APIClient()
        _login(client, viewer.email)
        self.assertEqual(self.send(A, client=client).status_code, 403)
        self.assertEqual(client.get(reverse('salary-import-sample')).status_code, 403)

    def test_structure_without_basic(self):
        SalaryStructure.objects.create(name='NoBasic')
        resp = self.send('SCA,,NoBasic,2026-03-01,,,,,', dry_run=True)
        self.assertIn('has no Basic component', self.rows(resp)[2]['message'])
