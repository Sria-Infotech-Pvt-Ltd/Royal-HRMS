"""
Phase 7A Task G — seed TaxRegime/TaxYearConfig/TaxSection with EXACTLY the
FY2026-27 values apps/payroll/services_income_tax.py hardcodes today (see
that module's own docstring for the full citation/justification of these
numbers — this command copies them, it does not re-derive or adjust them).

VERIFY EVERY SEEDED VALUE WITH A QUALIFIED PROFESSIONAL BEFORE GO-LIVE.
Idempotent (update_or_create by regime+financial_year_start / section code).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payroll.models import TaxRegime, TaxSection, TaxYearConfig
from apps.payroll import services_income_tax as legacy

FINANCIAL_YEAR_START = 2026  # FY2026-27, matching legacy module's own docstring


class Command(BaseCommand):
    help = 'Phase 7A Task G — seed tax-as-data from services_income_tax.py\'s current FY2026-27 constants (cited, verify-before-go-live).'

    def handle(self, *args, **options):
        old_regime, _ = TaxRegime.objects.update_or_create(code=TaxRegime.CODE_OLD, defaults={})
        new_regime, _ = TaxRegime.objects.update_or_create(code=TaxRegime.CODE_NEW, defaults={})

        def _slabs_as_data(slabs):
            return [
                {'start': str(start), 'end': (str(end) if end is not None else None), 'rate': str(rate)}
                for start, end, rate in slabs
            ]

        TaxYearConfig.objects.update_or_create(
            regime=new_regime, financial_year_start=FINANCIAL_YEAR_START,
            defaults={
                'slabs': _slabs_as_data(legacy._NEW_REGIME_SLABS),
                'rebate_threshold': legacy.REBATE_THRESHOLD_NEW,
                'standard_deduction': legacy.STANDARD_DEDUCTION_NEW,
                'cess_rate': legacy.CESS_RATE,
                'source_citation': 'apps/payroll/services_income_tax.py: _NEW_REGIME_SLABS, REBATE_THRESHOLD_NEW, STANDARD_DEDUCTION_NEW, CESS_RATE',
            },
        )
        TaxYearConfig.objects.update_or_create(
            regime=old_regime, financial_year_start=FINANCIAL_YEAR_START,
            defaults={
                'slabs': _slabs_as_data(legacy._OLD_REGIME_SLABS),
                'rebate_threshold': legacy.REBATE_THRESHOLD_OLD,
                'standard_deduction': legacy.STANDARD_DEDUCTION_OLD,
                'cess_rate': legacy.CESS_RATE,
                'source_citation': 'apps/payroll/services_income_tax.py: _OLD_REGIME_SLABS, REBATE_THRESHOLD_OLD, STANDARD_DEDUCTION_OLD, CESS_RATE',
            },
        )

        # Old-regime-only deductions — the new regime (115BAC) disallows
        # all of these, matching _capped_old_regime_deductions()'s own gate.
        sections = [
            ('80C', 'Section 80C', legacy.CAP_80C),
            ('80D', 'Section 80D', legacy.CAP_80D),
            ('80CCD1B', 'Section 80CCD(1B)', legacy.CAP_80CCD_1B),
            ('HRA', 'HRA Exemption', None),  # no cap enforced today — taken as declared
        ]
        for code, name, cap in sections:
            TaxSection.objects.update_or_create(
                code=code, defaults={'name': name, 'applicable_regime_codes': ['old'], 'cap_amount': cap},
            )

        self.stdout.write(self.style.SUCCESS(
            'Seeded TaxRegime (old/new), 2 TaxYearConfig rows (FY2026-27), 4 TaxSection rows. '
            'VERIFY EVERY VALUE WITH A QUALIFIED PROFESSIONAL BEFORE GO-LIVE.'
        ))
