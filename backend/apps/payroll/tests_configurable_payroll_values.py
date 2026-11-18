"""
Two numbers that used to be fixed inside the payroll code are now settings, with the old values as defaults so nothing changes until an
admin edits them:
  * PayrollSettings.default_working_days_per_month (was a bare 26: the working days used for a payslip when no attendance exists)
  * StatutoryConfig.esi_daily_wage_exemption_threshold (was a bare 176: the daily wage at or below which the employee's own ESI is waived)
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.branch.models import State
from apps.payroll.engine.legacy import _compute_employee_payslip, _run_payroll_processing
from apps.payroll.models import (
    EmployeePayslip, EmployeeSalaryConfig, PayrollCycle, PayrollSettings, SalaryComponent, SalaryStructure, StatutoryConfig,
)
from apps.payroll.serializers import PayrollSettingsSerializer, StatutoryConfigSerializer
from types import SimpleNamespace


def _structure() -> SalaryStructure:
    structure = SalaryStructure.objects.create(name='Configurable Values Structure')
    SalaryComponent.objects.create(
        structure=structure, name='Basic', component_type=SalaryComponent.TYPE_EARNING,
        calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('100'), order=0,
    )
    return structure


class DefaultsAndApiTests(TestCase):
    def test_the_defaults_are_the_old_fixed_numbers(self):
        self.assertEqual(PayrollSettings._meta.get_field('default_working_days_per_month').default, 26)
        self.assertEqual(StatutoryConfig._meta.get_field('esi_daily_wage_exemption_threshold').default, Decimal('176.00'))

    def test_both_settings_are_exposed_and_writable_through_the_serializers(self):
        self.assertIn('default_working_days_per_month', PayrollSettingsSerializer().fields)
        self.assertIn('esi_daily_wage_exemption_threshold', StatutoryConfigSerializer().fields)
        serializer = PayrollSettingsSerializer(PayrollSettings.objects.create(), data={'default_working_days_per_month': 30}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().default_working_days_per_month, 30)


class EsiDailyWageLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_schemes')
        call_command('seed_tax_year_config')
        cls.structure = _structure()
        cls.state = State.objects.create(name='EsiLimitState', code='EL')
        cls.statutory = StatutoryConfig.objects.create(
            state=cls.state, esi_applicable=True, esi_wage_ceiling=Decimal('21000.00'),
            esi_employee_rate=Decimal('0.75'), esi_employer_rate=Decimal('3.25'),
        )

    def _esi(self, threshold: str, monthly_ctc: str = '20000'):
        self.statutory.esi_daily_wage_exemption_threshold = Decimal(threshold)
        components = list(self.structure.components.filter(is_active=True).order_by('order'))
        config = SimpleNamespace(monthly_ctc=Decimal(monthly_ctc), annual_ctc=Decimal(monthly_ctc) * 12)
        return _compute_employee_payslip(
            config, components, None, self.statutory, [], self.structure, total_working_days=26, cycle_month=4,
        )

    def test_a_daily_wage_above_the_limit_pays_the_employee_share(self):
        result = self._esi('176')   # 20000 / 26 = 769 a day, well above 176
        self.assertGreater(result['esi_employee'], 0)
        self.assertGreater(result['esi_employer'], 0)

    def test_raising_the_limit_above_the_daily_wage_waives_only_the_employee_share(self):
        result = self._esi('5000')
        self.assertEqual(result['esi_employee'], 0)
        self.assertGreater(result['esi_employer'], 0)   # the employer share is due regardless

    def test_the_limit_is_the_setting_not_a_fixed_176(self):
        # 20000 / 26 = 769.23 a day: exempt at a limit of 770, charged at a limit of 769.
        self.assertEqual(self._esi('770')['esi_employee'], 0)
        self.assertGreater(self._esi('769')['esi_employee'], 0)


class DefaultWorkingDaysTests(TestCase):
    def setUp(self):
        call_command('seed_statutory_schemes')
        call_command('seed_tax_year_config')
        structure = _structure()
        self.employee = make_user(
            'cfg-days@example.com', role=make_role('cfg_days_role'), employee_id='CFG0001',
            onboarding_status=User.ONBOARDING_COMPLETE, date_of_joining=datetime.date(2025, 1, 1),
        )
        EmployeeSalaryConfig.objects.create(
            employee=self.employee, salary_structure=structure, annual_ctc=Decimal('240000'),
            effective_from=datetime.date(2025, 1, 1),
        )
        self.cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 11, 1), cycle_end=datetime.date(2026, 11, 30),
            pay_date=datetime.date(2026, 12, 5), created_by=self.employee,
        )

    def _working_days_on_the_payslip(self) -> int:
        _run_payroll_processing(self.cycle)
        return EmployeePayslip.objects.get(cycle=self.cycle, employee=self.employee).total_working_days

    def test_with_no_attendance_the_payslip_uses_26_by_default(self):
        self.assertEqual(self._working_days_on_the_payslip(), 26)

    def test_with_no_attendance_the_payslip_uses_the_configured_number(self):
        PayrollSettings.objects.all().delete()
        PayrollSettings.objects.create(default_working_days_per_month=30)
        self.assertEqual(self._working_days_on_the_payslip(), 30)
