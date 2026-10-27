"""
Phase 7A Task E — the documented mapping from fixed EmployeePayslip columns
to PayslipLine rows, plus persistence and YTD computation.

Column -> component_code mapping (every fixed column this company's payslip
actually has today):
    basic                 -> BASIC
    hra                   -> HRA
    special_allowance     -> SPECIAL
    other_earnings[name]  -> OTHER:<slugified name> (one line per entry —
                             these are free-text today, no PayComponent row
                             exists per custom name, so the line is tagged
                             with a derived code rather than invented as a
                             new catalogue entry on the fly)
    reimbursements        -> REIMB
    bonus                 -> BONUS
    pf_employee           -> PF_EE
    pf_employer           -> PF_ER
    esi_employee          -> ESI_EE
    esi_employer          -> ESI_ER
    pt_deduction          -> PT
    lwf_employee          -> LWF_EE
    lwf_employer          -> LWF_ER
    income_tax            -> TDS
    adjustments_earning   -> ADJ_EARN
    adjustments_deduction -> ADJ_DED
    gross_earnings        -> GROSS_EARNINGS
    net_pay               -> NET_PAY

Zero-amount lines are skipped unless the matching PayComponent.show_if_zero
is True, or the code has no PayComponent row at all (custom other_earnings
entries always show — there's nothing to configure "hide if zero" for).
"""
import re
from decimal import Decimal

from django.db.models import Sum

from apps.payroll.models import PayComponent


def _slugify_component_name(name: str) -> str:
    return 'OTHER:' + re.sub(r'[^A-Z0-9]+', '_', name.strip().upper()).strip('_')


# (column_name, component_code) — order here IS display_order.
_SCALAR_COLUMN_MAP = [
    ('basic', 'BASIC'),
    ('hra', 'HRA'),
    ('special_allowance', 'SPECIAL'),
    ('reimbursements', 'REIMB'),
    ('bonus', 'BONUS'),
    ('gross_earnings', 'GROSS_EARNINGS'),
    ('lop_deduction', 'LOP'),
    ('pf_employee', 'PF_EE'),
    ('pf_employer', 'PF_ER'),
    ('esi_employee', 'ESI_EE'),
    ('esi_employer', 'ESI_ER'),
    ('pt_deduction', 'PT'),
    ('lwf_employee', 'LWF_EE'),
    ('lwf_employer', 'LWF_ER'),
    ('income_tax', 'TDS'),
    ('adjustments_earning', 'ADJ_EARN'),
    ('adjustments_deduction', 'ADJ_DED'),
    ('net_pay', 'NET_PAY'),
]

# Extra calculation_basis fields worth keeping alongside specific lines —
# not exhaustive, just enough for a human to see what the amount depended on.
_EXTRA_BASIS_FIELDS = {
    'PF_EE': ['pf_wage_base'],
    'PF_ER': ['pf_wage_base'],
    'LOP': ['lop_days', 'total_working_days'],
}


def build_lines_for_payslip(payslip) -> list:
    """Pure — no DB write. Returns a list of dicts shaped like
    PayslipLine field kwargs (minus `payslip`/`ytd_amount`, which the
    caller fills in)."""
    show_if_zero_by_code = {
        c.code: c.show_if_zero
        for c in PayComponent.objects.filter(
            code__in=[code for _, code in _SCALAR_COLUMN_MAP],
        )
    }

    lines = []
    for order, (column, code) in enumerate(_SCALAR_COLUMN_MAP):
        amount = getattr(payslip, column)
        if amount == 0 and not show_if_zero_by_code.get(code, False):
            continue
        basis = {'source': 'legacy_column', 'column': column}
        for extra in _EXTRA_BASIS_FIELDS.get(code, []):
            value = getattr(payslip, extra, None)
            if value is not None:
                basis[extra] = str(value)
        lines.append({
            'component_code': code, 'amount': amount,
            'calculation_basis': basis, 'display_order': order,
        })

    base_order = len(_SCALAR_COLUMN_MAP)
    for i, (name, amount) in enumerate(sorted((payslip.other_earnings or {}).items())):
        lines.append({
            'component_code': _slugify_component_name(name),
            'amount': Decimal(str(amount)),
            'calculation_basis': {'source': 'legacy_column', 'column': 'other_earnings', 'original_name': name},
            'display_order': base_order + i,
        })

    deduction_order = base_order + len(payslip.other_earnings or {})
    for i, (name, amount) in enumerate(sorted((payslip.other_deductions or {}).items())):
        lines.append({
            'component_code': 'DEDUCTION:' + re.sub(
                r'[^A-Z0-9]+', '_', name.strip().upper(),
            ).strip('_'),
            'amount': Decimal(str(amount)),
            'calculation_basis': {
                'source': 'legacy_column',
                'column': 'other_deductions',
                'original_name': name,
            },
            'display_order': deduction_order + i,
        })

    return lines


def _financial_year_start(cycle_start_date):
    return cycle_start_date.year if cycle_start_date.month >= 4 else cycle_start_date.year - 1


def persist_lines_for_payslip(payslip):
    """Writes PayslipLine rows for an already-computed EmployeePayslip,
    with YTD computed from previously-persisted lines for the same
    employee+component within the same financial year. Idempotent
    (delete+recreate this payslip's own lines) — safe to re-run after a
    reprocess.

    Ordering requirement: for YTD to be correct across a financial year,
    payslips must be backfilled in cycle_start order (oldest first) — see
    backfill_payslip_lines management command, which enforces this.
    """
    from apps.payroll.models_payslip_line import PayslipLine

    fy_start = _financial_year_start(payslip.cycle.cycle_start)
    fy_boundary_start = payslip.cycle.cycle_start.replace(month=4, day=1) if payslip.cycle.cycle_start.month >= 4 \
        else payslip.cycle.cycle_start.replace(year=fy_start, month=4, day=1)

    PayslipLine.objects.filter(payslip=payslip).delete()

    line_dicts = build_lines_for_payslip(payslip)
    created = []
    for line in line_dicts:
        prior_total = PayslipLine.objects.filter(
            payslip__employee_id=payslip.employee_id,
            payslip__cycle__cycle_start__gte=fy_boundary_start,
            payslip__cycle__cycle_start__lt=payslip.cycle.cycle_start,
            component_code=line['component_code'],
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        ytd = prior_total + line['amount']
        created.append(PayslipLine.objects.create(payslip=payslip, ytd_amount=ytd, **line))

    return created
