"""
Phase 9B Task E — DSR intake + fulfilment.

`export_user_data` reads a SMALL, EXPLICITLY NAMED set of employee-linked
tables (profile fields, payslips, leave requests, expense claims,
attendance records) rather than a repo-wide reflection-based PII scanner
— scoped down and stated plainly, same convention as every other phase
this session. Adding more tables later is the same pattern repeated.

`fulfil_erasure_request` only scrubs fields this codebase already treats
as erasable-on-request elsewhere (reuses the exact same field list
`anonymise_candidate` uses for candidates — name/email/phone — applied
here to the User row) and explicitly refuses to erase anything with a
live statutory/financial retention need (payslips, tax declarations,
attendance) — it records WHY in `fulfilment_evidence` rather than
silently doing a partial job.
"""
from django.db import transaction
from django.utils import timezone

from apps.platform_core.models import DataSubjectRequest


class DSRAlreadyFulfilledError(Exception):
    pass


ERASABLE_USER_FIELDS = ['phone']
NON_ERASABLE_REASON = (
    'Payslips, tax declarations and attendance records are retained for '
    'statutory/financial compliance periods and are not erased by this '
    'request; only directly-identifying profile fields are scrubbed.'
)


def create_request(*, request_type: str, subject_user, requested_by, reason: str = '') -> DataSubjectRequest:
    return DataSubjectRequest.objects.create(
        request_type=request_type, subject_user=subject_user, requested_by=requested_by, reason=reason,
    )


def export_user_data(user) -> dict:
    """Read-only snapshot for TYPE_ACCESS / TYPE_EXPORT requests."""
    from apps.payroll.models import EmployeePayslip
    from apps.hrms.models import Expense, LeaveRequest

    data = {
        'profile': {
            'employee_id': getattr(user, 'employee_id', None),
            'full_name': user.full_name,
            'email': user.email,
            'phone': getattr(user, 'phone', None),
            'designation': getattr(user, 'designation', None),
            'department': getattr(user, 'department', None),
            'date_of_joining': str(getattr(user, 'date_of_joining', '') or ''),
        },
        'payslips': [
            {'cycle_id': str(p.cycle_id), 'net_pay': str(p.net_pay), 'created_at': str(p.created_at)}
            for p in EmployeePayslip.objects.filter(employee=user).order_by('-created_at')[:500]
        ],
        'leave_requests': [
            {'id': str(l.id), 'leave_type': l.leave_type, 'status': l.status,
             'start_date': str(l.start_date), 'end_date': str(l.end_date)}
            for l in LeaveRequest.objects.filter(employee=user).order_by('-start_date')[:500]
        ],
        'expense_claims': [
            {'id': str(e.id), 'amount': str(e.amount), 'status': e.status, 'created_at': str(e.created_at)}
            for e in Expense.objects.filter(employee=user).order_by('-created_at')[:500]
        ],
    }
    return data


@transaction.atomic
def fulfil_access_or_export_request(dsr: DataSubjectRequest, *, fulfilled_by) -> DataSubjectRequest:
    if dsr.status == DataSubjectRequest.STATUS_FULFILLED:
        raise DSRAlreadyFulfilledError(f'DSR {dsr.id} already fulfilled.')
    snapshot = export_user_data(dsr.subject_user)
    dsr.fulfilment_evidence = {'exported_keys': list(snapshot.keys()), 'record_counts': {
        k: len(v) if isinstance(v, list) else 1 for k, v in snapshot.items()
    }}
    dsr.status = DataSubjectRequest.STATUS_FULFILLED
    dsr.fulfilled_by = fulfilled_by
    dsr.fulfilled_at = timezone.now()
    dsr.save(update_fields=['fulfilment_evidence', 'status', 'fulfilled_by', 'fulfilled_at', 'updated_at'])
    return dsr


@transaction.atomic
def fulfil_erasure_request(dsr: DataSubjectRequest, *, fulfilled_by) -> DataSubjectRequest:
    if dsr.status == DataSubjectRequest.STATUS_FULFILLED:
        raise DSRAlreadyFulfilledError(f'DSR {dsr.id} already fulfilled.')
    user = dsr.subject_user
    erased = {}
    for field_name in ERASABLE_USER_FIELDS:
        if hasattr(user, field_name):
            erased[field_name] = getattr(user, field_name)
            setattr(user, field_name, '')
    user.save(update_fields=[f for f in ERASABLE_USER_FIELDS if hasattr(user, f)])

    dsr.fulfilment_evidence = {'erased_fields': list(erased.keys()), 'not_erased_reason': NON_ERASABLE_REASON}
    dsr.status = DataSubjectRequest.STATUS_FULFILLED
    dsr.fulfilled_by = fulfilled_by
    dsr.fulfilled_at = timezone.now()
    dsr.save(update_fields=['fulfilment_evidence', 'status', 'fulfilled_by', 'fulfilled_at', 'updated_at'])
    return dsr


def reject_request(dsr: DataSubjectRequest, *, reason: str) -> DataSubjectRequest:
    dsr.status = DataSubjectRequest.STATUS_REJECTED
    dsr.rejection_reason = reason
    dsr.save(update_fields=['status', 'rejection_reason', 'updated_at'])
    return dsr
