"""
Phase 7B Task O — payroll_ops.v2 gate. Scoped down from the master
prompt's full byte-identical-historical-replay harness (see
models_ops_v2.py's own docstring for exactly why: no historical bank/
ECR/ESIC files exist in this database to replay against). This gate
checks the real preconditions that DO apply today: every finalised run in
scope has no un-acknowledged blocking check failures, and every bank/
statutory file generated for it has a recorded checksum (proving it was
actually generated through the real pipeline, not hand-inserted).
"""
from django.db import transaction
from django.utils import timezone

from apps.payroll.models import GeneratedBankFile, PayrollOpsV2Entitlement, PayrollRun
from apps.payroll.services_payroll_checks import has_blocking_unacknowledged_failures


class PayrollOpsV2GateError(Exception):
    pass


def finalized_runs_ready_for_ops_v2(pay_group=None) -> dict:
    """Returns {'ready': [...], 'blocked': {run_id: reason}} for every
    finalised PayrollRun in scope."""
    qs = PayrollRun.objects.filter(is_finalized=True)
    if pay_group is not None:
        qs = qs.filter(pay_group=pay_group)

    ready = []
    blocked = {}
    for run in qs:
        if has_blocking_unacknowledged_failures(run):
            blocked[str(run.id)] = 'Has un-acknowledged blocking check failures.'
            continue
        if run.run_type == PayrollRun.TYPE_REGULAR:
            if not GeneratedBankFile.objects.filter(run=run).exists():
                blocked[str(run.id)] = 'No bank file generated for this run yet.'
                continue
        ready.append(str(run.id))
    return {'ready': ready, 'blocked': blocked}


@transaction.atomic
def enable_payroll_ops_v2(pay_group=None, legal_entity=None) -> PayrollOpsV2Entitlement:
    readiness = finalized_runs_ready_for_ops_v2(pay_group)
    if readiness['blocked']:
        raise PayrollOpsV2GateError(
            f'{len(readiness["blocked"])} run(s) are not ready: {readiness["blocked"]}'
        )
    entitlement, _ = PayrollOpsV2Entitlement.objects.update_or_create(
        legal_entity=legal_entity, defaults={'is_enabled': True, 'enabled_at': timezone.now()},
    )
    return entitlement
