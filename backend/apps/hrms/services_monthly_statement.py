"""
Monthly leave statement (Phase B) — the single calculation used by the
employee dashboard, leave-application validation, approval recheck and
month-end expiry for leave types on the Monthly credit schedule.

Business rules (approved):
  1. Only the unused part of a month's *monthly credit* expires, and only
     for monthly-schedule policies with monthly carry-forward disabled.
     Opening balances, carried-in amounts, annual lump credits and manual
     adjustments form a non-expiring pool.
  2. Leave in a future month can use only credits already recorded for
     that month, plus the non-expiring pool.
  3. Leave that was pending when a month closed is protected from that
     month's expiry; if it is later rejected/cancelled, the month's expiry is
     recalculated.
  4. Policy changes take effect from LeavePolicy.monthly_rules_from (the 1st
     of the month after the change). Months before it are never recalculated.

Consumption model, per month m of the balance year:
  - The non-expiring pool starts the year with everything in the balance
    that is not a monthly credit or expiry: opening/carried-in days, any
    annual lump and manual adjustments (they never expire, so they count
    from January whenever they were entered).
  - Carry-forward month: the month's credit joins the running pool; leave
    used/pending in the month comes out of the pool.
  - No-carry month: leave first uses that month's credit, the rest comes
    from the pool. Once the month has closed, whatever credit was not used by
    leave booked before the close (approved or still pending) expires.
    Leave booked after the close never uses that month's (expired) credit.

LeaveBalance stays the source of truth: expiry is written as an append-only
'monthly_expiry' ledger entry through apply_adjustment(), never by editing
or deleting history. A statement reconciles with the yearly balance:
    closing (December) + pending == total_days - used_days
once every closed month's expiry has been recorded.
"""
from __future__ import annotations

import calendar
import datetime
import logging
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from .models import (
    CREDIT_SCHEDULE_MONTHLY, CREDIT_TXN_EXPIRY, CREDIT_TXN_MONTHLY, LEAVE_LWP,
    REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING,
    LeaveBalance, LeaveCreditTransaction, LeaveRequest,
)

logger = logging.getLogger(__name__)

ZERO = Decimal('0')
_ONE_DP = Decimal('0.1')
_TWO_DP = Decimal('0.01')


# ─── Policy helpers ───────────────────────────────────────────────────────────

def is_monthly(policy) -> bool:
    return bool(policy) and getattr(policy, 'credit_schedule', None) == CREDIT_SCHEDULE_MONTHLY


def annual_allocation(policy) -> Decimal:
    """Days an annual-lump path (joining, back-fill, Credit All, yearly reset) may grant."""
    return ZERO if is_monthly(policy) else Decimal(policy.annual_days)


def _today() -> datetime.date:
    """Today's date in the company time zone (one place, so tests can fix it)."""
    return timezone.localdate()


def month_start(year: int, month: int) -> datetime.date:
    return datetime.date(year, month, 1)


def month_close(year: int, month: int) -> datetime.date:
    """First day after the month — the moment it closes."""
    return month_start(year, month) + datetime.timedelta(days=calendar.monthrange(year, month)[1])


def next_month_start(today: datetime.date | None = None) -> datetime.date:
    today = today or _today()
    return month_close(today.year, today.month)


def is_closed(year: int, month: int, today: datetime.date | None = None) -> bool:
    return (today or _today()) >= month_close(year, month)


def rules_cover(policy, year: int, month: int) -> bool:
    """Do the policy's current monthly rules apply to this month (rule 4)?"""
    rules_from = getattr(policy, 'monthly_rules_from', None)
    return rules_from is None or month_start(year, month) >= rules_from


def expiry_applies(policy, year: int, month: int) -> bool:
    return is_monthly(policy) and not policy.monthly_carry_forward and rules_cover(policy, year, month)


def _q2(value) -> Decimal:
    return Decimal(value).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


# ─── Statement ────────────────────────────────────────────────────────────────

@dataclass
class MonthRow:
    month:       int
    label:       str
    carry_off:   bool      # this month's credit is month-only (expires if unused)
    closed:      bool
    carried_in:  Decimal   # non-expiring pool brought into the month
    credit:      Decimal   # monthly credit recorded for the month
    used:        Decimal   # approved leave days in the month
    pending:     Decimal   # pending leave days in the month
    expired:     Decimal   # credit expired at month end (closed no-carry months)
    credit_left: Decimal   # this month's credit still usable (open no-carry months only)
    closing:     Decimal   # available at month end: pool + credit_left

    def as_dict(self) -> dict:
        return {
            'month': self.month, 'label': self.label, 'carry_off': self.carry_off, 'closed': self.closed,
            **{k: float(_q2(getattr(self, k))) for k in (
                'carried_in', 'credit', 'used', 'pending', 'expired', 'credit_left', 'closing',
            )},
        }


