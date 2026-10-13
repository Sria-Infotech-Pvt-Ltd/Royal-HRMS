"""
Phase 7B Task L — full and final settlement as a `final_settlement`
PayrollRun. Deliberately does NOT replace `apps.hrms.services_settlement
.compute_draft()` (the real, already-working F&F calculation reviewed by
HR/Finance) — this builds the loan-recovery piece (Task F, genuinely
missing from the existing settlement) and a thin mapping function that
copies a real SeparationSettlement's computed fields onto a PayrollRun's
RunVersion snapshot for cross-reference, so a settlement is visible
alongside other payroll runs without duplicating or second-guessing HR's
own settlement figures.
"""
from decimal import Decimal

from apps.payroll.models import PayrollRun
from apps.payroll.services_loans import outstanding_balance_for_settlement


def settlement_loan_recovery(employee) -> Decimal:
    """What Task L's `advances_recovery_amount` should be — the real
    outstanding balance across every active EmployeeLoan, which the
    existing apps.hrms.SeparationSettlement model has a field for
    (advances_recovery_amount) but nothing populates automatically today
    (confirmed: no loan model existed before this phase)."""
    return outstanding_balance_for_settlement(employee)


def settlement_run_snapshot(settlement) -> dict:
    """Maps a real, HR-finalised apps.hrms.SeparationSettlement onto the
    flat {component_code: amount} shape RunVersion.results expects — so a
    final_settlement-type PayrollRun can carry the same figures HR already
    approved, without recomputing anything independently (settlement
    figures involve real legal/policy judgment HR enters by hand — see
    that model's own docstring — this phase doesn't second-guess that)."""
    return {
        'PRO_RATA_SALARY':       settlement.pro_rata_salary,
        'LEAVE_ENCASHMENT':      settlement.leave_encashment_amount,
        'NOTICE_SHORTFALL':      -settlement.notice_period_recovery_amount,
        'GRATUITY':              settlement.gratuity_amount,
        'STATUTORY_BONUS':       settlement.statutory_bonus_amount,
        'REIMBURSEMENTS':        settlement.reimbursements_amount,
        'ADVANCES_RECOVERY':     -settlement.advances_recovery_amount,
        'TDS':                   -settlement.tds_amount,
        'OTHER_ADJUSTMENT':      settlement.other_adjustment_amount,
        'NET_PAYABLE':           settlement.net_payable_amount,
    }


def create_final_settlement_run(employee, pay_group, period, stage_template, created_by) -> PayrollRun:
    from apps.payroll.services_run import create_run
    return create_run(
        pay_group, period, stage_template, created_by,
        run_type=PayrollRun.TYPE_FINAL_SETTLEMENT, employee=employee,
    )
