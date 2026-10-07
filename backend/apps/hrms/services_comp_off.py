"""
Phase 6A Task G — comp-off earning, built from scratch (the Explore pass
confirmed: `comp_off` was purely a LEAVE_TYPE_CHOICES code with
`annual_days=0` and no earn/grant logic anywhere — this is genuinely new,
not an extension of an existing mechanism).

Each earned comp-off credit is one `LeaveTransaction` lot
(`txn_type=comp_off_earned`) with its own `expiry_date`. Expiry creates a
matching `comp_off_expired` reversal for any lot whose quantity hasn't
already been offset by one (tracked via `reversal_of`) — a simplification
versus true partial-lot consumption (see PHASE6A_REPORT.md): since
nothing in this pass wires leave-request approval to consume a specific
comp-off lot, a lot is treated as all-or-nothing — either unexpired, or
fully expired.

NOT wired to attendance/overtime automatically in this pass (that
integration point is Phase 6B's attendance engine, per the Phase 6B
prompt's own Task G.1: "feeding the 6A comp-off ledger") — `grant_comp_off()`
is the function such a future caller would invoke; manual/API-triggered
grants work today.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from apps.hrms.models_leave_ledger import LeaveTransaction
from apps.hrms.services_leave_ledger import create_transaction


class CompOffError(Exception):
    pass


def _get_comp_off_type():
    from apps.hrms.models_leave_ledger import LeaveType
    try:
        return LeaveType.objects.get(code='comp_off')
    except LeaveType.DoesNotExist:
        raise CompOffError('comp_off LeaveType is not seeded — run seed_leave_types.') from None


def grant_comp_off(employee, *, work_date, hours_worked=None, is_full_day=None,
                    expiry_days=60, reason='', created_by=None) -> LeaveTransaction:
    """Earns a comp-off lot for work done on `work_date` (a weekly off or
    holiday, per the prompt's own examples). Quantity rule (Task G.1's own
    example thresholds): >=8 hours -> 1 full day, >=4 hours -> 0.5 day,
    below that -> rejected. `is_full_day=True` bypasses the hours check
    for a manual full-day grant."""
    if is_full_day:
        quantity = Decimal('1')
    elif hours_worked is not None:
        if hours_worked >= 8:
            quantity = Decimal('1')
        elif hours_worked >= 4:
            quantity = Decimal('0.5')
        else:
            raise CompOffError(f'{hours_worked} hours worked is below the 4-hour minimum for a comp-off credit.')
    else:
        raise CompOffError('Either hours_worked or is_full_day=True must be provided.')

    comp_off_type = _get_comp_off_type()
    return create_transaction(
        employee, comp_off_type, txn_type=LeaveTransaction.TXN_COMP_OFF_EARNED, quantity=quantity,
        effective_date=work_date, expiry_date=work_date + timedelta(days=expiry_days),
        reason=reason or f'Comp-off earned for work on {work_date}.', created_by=created_by,
    )


def expire_comp_off_lots(as_of=None) -> dict:
    """Scheduler job (Task G.2) — for every comp_off_earned lot whose
    expiry_date has passed and which has no comp_off_expired reversal yet,
    creates one for the lot's full quantity."""
    from django.utils import timezone

    as_of = as_of or timezone.localdate()
    comp_off_type = _get_comp_off_type()

    expired_lot_ids = set(
        LeaveTransaction.objects.filter(
            txn_type=LeaveTransaction.TXN_COMP_OFF_EXPIRED,
        ).values_list('reversal_of_id', flat=True)
    )
    due_lots = LeaveTransaction.objects.filter(
        leave_type=comp_off_type, txn_type=LeaveTransaction.TXN_COMP_OFF_EARNED,
        expiry_date__lt=as_of,
    ).exclude(id__in=expired_lot_ids)

    due_lots = list(due_lots)
    expired_count = 0
    for lot in due_lots:
        create_transaction(
            lot.employee, comp_off_type, txn_type=LeaveTransaction.TXN_COMP_OFF_EXPIRED,
            quantity=-lot.quantity, effective_date=as_of, leave_year=lot.leave_year,
            reason=f'Comp-off lot earned {lot.effective_date} expired {lot.expiry_date}.', reversal_of=lot,
        )
        expired_count += 1
    return {'checked': len(due_lots), 'expired': expired_count}