@dataclass
class Statement:
    year:              int
    opening:           Decimal              # non-expiring pool at 1 Jan (opening/carried-in/lump/adjustments)
    adjustments:       Decimal              # manual adjustments within `opening`
    used_not_itemised: Decimal              # used days not tied to a request (e.g. imported)
    months:            list[MonthRow] = field(default_factory=list)
    expiry_target:     dict = field(default_factory=dict)    # month -> expiry that should be recorded
    expiry_recorded:   dict = field(default_factory=dict)    # month -> expiry already recorded
    lowest_pool:       Decimal = ZERO                        # most negative running pool (0 when fine)
    total_days:        Decimal = ZERO
    used_days:         Decimal = ZERO

    @property
    def shortfall(self) -> Decimal:
        return -self.lowest_pool if self.lowest_pool < 0 else ZERO

    @property
    def total_pending(self) -> Decimal:
        return sum((m.pending for m in self.months), ZERO)

    @property
    def unexpired_month_credit(self) -> Decimal:
        """Unused credit of open no-carry months — usable only in its own month, so not in the pool."""
        return sum((m.credit_left for m in self.months[:-1]), ZERO)

    @property
    def reconciled(self) -> bool:
        """December closing + pending + month-only credit == yearly total - used
        (true once every due expiry has been recorded)."""
        closing = self.months[-1].closing if self.months else self.opening
        expected = Decimal(self.total_days) - Decimal(self.used_days)
        return abs(closing + self.total_pending + self.unexpired_month_credit - expected) < Decimal('0.05')


def _local_date(dt) -> datetime.date:
    return timezone.localtime(dt).date() if timezone.is_aware(dt) else dt.date()


def _parts(req, policy, employee, year: int) -> list[tuple[int, Decimal]]:
    """[(month, days)] of a request's deducted days within the balance year.
    Days falling in the next year are booked to December (the request is
    deducted from its start year's balance, as approval already does)."""
    from .services_leave_credit import _split_by_working_days
    parts, _ = _split_by_working_days(req, policy, employee)
    out = []
    for part_year, month, days in parts:
        if part_year == year:
            out.append((month, Decimal(days)))
        elif part_year > year:
            out.append((12, Decimal(days)))
        else:
            out.append((1, Decimal(days)))
    return out


