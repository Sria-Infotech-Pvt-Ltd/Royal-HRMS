"""
Phase 7B Task E — arrears engine. Reuses Phase 7A Task J's composer
(services_shadow_engine.compute_payslip_via_new_data) to recompute an
affected past period with CORRECTED inputs in shadow, diffs it against
what was actually paid, and stores the difference as ArrearsLine rows —
never by editing the original EmployeePayslip.

Scoped down: this pass implements the `compensation_revision` trigger
(a back-dated CTC change) end-to-end, proven by test. The other triggers
(attendance-changed-after-payroll, LOP-change, back-dated-statutory,
manual) share the same preview/approve/pay mechanics below — only the
"what input changed" part differs per trigger — but only compensation
is wired to an actual input-substitution function in this pass; the
others are documented as the same mechanism, not yet given their own
input-resolution function.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from apps.payroll.models import ArrearsLine, ArrearsRequest
from apps.payroll.services_shadow_engine import compute_payslip_via_new_data

_DIFF_COMPONENT_FIELDS = ['basic', 'hra', 'special_allowance', 'gross_earnings', 'pf_employee', 'income_tax', 'net_pay']


def preview_compensation_arrears(employee, affected_payslips, corrected_annual_ctc: Decimal, *, created_by=None) -> ArrearsRequest:
    """For each payslip in `affected_payslips` (all for `employee`,
    ideally already covering the back-dated revision's effective window),
    recompute with the corrected CTC and record the per-component
    difference. Creates the ArrearsRequest + its lines in draft/previewed
    status — nothing is paid or approved yet."""
    request = ArrearsRequest.objects.create(
        employee=employee, trigger=ArrearsRequest.TRIGGER_COMPENSATION,
        trigger_note=f'Back-dated CTC revision to {corrected_annual_ctc}.',
        status=ArrearsRequest.STATUS_DRAFT, created_by=created_by,
    )

    corrected_annual_ctc = Decimal(corrected_annual_ctc)
    for payslip in affected_payslips:
        if payslip.employee_id != employee.id:
            raise ValueError(f'Payslip {payslip.id} does not belong to {employee}.')
        if payslip.salary_structure is None:
            continue  # same "cannot bridge" gap Task J's shadow run already reports — skip, don't guess

        corrected_salary_config = SimpleNamespace(
            monthly_ctc=corrected_annual_ctc / 12, annual_ctc=corrected_annual_ctc,
        )
        recomputed = compute_payslip_via_new_data(
            corrected_salary_config, payslip.salary_structure, None, None, adjustments=[],
            lop_days=payslip.lop_days, total_working_days=payslip.total_working_days,
            cycle_month=payslip.cycle.cycle_start.month, proration_factor=Decimal('1'),
        )

        for field in _DIFF_COMPONENT_FIELDS:
            original = getattr(payslip, field)
            corrected = recomputed[field]
            if original != corrected:
                ArrearsLine.objects.create(
                    request=request, affected_payslip=payslip, component_code=field.upper(),
                    original_amount=original, corrected_amount=corrected, difference=corrected - original,
                )

    request.status = ArrearsRequest.STATUS_PREVIEWED
    request.save(update_fields=['status'])
    return request


def total_arrears_due(request: ArrearsRequest) -> Decimal:
    from django.db.models import Sum
    return request.lines.aggregate(total=Sum('difference'))['total'] or Decimal('0')


@transaction.atomic
def approve_arrears(request: ArrearsRequest, approved_by) -> ArrearsRequest:
    if request.status != ArrearsRequest.STATUS_PREVIEWED:
        raise ValueError(f'Only a previewed request can be approved (current status: {request.status}).')
    request.status = ArrearsRequest.STATUS_APPROVED
    request.approved_by = approved_by
    request.approved_at = timezone.now()
    request.save(update_fields=['status', 'approved_by', 'approved_at'])
    return request


def mark_paid_in_run(request: ArrearsRequest, run) -> ArrearsRequest:
    if request.status != ArrearsRequest.STATUS_APPROVED:
        raise ValueError(f'Only an approved request can be paid (current status: {request.status}).')
    request.status = ArrearsRequest.STATUS_PAID
    request.paid_in_run = run
    request.save(update_fields=['status', 'paid_in_run'])
    return request
