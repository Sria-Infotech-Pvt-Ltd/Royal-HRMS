"""
Phase 7A Task J — run the Task J composer against every real, historical
EmployeePayslip, diff it against what was actually stored, and persist one
PayslipShadowRunResult per payslip. `enable_payroll_v2()` is the only way
to flip PayrollV2Entitlement.is_enabled — it refuses unless the latest
shadow run for every payslip in scope was a clean match.

IMPORTANT, stated per the master prompt's own rule ("where historical
inputs cannot be reconstructed, report it per cycle and stop for owner
guidance — do not tune formulas to force a match without documenting
why"): this recompute uses the EMPLOYEE'S CURRENT branch/statutory
configuration and the structure's CURRENTLY active components, not
whatever was configured at the moment the historical cycle actually ran
(no historical config snapshot exists anywhere in this codebase today —
apps.payroll.engine.legacy itself has never captured one either, see
Phase 7A Task A's own extraction). A reported diff therefore does not by
itself prove the new engine's FORMULAS are wrong — it may simply mean
branch/statutory config was edited after that historical cycle was
processed. Every diff is reported with full before/after detail precisely
so a human can tell the difference; nothing here silently reconciles or
suppresses a diff to force a pass.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.branch.models import Branch
from apps.payroll.engine.legacy import _esi_contribution_period
from apps.payroll.models import (
    EmployeePayslip, EmployeeTaxDeclaration, PayrollAdjustment, PayrollV2Entitlement,
    PayslipShadowRunResult,
)
from apps.payroll.services_shadow_engine import compute_payslip_via_new_data

_DIFF_FIELDS = [
    'basic', 'hra', 'special_allowance', 'gross_earnings', 'lop_deduction',
    'pf_wage_base', 'pf_employee', 'pf_employer', 'esi_employee', 'esi_employer',
    'pt_deduction', 'lwf_employee', 'lwf_employer', 'income_tax',
    'adjustments_earning', 'adjustments_deduction', 'total_deductions', 'net_pay',
]


def _financial_year_start(cycle_start_date):
    return cycle_start_date.year if cycle_start_date.month >= 4 else cycle_start_date.year - 1


_TWO_PLACES = Decimal('0.01')


def _money(value) -> Decimal:
    """Both apps.payroll.engine.legacy._compute_employee_payslip and the
    new composer return RAW, unrounded Decimals (rounding only ever
    happened implicitly at EmployeePayslip's DecimalField(decimal_places=2)
    column on save — confirmed by reading both functions, neither calls
    .quantize() itself). A stored payslip's columns are therefore already
    2-decimal-place values; this quantizes the freshly recomputed side the
    same way before comparing, so a float-precision tail (e.g.
    73333.332000 vs the stored 73333.33) is never mistaken for a real
    formula difference."""
    return Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def shadow_recompute_payslip(payslip: EmployeePayslip) -> PayslipShadowRunResult:
    """Recomputes one stored payslip via the new composer, using the
    payslip's OWN stored lop_days/total_working_days (real facts about
    that cycle, not re-derived) but the employee's CURRENT branch/
    statutory config and structure (see module docstring's caveat)."""
    employee = payslip.employee
    structure = payslip.salary_structure

    if structure is None:
        result, _ = PayslipShadowRunResult.objects.update_or_create(
            payslip=payslip, defaults={
                'is_match': False, 'diffs': {},
                'error': 'Payslip has no salary_structure recorded — cannot bridge to a PayStructure.',
            },
        )
        return result

    branch_obj = Branch.objects.filter(branch_name=employee.branch).select_related('state', 'payroll_config').first()
    branch_config = getattr(branch_obj, 'payroll_config', None) if branch_obj else None
    statutory_state = branch_obj.state if branch_obj else None
    is_metro = branch_obj.is_metro if branch_obj else False

    adj_month = payslip.cycle.cycle_start.replace(day=1)
    adjustments = list(PayrollAdjustment.objects.filter(employee_id=employee.id, month=adj_month))

    fy_start = _financial_year_start(payslip.cycle.cycle_start)
    tax_declaration = EmployeeTaxDeclaration.objects.filter(
        employee_id=employee.id, financial_year_start=fy_start,
    ).first()

    period_start, _period_end = _esi_contribution_period(payslip.cycle.cycle_start)
    esi_covered_earlier = EmployeePayslip.objects.filter(
        employee_id=employee.id, cycle__cycle_start__gte=period_start,
        cycle__cycle_start__lt=payslip.cycle.cycle_start, esi_employer__gt=0,
    ).exists()

    salary_config = type('_StoredSalarySnapshot', (), {
        'monthly_ctc': payslip.monthly_ctc, 'annual_ctc': payslip.annual_ctc,
    })()

    try:
        recomputed = compute_payslip_via_new_data(
            salary_config, structure, branch_config, statutory_state, adjustments,
            lop_days=payslip.lop_days, total_working_days=payslip.total_working_days,
            cycle_month=payslip.cycle.cycle_start.month,
            esi_covered_earlier_this_period=esi_covered_earlier,
            proration_factor=Decimal('1'),  # lop_days/total_working_days already reflect any historical proration window
            is_metro=is_metro,
            tax_regime=tax_declaration.tax_regime if tax_declaration else EmployeeTaxDeclaration.REGIME_NEW,
            declared_investments=tax_declaration.declared_investments if tax_declaration else None,
            financial_year_start=fy_start,
        )
    except Exception as exc:  # noqa: BLE001 — report any composer failure as a shadow-run error, don't crash the sweep
        result, _ = PayslipShadowRunResult.objects.update_or_create(
            payslip=payslip, defaults={'is_match': False, 'diffs': {}, 'error': str(exc)},
        )
        return result

    diffs = {}
    for field in _DIFF_FIELDS:
        stored = _money(getattr(payslip, field))
        new = _money(recomputed[field])
        if stored != new:
            diffs[field] = {'stored': str(stored), 'recomputed': str(new)}

    result, _ = PayslipShadowRunResult.objects.update_or_create(
        payslip=payslip, defaults={'is_match': not diffs, 'diffs': diffs, 'error': ''},
    )
    return result


def run_shadow_sweep(queryset=None) -> dict:
    """Recomputes every payslip in `queryset` (default: all of them),
    persists a PayslipShadowRunResult each, and returns a summary count."""
    queryset = queryset if queryset is not None else EmployeePayslip.objects.all()
    matched = 0
    mismatched = 0
    errored = 0
    for payslip in queryset.select_related('employee', 'cycle', 'salary_structure'):
        result = shadow_recompute_payslip(payslip)
        if result.error:
            errored += 1
        elif result.is_match:
            matched += 1
        else:
            mismatched += 1
    return {'total': matched + mismatched + errored, 'matched': matched, 'mismatched': mismatched, 'errored': errored}


class PayrollV2GateError(Exception):
    """Raised when payroll.v2 cannot be enabled yet — see enable_payroll_v2()."""


def approve_shadow_run_exception(result: PayslipShadowRunResult, note: str, approved_by=None) -> PayslipShadowRunResult:
    """The master prompt's own escape hatch: 'any difference blocks
    completion unless the owner approves it in writing... with the root
    cause explained.' This records that sign-off WITHOUT touching
    is_match/diffs — the mismatch stays a real, visible mismatch; this is
    a separate attestation that a human reviewed it and accepted the
    explained root cause (e.g. a StatutoryConfig row genuinely didn't
    exist yet when the historical payslip was processed), not a code fix
    pretending the numbers agree."""
    if not note.strip():
        raise ValueError('An approval note explaining the root cause is required.')
    result.owner_approved = True
    result.approval_note = note
    result.approved_by = approved_by
    result.approved_at = timezone.now()
    result.save(update_fields=['owner_approved', 'approval_note', 'approved_by', 'approved_at'])
    return result


@transaction.atomic
def enable_payroll_v2(legal_entity=None):
    """Enables PayrollV2Entitlement for `legal_entity` (None = company-wide)
    ONLY if every EmployeePayslip currently has a shadow-run result that is
    EITHER a clean match (is_match=True, no error) OR an explicitly
    owner-approved exception (approve_shadow_run_exception()) — the gate
    the master prompt requires ('the flag cannot be enabled for an entity
    without a passing shadow run', with owner-approved exceptions as the
    one documented way past a real difference). Run run_shadow_sweep()
    first; this never recomputes anything itself, it only checks the
    latest recorded results."""
    total_payslips = EmployeePayslip.objects.count()
    acceptable_results = PayslipShadowRunResult.objects.filter(
        models.Q(is_match=True, error='') | models.Q(owner_approved=True),
    ).count()
    if acceptable_results < total_payslips:
        raise PayrollV2GateError(
            f'{total_payslips - acceptable_results} of {total_payslips} payslip(s) have no clean or '
            f'owner-approved shadow-run result yet — run run_shadow_sweep() and either resolve every '
            f'diff or approve_shadow_run_exception() it before enabling payroll.v2.'
        )

    entitlement, _ = PayrollV2Entitlement.objects.update_or_create(
        legal_entity=legal_entity,
        defaults={'is_enabled': True, 'enabled_at': timezone.now(), 'last_passing_shadow_run_at': timezone.now()},
    )
    return entitlement