def build_statement(employee, policy, year: int, *, today: datetime.date | None = None,
                    exclude_request_id=None, extra_request=None) -> Statement | None:
    """
    `extra_request` is a not-yet-saved request (anything with start_date,
    end_date, duration, total_days, lop_days, created_at) counted as pending —
    used to test whether a new application fits. `exclude_request_id` leaves
    one saved request out entirely.
    """
    today = today or _today()
    balance = LeaveBalance.objects.filter(employee=employee, leave_type=policy.leave_type, year=year).first()
    if balance is None:
        return None

    credit = {m: ZERO for m in range(1, 13)}
    expired_rec = {m: ZERO for m in range(1, 13)}
    monthly_total = adjustments = ZERO
    for amount, txn_month, txn_type in LeaveCreditTransaction.objects.filter(
        employee=employee, leave_type=policy.leave_type, year=year,
    ).values_list('amount', 'month', 'txn_type'):
        if txn_type == CREDIT_TXN_MONTHLY and txn_month:
            credit[txn_month] += amount
            monthly_total += amount
        elif txn_type == CREDIT_TXN_EXPIRY and txn_month:
            expired_rec[txn_month] += -amount
            monthly_total += amount
        else:
            adjustments += amount

    # in-time (booked before the month closed) vs late usage/pending, per month
    in_used = {m: ZERO for m in range(1, 13)}
    late_used = {m: ZERO for m in range(1, 13)}
    in_pend = {m: ZERO for m in range(1, 13)}
    late_pend = {m: ZERO for m in range(1, 13)}
    approved_itemised = ZERO

    requests = list(
        LeaveRequest.objects.filter(
            employee=employee, leave_type=policy.leave_type, start_date__year=year, is_lwp=False,
            status__in=(REQ_APPROVED, REQ_PENDING, REQ_L2_PENDING),
        ).exclude(id=exclude_request_id)
    )
    if extra_request is not None:
        requests.append(extra_request)
    for req in requests:
        booked = _local_date(req.created_at) if getattr(req, 'created_at', None) else today
        approved = getattr(req, 'status', REQ_PENDING) == REQ_APPROVED
        for month, days in _parts(req, policy, employee, year):
            late = booked >= month_close(year, month)
            if approved:
                approved_itemised += days
                (late_used if late else in_used)[month] += days
            else:
                (late_pend if late else in_pend)[month] += days

    used_not_itemised = Decimal(balance.used_days) - approved_itemised
    # Everything that is not a monthly credit/expiry: opening, carried-in, lump, adjustments.
    opening = Decimal(balance.total_days) - monthly_total
    pool = opening - (used_not_itemised if used_not_itemised > 0 else ZERO)
    lowest = pool if pool < 0 else ZERO

    stmt = Statement(year=year, opening=opening, adjustments=adjustments, used_not_itemised=used_not_itemised,
                     total_days=Decimal(balance.total_days), used_days=Decimal(balance.used_days))
    for m in range(1, 13):
        closed = is_closed(year, m, today)
        carry_off = expiry_applies(policy, year, m) or expired_rec[m] != 0
        used = in_used[m] + late_used[m]
        pending = in_pend[m] + late_pend[m]
        carried_in = pool
        expired = credit_left = ZERO

        if carry_off and closed:
            in_need = in_used[m] + in_pend[m]
            from_credit = min(credit[m], in_need) if credit[m] > 0 else ZERO
            unused = credit[m] - from_credit
            target = (unused if unused > 0 else ZERO).quantize(_ONE_DP, rounding=ROUND_DOWN)
            if expiry_applies(policy, year, m):
                stmt.expiry_target[m] = target
                expired = target
            else:                       # frozen month (rule 4): keep what was recorded
                expired = expired_rec[m]
            pool += credit[m] - from_credit - expired        # rounding residual stays usable
            overflow = (in_need - from_credit) + late_used[m] + late_pend[m]
        elif carry_off:
            need = used + pending
            from_credit = min(credit[m], need) if credit[m] > 0 else ZERO
            credit_left = credit[m] - from_credit
            overflow = need - from_credit
        else:
            pool += credit[m]
            overflow = used + pending

        stmt.expiry_recorded[m] = expired_rec[m]
        pool -= overflow
        if pool < lowest:
            lowest = pool
        stmt.months.append(MonthRow(
            month=m, label=month_start(year, m).strftime('%b %Y'), carry_off=carry_off, closed=closed,
            carried_in=carried_in, credit=credit[m], used=used, pending=pending,
            expired=expired, credit_left=credit_left, closing=pool + credit_left,
        ))
    stmt.lowest_pool = lowest
    return stmt


# ─── Validation ───────────────────────────────────────────────────────────────

def request_shortfall(employee, policy, year: int, *, start, end, duration, total_days,
                      lop_days=ZERO, created_at=None, exclude_request_id=None,
                      today: datetime.date | None = None) -> Decimal:
    """
    Days of this (new or re-checked) request the monthly entitlement cannot
    cover: the extra deficit it adds to the running statement. 0 means it fits.
    Call with the balance row already locked (select_for_update).
    """
    without = build_statement(employee, policy, year, today=today, exclude_request_id=exclude_request_id)
    if without is None:
        return Decimal(str(total_days))
    hypothetical = SimpleNamespace(
        start_date=start, end_date=end, duration=duration, total_days=Decimal(str(total_days)),
        lop_days=Decimal(str(lop_days or 0)), created_at=created_at or timezone.now(), status=REQ_PENDING,
    )
    with_req = build_statement(employee, policy, year, today=today, exclude_request_id=exclude_request_id,
                               extra_request=hypothetical)
    extra = with_req.shortfall - without.shortfall
    if extra <= 0:
        return ZERO
    return min(extra, Decimal(str(total_days))).quantize(_ONE_DP, rounding=ROUND_UP)


def monthly_rules_apply_to_request(policy, start, end) -> bool:
    """Monthly validation applies when the policy is monthly and the request reaches a month its rules cover."""
    return is_monthly(policy) and rules_cover(policy, end.year, end.month)


# ─── Expiry ───────────────────────────────────────────────────────────────────

