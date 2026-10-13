"""
Phase 7A Task K — a "what-if" preview on the new engine: CTC x structure x
location -> monthly/annual breakup + statutory + tax estimate, with a
trace, explicitly labelled as an estimate.

Reuses services_shadow_engine.compute_payslip_via_new_data() directly — a
what-if is exactly that composer with no employee, no LOP, and no
adjustments (annual_ctc and a structure/location are the only real
inputs), so this is a thin, honest wrapper rather than a second
computation path to keep in sync.

NOT wired into services_estimate.py's live Hire-wizard preview endpoint —
that module does its own reverse-solve (CTC -> gross, iteratively, see its
own module docstring) for a genuinely different purpose, and real estimate
behavior used by an in-production wizard should not change as a side
effect of this task. This function is additive and stands alone, proven
correct by its own tests; actually swapping it in is deferred, same as
every other live-engine cutover in this phase (that's Task J's job, behind
payroll.v2, not Task K's).
"""
from decimal import Decimal
from types import SimpleNamespace

from apps.payroll.models import SalaryStructure
from apps.payroll.services_shadow_engine import compute_payslip_via_new_data


def what_if_salary_breakdown(
    annual_ctc: Decimal, legacy_structure: SalaryStructure, *,
    branch_config=None, statutory_state=None, is_metro: bool = False,
    tax_regime: str = 'new', declared_investments: dict | None = None,
    financial_year_start: int = 2026,
) -> dict:
    """Pure preview — no employee, no cycle, no write. `legacy_structure`
    is bridged the same way the Task J shadow run bridges a real payslip's
    structure, so a what-if for the same CTC/structure/location as a real
    employee produces the identical numbers a real payslip would (modulo
    LOP and one-time adjustments, which a what-if has none of by design)."""
    annual_ctc = Decimal(annual_ctc)
    salary_config = SimpleNamespace(monthly_ctc=annual_ctc / 12, annual_ctc=annual_ctc)

    monthly = compute_payslip_via_new_data(
        salary_config, legacy_structure, branch_config, statutory_state, adjustments=[],
        lop_days=Decimal('0'), total_working_days=26, cycle_month=None,
        esi_covered_earlier_this_period=False, proration_factor=Decimal('1'),
        is_metro=is_metro, tax_regime=tax_regime, declared_investments=declared_investments,
        financial_year_start=financial_year_start,
    )

    return {
        'is_estimate': True,
        'estimate_note': (
            'Estimate only — not a real payslip. Assumes a full working month with no '
            'Loss-of-Pay and no one-time adjustments; the real monthly payslip is still '
            'computed later, for real, by payroll processing.'
        ),
        'structure_code': legacy_structure.name,
        'annual_ctc': annual_ctc,
        'monthly_ctc': salary_config.monthly_ctc,
        'is_metro': is_metro,
        'tax_regime': tax_regime,
        'monthly_breakdown': {
            'basic': monthly['basic'], 'hra': monthly['hra'], 'special_allowance': monthly['special_allowance'],
            'other_earnings': monthly['other_earnings'],
            'gross_earnings': monthly['gross_earnings'],
            'pf_employee': monthly['pf_employee'], 'pf_employer': monthly['pf_employer'],
            'esi_employee': monthly['esi_employee'], 'esi_employer': monthly['esi_employer'],
            'pt_deduction': monthly['pt_deduction'],
            'lwf_employee': monthly['lwf_employee'], 'lwf_employer': monthly['lwf_employer'],
            'income_tax': monthly['income_tax'],
            'net_pay': monthly['net_pay'],
        },
        'annual_breakdown': {
            key: value * 12 for key, value in monthly.items()
            if key in ('basic', 'hra', 'special_allowance', 'gross_earnings', 'net_pay',
                       'pf_employee', 'pf_employer', 'income_tax')
        },
    }
