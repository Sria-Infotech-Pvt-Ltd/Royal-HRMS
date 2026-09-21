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

_PF_DEFAULT_RATE = Decimal('12.00')
_PF_DEFAULT_CEILING = Decimal('15000.00')


def estimate_salary_breakdown(annual_ctc, structure, branch, statutory) -> dict:
    """annual_ctc: Decimal-able. structure: SalaryStructure or None (falls back
    to a flat 40% Basic / 40% HRA-of-basic / remainder Special Allowance split
    — the same default the mockup itself shows — when no structure is picked
    yet). branch/statutory: Branch/StatutoryConfig or None."""
    annual_ctc = Decimal(str(annual_ctc))
    monthly_ctc = annual_ctc / 12
    is_metro = bool(branch and branch.is_metro)
    branch_config = BranchPayrollConfig.objects.filter(branch=branch).first() if branch else None

    basic = Decimal('0')
    hra = Decimal('0')
    special_allowance = Decimal('0')
    other_earnings: dict[str, float] = {}
    other_earnings_total = Decimal('0')

    components = list(structure.components.filter(is_active=True).order_by('order')) if structure else []
    if not components:
        # No structure picked yet — the same 40%/metro-HRA/remainder split
        # _compute_employee_payslip's own CALC_METRO_HRA formula uses,
        # so the preview isn't just a blank table before a structure exists.
        basic = monthly_ctc * Decimal('40') / 100
        hra = basic * (Decimal('50') if is_metro else Decimal('40')) / 100
        special_allowance = monthly_ctc - basic - hra
    else:
        for component in components:
            if component.calculation_type == SalaryComponent.CALC_PCT_CTC:
                amount = monthly_ctc * component.value / 100
            elif component.calculation_type == SalaryComponent.CALC_PCT_BASIC:
                amount = basic * component.value / 100
            elif component.calculation_type == SalaryComponent.CALC_METRO_HRA:
                metro_pct = Decimal('50') if is_metro else Decimal('40')
                amount = basic * metro_pct / 100
            else:
                amount = component.value

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

    gross = basic + hra + special_allowance + other_earnings_total

    pf_applicable = branch_config.pf_applicable if branch_config is not None else True
    pf_wage_base = Decimal('0')
    pf_employee = Decimal('0')
    pf_employer = Decimal('0')
    payroll_settings = PayrollSettings.objects.first()
    eps_rate = payroll_settings.eps_rate if payroll_settings else Decimal('8.33')
    gratuity_rate = payroll_settings.gratuity_rate if payroll_settings else Decimal('4.81')
    employer_eps = Decimal('0')
    gratuity_provision = Decimal('0')
    if pf_applicable:
        pf_ceiling  = branch_config.pf_wage_ceiling  if branch_config else _PF_DEFAULT_CEILING
        pf_emp_rate = branch_config.pf_employee_rate if branch_config else _PF_DEFAULT_RATE
        pf_er_rate  = branch_config.pf_employer_rate if branch_config else _PF_DEFAULT_RATE
        pf_wage_base = min(basic, pf_ceiling)
        pf_employee = pf_wage_base * pf_emp_rate / 100
        pf_employer = pf_wage_base * pf_er_rate / 100
        employer_eps = min(basic, pf_ceiling) * eps_rate / 100
        gratuity_provision = basic * gratuity_rate / 100

    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    if statutory and statutory.esi_applicable and gross <= statutory.esi_wage_ceiling:
        esi_employer = gross * statutory.esi_employer_rate / 100
        if (gross / 30) > Decimal('176'):
            esi_employee = gross * statutory.esi_employee_rate / 100

    pt = Decimal(str(statutory.compute_pt(gross))) if statutory else Decimal('0')

    total_deductions = pf_employee + esi_employee + pt
    net_pay = gross - total_deductions
    total_employer_contributions = pf_employer + employer_eps + gratuity_provision + esi_employer
    monthly_cost_to_company = gross + pf_employer + employer_eps + gratuity_provision + esi_employer

    return {
        'basic':                        float(basic),
        'hra':                          float(hra),
        'special_allowance':            float(special_allowance),
        'other_earnings':               other_earnings,
        'gross_earnings':               float(gross),
        'employer_pf':                  float(pf_employer),
        'employer_eps':                 float(employer_eps),
        'gratuity_provision':           float(gratuity_provision),
        'employer_esi':                 float(esi_employer),
        'total_employer_contributions': float(total_employer_contributions),
        'employee_pf':                  float(pf_employee),
        'employee_esi':                 float(esi_employee),
        'pt_deduction':                 float(pt),
        'total_deductions':             float(total_deductions),
        'monthly_cost_to_company':      float(monthly_cost_to_company),
        'annual_cost_to_company':       float(monthly_cost_to_company * 12),
        'net_pay':                      float(net_pay),
    }
