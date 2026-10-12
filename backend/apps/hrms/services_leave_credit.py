"""
Employee-wise leave credit management (Phase 1).

LeaveBalance stays the source of truth every existing leave workflow reads.
All manual credit changes go through apply_adjustment()/reverse_transaction(),
which lock the balance row, change total_days by a signed delta (never an
absolute overwrite, never used_days), and write an append-only
LeaveCreditTransaction in the same database transaction.
"""
from __future__ import annotations

import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import (
    CREDIT_TXN_ADJUSTMENT, CREDIT_TXN_REVERSAL, LEAVE_LWP, LEAVE_TYPE_CHOICES,
    REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING,
    LeaveBalance, LeaveCreditTransaction, LeavePolicy, LeaveRequest,
)

MAX_ABS_AMOUNT = Decimal('365')
MAX_TOTAL_DAYS = Decimal('9999.9')  # LeaveBalance.total_days is DecimalField(max_digits=5, decimal_places=1)
MAX_REASON_LENGTH = 1000
MIN_YEAR = 2000
_ONE_DP = Decimal('0.1')
_TWO_DP = Decimal('0.01')


class LeaveCreditError(Exception):
    """A request the caller can fix (validation / business rule)."""


class LeaveCreditConflict(LeaveCreditError):
    """Same idempotency key reused for a different request."""


def current_calendar_year() -> int:
    return timezone.localdate().year


def leave_type_label(leave_type: str, policy: LeavePolicy | None = None) -> str:
    if policy and policy.leave_type_label:
        return policy.leave_type_label
    return dict(LEAVE_TYPE_CHOICES).get(leave_type, leave_type.replace('_', ' ').title())


def _clean_amount(raw) -> Decimal:
    try:
        amount = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise LeaveCreditError('Amount must be a number, e.g. 2 or -1.5.')
    if not amount.is_finite() or amount == 0:
        raise LeaveCreditError('Amount must be a non-zero number of days.')
    if amount != amount.quantize(_ONE_DP):
        raise LeaveCreditError('Amount can have at most one decimal place, e.g. 1.5.')
    if abs(amount) > MAX_ABS_AMOUNT:
        raise LeaveCreditError(f'Amount cannot exceed {MAX_ABS_AMOUNT} days in a single adjustment.')
    return amount


def _clean_reason(raw) -> str:
    reason = (raw or '').strip() if isinstance(raw, str) else ''
    if not reason:
        raise LeaveCreditError('A reason is required.')
    if len(reason) > MAX_REASON_LENGTH:
        raise LeaveCreditError(f'Reason must be at most {MAX_REASON_LENGTH} characters.')
    return reason


def _clean_key(raw) -> str:
    key = (raw or '').strip() if isinstance(raw, str) else ''
    if not key or len(key) > 64:
        raise LeaveCreditError('A valid idempotency_key (1-64 characters) is required.')
    return key


def _clean_year(raw) -> int:
    try:
        year = int(raw)
    except (TypeError, ValueError):
        raise LeaveCreditError('Year must be a valid calendar year.')
    if year < MIN_YEAR or year > current_calendar_year():
        raise LeaveCreditError('Credits can only be adjusted for the current or a past calendar year.')
    return year


def pending_days(employee, leave_type: str, year: int) -> Decimal:
    """Days still awaiting approval that would be deducted from this balance on approval."""
    agg = LeaveRequest.objects.filter(
        employee=employee, leave_type=leave_type, start_date__year=year,
        status__in=(REQ_PENDING, REQ_L2_PENDING), is_lwp=False,
    ).aggregate(total=Sum('total_days'), lop=Sum('lop_days'))
    return (agg['total'] or Decimal('0')) - (agg['lop'] or Decimal('0'))


def _replay_or_conflict(existing, *, employee, leave_type, year, amount, reverses):
    same = (
        existing.employee_id == employee.id and existing.leave_type == leave_type
        and existing.year == year and existing.amount == amount
        and existing.reverses_id == (reverses.id if reverses else None)
    )
    if not same:
        raise LeaveCreditConflict('This request key was already used for a different adjustment.')
    return existing, False


