"""
Phase 7A Task D — create a compensation revision (dual-writing the legacy
EmployeeSalaryConfig row so every existing reader keeps working), and the
CTC breakup API: resolve an employee's compensation as of a date and
evaluate it through Task C's structure engine, with a trace of exactly
which version/structure/overrides produced the numbers.

Still not called by anything in apps.payroll.engine.legacy — real payroll
processing keeps reading EmployeeSalaryConfig directly, untouched.
"""
from decimal import Decimal

from django.db import transaction

from apps.payroll.models import EmployeeSalaryConfig, PayStructure
from apps.payroll.models_compensation import EmployeeCompensation, EmployeeCompensationComponent
from apps.payroll.services_pay_structure import evaluate_structure


@transaction.atomic
def create_compensation(
    employee, annual_ctc, effective_from, *, pay_structure=None, legacy_salary_structure=None,
    reason='', reason_note='', linked_promotion=None, component_overrides=None,
):
    """The one designated way to record a new compensation version from now
    on — writes a real EmployeeSalaryConfig row (so nothing downstream of
    payroll processing needs to change) AND an EmployeeCompensation row
    linked to it (so the new structure/override/breakup machinery has
    something to resolve). See module and model docstrings for the "only
    the new path is synced" caveat.

    `legacy_salary_structure`: the old SalaryStructure FK EmployeeSalaryConfig
    itself needs — deliberately a separate parameter from `pay_structure`
    (the new PayStructure FK) since nothing maps one to the other yet.
    """
    legacy = EmployeeSalaryConfig.objects.create(
        employee=employee,
        annual_ctc=annual_ctc,
        salary_structure=legacy_salary_structure,
        effective_from=effective_from,
        reason=reason,
        reason_note=reason_note,
        linked_promotion=linked_promotion,
    )

    compensation = EmployeeCompensation.objects.create(
        employee=employee,
        annual_ctc=annual_ctc,
        pay_structure=pay_structure,
        effective_from=effective_from,
        reason=reason,
        reason_note=reason_note,
        linked_promotion=linked_promotion,
        legacy_salary_config=legacy,
    )

    for override in (component_overrides or []):
        EmployeeCompensationComponent.objects.create(compensation=compensation, **override)

    return compensation, legacy


def resolve_compensation(employee, as_of_date):
    """The EmployeeCompensation version active for `employee` on
    `as_of_date` — latest row with effective_from <= as_of_date (and, if
    set, effective_to >= as_of_date), same "latest wins" convention
    EmployeeSalaryConfig's own callers already use."""
    qs = EmployeeCompensation.objects.filter(
        employee=employee, is_active=True, effective_from__lte=as_of_date,
    ).order_by('-effective_from')
    for compensation in qs:
        if compensation.effective_to is None or compensation.effective_to >= as_of_date:
            return compensation
    return None


def ctc_breakup(employee, as_of_date, *, is_metro=False):
    """Monthly/annual breakdown for `employee` as of `as_of_date`, with a
    trace of exactly what produced it. Returns None if no EmployeeCompensation
    version resolves (e.g. this employee was only ever given a plain
    EmployeeSalaryConfig row through the old path)."""
    compensation = resolve_compensation(employee, as_of_date)
    if compensation is None:
        return None

    structure = compensation.pay_structure or PayStructure.objects.filter(
        status=PayStructure.STATUS_PUBLISHED, is_active=True,
    ).order_by('code').first()
    if structure is None:
        return {
            'compensation_id': str(compensation.id),
            'error': 'No pay structure resolved for this employee (none pinned, none published).',
        }

    monthly_breakdown = evaluate_structure(structure, compensation.monthly_ctc, is_metro=is_metro)

    overrides = {o.component_code: o for o in compensation.component_overrides.all()}
    for code, override in overrides.items():
        if override.value is not None:
            monthly_breakdown[code] = Decimal(override.value)

    annual_breakdown = {code: amount * 12 for code, amount in monthly_breakdown.items()}

    return {
        'compensation_id': str(compensation.id),
        'effective_from': compensation.effective_from.isoformat(),
        'structure_code': structure.code,
        'structure_version': structure.version,
        'overrides_applied': list(overrides.keys()),
        'monthly_ctc': compensation.monthly_ctc,
        'annual_ctc': compensation.annual_ctc,
        'monthly_breakdown': monthly_breakdown,
        'annual_breakdown': annual_breakdown,
    }
