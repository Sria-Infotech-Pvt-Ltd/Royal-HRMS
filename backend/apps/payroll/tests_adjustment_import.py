"""
Payroll → Adjustments → Bulk Import: sample CSV / Excel, preview that saves
nothing, all-or-nothing confirmation, duplicate detection (in the file and
against saved adjustments), branch scope, and processed-month protection.
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
from apps.payroll.models import PayrollAdjustment, PayrollCycle
from apps.payroll.tests_salary_components import SalaryFixtureMixin, _login

URL = '/api/payroll/adjustments/bulk-import/?month=2026-01'
HEADER = 'Employee Code,Type,Label,Amount'


def _csv(*rows, header=HEADER):
    body = '\n'.join([header, *rows]) + '\n'
    return SimpleUploadedFile('adjustments.csv', body.encode(), content_type='text/csv')


class Fixture(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()

    def send(self, *rows, dry_run=False, client=None, url=URL, header=HEADER):
        body = {'file': _csv(*rows, header=header)}
        if dry_run:
            body['dry_run'] = 'true'
        return (client or self.api).post(url, body, format='multipart')

    def messages(self, resp):
        return {r['row']: r['message'] for r in resp.data['data']['rows']}


class SampleTests(Fixture):
    def test_sample_csv_and_excel(self):
        url = reverse('payroll-adjustment-import-sample')
        csv = self.api.get(url, {'format': 'csv'})
        self.assertEqual(csv.status_code, 200)
        self.assertTrue(csv.content.decode('utf-8-sig').startswith(HEADER))
        xlsx = self.api.get(url, {'format': 'xlsx'})
        self.assertEqual(xlsx.status_code, 200)
        self.assertIn('spreadsheetml', xlsx['Content-Type'])


class PreviewAndConfirmTests(Fixture):
    def test_preview_saves_nothing(self):
        resp = self.send('SCA,addition,Festival Bonus,5000', 'scb,Deduction,Advance,1500.50', dry_run=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['summary'], {'create': 2, 'error': 0, 'warnings': 0, 'total': 2})
        self.assertEqual(PayrollAdjustment.objects.count(), 0)

    def test_confirm_saves_all_and_audits(self):
        resp = self.send('SCA,addition,Festival Bonus,5000', 'SCB,arrear,March Arrear,"1,200"')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['imported'], 2)
        self.assertEqual(PayrollAdjustment.objects.filter(month=datetime.date(2026, 1, 1)).count(), 2)
        self.assertEqual(PayrollAdjustment.objects.get(employee=self.emp_b).amount, Decimal('1200.00'))
        self.assertTrue(AuditLog.objects.filter(action='payroll_adjustments_imported').exists())

    def test_one_bad_row_blocks_the_whole_file(self):
        resp = self.send('SCA,addition,Festival Bonus,5000', 'NOPE,addition,Bonus,100', 'SCB,bonus,X,abc')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(PayrollAdjustment.objects.count(), 0)
        msgs = self.messages(resp)
        self.assertIn('"NOPE" doesn\'t match any employee', msgs[3])
        self.assertIn('Type: must be addition, deduction or arrear', msgs[4])
        self.assertIn('Amount: "abc" is not a number', msgs[4])
        self.assertIn('Nothing was imported', resp.data['message'])

    def test_field_validation(self):
        resp = self.send(',addition,X,10', 'SCA,addition,,10', 'SCA,addition,Y,-5', 'SCA,addition,Z,1.234',
                         dry_run=True)
        msgs = self.messages(resp)
        self.assertIn('Employee Code: required', msgs[2])
        self.assertIn('Label: required', msgs[3])
        self.assertIn('must be more than 0', msgs[4])
        self.assertIn('at most 2 decimal places', msgs[5])

    def test_inactive_employee(self):
        self.emp_b.is_active = False
        self.emp_b.save(update_fields=['is_active'])
        self.assertIn('inactive', self.messages(self.send('SCB,addition,X,10', dry_run=True))[2])

    def test_bad_month_and_missing_column(self):
        self.assertEqual(self.send('SCA,addition,X,10', url='/api/payroll/adjustments/bulk-import/?month=2026-13')
                         .status_code, 400)
        resp = self.send('SCA,X,10', header='Employee Code,Label,Amount')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('"Type" column', resp.data['message'])


class DuplicateTests(Fixture):
    def test_same_row_twice_in_file(self):
        resp = self.send('SCA,addition,Festival Bonus,5000', 'SCA,Addition,festival bonus,5000.00', dry_run=True)
        self.assertIn('Same adjustment as row 2', self.messages(resp)[3])

    def test_uploading_the_same_file_again_is_refused(self):
        self.assertEqual(self.send('SCA,addition,Festival Bonus,5000').status_code, 201)
        resp = self.send('SCA,addition,Festival Bonus,5000')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already saved for January 2026', self.messages(resp)[2])
        self.assertEqual(PayrollAdjustment.objects.count(), 1)

    def test_same_label_different_amount_is_allowed(self):
        resp = self.send('SCA,addition,Overtime,500', 'SCA,addition,Overtime,750', dry_run=True)
        self.assertEqual(resp.data['data']['summary']['create'], 2)


class ProcessedMonthTests(Fixture):
    def test_paid_or_sent_month_is_refused(self):
        for status in (PayrollCycle.STATUS_PAID, PayrollCycle.STATUS_QUERY_WINDOW_OPEN):
            PayrollCycle.objects.all().delete()
            self.cycle(1, status=status)
            resp = self.send('SCA,addition,X,10', dry_run=True)
            self.assertIn('already sent to employees or paid', self.messages(resp)[2], status)

    def test_calculated_month_is_accepted_with_warning(self):
        self.cycle(1, status=PayrollCycle.STATUS_PAYSLIPS_GENERATED)
        resp = self.send('SCA,addition,X,10', dry_run=True)
        self.assertEqual(resp.data['data']['summary']['warnings'], 1)
        self.assertIn('run the calculation again', self.messages(resp)[2])

    def test_cancelled_cycle_does_not_block(self):
        self.cycle(1, status=PayrollCycle.STATUS_CANCELLED)
        self.assertEqual(self.send('SCA,addition,X,10').status_code, 201)

    def test_other_branch_cycle_does_not_block(self):
        other = Branch.objects.create(branch_code='OTH', branch_name='OtherBranch', status=Branch.STATUS_ACTIVE,
                                      state=self.state, city=City.objects.first())
        cycle = self.cycle(1, status=PayrollCycle.STATUS_PAID)
        cycle.branch = other
        cycle.save(update_fields=['branch'])
        self.assertEqual(self.send('SCA,addition,X,10').status_code, 201)


class BranchScopeTests(Fixture):
    def test_branch_hr_cannot_import_for_another_branch(self):
        other = Branch.objects.create(branch_code='OTH2', branch_name='OtherBranch2', status=Branch.STATUS_ACTIVE,
                                      state=self.state, city=City.objects.first())
        make_user('other.emp@test.com', role=make_role('oth_emp'), employee_id='OTH1', full_name='Other Emp',
                  branch=other.branch_name)
        branch_hr = make_user('branch.hr@test.com', role=make_role('branch_hr', permission_codenames=[
            'payroll.view', 'payroll.edit']), employee_id='BHR', full_name='Branch HR', branch=self.branch.branch_name)
        client = APIClient()
        _login(client, branch_hr.email)
        resp = self.send('SCA,addition,X,10', 'OTH1,addition,X,10', dry_run=True, client=client)
        self.assertEqual(resp.data['data']['rows'][0]['status'], 'create')
        self.assertIn('doesn\'t match any employee you can manage', self.messages(resp)[3])

    def test_permission_required(self):
        viewer = make_user('viewer@test.com', role=make_role('pay_viewer', permission_codenames=['payroll.view']),
                           employee_id='VW1', full_name='Viewer', branch=self.branch.branch_name)
        client = APIClient()
        _login(client, viewer.email)
        self.assertEqual(self.send('SCA,addition,X,10', client=client).status_code, 403)


class AdjustmentBranchScopeTests(Fixture):
    """List / add / delete are limited to the user's branch unless they have
    company-wide payroll access (settings.edit)."""

    def setUp(self):
        super().setUp()
        other = Branch.objects.create(branch_code='SCOP', branch_name='ScopeOther', status=Branch.STATUS_ACTIVE,
                                      state=self.state, city=City.objects.first())
        self.other_emp = make_user('scope.other@test.com', role=make_role('scope_emp'), employee_id='SCO1',
                                   full_name='Other Emp', branch=other.branch_name)
        month = datetime.date(2026, 1, 1)
        self.own = PayrollAdjustment.objects.create(employee=self.emp_a, month=month, type='addition',
                                                    label='Own', amount=Decimal('100'))
        self.foreign = PayrollAdjustment.objects.create(employee=self.other_emp, month=month, type='deduction',
                                                        label='Foreign', amount=Decimal('900'))
        role = make_role('scope_bhr', permission_codenames=['payroll.view', 'payroll.edit'])
        self.branch_hr = make_user('scope.bhr@test.com', role=role, employee_id='SBHR', full_name='Branch HR',
                                   branch=self.branch.branch_name)
        self.bhr = APIClient()
        _login(self.bhr, self.branch_hr.email)

    def test_list_and_totals_only_own_branch(self):
        data = self.bhr.get('/api/payroll/adjustments/?month=2026-01').data['data']
        self.assertEqual([r['label'] for r in data['results']], ['Own'])
        self.assertEqual((Decimal(str(data['total_additions'])), Decimal(str(data['total_deductions']))),
                         (Decimal('100'), Decimal('0')))

    def test_company_wide_user_sees_all(self):
        data = self.api.get('/api/payroll/adjustments/?month=2026-01').data['data']
        self.assertEqual(sorted(r['label'] for r in data['results']), ['Foreign', 'Own'])

    def test_cannot_delete_other_branch(self):
        resp = self.bhr.delete(f'/api/payroll/adjustments/{self.foreign.pk}/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(PayrollAdjustment.objects.filter(pk=self.foreign.pk).exists())
        self.assertEqual(self.bhr.delete(f'/api/payroll/adjustments/{self.own.pk}/').status_code, 200)

    def test_cannot_add_for_other_branch(self):
        body = {'employee_code': 'SCO1', 'month': '2026-01', 'type': 'addition', 'label': 'X', 'amount': '10'}
        self.assertEqual(self.bhr.post('/api/payroll/adjustments/', body, format='json').status_code, 403)
        body['employee'] = str(self.other_emp.pk)
        del body['employee_code']
        self.assertEqual(self.bhr.post('/api/payroll/adjustments/', body, format='json').status_code, 403)
        body['employee'] = str(self.emp_a.pk)
        self.assertEqual(self.bhr.post('/api/payroll/adjustments/', body, format='json').status_code, 201)

    def test_user_without_branch_gets_clear_error(self):
        self.branch_hr.branch = ''
        self.branch_hr.save(update_fields=['branch'])
        resp = self.bhr.get('/api/payroll/adjustments/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not assigned to a branch', resp.data['message'])