def _locked_balance(employee, leave_type: str, year: int, amount: Decimal, policy):
    balance = (
        LeaveBalance.objects.select_for_update()
        .filter(employee=employee, leave_type=leave_type, year=year).first()
    )
    if balance is not None:
        return balance
    # Only the current year may get a brand-new row: a pre-created future-year row
    # would make the annual reset's get_or_create skip that employee's allocation.
    if amount < 0:
        raise LeaveCreditError('There is no balance for this leave type and year to reduce.')
    if year != current_calendar_year():
        raise LeaveCreditError('No balance exists for this leave type in that year; new balances can only be created for the current year.')
    if policy is None or not policy.is_active:
        raise LeaveCreditError('Credits can only be assigned for an active leave type.')
    created_row, _ = LeaveBalance.objects.get_or_create(
        employee=employee, leave_type=leave_type, year=year,
        defaults={'total_days': Decimal('0'), 'used_days': Decimal('0'), 'carried_forward': Decimal('0')},
    )
    return LeaveBalance.objects.select_for_update().get(pk=created_row.pk)


def apply_adjustment(*, employee, leave_type, year, amount, reason, actor, idempotency_key,
                     reverses: LeaveCreditTransaction | None = None, ip_address=None):
    """
    Returns (transaction, created). created=False means an identical earlier
    request with the same idempotency_key was found and nothing was re-applied.
    """
    leave_type = (leave_type or '').strip()
    if not leave_type or leave_type == LEAVE_LWP:
        raise LeaveCreditError('Choose a leave type that has a balance (Loss of Pay has none).')
    year   = _clean_year(year)
    amount = _clean_amount(amount)
    reason = _clean_reason(reason)
    key    = _clean_key(idempotency_key)

    existing = LeaveCreditTransaction.objects.filter(idempotency_key=key).first()
    if existing:
        return _replay_or_conflict(existing, employee=employee, leave_type=leave_type, year=year,
                                   amount=amount, reverses=reverses)

    policy = LeavePolicy.objects.filter(leave_type=leave_type).first()
    try:
        with transaction.atomic():
            balance = _locked_balance(employee, leave_type, year, amount, policy)
            total_before = balance.total_days
            total_after  = total_before + amount
            if total_after > MAX_TOTAL_DAYS:
                raise LeaveCreditError(f'Total credits cannot exceed {MAX_TOTAL_DAYS} days.')

            if amount < 0:
                if total_after < 0:
                    raise LeaveCreditError('Total credits cannot go below zero.')
                committed = balance.used_days + pending_days(employee, leave_type, year)
                if total_after < committed and not (policy and policy.allow_negative_balance):
                    raise LeaveCreditError(
                        f'This would leave {total_after} day(s) credited, below the {balance.used_days} '
                        f'used plus {committed - balance.used_days} pending day(s).'
                    )

            # F() delta, never an absolute write, so a concurrent used_days change is never lost.
            LeaveBalance.objects.filter(pk=balance.pk).update(
                total_days=F('total_days') + amount, updated_at=timezone.now(),
            )
            txn = LeaveCreditTransaction.objects.create(
                balance=balance, employee=employee, leave_type=leave_type, year=year,
                txn_type=CREDIT_TXN_REVERSAL if reverses else CREDIT_TXN_ADJUSTMENT,
                amount=amount, total_before=total_before, total_after=total_after,
                reason=reason, reverses=reverses, idempotency_key=key,
                created_by=actor, created_by_name=(getattr(actor, 'full_name', '') or getattr(actor, 'email', '') or ''),
            )

            from apps.accounts.models import AuditLog
            AuditLog.objects.create(
                user=actor, module='leave',
                action='leave_credit_reversed' if reverses else 'leave_credit_adjusted',
                object_id=str(txn.id),
                changes={
                    'employee_id': employee.employee_id, 'leave_type': leave_type, 'year': year,
                    'amount': str(amount), 'total_before': str(total_before), 'total_after': str(total_after),
                    'reason': reason, 'reverses': str(reverses.id) if reverses else None,
                },
                branch=employee.branch or '',
                ip_address=ip_address,
            )
    except IntegrityError:
        existing = LeaveCreditTransaction.objects.filter(idempotency_key=key).first()
        if existing:
            return _replay_or_conflict(existing, employee=employee, leave_type=leave_type, year=year,
                                       amount=amount, reverses=reverses)
        if reverses is not None:
            raise LeaveCreditError('This adjustment has already been reversed.')
        raise
    return txn, True


