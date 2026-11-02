"""
Payslip enhancements: display settings (UAN/ESIC hidden / masked / full,
server-side), saved payslip copies (layout, itemised adjustments, employee
and company details), payslip layouts per company/branch, the payroll stamp,
audit entries for payroll configuration, employee statutory eligibility
(PF / ESI / PT opt-out, default = unchanged results), drafts hidden from
employees, and the salary structure / structure assignment imports.
"""
from __future__ import annotations

import datetime
import io
import json
from decimal import Decimal
from unittest import mock

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile
from apps.payroll.models import (
    EmployeePayslip, EmployeeSalaryConfig, PayrollAdjustment, PayrollSettings, SalaryComponent, SalaryStructure,
)
from apps.payroll.serializers import mask_statutory_number
from apps.payroll.tests_salary_components import _login, SalaryFixtureMixin
from apps.payroll.views.cycles import process_payroll_cycle

D = Decimal
UAN, ESIC = '123456789012', '9876543210'


def _csv(name, header, *rows):
    body = '\n'.join([header, *rows]) + '\n'
    return SimpleUploadedFile(name, body.encode(), content_type='text/csv')


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buf, format='PNG')
    return SimpleUploadedFile('stamp.png', buf.getvalue(), content_type='image/png')


class Fixture(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()
        EmployeeProfile.objects.update_or_create(user=self.emp_a, defaults={'uan_number': UAN, 'esi_number': ESIC})
        own = make_role('pse_own', permission_codenames=['payroll.view_own'])
        self.emp_a.role = own
        self.emp_a.save(update_fields=['role'])

    def client_for(self, user):
        c = APIClient()
        _login(c, user.email)
        return c

    def processed(self, ctc='600000', **assign_extra):
        self.assertEqual(self.assign(self.emp_a, ctc=ctc, **assign_extra).status_code, 201)
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        return jan, self.payslip(jan, self.emp_a)

    def detail(self, payslip, client=None):
        return (client or self.api).get(reverse('payslip-detail', kwargs={'pk': payslip.pk}))


class MaskingTests(Fixture):
    def test_mask_helper(self):
        self.assertEqual(mask_statutory_number(UAN, True, True), '********9012')
        self.assertEqual(mask_statutory_number(UAN, True, False), UAN)
        self.assertIsNone(mask_statutory_number(UAN, False, True))
        self.assertIsNone(mask_statutory_number('', True, True))

    def test_default_is_masked_and_full_number_never_sent(self):
        _, slip = self.processed()
        resp = self.detail(slip)
        self.assertEqual(resp.data['data']['uan_display'], '********9012')
        self.assertEqual(resp.data['data']['esic_display'], '******3210')
        body = json.dumps(resp.data, default=str)
        self.assertNotIn(UAN, body)
        self.assertNotIn(ESIC, body)

    def test_full_and_hidden(self):
        _, slip = self.processed()
        PayrollSettings.objects.update_or_create(defaults={'mask_uan': False, 'show_esic': False})
        data = self.detail(slip).data['data']
        self.assertEqual(data['uan_display'], UAN)
        self.assertIsNone(data['esic_display'])
        self.assertNotIn(ESIC, json.dumps(data, default=str))


class SnapshotTests(Fixture):
    def test_processing_saves_copies_amounts_unchanged(self):
        PayrollAdjustment.objects.create(employee=self.emp_a, month=datetime.date(2026, 1, 1), type='deduction',
                                         label='Shoes', amount=D('150'), created_by=self.hr)
        PayrollAdjustment.objects.create(employee=self.emp_a, month=datetime.date(2026, 1, 1), type='arrear',
                                         label='Arrear', amount=D('500'), created_by=self.hr)
        self.branch_config.payslip_template = 'wage_slip'
        self.branch_config.principal_employer_name = 'Client Site Ltd'
        self.branch_config.save()
        _, slip = self.processed()
        # Same figures as before this change (35000 gross; PF 1800, PT 200, LWF 10).
        self.assertEqual((slip.gross_earnings, slip.adjustments_earning, slip.adjustments_deduction),
                         (D('35000.00'), D('500.00'), D('150.00')))
        self.assertEqual(slip.net_pay, D('35000') + D('500') - (D('1800') + D('200') + D('10') + D('150')))
        self.assertEqual(slip.template, 'wage_slip')
        self.assertEqual({(i['label'], i['type'], i['amount']) for i in slip.adjustment_items},
                         {('Shoes', 'deduction', '150.00'), ('Arrear', 'arrear', '500.00')})
        self.assertEqual(slip.identity_snapshot['principal_employer_name'], 'Client Site Ltd')

    def test_issued_payslip_keeps_original_details(self):
        _, slip = self.processed()
        self.emp_a.full_name, self.emp_a.designation = 'Renamed Person', 'New Role'
        self.emp_a.save(update_fields=['full_name', 'designation'])
        data = self.detail(slip).data['data']
        self.assertEqual(data['employee_name'], 'Emp A')
        self.assertEqual(data['designation'], '')

    def test_old_payslip_falls_back_to_live_and_standard(self):
        _, slip = self.processed()
        EmployeePayslip.objects.filter(pk=slip.pk).update(identity_snapshot={}, template='')
        data = self.detail(slip).data['data']
        self.assertEqual((data['employee_name'], data['payslip_template']), ('Emp A', 'standard'))

    def test_company_template_used_without_branch_override(self):
        PayrollSettings.objects.update_or_create(defaults={'payslip_template': 'wage_slip'})
        _, slip = self.processed()
        self.assertEqual(slip.template, 'wage_slip')


class EmployeeVisibilityTests(Fixture):
    def test_drafts_hidden_from_employee(self):
        _, slip = self.processed()                               # processing leaves drafts
        emp = self.client_for(self.emp_a)
        self.assertEqual(emp.get(reverse('my-payslips')).data['data']['count'], 0)
        self.assertEqual(self.detail(slip, emp).status_code, 404)
        EmployeePayslip.objects.filter(pk=slip.pk).update(status='sent')
        self.assertEqual(emp.get(reverse('my-payslips')).data['data']['count'], 1)
        self.assertEqual(self.detail(slip, emp).status_code, 200)

    def test_own_payslip_needs_view_own(self):
        _, slip = self.processed()
        EmployeePayslip.objects.filter(pk=slip.pk).update(status='sent')
        self.emp_a.role = make_role('pse_noperm')
        self.emp_a.save(update_fields=['role'])
        self.assertEqual(self.detail(slip, self.client_for(self.emp_a)).status_code, 403)

    def test_other_employees_payslip_forbidden(self):
        _, slip = self.processed()
        EmployeePayslip.objects.filter(pk=slip.pk).update(status='sent')
        self.emp_b.role = self.emp_a.role
        self.emp_b.save(update_fields=['role'])
        self.assertEqual(self.detail(slip, self.client_for(self.emp_b)).status_code, 403)


class SettingsAndAuditTests(Fixture):
    def test_settings_fields_and_audit(self):
        url = reverse('payroll-settings')
        data = self.api.get(url).data['data']
        self.assertEqual((data['payslip_template'], data['mask_uan'], data['show_esic']), ('standard', True, True))
        resp = self.api.put(url, {'payslip_template': 'wage_slip', 'fixed_deduction_rows': [' Food ', 'Shoes']},
                            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['fixed_deduction_rows'], ['Food', 'Shoes'])
        log = AuditLog.objects.filter(action='payroll_settings_updated').latest('created_at')
        self.assertEqual(log.changes['payslip_template'], {'from': 'standard', 'to': 'wage_slip'})

    def test_fixed_rows_validation(self):
        url = reverse('payroll-settings')
        self.assertEqual(self.api.put(url, {'fixed_deduction_rows': ['Food', 'food']}, format='json').status_code, 400)
        self.assertEqual(self.api.put(url, {'fixed_deduction_rows': ['x' * 41]}, format='json').status_code, 400)

    def test_settings_need_payroll_edit(self):
        viewer = make_user('pse.viewer@test.com', role=make_role('pse_view', permission_codenames=['payroll.view']),
                           full_name='Viewer')
        resp = self.client_for(viewer).put(reverse('payroll-settings'), {'show_uan': False}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_branch_config_audit_and_client_name(self):
        url = reverse('branch-config-detail', kwargs={'pk': self.branch_config.pk})
        resp = self.api.put(url, {'principal_employer_name': '  Client  Site ', 'payslip_template': 'wage_slip'},
                            format='json')
        self.assertEqual(resp.data['data']['principal_employer_name'], 'Client Site')
        log = AuditLog.objects.filter(action='payroll_branch_config_updated').latest('created_at')
        self.assertEqual(log.changes['payslip_template'], {'from': '', 'to': 'wage_slip'})

    def test_stamp_upload_validated_and_audited(self):
        storage = InMemoryStorage()
        with mock.patch.object(PayrollSettings._meta.get_field('payslip_stamp'), 'storage', storage):
            url = reverse('payroll-settings-stamp')
            bad = SimpleUploadedFile('x.png', b'not an image', content_type='image/png')
            self.assertEqual(self.api.post(url, {'stamp': bad}, format='multipart').status_code, 400)
            resp = self.api.post(url, {'stamp': _png()}, format='multipart')
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertTrue(PayrollSettings.objects.first().payslip_stamp)
            self.assertTrue(AuditLog.objects.filter(action='payroll_stamp_updated').exists())
            self.assertEqual(self.api.delete(url).status_code, 200)
            self.assertFalse(PayrollSettings.objects.first().payslip_stamp)


class EligibilityTests(Fixture):
    """Only an explicit False switches a deduction off; None = unchanged."""

    def test_default_unchanged(self):
        _, slip = self.processed(ctc='240000')                   # 17000 gross: PF, ESI and PT apply
        self.assertEqual((slip.pf_employee, slip.esi_employee, slip.pt_deduction),
                         (D('960.00'), D('127.50'), D('200.00')))

    def test_opt_outs(self):
        _, slip = self.processed(ctc='240000', pf_eligible=False, esi_eligible=False, pt_applicable=False)
        self.assertEqual((slip.pf_employee, slip.pf_employer, slip.esi_employee, slip.esi_employer, slip.pt_deduction),
                         (D('0.00'),) * 5)
        self.assertEqual(slip.lwf_employee, D('10.00'))           # LWF has no employee flag

    def test_true_cannot_force_policy(self):
        self.branch_config.pf_applicable = False
        self.branch_config.save()
        _, slip = self.processed(ctc='240000', pf_eligible=True)
        self.assertEqual(slip.pf_employee, D('0.00'))

    def test_flags_carry_to_new_revision_and_edits_audited(self):
        self.assertEqual(self.assign(self.emp_a, pf_eligible=False).status_code, 201)
        self.assertEqual(self.assign(self.emp_a, ctc='700000', effective='2026-02-01').status_code, 201)
        current = EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=True)
        self.assertIs(current.pf_eligible, False)
        url = reverse('employee-salary-detail', kwargs={'pk': current.pk})
        self.assertEqual(self.api.put(url, {'pf_eligible': None}, format='json').status_code, 200)
        log = AuditLog.objects.get(action='payroll_eligibility_updated')
        self.assertEqual(log.changes['pf_eligible'], {'from': False, 'to': None})
        old = EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=False)
        resp = self.api.put(reverse('employee-salary-detail', kwargs={'pk': old.pk}), {'esi_eligible': False},
                            format='json')
        self.assertEqual(resp.status_code, 400)


