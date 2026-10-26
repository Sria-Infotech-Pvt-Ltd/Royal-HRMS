"""
Phase 6A Task C.2 — ledger-to-cache recomputation. Precise mapping,
stated once here rather than scattered across call sites:

- `total_days` (today's meaning: granted entitlement for the year,
  including carry-forward, NOT reduced by usage) = sum of quantity for
  every transaction whose txn_type is in `LeaveTransaction.ENTITLEMENT_TYPES`
  (opening, accrual, proration, adjustment, carry_forward_in,
  carry_forward_out, lapse — lapse and carry_forward_out are stored
  negative, so they net out correctly).
- `used_days` = -1 * sum of quantity for every transaction whose txn_type
  is in `LeaveTransaction.USAGE_TYPES` (availed is stored negative,
  availed_reversal/cancellation positive, so this sum is naturally
  negative and flipping its sign gives a positive "days used").
- `carried_forward` = sum of quantity for carry_forward_in/carry_forward_out
  transactions only — the net OUTSTANDING carry-forward lot amount, not
  the full entitlement.
- `carry_forward_expiry_date` = the latest `expiry_date` among
  carry_forward_in transactions that still have unexpired/unconsumed
  quantity (a simplification — lot-level partial consumption isn't
  tracked per-lot in this pass, see PHASE6A_REPORT.md).

This function is NOT called from the existing balance-writing code paths
(tasks.py's three scheduler jobs, leave_shared.py's `_deduct_balance`) in
this pass — it exists so a caller that creates ledger transactions (comp-off
earning, in this pass) can keep `LeaveBalance` in sync for that one leave
type/year, without migrating every existing write path onto the ledger
(Task K's full cutover, deferred).
"""
from __future__ import annotations

from django.db.models import Sum

from apps.hrms.models_leave_ledger import LeaveTransaction


def recompute_balance_cache(employee, leave_type, year: int):
    from apps.hrms.models import LeaveBalance

    qs = LeaveTransaction.objects.filter(employee=employee, leave_type=leave_type, leave_year=year)

    total_days = qs.filter(txn_type__in=LeaveTransaction.ENTITLEMENT_TYPES).aggregate(s=Sum('quantity'))['s'] or 0
    used_days = qs.filter(txn_type__in=LeaveTransaction.USAGE_TYPES).aggregate(s=Sum('quantity'))['s'] or 0
    carried_forward = qs.filter(
        txn_type__in=[LeaveTransaction.TXN_CARRY_FORWARD_IN, LeaveTransaction.TXN_CARRY_FORWARD_OUT],
    ).aggregate(s=Sum('quantity'))['s'] or 0

    latest_expiry = (
        qs.filter(txn_type=LeaveTransaction.TXN_CARRY_FORWARD_IN, expiry_date__isnull=False)
        .order_by('-expiry_date')
        .values_list('expiry_date', flat=True)
        .first()
    )

    balance, _ = LeaveBalance.objects.get_or_create(
        employee=employee, leave_type=leave_type.code, year=year,
        defaults={'leave_type_ref': leave_type},
    )
    balance.leave_type_ref = leave_type
    balance.total_days = total_days
    balance.used_days = -used_days
    balance.carried_forward = carried_forward
    balance.carry_forward_expiry_date = latest_expiry
    balance.save(update_fields=['leave_type_ref', 'total_days', 'used_days', 'carried_forward', 'carry_forward_expiry_date', 'updated_at'])
    return balance


def is_unpaid_lwp(leave_type_code: str) -> bool:
    """Phase 6A Task A.4 — replaces direct `leave_type == LEAVE_LWP`
    comparisons with a LeaveType attribute read, so an admin-created type
    marked `is_unpaid_lwp=True` behaves like LWP everywhere this is used,
    without a code change. Falls back to the old literal comparison if no
    LeaveType row exists yet for this code (e.g. `seed_leave_types` hasn't
    run) — never silently treats an unseeded code as "not LWP" when it
    actually is the legacy 'lwp' code."""
    from apps.hrms.models import LEAVE_LWP
    from apps.hrms.models_leave_ledger import LeaveType

    row = LeaveType.objects.filter(code=leave_type_code).values_list('is_unpaid_lwp', flat=True).first()
    if row is not None:
        return row
    return leave_type_code == LEAVE_LWP


def employee_matches_policy_gender(employee, policy) -> bool:
    """Return whether an employee's recorded profile gender satisfies a policy."""
    required_gender = (policy.applicable_gender or 'all').strip().lower()
    if required_gender in ('', 'all'):
        return True

    cached_gender = getattr(employee, '_leave_policy_gender', None)
    if cached_gender is None:
        from apps.accounts.models import EmployeeProfile

        profile = EmployeeProfile.objects.filter(user_id=employee.pk).only('gender').first()
        cached_gender = (profile.gender or '').strip().lower() if profile else ''
        employee._leave_policy_gender = cached_gender
    return cached_gender == required_gender


def create_transaction(employee, leave_type, *, txn_type, quantity, effective_date, leave_year=None,
                        expiry_date=None, reason='', run_id='', created_by=None, reversal_of=None) -> LeaveTransaction:
    """Creates one ledger entry and recomputes that employee/type/year's
    LeaveBalance cache in the same call — never leaves the cache stale
    relative to the ledger it was just told about."""
    leave_year = leave_year or effective_date.year
    txn = LeaveTransaction.objects.create(
        employee=employee, leave_type=leave_type, leave_year=leave_year, txn_type=txn_type,
        quantity=quantity, effective_date=effective_date, expiry_date=expiry_date,
        reason=reason, run_id=run_id, created_by=created_by, reversal_of=reversal_of,
    )
    recompute_balance_cache(employee, leave_type, leave_year)
    return txn