def reverse_transaction(*, employee, txn_id, reason, actor, idempotency_key, ip_address=None):
    original = LeaveCreditTransaction.objects.filter(id=txn_id, employee=employee).first()
    if original is None:
        raise LeaveCreditError('Adjustment not found.')
    if original.txn_type == CREDIT_TXN_REVERSAL:
        raise LeaveCreditError('A reversal cannot itself be reversed.')

    key = _clean_key(idempotency_key)
    existing = LeaveCreditTransaction.objects.filter(idempotency_key=key).first()
    if existing:
        return _replay_or_conflict(existing, employee=employee, leave_type=original.leave_type,
                                   year=original.year, amount=-original.amount, reverses=original)
    if LeaveCreditTransaction.objects.filter(reverses=original).exists():
        raise LeaveCreditError('This adjustment has already been reversed.')

    return apply_adjustment(
        employee=employee, leave_type=original.leave_type, year=original.year,
        amount=-original.amount, reason=reason, actor=actor, idempotency_key=key,
        reverses=original, ip_address=ip_address,
    )


# ─── Summaries ────────────────────────────────────────────────────────────────

def _f(value) -> float:
    return float(Decimal(value).quantize(_TWO_DP, rounding=ROUND_HALF_UP))


def yearly_summary(employee, year: int) -> list[dict]:
    """
    One row per leave type with a balance. Reconciles exactly to LeaveBalance:
    opening_or_allocated + carried_forward + manual_adjustments == total_credits,
    and remaining == total_credits - used.
    """
    balances = list(
        LeaveBalance.objects.filter(employee=employee, year=year).exclude(leave_type=LEAVE_LWP).order_by('leave_type')
    )
    adjustments = dict(
        LeaveCreditTransaction.objects.filter(employee=employee, year=year)
        .values_list('leave_type').annotate(s=Sum('amount')).values_list('leave_type', 's')
    )
    policies = {p.leave_type: p for p in LeavePolicy.objects.filter(leave_type__in=[b.leave_type for b in balances])}
    rows = []
    for b in balances:
        manual  = adjustments.get(b.leave_type) or Decimal('0')
        pending = pending_days(employee, b.leave_type, year)
        rows.append({
            'leave_type':           b.leave_type,
            'leave_type_label':     leave_type_label(b.leave_type, policies.get(b.leave_type)),
            'opening_or_allocated': _f(b.total_days - b.carried_forward - manual),
            'carried_forward':      _f(b.carried_forward),
            'manual_adjustments':   _f(manual),
            'total_credits':        _f(b.total_days),
            'used':                 _f(b.used_days),
            'pending':              _f(pending),
            'remaining':            _f(b.total_days - b.used_days),
            'available_after_pending': _f(b.total_days - b.used_days - pending),
        })
    return rows


def _month_segments(start: datetime.date, end: datetime.date):
    current = start
    while current <= end:
        last = datetime.date(current.year, current.month, calendar.monthrange(current.year, current.month)[1])
        seg_end = min(last, end)
        yield current, seg_end
        current = seg_end + datetime.timedelta(days=1)