STRUCT_HEADER = 'Structure Name,Description,Component,Type,Calculation,Value,Role,Taxable,Order'


class StructureImportTests(Fixture):
    url = 'salary-structure-import'

    def send(self, upload, dry_run=True, update=False, client=None):
        data = {'file': upload}
        if dry_run:
            data['dry_run'] = 'true'
        if update:
            data['update_existing'] = 'true'
        return (client or self.api).post(reverse(self.url), data, format='multipart')

    def test_preview_then_create(self):
        rows = ('Site,Site staff,Basic,earning,fixed,13325,basic,yes,1',
                'Site,,HRA,allowance,percentage_of_basic,10,,yes,2',
                'Site,,Uniform,deduction,fixed,100,other,no,3')
        preview = self.send(_csv('s.csv', STRUCT_HEADER, *rows))
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['data']['summary']['create'], 1)
        self.assertFalse(SalaryStructure.objects.filter(name='Site').exists())
        done = self.send(_csv('s.csv', STRUCT_HEADER, *rows), dry_run=False)
        self.assertEqual(done.data['data']['summary']['created'], 1)
        site = SalaryStructure.objects.get(name='Site')
        comps = {c.name: c for c in site.components.all()}
        self.assertEqual(comps['HRA'].role, 'hra')                  # blank role -> by name
        self.assertFalse(comps['Uniform'].is_taxable)
        self.assertTrue(AuditLog.objects.filter(action='salary_structure_imported', object_id=str(site.pk)).exists())

    def test_validation_errors_block_import(self):
        rows = ('Bad,,Basic,salary,fixed,100,basic,yes,1',          # bad type
                'NoBasic,,HRA,allowance,fixed,100,hra,yes,1',
                'Over,,Basic,earning,percentage_of_ctc,80,basic,yes,1',
                'Over,,Special,allowance,percentage_of_ctc,30,special_allowance,yes,2',
                'Dup,,Basic,earning,fixed,100,basic,yes,1',
                'Dup,,basic,earning,fixed,100,other,yes,2')
        plan = {p['name']: p for p in self.send(_csv('s.csv', STRUCT_HEADER, *rows)).data['data']['structures']}
        self.assertTrue(all(p['status'] == 'error' for p in plan.values()))
        self.assertIn('Type must be', plan['Bad']['errors'][0])
        self.assertIn('exactly one Basic', ' '.join(plan['NoBasic']['errors']))
        self.assertIn('more than 100%', ' '.join(plan['Over']['errors']))
        self.assertIn('more than once', ' '.join(plan['Dup']['errors']))
        resp = self.send(_csv('s.csv', STRUCT_HEADER, *rows), dry_run=False)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(SalaryStructure.objects.filter(name__in=['Bad', 'NoBasic', 'Over', 'Dup']).exists())

    def test_existing_name_needs_explicit_update(self):
        rows = ('Standard,,Basic,earning,percentage_of_ctc,45,basic,yes,1',
                'Standard,,Conveyance,allowance,fixed,1600,other,yes,2')
        plan = self.send(_csv('s.csv', STRUCT_HEADER, *rows)).data['data']['structures'][0]
        self.assertIn('already exists', plan['errors'][0])
        plan = self.send(_csv('s.csv', STRUCT_HEADER, *rows), update=True).data['data']['structures'][0]
        self.assertEqual(plan['status'], 'update')
        self.assertEqual(plan['changes'], {'added': ['Conveyance'], 'removed': ['HRA', 'Special Allowance'],
                                           'changed': ['Basic']})
        self.send(_csv('s.csv', STRUCT_HEADER, *rows), dry_run=False, update=True)
        active = set(self.standard.components.filter(is_active=True).values_list('name', flat=True))
        self.assertEqual(active, {'Basic', 'Conveyance'})
        self.basic.refresh_from_db()
        self.assertEqual(self.basic.value, D('45'))

    def test_update_never_touches_existing_revisions(self):
        self.assign(self.emp_a)
        cfg = EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=True)
        before = list(cfg.components.values_list('name', 'value'))
        rows = ('Standard,,Basic,earning,percentage_of_ctc,45,basic,yes,1',)
        self.send(_csv('s.csv', STRUCT_HEADER, *rows), dry_run=False, update=True)
        self.assertEqual(list(cfg.components.values_list('name', 'value')), before)

    def test_permissions_and_file_checks(self):
        viewer = make_user('pse.v2@test.com', role=make_role('pse_v2', permission_codenames=['payroll.view']),
                           full_name='V2')
        rows = ('Site,,Basic,earning,fixed,100,basic,yes,1',)
        self.assertEqual(self.send(_csv('s.csv', STRUCT_HEADER, *rows), client=self.client_for(viewer)).status_code, 403)
        creator = make_user('pse.c@test.com', role=make_role('pse_c', permission_codenames=['payroll.create']),
                            full_name='Creator')
        self.assertEqual(self.send(_csv('s.csv', STRUCT_HEADER, *rows), update=True,
                                   client=self.client_for(creator)).status_code, 403)
        self.assertEqual(self.send(_csv('s.csv', 'Structure Name,Component')).status_code, 400)
        self.assertEqual(self.send(SimpleUploadedFile('s.txt', b'x')).status_code, 400)

    def test_samples(self):
        for fmt in ('csv', 'xlsx'):
            resp = self.api.get(reverse('salary-structure-import-sample'), {'format': fmt})
            self.assertEqual(resp.status_code, 200)
        sample = self.api.get(reverse('salary-structure-import-sample'), {'format': 'csv'}).content
        resp = self.send(SimpleUploadedFile('sample.csv', sample, content_type='text/csv'))
        self.assertEqual(resp.data['data']['summary']['error'], 0, resp.data)


