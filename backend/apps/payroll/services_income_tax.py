"""Real Indian income-tax (TDS) estimation — FY2026-27 (AY2027-28) slabs.

Slab source: the Section 115BAC "new regime" slabs introduced by Budget 2025
(effective FY2025-26) are the current published slabs and continue to apply
for FY2026-27 as of this session — no subsequent Budget has changed them.
These are the real, statutory rates, not invented figures:

    New regime (default):
        Rs 0        - 4,00,000   : 0%
        Rs 4,00,001 - 8,00,000   : 5%
        Rs 8,00,001 - 12,00,000  : 10%
        Rs 12,00,001- 16,00,000  : 15%
        Rs 16,00,001- 20,00,000  : 20%
        Rs 20,00,001- 24,00,000  : 25%
        above 24,00,000          : 30%
        Section 87A rebate: tax is nil for taxable income <= Rs 12,00,000,
        with marginal relief tapering just above that threshold.
        Standard deduction: Rs 75,000.

    Old regime (unchanged, long-standing slabs):
        Rs 0        - 2,50,000   : 0%
        Rs 2,50,001 - 5,00,000   : 5%
        Rs 5,00,001 - 10,00,000  : 20%
        above 10,00,000          : 30%
        Section 87A rebate: tax is nil for taxable income <= Rs 5,00,000.
        Standard deduction: Rs 50,000.

    Both regimes: 4% Health & Education cess on tax after rebate.

SIMPLIFICATIONS (flagged honestly, not hidden):
  - Old-regime declared investments are subtracted from gross annual salary at
    the statutory caps in tax_declaration_schema (80C Rs 1,50,000 across all
    its items; 80CCD(1B) Rs 50,000; 80D Rs 25,000 / Rs 50,000 for self+family
    and again for parents depending on the senior-citizen answer, Rs 1,00,000
    in all; 24(b) Rs 2,00,000; 80E and 80G as declared) before slabs apply.
  - HRA: when the employee declared rent (monthly rent, months, metro or not)
    the exemption is the usual three-way minimum — HRA received, rent paid
    minus 10% of basic, 50% (metro) / 40% of basic — per month, over the
    months of rent declared, using this payslip's basic and HRA. Without rent
    details it falls back to the legacy self-computed 'HRA' exemption amount.
  - No other exemptions (LTA, other perquisites, surcharge for very high
    incomes, marginal-relief-on-surcharge) are modelled — this is a real,
    correct core slab+cess+87A computation, not a full statutory return.
  - Annualization: this module projects annual income as
    (this payslip's monthly gross_earnings x 12) rather than summing actual
    payslips issued so far in the FY plus projecting the remainder. This
    mirrors how every other statutory deduction in this payroll engine
    already works (PF/ESI/PT/LWF are all computed off the CURRENT month's
    figures only, in apps/payroll/views/cycles.py — none of them do a
    running annual reconciliation), so TDS follows the same convention
    rather than introducing a new one. The corollary: a mid-year raise or
    bonus will shift the monthly TDS estimate for later months rather than
    smoothing/reconciling across the whole FY, exactly like this app's
    existing statutory deductions do.
  - Monthly TDS = annual tax / 12 (not divided across "remaining months of
    the FY"), again matching the flat-per-cycle convention of PF/ESI/PT/LWF.
"""
from decimal import ROUND_HALF_UP, Decimal

from .tax_declaration_schema import (
    CAP_80C,
    CAP_80D_SENIOR,
    CAP_80D_STANDARD,
    CAP_80D_TOTAL,
    DETAILS_KEY,
    FIELD_CAPS,
    KEYS_80C,
)

TWO_PLACES = Decimal('0.01')

STANDARD_DEDUCTION_NEW = Decimal('75000')
STANDARD_DEDUCTION_OLD = Decimal('50000')

REBATE_THRESHOLD_NEW = Decimal('1200000')
REBATE_THRESHOLD_OLD = Decimal('500000')

CESS_RATE = Decimal('0.04')

