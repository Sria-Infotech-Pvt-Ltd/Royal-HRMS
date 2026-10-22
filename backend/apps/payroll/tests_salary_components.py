"""
Employee-wise salary components (Assign CTC) and how payroll uses them.

Figures are worked out by hand in each test so a change in payroll results
is caught, not just "it runs".
"""
from __future__ import annotations

import datetime
import io
from decimal import Decimal

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.payroll.models import (
    BranchPayrollConfig, EmployeePayslip, EmployeeSalaryComponent, EmployeeSalaryConfig, PayrollCycle,
    SalaryComponent, SalaryStructure, StatutoryConfig,
)
from apps.payroll.services_salary_components import ComponentSpec, calculate, parse_components, role_for_name
from apps.payroll.views.cycles import PayrollAlreadyProcessing, process_payroll_cycle
from config.test_runner import TEST_COMPANY_CODE

D = Decimal
PCT_CTC, PCT_BASIC, FIXED = (SalaryComponent.CALC_PCT_CTC, SalaryComponent.CALC_PCT_BASIC, SalaryComponent.CALC_FIXED)
EARN, ALLOW, DED = SalaryComponent.TYPE_EARNING, SalaryComponent.TYPE_ALLOWANCE, SalaryComponent.TYPE_DEDUCTION


def _login(client, email):
    resp = client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': email,
                                          'password': 'TestPass123!'}, format='json')
    assert resp.status_code == 200, resp.data


def _spec(name, calc, value, role='other', ctype=EARN, order=0, enabled=True):
    return ComponentSpec(name=name, component_type=ctype, calculation_type=calc, role=role,
                         value=D(str(value)), order=order, is_enabled=enabled)


def _row(name, calc, value, role='other', ctype=EARN, order=0, **extra):
    return {'name': name, 'component_type': ctype, 'calculation_type': calc, 'role': role,
            'value': str(value), 'order': order, **extra}


class SalaryFixtureMixin:
    """Branch with PF / ESI / PT / LWF configured, a default structure, HR and two employees."""

    def make_fixtures(self):
        cache.clear()
        self.state = State.objects.create(name='SalCompState', code='SC1')
        city = City.objects.create(name='SalCompCity', state=self.state)
        self.branch = Branch.objects.create(branch_code='SCBR', branch_name='SalCompBranch',
                                            status=Branch.STATUS_ACTIVE, state=self.state, city=city)
        StatutoryConfig.objects.create(
            state=self.state, pt_applicable=True,
            pt_slabs=[{'min': 0, 'max': 15000, 'amount': 0}, {'min': 15001, 'max': None, 'amount': 200}],
            esi_applicable=True, lwf_applicable=True, lwf_employee_amount=D('10'), lwf_employer_amount=D('20'),
            lwf_frequency=StatutoryConfig.LWF_MONTHLY,
        )
        self.branch_config = BranchPayrollConfig.objects.create(branch=self.branch)   # PF 12% / 12%, ceiling 15000
        self.standard = SalaryStructure.objects.create(name='Standard', is_default=True)
        self.basic = SalaryComponent.objects.create(structure=self.standard, name='Basic', component_type=EARN,
                                                    calculation_type=PCT_CTC, value=D('40'), role='basic', order=1)
        SalaryComponent.objects.create(structure=self.standard, name='HRA', component_type=ALLOW,
                                       calculation_type=PCT_BASIC, value=D('50'), role='hra', order=2)
        SalaryComponent.objects.create(structure=self.standard, name='Special Allowance', component_type=ALLOW,
                                       calculation_type=FIXED, value=D('5000'), role='special_allowance', order=3)
        hr_role = make_role('salcomp_hr', permission_codenames=[
            'payroll.view', 'payroll.edit', 'payroll.create', 'settings.edit'])
        self.hr = make_user('salcomp.hr@test.com', role=hr_role, employee_id='SCHR', full_name='Sal HR',
                            branch=self.branch.branch_name)
        emp_role = make_role('salcomp_emp')
        self.emp_a = make_user('salcomp.a@test.com', role=emp_role, employee_id='SCA', full_name='Emp A',
                               branch=self.branch.branch_name)
        self.emp_b = make_user('salcomp.b@test.com', role=emp_role, employee_id='SCB', full_name='Emp B',
                               branch=self.branch.branch_name)
        self.api = APIClient()
        _login(self.api, self.hr.email)

    def assign(self, employee, ctc='600000', effective='2026-01-01', **extra):
        body = {'employee': str(employee.pk), 'annual_ctc': ctc, 'effective_from': effective, **extra}
        return self.api.post(reverse('employee-salary-list'), body, format='json')

    def cycle(self, month, status=PayrollCycle.STATUS_ATTENDANCE_APPROVED):
        start = datetime.date(2026, month, 1)
        end = (datetime.date(2026, month + 1, 1) - datetime.timedelta(days=1)) if month < 12 else datetime.date(2026, 12, 31)
        return PayrollCycle.objects.create(cycle_start=start, cycle_end=end, pay_date=end, created_by=self.hr,
                                           status=status)

    def payslip(self, cycle, employee):
        return EmployeePayslip.objects.get(cycle=cycle, employee=employee)


