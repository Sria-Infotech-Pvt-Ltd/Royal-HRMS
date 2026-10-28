"""
CTC breakdown ESTIMATE for the Hire wizard's "Basic pay" step — deliberately
separate from apps.payroll.views.cycles._compute_employee_payslip (the real
payroll engine, which only ever runs inside a real PayrollCycle with actual
attendance/LOP/adjustment data). This trades that precision for something
_compute_employee_payslip can't do at all: producing numbers before the
employee, a payroll cycle, or even a month of attendance exists.

The real, authoritative monthly payslip is still computed later, for real,
by the actual payroll cycle — this is purely a preview so a hiring manager
can see a plausible breakdown before committing to a CTC figure.
"""
from decimal import Decimal

from apps.payroll.models import BranchPayrollConfig, PayrollSettings, SalaryComponent
# Phase 7A Task A — read the one source of truth (apps.payroll.engine.legacy)
# instead of duplicating these two values under a second name here; values
# are unchanged (12.00 / 15000.00), only the duplication is removed.
from apps.payroll.engine.legacy import _PF_DEFAULT_RATE, _PF_DEFAULT_CEILING
# Fixed-point convergence: Annual CTC, by definition, already INCLUDES the
# employer's PF/EPS/gratuity/ESI contributions — it is not the same figure
# as gross earnings. Gross earnings must be solved for such that
# gross + employer_contributions(gross) == the entered CTC, not assumed
# to equal it outright (that was the bug: entering 6,00,000 produced an
# "Annual cost to company" of 6,48,138 — the employer contributions were
# added ON TOP of the full entered CTC instead of being carved out of it).
# The relationship is monotonic and near-linear (employer contributions are
# a roughly-fixed percentage of gross, with one ceiling-driven kink), so a
# few iterations of "scale gross by target/actual" converges to well under
# a rupee — no closed-form per-case algebra needed, and it stays correct
# regardless of whether a real SalaryStructure or the flat default split
# is used.
_MAX_ITERATIONS = 8
_CONVERGENCE_TOLERANCE = Decimal('0.01')


def _resolve_override(overrides, component):
    """overrides is keyed by SalaryComponent id (new convention) or a legacy
    fixed-breakup code (basic/hra/...) matched by component name — see
    EmployeeSalaryConfigSerializer.validate_earnings_override. Returns None
    when nothing overrides this component."""
    if not overrides:
        return None
    by_id = overrides.get(str(component.id))
    if by_id is not None:
        return by_id
    legacy_key = {
        'basic': 'basic', 'hra': 'hra', 'special allowance': 'special',
        'conveyance allowance': 'conv', 'medical allowance': 'med',
        'leave travel allowance': 'lta', 'dearness allowance': 'da',
    }.get(component.name.lower())
    return overrides.get(legacy_key) if legacy_key else None


