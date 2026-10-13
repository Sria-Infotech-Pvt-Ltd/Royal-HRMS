"""
Phase 7B Task B — run lifecycle: stage registry, versioned recalculation
with a diff, finalisation (a real, enforced one-way transition), and the
SoD check (creator cannot approve their own run).
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.payroll.models import PayrollRun, RunVersion
from apps.platform_core.services_numbering import allocate

# The stage codes RunStageTemplate.stage_codes may list, in the order the
# master prompt's own stage list gives them. Each is just a label this
# pass's advance_stage() moves through in order — no per-stage handler
# function is wired to live payroll processing yet (that would require
# touching apps.payroll.engine.legacy / process_payroll_cycle, which this
# whole phase has deliberately left untouched).
STAGE_REGISTRY = [
    'open_inputs', 'inputs_cutoff', 'attendance_approval', 'attendance_lock',
    'calculation', 'validation_checks', 'review_approval', 'payslip_publish',
    'payment_file', 'mark_paid', 'accounting_journal', 'statutory_returns', 'close',
]


class InvalidStageTemplateError(Exception):
    pass


class RunFinalizedError(Exception):
    """Raised by any attempt to mutate a finalised run."""


class SoDViolationError(Exception):
    """The run's own creator attempted to approve it."""


def validate_stage_codes(stage_codes: list) -> None:
    unknown = [c for c in stage_codes if c not in STAGE_REGISTRY]
    if unknown:
        raise InvalidStageTemplateError(f'Unknown stage code(s): {unknown}. Valid codes: {STAGE_REGISTRY}')


@transaction.atomic
def create_run(pay_group, period, stage_template, created_by, *, run_type=PayrollRun.TYPE_REGULAR, employee=None, parent_run=None) -> PayrollRun:
    reference_number = allocate('PAYROLL_RUN') if _run_number_series_exists() else f'RUN-{period.id}-{run_type}'
    return PayrollRun.objects.create(
        pay_group=pay_group, period=period, run_type=run_type, stage_template=stage_template,
        reference_number=reference_number, created_by=created_by, employee=employee, parent_run=parent_run,
    )


def _run_number_series_exists() -> bool:
    from apps.platform_core.models import NumberSeries
    return NumberSeries.objects.filter(code='PAYROLL_RUN', is_active=True).exists()


def advance_stage(run: PayrollRun) -> PayrollRun:
    if run.is_finalized:
        raise RunFinalizedError(f'Run {run.reference_number} is finalised — cannot advance further.')
    codes = run.stage_template.stage_codes
    if run.current_stage_index + 1 >= len(codes):
        raise InvalidStageTemplateError('Already at the last stage.')
    run.current_stage_index += 1
    run.save(update_fields=['current_stage_index', 'updated_at'])
    return run


def can_approve_run(user, run: PayrollRun) -> bool:
    """SoD: the person who created (calculated) a run may not also approve
    it. A real permission check (payroll.approve or similar) is a separate,
    already-existing concern — this only enforces the creator/approver
    split the master prompt's Task B.6 asks for."""
    return user_id_differs(user, run)


def user_id_differs(user, run: PayrollRun) -> bool:
    return getattr(user, 'id', None) != run.created_by_id


def approve_run(user, run: PayrollRun) -> None:
    if not can_approve_run(user, run):
        raise SoDViolationError(f'{user} created run {run.reference_number} and cannot also approve it.')


@transaction.atomic
def recalculate(run: PayrollRun, results: dict, *, created_by=None, affected_employee_ids=None) -> RunVersion:
    """Records a new versioned snapshot. `results` is the caller-supplied
    {employee_id: {component_code: amount}} dict (the actual per-employee
    computation is the engine's job — this function versions and diffs
    whatever was computed, it doesn't compute anything itself)."""
    if run.is_finalized:
        raise RunFinalizedError(f'Run {run.reference_number} is finalised — no further recalculation allowed.')
    next_version = (run.versions.aggregate(models_max=_max_version())['models_max'] or 0) + 1
    return RunVersion.objects.create(
        run=run, version_number=next_version, results=results,
        affected_employee_ids=affected_employee_ids or list(results.keys()), created_by=created_by,
    )


def _max_version():
    from django.db.models import Max
    return Max('version_number')


def diff_versions(version_a: RunVersion, version_b: RunVersion) -> dict:
    """Per-employee, per-component differences between two RunVersions of
    the same run."""
    diffs = {}
    all_employee_ids = set(version_a.results) | set(version_b.results)
    for employee_id in all_employee_ids:
        before = version_a.results.get(employee_id, {})
        after = version_b.results.get(employee_id, {})
        component_diff = {}
        for code in set(before) | set(after):
            b = Decimal(str(before.get(code, 0)))
            a = Decimal(str(after.get(code, 0)))
            if a != b:
                component_diff[code] = {'before': str(b), 'after': str(a), 'delta': str(a - b)}
        if component_diff:
            diffs[employee_id] = component_diff
    return diffs


@transaction.atomic
def finalize_run(run: PayrollRun) -> PayrollRun:
    if run.is_finalized:
        raise RunFinalizedError(f'Run {run.reference_number} is already finalised.')
    if not run.versions.exists():
        raise ValueError('Cannot finalise a run with no recalculated version.')
    run.is_finalized = True
    run.finalized_at = timezone.now()
    run.save(update_fields=['is_finalized', 'finalized_at', 'updated_at'])
    return run