# ─── Pure calculation ────────────────────────────────────────────────────────

class CalculationTests(TestCase):
    def test_percent_of_ctc_percent_of_basic_and_fixed(self):
        b = calculate([_spec('Basic', PCT_CTC, 40, 'basic', order=1), _spec('HRA', PCT_BASIC, 50, 'hra', order=2),
                       _spec('Special Allowance', FIXED, 5000, 'special_allowance', order=3)], D('50000'))
        self.assertEqual((b.basic, b.hra, b.special_allowance, b.gross), (D('20000'), D('10000'), D('5000'), D('35000')))

    def test_percent_of_basic_works_whatever_the_order(self):
        # Before: a % of Basic component listed above Basic was calculated as 0.
        b = calculate([_spec('HRA', PCT_BASIC, 50, 'hra', order=1), _spec('LTA', PCT_BASIC, 10, order=2),
                       _spec('Basic', PCT_CTC, 40, 'basic', order=9)], D('50000'))
        self.assertEqual((b.basic, b.hra, b.other_earnings['LTA']), (D('20000'), D('10000'), D('2000')))

    def test_basic_found_by_role_not_name(self):
        # Before: a component named "Basic Pay" was not Basic, so Basic (and PF on Basic) was 0.
        b = calculate([_spec('Basic Pay', PCT_CTC, 40, 'basic')], D('50000'))
        self.assertEqual((b.basic, b.other_earnings), (D('20000'), {}))

    def test_deductions_are_not_added_to_gross(self):
        # Before: a deduction-type component was added to gross like an earning.
        b = calculate([_spec('Basic', PCT_CTC, 40, 'basic'), _spec('Canteen', FIXED, 500, ctype=DED)], D('50000'))
        self.assertEqual((b.gross, b.other_deductions, b.other_earnings), (D('20000'), {'Canteen': D('500')}, {}))

    def test_disabled_components_count_as_zero(self):
        b = calculate([_spec('Basic', PCT_CTC, 40, 'basic'), _spec('Bonus', FIXED, 900, enabled=False)], D('50000'))
        self.assertEqual(b.gross, D('20000'))

    def test_role_for_name_matches_the_old_exact_name_rule(self):
        self.assertEqual([role_for_name(n) for n in ('Basic', 'BASIC', 'hra', 'Special Allowance', 'Basic Pay', 'HRA ')],
                         ['basic', 'basic', 'hra', 'special_allowance', 'other', 'other'])

    def test_validation(self):
        cases = [
            ([_row('Basic', PCT_CTC, 40, 'basic'), _row('basic', FIXED, 1)], 'appears more than once'),
            ([_row('Basic', PCT_BASIC, 40, 'basic')], 'Basic cannot be a percentage of Basic'),
            ([_row('HRA', PCT_BASIC, 40, 'hra')], 'no enabled Basic component'),
            ([_row('Basic', PCT_CTC, 40, 'basic'), _row('Basic 2', PCT_CTC, 10, 'basic')], 'Only one enabled component can be Basic'),
            ([_row('Basic', PCT_CTC, -1, 'basic')], 'cannot be negative'),
            ([_row('Basic', PCT_CTC, 140, 'basic')], '% of CTC cannot exceed 100'),
            ([_row('Basic', 'formula', 40, 'basic')], 'unsupported calculation method'),
            ([_row('Basic', PCT_CTC, 'abc', 'basic')], 'value must be a number'),
            ([_row('Canteen', FIXED, 500, ctype=DED)], 'at least one enabled earning'),
            ([_row('Basic', PCT_CTC, 40, 'basic', ctype=DED)], 'not a deduction'),
        ]
        for rows, expected in cases:
            _specs, errors = parse_components(rows)
            self.assertTrue(any(expected in e for e in errors), (expected, errors))
        _specs, errors = parse_components([_row('Basic', PCT_CTC, 40, 'basic'), _row('HRA', PCT_BASIC, 50, 'hra')])
        self.assertEqual(errors, [])