ASSIGN_HEADER = 'Employee ID,Structure Name,Effective From'


class AssignImportTests(Fixture):
    def setUp(self):
        super().setUp()
        self.site = SalaryStructure.objects.create(name='Site')
        SalaryComponent.objects.create(structure=self.site, name='Basic', component_type='earning',
                                       calculation_type='percentage_of_ctc', value=D('60'), role='basic', order=1)

    def send(self, upload, dry_run=True):
        data = {'file': upload}
        if dry_run:
            data['dry_run'] = 'true'
        return self.api.post(reverse('salary-structure-assign-import'), data, format='multipart')

    def test_preview_then_new_revision(self):
        self.assign(self.emp_a, pf_eligible=False)
        rows = ('SCA,site,2026-02-01', 'SCB,Site,2026-02-01', 'NOPE,Site,2026-02-01', 'SCA,Site,2026-03-01')
        plan = self.send(_csv('a.csv', ASSIGN_HEADER, *rows)).data['data']['rows']
        self.assertEqual([p['status'] for p in plan], ['error', 'error', 'error', 'error'])  # SCA duplicated
        rows = ('SCA,site,01/02/2026', 'SCB,Site,2026-02-01', 'NOPE,Site,2026-02-01')
        plan = {p['employee_id']: p for p in self.send(_csv('a.csv', ASSIGN_HEADER, *rows)).data['data']['rows']}
        self.assertEqual(plan['SCA']['status'], 'update')
        self.assertIn('No current salary', plan['SCB']['message'])
        self.assertEqual(plan['NOPE']['message'], 'Employee not found.')
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).count(), 1)

        done = self.send(_csv('a.csv', ASSIGN_HEADER, *rows), dry_run=False)
        self.assertEqual(done.data['data']['summary']['updated'], 1)
        current = EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=True)
        self.assertEqual((current.salary_structure, current.annual_ctc, current.effective_from),
                         (self.site, D('600000.00'), datetime.date(2026, 2, 1)))
        self.assertEqual(list(current.components.values_list('name', flat=True)), ['Basic'])
        self.assertIs(current.pf_eligible, False)                  # carried over
        self.assertTrue(AuditLog.objects.filter(action='salary_structure_assignment_import').exists())

    def test_branch_scope(self):
        branch_hr = make_user('pse.bhr@test.com', role=make_role('pse_bhr', permission_codenames=[
            'payroll.view', 'payroll.edit']), full_name='Branch HR', branch='Elsewhere')
        self.assign(self.emp_a)
        c = APIClient()
        _login(c, branch_hr.email)
        resp = c.post(reverse('salary-structure-assign-import'),
                      {'file': _csv('a.csv', ASSIGN_HEADER, 'SCA,Site,2026-02-01'), 'dry_run': 'true'},
                      format='multipart')
        self.assertEqual(resp.data['data']['rows'][0]['message'], 'Employee not found.')