def _compute_from_gross_basis(
    monthly_gross_basis, structure, is_metro, branch_config, eps_rate, gratuity_rate, statutory,
    overrides=None, basic_percent=None,
):
    """One forward pass: given a monthly gross-earnings basis, returns every
    earnings/employer-contribution figure this module produces. Pure
    function of monthly_gross_basis — used both for the final real answer
    and repeatedly during the reverse-solve below.

    `overrides` (optional, see _resolve_override) lets HR's Basic pay dialog
    override an individual component's amount without changing the
    structure itself — resolved per component, in structure `order`, so a
    CALC_BALANCE_CTC component downstream still balances AROUND an
    upstream override exactly as it would around that component's normal
    computed amount."""
    basic = Decimal('0')
    hra = Decimal('0')
    special_allowance = Decimal('0')
    other_earnings: dict[str, float] = {}
    other_earnings_total = Decimal('0')
    component_breakdown: list[dict] = []
    component_deductions_total = Decimal('0')

    components = list(structure.components.filter(is_active=True).order_by('order')) if structure else []
    if not components:
        # No structure picked yet — the same metro-HRA/remainder split
        # _compute_employee_payslip's own CALC_METRO_HRA formula uses, so
        # the preview isn't just a blank table before a structure exists.
        # basic_percent (the Basic pay dialog's own "Basic as % of CTC"
        # field, 40/45/50) drives Basic here — it has no effect once a real
        # structure's own components take over, same as it never did.
        pct = Decimal(str(basic_percent)) if basic_percent else Decimal('40')
        basic = monthly_gross_basis * pct / 100
        hra = basic * (Decimal('50') if is_metro else Decimal('40')) / 100
        special_allowance = monthly_gross_basis - basic - hra
    else:
        # Balance-to-CTC components are resolved in a second pass (they need
        # every other earning/allowance component's amount first); non-balance
        # components are computed in order below exactly as before.
        balance_components = []
        earning_allowance_total = Decimal('0')
        for component in components:
            override = _resolve_override(overrides, component)
            if override is not None:
                amount = Decimal(str(override))
            elif component.calculation_type == SalaryComponent.CALC_PCT_CTC:
                # Despite the name, this is a % of the resolved GROSS basis,
                # not of the raw entered CTC figure — CALC_PCT_CTC components
                # are computed the same way _compute_employee_payslip's real
                # engine computes them (relative to the structure's own
                # earnings total), so the reverse-solve loop around this
                # function converges on the true CTC-inclusive figure either way.
                amount = monthly_gross_basis * component.value / 100
            elif component.calculation_type == SalaryComponent.CALC_PCT_BASIC:
                amount = basic * component.value / 100
            elif component.calculation_type == SalaryComponent.CALC_METRO_HRA:
                metro_pct = Decimal('50') if is_metro else Decimal('40')
                amount = basic * metro_pct / 100
            elif component.calculation_type == SalaryComponent.CALC_BALANCE_CTC:
                balance_components.append(component)
                continue
            else:
                amount = component.value

            # A structure's deduction-type component (e.g. a loan recovery
            # line) is not part of earnings/gross — it reduces net pay the
            # same way PF/ESI/PT already do, via component_deductions_total,
            # never via other_earnings (which would otherwise have silently
            # inflated gross by a component that's supposed to shrink net).
            if component.component_type == SalaryComponent.TYPE_DEDUCTION:
                component_deductions_total += amount
            else:
                name_lower = component.name.lower()
                if name_lower == 'basic':
                    basic = amount
                elif name_lower == 'hra':
                    hra = amount
                elif name_lower == 'special allowance':
                    special_allowance = amount
                else:
                    other_earnings[component.name] = float(amount)
                    other_earnings_total += amount
                earning_allowance_total += amount
            component_breakdown.append({
                'id': str(component.id), 'name': component.name,
                'component_type': component.component_type, 'is_taxable': component.is_taxable,
                'calculation_type': component.calculation_type, 'amount': float(amount),
            })

        if balance_components:
            # Split the remainder evenly across every balance component in
            # this structure — in practice there is exactly one (the
            # Special-Allowance-equivalent "soaks up what's left" role), but
            # nothing stops an admin defining more than one.
            remainder = max(Decimal('0'), monthly_gross_basis - earning_allowance_total)
            share = remainder / len(balance_components)
            for component in balance_components:
                override = _resolve_override(overrides, component)
                amount = Decimal(str(override)) if override is not None else share
                name_lower = component.name.lower()
                if name_lower == 'special allowance':
                    special_allowance = amount
                else:
                    other_earnings[component.name] = float(amount)
                    other_earnings_total += amount
                component_breakdown.append({
                    'id': str(component.id), 'name': component.name,
                    'component_type': component.component_type, 'is_taxable': component.is_taxable,
                    'calculation_type': component.calculation_type, 'amount': float(amount),
                })

        # Balance components were appended last regardless of their own
        # `order` relative to the others — restore the structure's real order.
        if balance_components:
            order_by_id = {str(c.id): i for i, c in enumerate(components)}
            component_breakdown.sort(key=lambda row: order_by_id[row['id']])

    gross = basic + hra + special_allowance + other_earnings_total

    pf_applicable = branch_config.pf_applicable if branch_config is not None else True
    pf_wage_base = Decimal('0')
    pf_employee = Decimal('0')
    pf_employer = Decimal('0')
    employer_eps = Decimal('0')
    gratuity_provision = Decimal('0')
    if pf_applicable:
        pf_ceiling  = branch_config.pf_wage_ceiling  if branch_config else _PF_DEFAULT_CEILING
        pf_emp_rate = branch_config.pf_employee_rate if branch_config else _PF_DEFAULT_RATE
        pf_er_rate  = branch_config.pf_employer_rate if branch_config else _PF_DEFAULT_RATE
        pf_wage_base = min(basic, pf_ceiling)
        pf_employee = pf_wage_base * pf_emp_rate / 100
        # QA report #47 — EPS is not an ADDITIONAL employer contribution on
        # top of the employer's 12% PF share, it's carved OUT of it (the
        # statutory 12% employer contribution splits into 8.33% to EPS and
        # the remainder to the employee's own PF account). Showing both
        # "Employer PF" at the full pf_er_rate AND "EPS" at eps_rate
        # double-counted EPS. "Employer PF" here is now only the
        # non-EPS remainder, so pf_employer + employer_eps together still
        # equal the true total employer PF-side contribution.
        employer_eps = pf_wage_base * eps_rate / 100
        pf_employer = pf_wage_base * max(pf_er_rate - eps_rate, Decimal('0')) / 100
        gratuity_provision = basic * gratuity_rate / 100

    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    if statutory and statutory.esi_applicable and gross <= statutory.esi_wage_ceiling:
        esi_employer = gross * statutory.esi_employer_rate / 100
        if (gross / 30) > Decimal('176'):
            esi_employee = gross * statutory.esi_employee_rate / 100

    pt = Decimal(str(statutory.compute_pt(gross))) if statutory else Decimal('0')

    total_deductions = pf_employee + esi_employee + pt + component_deductions_total
    net_pay = gross - total_deductions
    total_employer_contributions = pf_employer + employer_eps + gratuity_provision + esi_employer
    monthly_cost_to_company = gross + total_employer_contributions

    return {
        'basic': basic, 'hra': hra, 'special_allowance': special_allowance,
        'other_earnings': other_earnings, 'other_earnings_total': other_earnings_total,
        'gross': gross,
        'pf_employer': pf_employer, 'employer_eps': employer_eps,
        'gratuity_provision': gratuity_provision, 'esi_employer': esi_employer,
        'pf_employee': pf_employee, 'esi_employee': esi_employee, 'pt': pt,
        'total_deductions': total_deductions, 'net_pay': net_pay,
        'total_employer_contributions': total_employer_contributions,
        'monthly_cost_to_company': monthly_cost_to_company,
        'component_breakdown': component_breakdown,
    }