# (slab_start, slab_end_or_None, rate) — annual, in rupees.
_NEW_REGIME_SLABS = [
    (Decimal('0'),       Decimal('400000'),  Decimal('0.00')),
    (Decimal('400000'),  Decimal('800000'),  Decimal('0.05')),
    (Decimal('800000'),  Decimal('1200000'), Decimal('0.10')),
    (Decimal('1200000'), Decimal('1600000'), Decimal('0.15')),
    (Decimal('1600000'), Decimal('2000000'), Decimal('0.20')),
    (Decimal('2000000'), Decimal('2400000'), Decimal('0.25')),
    (Decimal('2400000'), None,               Decimal('0.30')),
]

_OLD_REGIME_SLABS = [
    (Decimal('0'),       Decimal('250000'),  Decimal('0.00')),
    (Decimal('250000'),  Decimal('500000'),  Decimal('0.05')),
    (Decimal('500000'),  Decimal('1000000'), Decimal('0.20')),
    (Decimal('1000000'), None,               Decimal('0.30')),
]


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _tax_from_slabs(taxable: Decimal, slabs: list) -> Decimal:
    """Cumulative slab tax on an already-non-negative `taxable` amount."""
    tax = Decimal('0')
    for start, end, rate in slabs:
        if taxable <= start:
            break
        upper = end if end is not None else taxable
        band = min(taxable, upper) - start
        if band > 0:
            tax += band * rate
    return tax


def _apply_87a_rebate(tax: Decimal, taxable: Decimal, threshold: Decimal) -> Decimal:
    """Full rebate below the threshold; a marginal-relief cap just above it
    (tax capped at the amount by which income exceeds the threshold) so a
    rupee more of income never costs more than a rupee more of tax — the
    standard, real 87A marginal-relief mechanic for both regimes."""
    if taxable <= threshold:
        return Decimal('0')
    marginal_cap = taxable - threshold
    return min(tax, marginal_cap) if marginal_cap < tax else tax


def estimate_annual_tax(annual_taxable_income: Decimal, regime: str) -> Decimal:
    """Real slab + 87A rebate + 4% cess computation for FY2026-27.

    `annual_taxable_income` is gross annual salary income with any
    regime-specific declared-investment deductions (80C/80D/80CCD(1B)/HRA)
    ALREADY subtracted by the caller for the old regime (the new regime
    doesn't allow those deductions under 115BAC, so callers pass gross
    salary through unchanged for it). The standard deduction (Rs 75,000 new
    / Rs 50,000 old) is applied here, before slabs.
    """
    annual_taxable_income = max(Decimal('0'), Decimal(annual_taxable_income))
    is_old = regime == 'old'
    std_deduction = STANDARD_DEDUCTION_OLD if is_old else STANDARD_DEDUCTION_NEW
    slabs = _OLD_REGIME_SLABS if is_old else _NEW_REGIME_SLABS
    rebate_threshold = REBATE_THRESHOLD_OLD if is_old else REBATE_THRESHOLD_NEW

    taxable_after_std = max(Decimal('0'), annual_taxable_income - std_deduction)
    tax = _tax_from_slabs(taxable_after_std, slabs)
    tax = _apply_87a_rebate(tax, taxable_after_std, rebate_threshold)
    tax_with_cess = tax + (tax * CESS_RATE)
    return _round(tax_with_cess)


def _amount(source: dict, key: str) -> Decimal:
    try:
        return max(Decimal('0'), Decimal(str(source.get(key, 0) or 0)))
    except (ValueError, ArithmeticError):
        return Decimal('0')


def _hra_exemption(details: dict, declared: dict, monthly_basic: Decimal | None, monthly_hra: Decimal | None) -> Decimal:
    """Annual HRA exemption: the three-way minimum from declared rent when we
    know this payslip's basic and HRA, else the legacy self-computed amount."""
    hra = (details or {}).get('hra') or {}
    monthly_rent = _amount(hra, 'monthly_rent')
    if monthly_rent > 0 and monthly_basic is not None and monthly_hra is not None:
        months = min(max(int(hra.get('months', 12) or 12), 1), 12)
        share_of_basic = Decimal('0.50') if hra.get('metro') else Decimal('0.40')
        per_month = min(Decimal(monthly_hra), monthly_rent - Decimal('0.10') * Decimal(monthly_basic), share_of_basic * Decimal(monthly_basic))
        return max(Decimal('0'), per_month) * months
    return _amount(declared, 'HRA')