# ─── Assign CTC API + payroll ────────────────────────────────────────────────

class EmployeeWiseComponentTests(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()

    def _custom_b(self, effective='2026-01-01', ctc='600000'):
        return self.assign(self.emp_b, ctc=ctc, effective=effective, components=[
            _row('HRA', PCT_BASIC, 40, 'hra', order=1),                 # listed before Basic on purpose
            _row('Basic', PCT_CTC, 30, 'basic', order=2, source_component=str(self.basic.pk)),
            _row('Conveyance', FIXED, 1600, order=3),
            _row('Canteen', FIXED, 500, ctype=DED, order=4),
        ])

    def test_same_structure_different_components_per_employee(self):
        self.assertEqual(self.assign(self.emp_a).status_code, 201)     # no components → copy of the template
        resp = self._custom_b()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data['data']['components']), 4)
        cfg_a = EmployeeSalaryConfig.objects.get(employee=self.emp_a)
        self.assertEqual(cfg_a.template_structure, self.standard)
        self.assertEqual({c.name: c.monthly_amount for c in cfg_a.components.all()},
                         {'Basic': D('20000.00'), 'HRA': D('10000.00'), 'Special Allowance': D('5000.00')})

        cycle = self.cycle(1)
        process_payroll_cycle(cycle)
        a, b = self.payslip(cycle, self.emp_a), self.payslip(cycle, self.emp_b)
        # A: 20000 + 10000 + 5000 = 35000; PF 12% of min(20000, 15000) = 1800; PT 200; LWF 10; ESI 0 (above 21000)
        self.assertEqual((a.basic, a.hra, a.special_allowance, a.gross_earnings),
                         (D('20000.00'), D('10000.00'), D('5000.00'), D('35000.00')))
        self.assertEqual((a.pf_employee, a.pf_employer, a.esi_employee, a.pt_deduction, a.lwf_employee, a.lwf_employer),
                         (D('1800.00'), D('1800.00'), D('0.00'), D('200.00'), D('10.00'), D('20.00')))
        self.assertEqual((a.total_deductions, a.net_pay), (D('2010.00'), D('32990.00')))
        # B: Basic 15000, HRA 6000, Conveyance 1600 = 22600; Canteen 500 deducted, not earned
        self.assertEqual((b.basic, b.hra, b.special_allowance, b.other_earnings, b.other_deductions, b.gross_earnings),
                         (D('15000.00'), D('6000.00'), D('0.00'), {'Conveyance': 1600.0}, {'Canteen': 500.0},
                          D('22600.00')))
        self.assertEqual((b.total_deductions, b.net_pay), (D('2510.00'), D('20090.00')))   # 1800 + 200 + 10 + 500
        self.assertEqual(b.salary_structure, self.standard)

    def test_esi_covered_employee(self):
        self.assign(self.emp_a, ctc='240000')       # monthly 20000: 8000 + 4000 + 5000 = 17000 ≤ 21000
        cycle = self.cycle(1)
        process_payroll_cycle(cycle)
        a = self.payslip(cycle, self.emp_a)
        self.assertEqual((a.gross_earnings, a.pf_employee, a.esi_employee, a.esi_employer, a.pt_deduction),
                         (D('17000.00'), D('960.00'), D('127.50'), D('552.50'), D('200.00')))

    def test_changing_one_employee_leaves_the_other_alone(self):
        self.assign(self.emp_a)
        self._custom_b()
        before = list(EmployeeSalaryComponent.objects.filter(salary_config__employee=self.emp_a)
                      .values_list('name', 'value', 'monthly_amount'))
        self.assertEqual(self._custom_b(effective='2026-02-01', ctc='720000').status_code, 201)
        after = list(EmployeeSalaryComponent.objects.filter(salary_config__employee=self.emp_a)
                     .values_list('name', 'value', 'monthly_amount'))
        self.assertEqual(before, after)
        self.assertEqual(list(self.standard.components.order_by('order').values_list('value', flat=True)),
                         [D('40.0000'), D('50.0000'), D('5000.0000')])      # template untouched

    def test_structure_edit_does_not_change_saved_revision(self):
        self.assign(self.emp_a)                                         # snapshot
        EmployeeSalaryConfig.objects.create(employee=self.emp_b, annual_ctc=D('600000'),
                                            effective_from=datetime.date(2026, 1, 1))   # older-style, no snapshot
        self.basic.value = D('50')
        self.basic.save()
        cycle = self.cycle(1)
        process_payroll_cycle(cycle)
        self.assertEqual(self.payslip(cycle, self.emp_a).basic, D('20000.00'))   # kept 40%
        self.assertEqual(self.payslip(cycle, self.emp_b).basic, D('25000.00'))   # live structure, as before

    def test_structure_selection_order(self):
        special = SalaryStructure.objects.create(name='Branch Plan')
        SalaryComponent.objects.create(structure=special, name='Basic', component_type=EARN,
                                       calculation_type=PCT_CTC, value=D('60'), role='basic')
        personal = SalaryStructure.objects.create(name='Personal Plan')
        SalaryComponent.objects.create(structure=personal, name='Basic', component_type=EARN,
                                       calculation_type=PCT_CTC, value=D('70'), role='basic')
        # company default (no branch structure yet)
        self.assign(self.emp_a)
        self.assertEqual(EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=True).template_structure,
                         self.standard)
        # branch structure
        self.branch_config.salary_structure = special
        self.branch_config.save()
        self.assign(self.emp_a, effective='2026-02-01')
        self.assertEqual(EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=True).template_structure, special)
        # employee's own pick wins
        self.assign(self.emp_a, effective='2026-03-01', salary_structure=str(personal.pk))
        cfg = EmployeeSalaryConfig.objects.get(employee=self.emp_a, is_active=True)
        self.assertEqual((cfg.salary_structure, cfg.template_structure), (personal, personal))
        self.assertEqual(cfg.components.get().monthly_amount, D('35000.00'))

    def test_legacy_revision_without_snapshot_uses_branch_then_default(self):
        special = SalaryStructure.objects.create(name='Branch Plan')
        SalaryComponent.objects.create(structure=special, name='Basic', component_type=EARN,
                                       calculation_type=PCT_CTC, value=D('60'), role='basic')
        EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('600000'),
                                            effective_from=datetime.date(2026, 1, 1))
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        self.assertEqual(self.payslip(jan, self.emp_a).basic, D('20000.00'))       # company default 40%
        self.branch_config.salary_structure = special
        self.branch_config.save()
        feb = self.cycle(2)
        process_payroll_cycle(feb)
        self.assertEqual(self.payslip(feb, self.emp_a).basic, D('30000.00'))       # branch structure 60%

    def test_future_dated_revision_keeps_current_salary_until_it_starts(self):
        self.assign(self.emp_a, ctc='600000', effective='2026-01-01')
        self.assign(self.emp_a, ctc='720000', effective='2026-03-01')    # entered in advance
        feb, mar = self.cycle(2), self.cycle(3)
        process_payroll_cycle(feb)
        process_payroll_cycle(mar)
        # Before: February skipped the employee (the January revision had been switched off).
        self.assertEqual(self.payslip(feb, self.emp_a).annual_ctc, D('600000.00'))
        self.assertEqual(self.payslip(mar, self.emp_a).annual_ctc, D('720000.00'))
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).count(), 2)    # history kept

    def test_back_dated_revision_is_rejected(self):
        self.assign(self.emp_a, ctc='600000', effective='2026-02-01')
        for dry_run in (True, False):
            resp = self.assign(self.emp_a, ctc='540000', effective='2026-01-01', dry_run=dry_run)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("can't be before the current revision", resp.data['message'])
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).count(), 1)

    def test_legacy_correction_rows_still_resolve_as_before(self):
        # Data saved before this change may contain a later-saved, earlier-dated
        # correction; payroll keeps using the correction, as it did then.
        from django.utils import timezone
        first = EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('600000'),
                                                    effective_from=datetime.date(2026, 2, 1), is_active=False)
        second = EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('540000'),
                                                     effective_from=datetime.date(2026, 1, 1))
        # Saved one after the other (explicit times: the clock can tie within one test).
        now = timezone.now()
        EmployeeSalaryConfig.objects.filter(pk=first.pk).update(created_at=now - datetime.timedelta(minutes=5))
        EmployeeSalaryConfig.objects.filter(pk=second.pk).update(created_at=now)
        mar = self.cycle(3)
        process_payroll_cycle(mar)
        self.assertEqual(self.payslip(mar, self.emp_a).annual_ctc, D('540000.00'))

    def test_same_effective_date_latest_saved_wins(self):
        self.assign(self.emp_a, ctc='600000', effective='2026-01-01')
        self.assign(self.emp_a, ctc='660000', effective='2026-01-01')
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        self.assertEqual(self.payslip(jan, self.emp_a).annual_ctc, D('660000.00'))

    def test_switched_off_salary_is_still_skipped(self):
        self.assign(self.emp_a)
        EmployeeSalaryConfig.objects.filter(employee=self.emp_a).update(is_active=False)
        result = process_payroll_cycle(self.cycle(1))
        self.assertIn('Emp A', result['skipped'])

    def test_paid_payslips_are_preserved_and_unpaid_cycles_reprocess(self):
        self.assign(self.emp_a, ctc='600000', effective='2026-01-01')
        jan, feb = self.cycle(1), self.cycle(2)
        process_payroll_cycle(jan)
        process_payroll_cycle(feb)
        PayrollCycle.objects.filter(pk=jan.pk).update(status=PayrollCycle.STATUS_PAID)
        jan.refresh_from_db()
        feb.refresh_from_db()
        # A revision reaching into the paid month is refused (no arrears yet)...
        resp = self.assign(self.emp_a, ctc='720000', effective='2026-01-15')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already finalised', resp.data['message'])
        # ...one starting after it is fine, and the unpaid February cycle picks it up when re-processed.
        self.assertEqual(self.assign(self.emp_a, ctc='720000', effective='2026-02-01').status_code, 201)
        with self.assertRaises(PayrollAlreadyProcessing):
            process_payroll_cycle(jan)
        process_payroll_cycle(feb)
        self.assertEqual(self.payslip(jan, self.emp_a).annual_ctc, D('600000.00'))
        self.assertEqual(self.payslip(feb, self.emp_a).annual_ctc, D('720000.00'))

    def test_revision_audit_records_who_and_component_changes(self):
        from apps.accounts.models import AuditLog
        self.assign(self.emp_a)
        resp = self.assign(self.emp_a, effective='2026-02-01', components=[
            _row('Basic', PCT_CTC, 45, 'basic', order=1), _row('HRA', PCT_BASIC, 50, 'hra', ctype=ALLOW, order=2),
            _row('Conveyance', FIXED, 1600, order=3),
        ])
        self.assertEqual(resp.status_code, 201, resp.data)
        logs = AuditLog.objects.filter(action='salary_revision_created').order_by('created_at')
        self.assertEqual(logs.count(), 2)
        first, second = logs
        self.assertEqual((first.user, first.changes['source'], first.changes['employee_code']), (self.hr, 'assign_ctc', 'SCA'))
        c = second.changes
        self.assertEqual((c['previous_annual_ctc'], c['components_added'], c['components_removed']),
                         ('600000.00', ['Conveyance'], ['Special Allowance']))
        self.assertEqual(c['components_changed'], {'Basic': ['percentage_of_ctc:40:earning:basic',
                                                             'percentage_of_ctc:45:earning:basic']})
        history = self.api.get(reverse('employee-salary-history', kwargs={'employee_pk': str(self.emp_a.pk)})).data['data']
        self.assertEqual(history[0]['created_by_name'], 'Sal HR')

    def test_preview_saves_no_audit(self):
        from apps.accounts.models import AuditLog
        self.assign(self.emp_a, dry_run=True)
        self.assertFalse(AuditLog.objects.filter(action='salary_revision_created').exists())

    def test_deduction_component_in_older_structure_is_now_subtracted(self):
        SalaryComponent.objects.create(structure=self.standard, name='Canteen', component_type=DED,
                                       calculation_type=FIXED, value=D('500'), order=4)
        EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('600000'),
                                            effective_from=datetime.date(2026, 1, 1))
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        a = self.payslip(jan, self.emp_a)
        self.assertEqual((a.gross_earnings, a.other_deductions, a.total_deductions, a.net_pay),
                         (D('35000.00'), {'Canteen': 500.0}, D('2510.00'), D('32490.00')))

    # ── API: preview, validation, history, permissions ──────────────────────
    def test_preview_shows_template_totals_previous_and_saves_nothing(self):
        self.assign(self.emp_a, ctc='600000')
        resp = self.assign(self.emp_a, ctc='720000', effective='2026-04-01', dry_run=True)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['data']
        self.assertEqual(data['template_structure']['name'], 'Standard')
        self.assertEqual([(c['name'], c['monthly_amount']) for c in data['components']],
                         [('Basic', '24000.00'), ('HRA', '12000.00'), ('Special Allowance', '5000.00')])
        # 41000 × 12 = 492000 earnings vs 720000 CTC → reported, not balanced
        self.assertEqual(data['totals']['annual_earnings'], '492000.00')
        self.assertEqual(data['totals']['annual_difference'], '228000.00')
        self.assertTrue(any('Nothing is balanced automatically' in w for w in data['warnings']))
        self.assertEqual((data['previous']['annual_ctc'], data['previous']['totals']['monthly_earnings']),
                         ('600000.00', '35000.00'))
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).count(), 1)

    def test_validation_errors_are_returned(self):
        resp = self.assign(self.emp_a, components=[_row('HRA', PCT_BASIC, 50, 'hra'), _row('hra', FIXED, 1)])
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp.data['data']['errors'])
        self.assertEqual(self.assign(self.emp_a, ctc='0').status_code, 400)
        self.assertFalse(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).exists())

    def test_history_returns_each_revision_breakdown(self):
        self.assign(self.emp_a, ctc='600000')
        self._custom_b()
        self.assign(self.emp_a, ctc='720000', effective='2026-02-01')
        resp = self.api.get(reverse('employee-salary-history', kwargs={'employee_pk': str(self.emp_a.pk)}))
        rows = resp.data['data']
        self.assertEqual([r['annual_ctc'] for r in rows], ['720000.00', '600000.00'])
        self.assertEqual([c['monthly_amount'] for c in rows[1]['components']], ['20000.00', '10000.00', '5000.00'])
        listing = self.api.get(reverse('employee-salary-list')).data['data']
        self.assertTrue(all('components' in r and 'template_structure_name' in r for r in listing['results']))

    def test_saved_revision_terms_cannot_be_edited_in_place(self):
        cfg_id = self.assign(self.emp_a).data['data']['id']
        url = reverse('employee-salary-detail', kwargs={'pk': cfg_id})
        self.assertEqual(self.api.put(url, {'annual_ctc': '1'}, format='json').status_code, 400)
        self.assertEqual(self.api.put(url, {'components': []}, format='json').status_code, 400)
        legacy = EmployeeSalaryConfig.objects.create(employee=self.emp_b, annual_ctc=D('1'),
                                                     effective_from=datetime.date(2026, 1, 1))
        resp = self.api.put(reverse('employee-salary-detail', kwargs={'pk': legacy.pk}), {'annual_ctc': '2'}, format='json')
        self.assertEqual(resp.status_code, 200)                         # older revisions behave as before

    def test_permissions(self):
        viewer = make_user('salcomp.viewer@test.com', role=make_role('salcomp_view', permission_codenames=['payroll.view']),
                           employee_id='SCV', branch=self.branch.branch_name)
        api = APIClient()
        _login(api, viewer.email)
        resp = api.post(reverse('employee-salary-list'), {'employee': str(self.emp_a.pk), 'annual_ctc': '600000',
                                                          'effective_from': '2026-01-01', 'dry_run': True}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(EmployeeSalaryConfig.objects.exists())

    def test_structure_component_role_defaults_from_name(self):
        other = SalaryStructure.objects.create(name='Other')
        url = reverse('salary-component-list', kwargs={'structure_pk': other.pk})
        resp = self.api.post(url, {'name': 'Basic', 'component_type': EARN, 'calculation_type': FIXED, 'value': '1'},
                             format='json')
        self.assertEqual(resp.data['data']['role'], 'basic')
        resp = self.api.post(url, {'name': 'Base Pay', 'component_type': EARN, 'calculation_type': FIXED,
                                   'value': '1', 'role': 'other'}, format='json')
        self.assertEqual(resp.data['data']['role'], 'other')


class BackfillCommandTests(SalaryFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixtures()

    def test_dry_run_then_apply_and_flags_unclear_rows(self):
        cfg = EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('600000'),
                                                  effective_from=datetime.date(2026, 1, 1))
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        before = self.payslip(jan, self.emp_a)
        stray = make_user('salcomp.stray@test.com', employee_id='SCX', branch='NoSuchBranch')
        EmployeeSalaryConfig.objects.create(employee=stray, annual_ctc=D('1'), effective_from=datetime.date(2026, 1, 1))

        out = io.StringIO()
        call_command('backfill_salary_components', stdout=out)
        self.assertIn('1 revision(s) ready, 1 skipped', out.getvalue())
        self.assertNotIn('salcomp', out.getvalue())                      # no emails/names in the report
        self.assertFalse(EmployeeSalaryComponent.objects.exists())

        call_command('backfill_salary_components', '--apply', stdout=io.StringIO())
        cfg.refresh_from_db()
        self.assertEqual((cfg.components.count(), cfg.template_structure), (3, self.standard))
        PayrollCycle.objects.filter(pk=jan.pk).update(status=PayrollCycle.STATUS_PAYSLIPS_GENERATED)
        jan.refresh_from_db()
        process_payroll_cycle(jan)                                      # same result from the snapshot
        after = self.payslip(jan, self.emp_a)
        self.assertEqual((after.gross_earnings, after.net_pay), (before.gross_earnings, before.net_pay))
        call_command('backfill_salary_components', '--apply', stdout=io.StringIO())     # idempotent
        self.assertEqual(cfg.components.count(), 3)
        from apps.accounts.models import AuditLog
        self.assertEqual(AuditLog.objects.filter(action='salary_components_backfilled').count(), 1)

    def test_unclear_histories_are_flagged_not_guessed(self):
        EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('1'), effective_from=datetime.date(2026, 1, 1))
        EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('2'), effective_from=datetime.date(2026, 2, 1))
        EmployeeSalaryConfig.objects.create(employee=self.emp_b, annual_ctc=D('1'), effective_from=datetime.date(2026, 1, 1),
                                            is_active=False)
        EmployeeSalaryConfig.objects.create(employee=self.emp_b, annual_ctc=D('2'), effective_from=datetime.date(2026, 1, 1))
        out = io.StringIO()
        call_command('backfill_salary_components', '--apply', stdout=out)
        text = out.getvalue()
        self.assertIn('2 revisions marked current', text)
        self.assertIn('same effective date', text)
        self.assertIn('0 revision(s) ready, 4 skipped', text)
        self.assertFalse(EmployeeSalaryComponent.objects.exists())