def sync_expiries(employee, policy, year: int, *, today: datetime.date | None = None, actor=None) -> Decimal:
    """
    Bring the recorded expiry of every closed, rule-covered month of `year`
    in line with the statement — by difference, through apply_adjustment(),
    so reruns/catch-ups are idempotent and history is never deleted. Locks
    the balance row first. Returns the net change applied (negative = more
    expired).
    """
    from .services_leave_credit import LeaveCreditError, apply_adjustment

    # Targets exist only for months the current no-carry rules cover; months
    # recorded under an earlier rule are frozen (rule 4), so carry-forward or
    # annual policies have nothing to sync.
    if not (is_monthly(policy) and not policy.monthly_carry_forward):
        return ZERO
    net = ZERO
    with transaction.atomic():
        balance = (
            LeaveBalance.objects.select_for_update()
            .filter(employee=employee, leave_type=policy.leave_type, year=year).first()
        )
        if balance is None:
            return ZERO
        stmt = build_statement(employee, policy, year, today=today)
        for month, target in sorted(stmt.expiry_target.items()):
            recorded = stmt.expiry_recorded.get(month, ZERO)
            change = recorded - target          # ledger amount: negative expires more, positive restores
            if change == 0:
                continue
            label = month_start(year, month).strftime('%b %Y')
            reason = (f'Unused monthly credit for {label} expired at month end' if recorded == 0
                      else f'Expiry for {label} recalculated ({recorded} → {target} day(s))')
            try:
                apply_adjustment(
                    employee=employee, leave_type=policy.leave_type, year=year, amount=change,
                    reason=reason, actor=actor, idempotency_key=uuid.uuid4().hex,
                    month=month, txn_type=CREDIT_TXN_EXPIRY,
                )
            except LeaveCreditError as exc:
                logger.warning('Monthly expiry for %s %s %s/%s skipped: %s',
                               employee.employee_id, policy.leave_type, month, year, exc)
                continue
            net += change
    return net


def reopen_month_expiry(employee, policy, year: int, month: int, *, actor=None) -> Decimal:
    """
    Before a closed month's credit is reduced: add back that month's recorded
    expiry (an append-only 'monthly_expiry' entry), so the credit reduction
    never has to take the balance below zero; sync_expiries() then re-expires
    the correct amount. Call inside the same transaction, balance row locked.
    """
    from .services_leave_credit import apply_adjustment

    if not expiry_applies(policy, year, month):
        return ZERO
    recorded = -sum(LeaveCreditTransaction.objects.filter(
        employee=employee, leave_type=policy.leave_type, year=year, month=month, txn_type=CREDIT_TXN_EXPIRY,
    ).values_list('amount', flat=True), ZERO)
    if recorded <= 0:
        return ZERO
    label = month_start(year, month).strftime('%b %Y')
    apply_adjustment(
        employee=employee, leave_type=policy.leave_type, year=year, amount=recorded,
        reason=f'Expiry for {label} reopened for a change to the month\'s credit', actor=actor,
        idempotency_key=uuid.uuid4().hex, month=month, txn_type=CREDIT_TXN_EXPIRY,
    )
    return recorded


def sync_after_request_change(leave_request, policy=None) -> None:
    """After a pending request is rejected/cancelled/deleted: recalculate expiry of the closed months it touched."""
    if leave_request.is_lwp:
        return
    if policy is None:
        from .models import LeavePolicy
        policy = LeavePolicy.objects.filter(leave_type=leave_request.leave_type).first()
    if not (is_monthly(policy) and not policy.monthly_carry_forward):
        return
    year = leave_request.start_date.year
    if not any(is_closed(year, m) for m, _ in _parts(leave_request, policy, leave_request.employee, year)):
        return
    sync_expiries(leave_request.employee, policy, year)


def unused_for_carry_forward(employee, policy, balance) -> Decimal:
    """Year-end unused days for the yearly carry-forward. Annual policies: total - used,
    exactly as before. Monthly no-carry policies: also excludes credit whose expiry
    is due but not yet recorded, so carry-forward never carries expiring credit."""
    unused = Decimal(balance.total_days) - Decimal(balance.used_days)
    if not (is_monthly(policy) and not policy.monthly_carry_forward):
        return unused
    stmt = build_statement(employee, policy, balance.year, today=month_close(balance.year, 12))
    if stmt is None:
        return unused
    due = sum((t - stmt.expiry_recorded.get(m, ZERO) for m, t in stmt.expiry_target.items()), ZERO)
    return unused - (due if due > 0 else ZERO)
