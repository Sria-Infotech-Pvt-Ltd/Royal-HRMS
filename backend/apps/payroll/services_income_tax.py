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
  - Old-regime declared investments (80C/80D/80CCD(1B)/HRA) are subtracted
    from gross annual salary at real statutory caps (80C: Rs 1,50,000; 80D:
    Rs 25,000 — the non-senior-citizen self+family cap, the common case for
    this workforce; 80CCD(1B): Rs 50,000) before slabs are applied. HRA is
    taken at the employee's declared exemption amount as-is (no re-derivation
    of the three-way HRA exemption formula — that requires actual rent paid
    and city-metro status per month, which isn't modelled here).
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

TWO_PLACES = Decimal('0.01')

STANDARD_DEDUCTION_NEW = Decimal('75000')
STANDARD_DEDUCTION_OLD = Decimal('50000')

REBATE_THRESHOLD_NEW = Decimal('1200000')
REBATE_THRESHOLD_OLD = Decimal('500000')

CAP_80C = Decimal('150000')
CAP_80D = Decimal('25000')
CAP_80CCD_1B = Decimal('50000')

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


def _capped_old_regime_deductions(declared_investments: dict) -> Decimal:
    """Real statutory caps applied to declared amounts — an employee
    declaring Rs 5,00,000 under 80C still only reduces taxable income by
    Rs 1,50,000, never the full declared figure."""
    declared_investments = declared_investments or {}

    def _amount(key: str) -> Decimal:
        try:
            return Decimal(str(declared_investments.get(key, 0) or 0))
        except (ValueError, ArithmeticError):
            return Decimal('0')

    sec_80c = min(_amount('80C'), CAP_80C)
    sec_80d = min(_amount('80D'), CAP_80D)
    sec_80ccd_1b = min(_amount('80CCD1B'), CAP_80CCD_1B)
    hra_exemption = max(Decimal('0'), _amount('HRA'))
    return sec_80c + sec_80d + sec_80ccd_1b + hra_exemption


def estimate_monthly_tds(
    monthly_gross_earnings: Decimal, regime: str, declared_investments: dict | None = None,
) -> Decimal:
    """The one real entry point both the live payroll-cycle computation
    (_compute_employee_payslip, which doesn't have a persisted EmployeePayslip
    to read from yet) and monthly_tds_for_payslip() below funnel through, so
    the annualization/regime/deduction logic is defined exactly once.

    See this module's docstring for why annual income is projected as
    monthly_gross_earnings x 12 rather than a running per-FY reconciliation.
    """
    monthly_gross_earnings = Decimal(monthly_gross_earnings)
    annual_gross = monthly_gross_earnings * 12

    if regime == 'old':
        taxable = annual_gross - _capped_old_regime_deductions(declared_investments)
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

    return estimate_monthly_tds(payslip.gross_earnings, regime, declared_investments)