class LopRegressionTests(SalaryFixtureMixin, TestCase):
    """
    LOP stays on gross earnings (gross / working days x LOP days), as before.
    Component deductions keep their own basis (fixed, % of CTC, % of Basic on
    the full-month Basic) and are not prorated; PF / ESI / PT / LWF are
    calculated exactly as before (not on LOP-reduced wages).
    """

    def setUp(self):
        self.make_fixtures()

    def _attendance(self, employee, absent=1, half=0, working=26):
        from apps.attendance.models import AttendanceRecord
        statuses = ([AttendanceRecord.STATUS_ABSENT] * absent + [AttendanceRecord.STATUS_HALF_DAY] * half)
        statuses += [AttendanceRecord.STATUS_PRESENT] * (working - len(statuses))
        for day, status in enumerate(statuses, start=1):
            AttendanceRecord.objects.create(employee=employee, date=datetime.date(2026, 1, day), status=status)

    def test_lop_on_gross_statutory_unchanged(self):
        self.assign(self.emp_a)                                 # 35000 gross
        self._attendance(self.emp_a, absent=1)
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        a = self.payslip(jan, self.emp_a)
        # LOP 35000 / 26 x 1 = 1346.15; PF still 12% of min(Basic 20000, 15000); PT on full gross
        self.assertEqual((a.total_working_days, a.lop_days, a.lop_deduction), (26, D('1.0'), D('1346.15')))
        self.assertEqual((a.pf_employee, a.pf_employer, a.pt_deduction, a.lwf_employee),
                         (D('1800.00'), D('1800.00'), D('200.00'), D('10.00')))
        self.assertEqual((a.total_deductions, a.net_pay), (D('3356.15'), D('31643.85')))

    def test_component_deductions_keep_their_basis_under_lop(self):
        self.assign(self.emp_a, components=[
            _row('Basic', PCT_CTC, 40, 'basic', order=1), _row('HRA', PCT_BASIC, 50, 'hra', order=2),
            _row('Special Allowance', FIXED, 5000, 'special_allowance', order=3),
            _row('Canteen', FIXED, 500, ctype=DED, order=4),
            _row('Welfare', PCT_BASIC, 1, ctype=DED, order=5),          # 1% of full-month Basic = 200
        ])
        self._attendance(self.emp_a, absent=1, half=1)                  # LOP 1.5 days
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        a = self.payslip(jan, self.emp_a)
        # LOP 35000 / 26 x 1.5 = 2019.23 (deductions not part of gross, not prorated)
        self.assertEqual((a.lop_days, a.lop_deduction), (D('1.5'), D('2019.23')))
        self.assertEqual(a.other_deductions, {'Canteen': 500.0, 'Welfare': 200.0})
        # 2019.2308 + 1800 + 200 + 10 + 700 = 4729.23; net 35000 - 4729.2308 = 30270.77
        self.assertEqual((a.total_deductions, a.net_pay), (D('4729.23'), D('30270.77')))

    def test_esi_under_lop_unchanged(self):
        self.assign(self.emp_a, ctc='240000')                   # 17000 gross, ESI covered
        self._attendance(self.emp_a, absent=1)
        jan = self.cycle(1)
        process_payroll_cycle(jan)
        a = self.payslip(jan, self.emp_a)
        self.assertEqual((a.lop_deduction, a.esi_employee, a.esi_employer, a.pf_employee),
                         (D('653.85'), D('127.50'), D('552.50'), D('960.00')))