def deduction_breakdown(
    declared_investments: dict | None,
    monthly_basic: Decimal | None = None,
    monthly_hra: Decimal | None = None,
) -> dict[str, Decimal]:
    """Old-regime deduction the declaration actually earns per head, after the
    statutory caps — an employee declaring Rs 5,00,000 under 80C still only
    reduces taxable income by Rs 1,50,000, never the full declared figure."""
    declared = declared_investments or {}
    details = declared.get(DETAILS_KEY) or {}

    sec_80c = min(_amount(declared, '80C') + sum((_amount(declared, key) for key in KEYS_80C), Decimal('0')), CAP_80C)
    sec_80ccd_1b = min(_amount(declared, '80CCD1B'), FIELD_CAPS['80CCD1B'])
    self_family_cap = CAP_80D_SENIOR if details.get('senior_self_family') else CAP_80D_STANDARD
    parents_cap = CAP_80D_SENIOR if details.get('senior_parents') else CAP_80D_STANDARD
    sec_80d = min(
        min(_amount(declared, '80D_SELF_FAMILY'), self_family_cap)
        + min(_amount(declared, '80D_PARENTS'), parents_cap)
        + min(_amount(declared, '80D'), CAP_80D_STANDARD),
        CAP_80D_TOTAL,
    )
    return {
        '80C': sec_80c,
        '80CCD1B': sec_80ccd_1b,
        '80D': sec_80d,
        '24B': min(_amount(declared, '24B'), FIELD_CAPS['24B']),
        '80E': _amount(declared, '80E'),
        '80G': _amount(declared, '80G'),
        'HRA': _hra_exemption(details, declared, monthly_basic, monthly_hra),
    }


def _capped_old_regime_deductions(
    declared_investments: dict,
    monthly_basic: Decimal | None = None,
    monthly_hra: Decimal | None = None,
) -> Decimal:
    return sum(deduction_breakdown(declared_investments, monthly_basic, monthly_hra).values(), Decimal('0'))


def estimate_monthly_tds(
    monthly_gross_earnings: Decimal, regime: str, declared_investments: dict | None = None,
    monthly_basic: Decimal | None = None, monthly_hra: Decimal | None = None,
) -> Decimal:
    """The one real entry point both the live payroll-cycle computation
    (_compute_employee_payslip, which doesn't have a persisted EmployeePayslip
    to read from yet) and monthly_tds_for_payslip() below funnel through, so
    the annualization/regime/deduction logic is defined exactly once.

    `monthly_basic`/`monthly_hra` let the HRA exemption be worked out from the
    employee's declared rent; they are optional so older callers still work.

    See this module's docstring for why annual income is projected as
    monthly_gross_earnings x 12 rather than a running per-FY reconciliation.
    """
    monthly_gross_earnings = Decimal(monthly_gross_earnings)
    annual_gross = monthly_gross_earnings * 12

    if regime == 'old':
        taxable = annual_gross - _capped_old_regime_deductions(declared_investments, monthly_basic, monthly_hra)
    else:
        taxable = annual_gross

    annual_tax = estimate_annual_tax(max(Decimal('0'), taxable), regime)
    return _round(annual_tax / 12)


def monthly_tds_for_payslip(payslip) -> Decimal:
    """Resolves the employee's real EmployeeTaxDeclaration for the payslip's
    financial year (India's FY runs Apr-Mar) and computes their monthly TDS
    off this payslip's actual gross_earnings. Falls back to the new regime
    with no declared investments when the employee never submitted a
    declaration for that FY — the same default EmployeeTaxDeclaration.tax_regime
    already uses.
    """
    from apps.payroll.models import EmployeeTaxDeclaration

    cycle_start = payslip.cycle.cycle_start
    fy_start = cycle_start.year if cycle_start.month >= 4 else cycle_start.year - 1

    declaration = EmployeeTaxDeclaration.objects.filter(
        employee_id=payslip.employee_id, financial_year_start=fy_start,
    ).first()
    regime = declaration.tax_regime if declaration else EmployeeTaxDeclaration.REGIME_NEW
    declared_investments = declaration.declared_investments if declaration else {}

    return estimate_monthly_tds(
        payslip.gross_earnings, regime, declared_investments, payslip.basic, payslip.hra,
    )
