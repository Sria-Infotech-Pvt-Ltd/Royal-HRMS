"""
Phase 7A Task G — proves services_tax_engine (data-driven) reproduces
services_income_tax (hardcoded) EXACTLY, across regimes, declared
investments, and a wide range of incomes including the 87A rebate edges.

This is the parity proof the master prompt's Task G requires before any
future cutover — not a cutover itself (nothing calls services_tax_engine
from real payroll processing yet).
"""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.payroll import services_income_tax as legacy
from apps.payroll import services_tax_engine as data_driven

FY = 2026  # matches seed_tax_year_config.FINANCIAL_YEAR_START


class TaxEngineParityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_tax_year_config')

    def _assert_parity(self, monthly_gross, regime, declared_investments=None):
        legacy_result = legacy.estimate_monthly_tds(Decimal(monthly_gross), regime, declared_investments)
        data_result = data_driven.compute_monthly_tds(Decimal(monthly_gross), regime, declared_investments, FY)
        self.assertEqual(
            legacy_result, data_result,
            f'Mismatch at gross={monthly_gross} regime={regime} declared={declared_investments}: '
            f'legacy={legacy_result} data_driven={data_result}',
        )

    def test_new_regime_across_income_bands(self):
        for monthly_gross in [Decimal('20000'), Decimal('50000'), Decimal('80000'),
                               Decimal('100000'), Decimal('150000'), Decimal('250000')]:
            self._assert_parity(monthly_gross, 'new')

    def test_new_regime_rebate_edge(self):
        # Annual taxable just at/above/below the 12,00,000 87A threshold.
        for monthly_gross in [Decimal('106250'), Decimal('100000'), Decimal('100001')]:
            self._assert_parity(monthly_gross, 'new')

    def test_old_regime_no_declarations(self):
        for monthly_gross in [Decimal('30000'), Decimal('60000'), Decimal('90000'), Decimal('200000')]:
            self._assert_parity(monthly_gross, 'old')

    def test_old_regime_with_declarations_under_and_over_caps(self):
        self._assert_parity(Decimal('80000'), 'old', {'80C': '100000', '80D': '15000'})
        # Declared well above the statutory caps — must clamp identically.
        self._assert_parity(Decimal('80000'), 'old', {
            '80C': '500000', '80D': '100000', '80CCD1B': '200000', 'HRA': '60000',
        })

    def test_old_regime_rebate_edge(self):
        for monthly_gross in [Decimal('41000'), Decimal('42000'), Decimal('43000')]:
            self._assert_parity(monthly_gross, 'old', {'80C': '150000'})

    def test_zero_income(self):
        self._assert_parity(Decimal('0'), 'new')
        self._assert_parity(Decimal('0'), 'old')
