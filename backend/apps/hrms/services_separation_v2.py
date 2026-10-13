"""Phase 8B Task B — trigger the real Phase 7B final_settlement run from a separation, and create the alumni/rehire record on deactivation."""
from django.db import transaction

from apps.hrms.models import AlumniRecord, SeparationFinalSettlementLink, SeparationRequest


@transaction.atomic
def trigger_final_settlement(request: SeparationRequest, pay_group, period, stage_template, created_by) -> SeparationFinalSettlementLink:
    """Idempotent — returns the existing link if a settlement run already
    exists for this request. Uses the REAL Phase 7B
    create_final_settlement_run(), not a re-derived calculation."""
    existing = getattr(request, 'final_settlement_link', None)
    if existing is not None:
        return existing

    from apps.payroll.services_final_settlement import create_final_settlement_run
    run = create_final_settlement_run(request.employee, pay_group, period, stage_template, created_by)
    return SeparationFinalSettlementLink.objects.create(request=request, payroll_run=run)


@transaction.atomic
def create_alumni_record(request: SeparationRequest, last_working_day, rehire_eligible: bool = True, rehire_note: str = '') -> AlumniRecord:
    """Idempotent per employee (OneToOneField) — called once an employee's
    account is actually deactivated (existing scheduler behavior,
    untouched by this function)."""
    record, _ = AlumniRecord.objects.update_or_create(
        employee=request.employee,
        defaults={
            'separation_request': request, 'last_working_day': last_working_day,
            'rehire_eligible': rehire_eligible, 'rehire_note': rehire_note,
        },
    )
    return record


def is_rehire_eligible(employee_email: str) -> bool:
    """Used by 8A's duplicate-detection and a future 5B rehire action —
    True (eligible) if no AlumniRecord exists at all, or the most recent
    one says eligible."""
    record = AlumniRecord.objects.filter(employee__email=employee_email).order_by('-last_working_day').first()
    return record is None or record.rehire_eligible
