"""
Phase 7A Task G — income tax computed from TaxRegime/TaxYearConfig/
TaxSection DATA instead of services_income_tax.py's hardcoded constants.

This module is proven, by test (tests_tax_engine.py), to reproduce
`services_income_tax.estimate_monthly_tds()`'s output EXACTLY across a wide
range of inputs — same slab logic, same 87A marginal-relief mechanic, same
rounding. It is NOT called by anything yet; `estimate_monthly_tds` (the
legacy, hardcoded version) remains the one real payroll processing calls,
via apps.payroll.engine.legacy. This module exists to prove the DATA is
sufficient to replace the hardcoded constants later — the actual swap-over
is Task J's job (shadow-run the data-driven path, verify zero differences
across every historical payslip, THEN cut over behind payroll.v2).
"""
from decimal import ROUND_HALF_UP, Decimal

from apps.payroll.models import TaxSection, TaxYearConfig

TWO_PLACES = Decimal('0.01')


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _tax_from_slabs(taxable: Decimal, slabs: list) -> Decimal:
    tax = Decimal('0')
    for row in slabs:
        start = Decimal(row['start'])
        end = Decimal(row['end']) if row['end'] is not None else None
        rate = Decimal(row['rate'])
        if taxable <= start:
            break
        upper = end if end is not None else taxable
        band = min(taxable, upper) - start
        if band > 0:
            tax += band * rate
    return tax


def _apply_87a_rebate(tax: Decimal, taxable: Decimal, threshold: Decimal) -> Decimal:
    if taxable <= threshold:
        return Decimal('0')
    marginal_cap = taxable - threshold
    return min(tax, marginal_cap) if marginal_cap < tax else tax


def get_year_config(regime_code: str, financial_year_start: int) -> TaxYearConfig:
    """Exact FY match if seeded; otherwise the latest FY at or before the
    requested one, same "a law stays in force until explicitly superseded"
    convention real tax config needs (and matches the legacy module's own
    single-FY-forever behavior when only one year is seeded)."""
    config = TaxYearConfig.objects.filter(
        regime__code=regime_code, financial_year_start__lte=financial_year_start,
    ).order_by('-financial_year_start').first()
    if config is None:
        raise TaxYearConfig.DoesNotExist(
            f'No TaxYearConfig for regime={regime_code!r} at or before FY{financial_year_start}.'
        )
    return config


def compute_annual_tax(annual_taxable_income: Decimal, regime_code: str, financial_year_start: int) -> Decimal:
    annual_taxable_income = max(Decimal('0'), Decimal(annual_taxable_income))
    config = get_year_config(regime_code, financial_year_start)

    taxable_after_std = max(Decimal('0'), annual_taxable_income - config.standard_deduction)
    tax = _tax_from_slabs(taxable_after_std, config.slabs)
    tax = _apply_87a_rebate(tax, taxable_after_std, config.rebate_threshold)
    tax_with_cess = tax + (tax * config.cess_rate)
    return _round(tax_with_cess)


def _capped_old_regime_deductions(declared_investments: dict, financial_year_start: int) -> Decimal:
    declared_investments = declared_investments or {}
    sections = {
        s.code: s for s in TaxSection.objects.filter(is_active=True, applicable_regime_codes__contains=['old'])
    }

    def _amount(key: str) -> Decimal:
        try:
            return Decimal(str(declared_investments.get(key, 0) or 0))
        except (ValueError, ArithmeticError):
            return Decimal('0')

    sec_80c = _amount('80C')
    sec_80d = _amount('80D')
    sec_80ccd_1b = _amount('80CCD1B')
    hra = max(Decimal('0'), _amount('HRA'))

    if '80C' in sections and sections['80C'].cap_amount is not None:
        sec_80c = min(sec_80c, sections['80C'].cap_amount)
    if '80D' in sections and sections['80D'].cap_amount is not None:
        sec_80d = min(sec_80d, sections['80D'].cap_amount)
    if '80CCD1B' in sections and sections['80CCD1B'].cap_amount is not None:
        sec_80ccd_1b = min(sec_80ccd_1b, sections['80CCD1B'].cap_amount)
    # HRA has no cap row value today (cap_amount=None) — taken as declared,
    # matching the legacy module exactly.

    return sec_80c + sec_80d + sec_80ccd_1b + hra


def compute_monthly_tds(
    monthly_gross_earnings: Decimal, regime_code: str, declared_investments: dict | None,
    financial_year_start: int,
) -> Decimal:
    monthly_gross_earnings = Decimal(monthly_gross_earnings)
    annual_gross = monthly_gross_earnings * 12

    if regime_code == 'old':
        taxable = annual_gross - _capped_old_regime_deductions(declared_investments, financial_year_start)
    else:
        taxable = annual_gross

    annual_tax = compute_annual_tax(max(Decimal('0'), taxable), regime_code, financial_year_start)
    return _round(annual_tax / 12)
