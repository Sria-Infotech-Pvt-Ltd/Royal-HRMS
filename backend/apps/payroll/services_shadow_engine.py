"""
Phase 7A Task J — the composer: a real function that assembles a full
payslip computation from the Tasks B/C/F/G data (PayStructure,
StatutoryRate, TaxYearConfig) instead of SalaryComponent/StatutoryConfig/
hardcoded tax constants, returning the EXACT SAME dict shape as
apps.payroll.engine.legacy._compute_employee_payslip — so the two can be
diffed field-by-field for identical inputs.

`get_or_create_pay_structure_for_legacy()` is the bridge: given a real
SalaryStructure, it builds (once, idempotently) a matching PayStructure +
PayStructureComponent rows, so the shadow run can exercise Task C's
formula-graph engine against structures that actually exist today, without
requiring every employee to already have an EmployeeCompensation row
(Task D's dual-write only covers compensation created from now on — see
that task's own documented limitation).

Still not wired into real payroll processing. This is the shadow-only
composer Task J's parity check runs against; apps.payroll.engine.legacy
remains the only thing that writes a real EmployeePayslip.
"""
from decimal import Decimal

from apps.payroll.models import BranchPayrollConfig, PayStructure, PayStructureComponent, SalaryComponent, StatutoryRate
from apps.payroll.services_pay_structure import evaluate_structure
from apps.payroll.services_tax_engine import compute_monthly_tds


# ── Bridge: legacy SalaryStructure -> Task C PayStructure ───────────────

_LEGACY_CALC_TYPE_TO_METHOD = {
    SalaryComponent.CALC_PCT_CTC: 'percentage',
    SalaryComponent.CALC_PCT_BASIC: 'percentage',
    SalaryComponent.CALC_FIXED: 'fixed',
    SalaryComponent.CALC_METRO_HRA: 'metro_hra_of_basic',
}
_LEGACY_CALC_TYPE_TO_BASE = {
    SalaryComponent.CALC_PCT_CTC: 'CTC_MONTHLY',
    SalaryComponent.CALC_PCT_BASIC: 'BASIC',
    SalaryComponent.CALC_METRO_HRA: 'BASIC',
}


def _code_for_component_name(name: str) -> str:
    name_lower = name.strip().lower()
    if name_lower == 'basic':
        return 'BASIC'
    if name_lower == 'hra':
        return 'HRA'
    if name_lower == 'special allowance':
        return 'SPECIAL'
    import re
    return 'CUSTOM_' + re.sub(r'[^A-Z0-9]+', '_', name.strip().upper()).strip('_')


def get_or_create_pay_structure_for_legacy(structure) -> PayStructure:
    """Idempotent — re-running finds the same bridged PayStructure (keyed
    by a deterministic code derived from the legacy structure's id) rather
    than creating a duplicate each shadow run."""
    code = f'LB:{structure.id}'
    pay_structure, _ = PayStructure.objects.get_or_create(
        code=code, defaults={'name': f'Bridged from {structure.name}', 'status': PayStructure.STATUS_PUBLISHED},
    )

    legacy_components = list(structure.components.filter(is_active=True).order_by('order'))
    seen_codes = set()
    for order, component in enumerate(legacy_components):
        comp_code = _code_for_component_name(component.name)
        seen_codes.add(comp_code)
        PayStructureComponent.objects.update_or_create(
            structure=pay_structure, component_code=comp_code,
            defaults={
                'calculation_method': _LEGACY_CALC_TYPE_TO_METHOD.get(component.calculation_type, 'fixed'),
                'base_component_code': _LEGACY_CALC_TYPE_TO_BASE.get(component.calculation_type, ''),
                'value': component.value,
                'order': order,
            },
        )
    # Drop any bridged rows for components no longer active on the legacy
    # structure (e.g. a component was deactivated since the last bridge run).
    pay_structure.structure_components.exclude(component_code__in=seen_codes).delete()

    return pay_structure


# ── Statutory resolution against Task F's StatutoryRate ─────────────────

def _resolve_rate(scheme_code: str, state):
    rate = None
    if state is not None:
        rate = StatutoryRate.objects.filter(scheme__code=scheme_code, state=state, is_active=True).first()
    if rate is None:
        rate = StatutoryRate.objects.filter(scheme__code=scheme_code, state=None, is_active=True).first()
    return rate.parameters if rate else None


def _pt_from_slabs(gross: Decimal, slabs: list) -> Decimal:
    gross_f = float(gross)
    for slab in slabs:
        min_val = slab.get('min', 0)
        max_val = slab.get('max')
        amount = slab.get('amount', 0)
        if max_val is None:
            if gross_f >= min_val:
                return Decimal(str(amount))
        elif min_val <= gross_f <= max_val:
            return Decimal(str(amount))
    return Decimal('0')


def _lwf_due(parameters: dict, cycle_month) -> bool:
    frequency = parameters.get('frequency')
    if frequency == 'monthly':
        return True
    return cycle_month in (parameters.get('due_months') or [])


# ── The composer ─────────────────────────────────────────────────────────