def _split_by_working_days(req, policy, employee) -> tuple[list[tuple[int, int, Decimal]], bool]:
    """[(year, month, days)] for one approved request's deducted days, plus whether it was approximated."""
    from .views.leave import _calc_working_days

    deducted = Decimal(req.total_days) - Decimal(req.lop_days or 0)
    if deducted <= 0:
        return [], False
    segments = list(_month_segments(req.start_date, req.end_date))
    weights = [
        Decimal(str(_calc_working_days(s, e, req.duration, policy, employee))) for s, e in segments
    ]
    total_weight = sum(weights)
    if total_weight <= 0:
        # Working-day rules no longer yield any working day (e.g. a holiday added after approval).
        return [(req.start_date.year, req.start_date.month, deducted)], True

    parts, allocated = [], Decimal('0')
    for i, ((seg_start, _), weight) in enumerate(zip(segments, weights)):
        if i == len(segments) - 1:
            share = deducted - allocated
        else:
            share = (deducted * weight / total_weight).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
            allocated += share
        if share:
            parts.append((seg_start.year, seg_start.month, share))
    return parts, False


def monthly_summary(employee, leave_type: str, year: int) -> dict | None:
    balance = LeaveBalance.objects.filter(employee=employee, leave_type=leave_type, year=year).first()
    if balance is None:
        return None
    policy = LeavePolicy.objects.filter(leave_type=leave_type).first()

    credits = {m: Decimal('0') for m in range(1, 13)}
    used    = {m: Decimal('0') for m in range(1, 13)}
    credits_outside_year = Decimal('0')
    used_next_year       = Decimal('0')
    approximated         = 0

    for amount, created_at in LeaveCreditTransaction.objects.filter(
        employee=employee, leave_type=leave_type, year=year,
    ).values_list('amount', 'created_at'):
        when = timezone.localtime(created_at)
        if when.year == year:
            credits[when.month] += amount
        else:
            credits_outside_year += amount

    requests = LeaveRequest.objects.filter(
        employee=employee, leave_type=leave_type, start_date__year=year, status=REQ_APPROVED, is_lwp=False,
    )
    for req in requests:
        parts, approx = _split_by_working_days(req, policy, employee)
        approximated += int(approx)
        for part_year, month, days in parts:
            if part_year == year:
                used[month] += days
            else:
                used_next_year += days  # booked against this year's balance (deduction uses start_date.year)

    credits_total = sum(credits.values()) + credits_outside_year
    used_itemised = sum(used.values()) + used_next_year
    return {
        'leave_type':           leave_type,
        'leave_type_label':     leave_type_label(leave_type, policy),
        'year':                 year,
        'months': [
            {'month': m, 'label': datetime.date(year, m, 1).strftime('%b %Y'),
             'credit_adjustments': _f(credits[m]), 'used': _f(used[m])}
            for m in range(1, 13)
        ],
        'credit_adjustments_outside_year': _f(credits_outside_year),
        'used_in_next_year_months':        _f(used_next_year),
        'used_not_itemised':               _f(balance.used_days - used_itemised),
        'total_credit_adjustments':        _f(credits_total),
        'total_used':                      _f(balance.used_days),
        'approximated_requests':           approximated,
    }


def transaction_history(employee, year: int, leave_type: str | None = None) -> list[dict]:
    qs = LeaveCreditTransaction.objects.filter(employee=employee, year=year).select_related('reversed_by')
    if leave_type:
        qs = qs.filter(leave_type=leave_type)
    return [serialize_transaction(t) for t in qs.order_by('-created_at')]


def serialize_transaction(txn: LeaveCreditTransaction) -> dict:
    reversed_by = getattr(txn, 'reversed_by', None)
    return {
        'id':              str(txn.id),
        'leave_type':      txn.leave_type,
        'year':            txn.year,
        'txn_type':        txn.txn_type,
        'amount':          _f(txn.amount),
        'total_before':    _f(txn.total_before),
        'total_after':     _f(txn.total_after),
        'reason':          txn.reason,
        'created_by_name': txn.created_by_name,
        'created_at':      timezone.localtime(txn.created_at).isoformat(),
        'reverses':        str(txn.reverses_id) if txn.reverses_id else None,
        'reversed_by':     str(reversed_by.id) if reversed_by else None,
        'can_reverse':     txn.txn_type == CREDIT_TXN_ADJUSTMENT and reversed_by is None,
    }