class OtherSalarySourcesTests(SalaryFixtureMixin, TestCase):
    """Onboarding approval and employee bulk import save the same revision + component copy as Assign CTC."""

    def setUp(self):
        self.make_fixtures()

    def test_onboarding_approval_copies_components(self):
        from apps.accounts.models import AuditLog, User
        make_role('employee')                       # OnboardingApprovalView looks this up by name
        approver = make_user('salcomp.onb@test.com', role=make_role('salcomp_onb', permission_codenames=[
            'onboarding.approve', 'settings.edit']), employee_id='SCO', branch=self.branch.branch_name)
        hire = make_user('salcomp.hire@test.com', role=None, onboarding_status=User.ONBOARDING_SUBMITTED,
                         branch=self.branch.branch_name, date_of_joining=datetime.date(2026, 3, 1))
        api = APIClient()
        _login(api, approver.email)
        resp = api.post(reverse('onboarding-approve', kwargs={'user_id': str(hire.pk)}),
                        {'decision': 'approve', 'department': 'Engineering', 'designation': 'Engineer',
                         'annual_ctc': '600000'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = EmployeeSalaryConfig.objects.get(employee=hire)
        self.assertEqual((cfg.annual_ctc, cfg.effective_from, cfg.template_structure, cfg.components.count(), cfg.created_by),
                         (D('600000.00'), datetime.date(2026, 3, 1), self.standard, 3, approver))
        self.assertEqual(AuditLog.objects.get(action='salary_revision_created').changes['source'], 'onboarding_approval')

    def test_bulk_import_copies_components(self):
        from apps.accounts.models import Department, Designation
        from django.core.files.uploadedfile import SimpleUploadedFile
        dept = Department.objects.create(name='Engineering')
        Designation.objects.create(name='Engineer', department=dept)
        importer = make_user('salcomp.imp@test.com', role=make_role('salcomp_imp', permission_codenames=[
            'employees.create', 'settings.edit']), employee_id='SCI', branch=self.branch.branch_name)
        api = APIClient()
        _login(api, importer.email)
        csv_text = ('First Name,Last Name,Work Email,Role,Department,Designation,Branch,Date of Joining,Annual CTC\n'
                    f'Imp,One,salcomp.imp1@test.com,salcomp_emp,Engineering,Engineer,{self.branch.branch_name},'
                    '2026-04-01,"6,00,000"\n')
        resp = api.post(reverse('employee-bulk-import'),
                        {'file': SimpleUploadedFile('emp.csv', csv_text.encode(), content_type='text/csv')},
                        format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        cfg = EmployeeSalaryConfig.objects.get(employee__email='salcomp.imp1@test.com')
        self.assertEqual((cfg.annual_ctc, cfg.effective_from, cfg.components.count()),
                         (D('600000.00'), datetime.date(2026, 4, 1), 3))

    def test_assign_salary_is_idempotent(self):
        from apps.payroll.services_salary_components import assign_salary
        first, created = assign_salary(employee=self.emp_a, annual_ctc=D('600000'),
                                       effective_from=datetime.date(2026, 1, 1), source='test')
        again, created_again = assign_salary(employee=self.emp_a, annual_ctc=D('600000'),
                                             effective_from=datetime.date(2026, 1, 1), source='test')
        self.assertEqual((created, created_again, first.pk), (True, False, again.pk))
        self.assertEqual((EmployeeSalaryConfig.objects.filter(employee=self.emp_a).count(), first.components.count()), (1, 3))

    def test_assign_salary_adds_missing_copy_to_existing_revision(self):
        from apps.payroll.services_salary_components import assign_salary
        legacy = EmployeeSalaryConfig.objects.create(employee=self.emp_a, annual_ctc=D('600000'),
                                                     effective_from=datetime.date(2026, 1, 1))
        cfg, created = assign_salary(employee=self.emp_a, annual_ctc=D('600000'),
                                     effective_from=datetime.date(2026, 1, 1), source='test')
        self.assertEqual((cfg.pk, created, cfg.components.count()), (legacy.pk, False, 3))

    def test_component_failure_leaves_no_half_saved_revision(self):
        from unittest import mock
        from django.db import IntegrityError
        from apps.payroll.services_salary_components import assign_salary
        with mock.patch('apps.payroll.models.EmployeeSalaryComponent.objects.bulk_create',
                        side_effect=IntegrityError('boom')):
            with self.assertRaises(IntegrityError):
                assign_salary(employee=self.emp_a, annual_ctc=D('600000'),
                              effective_from=datetime.date(2026, 1, 1), source='test')
        self.assertFalse(EmployeeSalaryConfig.objects.filter(employee=self.emp_a).exists())