def compute_payslip_via_new_data(
    salary_config, legacy_structure, branch_config, statutory_state, adjustments,
    lop_days=Decimal('0'), total_working_days=26, cycle_month=None,
    esi_covered_earlier_this_period=False, proration_factor=Decimal('1'),
    is_metro=False, tax_regime='new', declared_investments=None,
    financial_year_start=2026,
) -> dict:
    """Same signature shape as apps.payroll.engine.legacy._compute_employee_payslip
    (statutory_state replaces `statutory` — a State object instead of a
    StatutoryConfig row, since Task F's data is resolved by state, not by
    a single config row) and the SAME return dict shape, for direct
    field-by-field diffing."""
    from apps.payroll.models import PayrollAdjustment, EmployeePayslip

    pay_structure = get_or_create_pay_structure_for_legacy(legacy_structure)
    monthly_breakdown = evaluate_structure(pay_structure, salary_config.monthly_ctc, is_metro=is_metro)

    legacy_name_by_code = {
        _code_for_component_name(c.name): c.name
        for c in legacy_structure.components.filter(is_active=True)
    }

    if proration_factor != Decimal('1'):
        monthly_breakdown = {code: amt * proration_factor for code, amt in monthly_breakdown.items()}

    basic = monthly_breakdown.get('BASIC', Decimal('0'))
    hra = monthly_breakdown.get('HRA', Decimal('0'))
    special_allowance = monthly_breakdown.get('SPECIAL', Decimal('0'))
    other_earnings = {}
    other_earnings_total = Decimal('0')
    for code, amount in monthly_breakdown.items():
        if code in ('BASIC', 'HRA', 'SPECIAL'):
            continue
        name = legacy_name_by_code.get(code, code)
        other_earnings[name] = float(amount)
        other_earnings_total += amount

    gross = basic + hra + special_allowance + other_earnings_total
    lop_deduction = (gross / total_working_days) * lop_days if total_working_days else Decimal('0')

    # PF — branch_config override takes the same priority as legacy; the
    # company-wide default now comes from StatutoryRate('PF', state=None)
    # instead of the hardcoded _PF_DEFAULT_RATE/_PF_DEFAULT_CEILING.
    pf_applicable = branch_config.pf_applicable if branch_config is not None else True
    pf_employee = Decimal('0')
    pf_employer = Decimal('0')
    pf_wage_base = Decimal('0')
    if pf_applicable:
        pf_default = _resolve_rate('PF', None) or {'employee_rate': '12.00', 'employer_rate': '12.00', 'wage_ceiling': '15000.00'}
        pf_ceiling = branch_config.pf_wage_ceiling if branch_config else Decimal(pf_default['wage_ceiling'])
        pf_emp_rate = branch_config.pf_employee_rate if branch_config else Decimal(pf_default['employee_rate'])
        pf_er_rate = branch_config.pf_employer_rate if branch_config else Decimal(pf_default['employer_rate'])
        pf_wage_basis = branch_config.pf_wage_basis if branch_config else BranchPayrollConfig.PF_WAGE_BASIC_ONLY
        if pf_wage_basis == BranchPayrollConfig.PF_WAGE_BASIC_PLUS_ALLOWANCES:
            uncapped_pf_wage = basic + special_allowance + other_earnings_total
        else:
            uncapped_pf_wage = basic
        pf_wage_base = min(uncapped_pf_wage, pf_ceiling)
        pf_employee = pf_wage_base * pf_emp_rate / 100
        pf_employer = pf_wage_base * pf_er_rate / 100

    # ESI
    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    esi_params = _resolve_rate('ESI', statutory_state)
    if esi_params and (gross <= Decimal(esi_params['wage_ceiling']) or esi_covered_earlier_this_period):
        esi_employer = gross * Decimal(esi_params['employer_rate']) / 100
        days_paid = max(Decimal('1'), Decimal(total_working_days) - lop_days)
        daily_wage = gross / days_paid
        if daily_wage > Decimal('176'):
            esi_employee = gross * Decimal(esi_params['employee_rate']) / 100

    # PT
    pt_params = _resolve_rate('PT', statutory_state)
    pt = _pt_from_slabs(gross, pt_params['slabs']) if pt_params else Decimal('0')

    # LWF
    lwf_params = _resolve_rate('LWF', statutory_state)
    lwf_employee = Decimal('0')
    lwf_employer = Decimal('0')
    if lwf_params and _lwf_due(lwf_params, cycle_month):
        lwf_employee = Decimal(lwf_params['employee_amount'])
        lwf_employer = Decimal(lwf_params['employer_amount'])

    adj_earning = sum(
        (a.amount for a in adjustments if a.type in (PayrollAdjustment.ADDITION, PayrollAdjustment.ARREAR)),
        Decimal('0'),
    )
    adj_deduction = sum(
        (a.amount for a in adjustments if a.type == PayrollAdjustment.DEDUCTION),
        Decimal('0'),
    )

    income_tax = compute_monthly_tds(gross, tax_regime, declared_investments, financial_year_start)

    total_deductions = lop_deduction + pf_employee + esi_employee + pt + lwf_employee + income_tax + adj_deduction
    net_pay = gross + adj_earning - total_deductions

    return {
        'salary_structure': legacy_structure,
        'annual_ctc': salary_config.annual_ctc,
        'monthly_ctc': salary_config.monthly_ctc,
        'basic': basic,
        'hra': hra,
        'special_allowance': special_allowance,
        'other_earnings': other_earnings,
        'reimbursements': Decimal('0'),
        'bonus': Decimal('0'),
        'gross_earnings': gross,
        'total_working_days': total_working_days,
        'lop_days': lop_days,
        'lop_deduction': lop_deduction,
        'pf_wage_base': pf_wage_base,
        'pf_employee': pf_employee,
        'pf_employer': pf_employer,
        'esi_employee': esi_employee,
        'esi_employer': esi_employer,
        'pt_deduction': pt,
        'lwf_employee': lwf_employee,
        'lwf_employer': lwf_employer,
        'income_tax': income_tax,
        'adjustments_earning': adj_earning,
        'adjustments_deduction': adj_deduction,
        'total_deductions': total_deductions,
        'net_pay': net_pay,
        'status': EmployeePayslip.STATUS_DRAFT,
    }