def estimate_salary_breakdown(annual_ctc, structure, branch, statutory, overrides=None, basic_percent=None) -> dict:
    """annual_ctc: Decimal-able, the TRUE cost-to-company ceiling (already
    includes employer PF/EPS/gratuity/ESI — never treated as gross
    earnings). structure: SalaryStructure or None (falls back to a flat 40%
    Basic / 40% HRA-of-basic / remainder Special Allowance split — the same
    default the mockup itself shows — when no structure is picked yet).
    branch/statutory: Branch/StatutoryConfig or None. overrides: optional
    dict, see _resolve_override — lets the Basic pay dialog override an
    individual component's amount without touching the structure itself."""
    annual_ctc = Decimal(str(annual_ctc))
    target_monthly_ctc = annual_ctc / 12
    is_metro = bool(branch and branch.is_metro)
    branch_config = BranchPayrollConfig.objects.filter(branch=branch).first() if branch else None
    payroll_settings = PayrollSettings.objects.first()
    eps_rate = payroll_settings.eps_rate if payroll_settings else Decimal('8.33')
    gratuity_rate = payroll_settings.gratuity_rate if payroll_settings else Decimal('4.81')

    # Reverse-solve: find the monthly gross-earnings basis whose resulting
    # monthly_cost_to_company converges to target_monthly_ctc. Start from
    # the naive "gross == CTC" guess (a slight overestimate of the true
    # gross, since real employer contributions still need to be carved out
    # of it) and scale down each pass by how far off the last guess was.
    gross_basis_guess = target_monthly_ctc
    result = None
    for _ in range(_MAX_ITERATIONS):
        result = _compute_from_gross_basis(
            gross_basis_guess, structure, is_metro, branch_config, eps_rate, gratuity_rate, statutory,
            overrides=overrides, basic_percent=basic_percent,
        )
        actual = result['monthly_cost_to_company']
        if actual == 0:
            break
        diff = target_monthly_ctc - actual
        if abs(diff) <= _CONVERGENCE_TOLERANCE:
            break
        gross_basis_guess = gross_basis_guess * (target_monthly_ctc / actual)

    monthly_cost_to_company = result['monthly_cost_to_company']

    return {
        'basic':                        float(result['basic']),
        'hra':                          float(result['hra']),
        'special_allowance':            float(result['special_allowance']),
        'other_earnings':               result['other_earnings'],
        'gross_earnings':               float(result['gross']),
        'employer_pf':                  float(result['pf_employer']),
        'employer_eps':                 float(result['employer_eps']),
        'gratuity_provision':           float(result['gratuity_provision']),
        'employer_esi':                 float(result['esi_employer']),
        'total_employer_contributions': float(result['total_employer_contributions']),
        'employee_pf':                  float(result['pf_employee']),
        'employee_esi':                 float(result['esi_employee']),
        'pt_deduction':                 float(result['pt']),
        'total_deductions':             float(result['total_deductions']),
        'monthly_cost_to_company':      float(monthly_cost_to_company),
        'annual_cost_to_company':       float(monthly_cost_to_company * 12),
        'net_pay':                      float(result['net_pay']),
        # Generic per-component list (id/name/type/taxable/calc_type/amount)
        # for a structure-driven dialog to render arbitrary admin-defined
        # components — empty when no structure is picked (the flat-split
        # fallback above has no individual SalaryComponent rows to list).
        'component_breakdown':          result['component_breakdown'],
    }
