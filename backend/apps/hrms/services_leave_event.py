"""Event-based ("on request") leave: maternity, paternity and similar leave that is not a yearly quota.

Normal leave (casual, sick, earned) is credited to every eligible employee each year. Maternity and paternity are different in real
companies: they are granted for one case, to one employee, when she/he applies and HR approves. A policy with grant_mode='on_request'
is therefore never credited by the yearly, monthly or joining-time credit jobs; the employee's balance for it is created here, at the
moment an eligible employee applies, holding the policy's entitlement for the event (less what was already taken in the last year, so
the same case cannot be claimed again in the next calendar year).
"""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal

from django.db.models import F, Sum

from .models import REQ_APPROVED, LeaveBalance, LeavePolicy, LeaveRequest
from .services_leave_ledger import employee_matches_policy_gender

logger = logging.getLogger(__name__)

GRANT_ANNUAL = 'annual'
GRANT_ON_REQUEST = 'on_request'
EVENT_LOOKBACK_DAYS = 365


def is_on_request(policy: LeavePolicy | None) -> bool:
    return bool(policy and policy.grant_mode == GRANT_ON_REQUEST)


def days_taken_recently(employee, leave_type: str, as_of: datetime.date) -> Decimal:
    """Approved days of this leave type (not counting days converted to Leave Without Pay) in the year before `as_of`."""
    since = as_of - datetime.timedelta(days=EVENT_LOOKBACK_DAYS)
    taken = LeaveRequest.objects.filter(
        employee=employee, leave_type=leave_type, status=REQ_APPROVED, start_date__gte=since, start_date__lte=as_of,
    ).aggregate(total=Sum(F('total_days') - F('lop_days')))['total']
    return Decimal(str(taken or 0))


def _meets_service_requirement(employee, policy: LeavePolicy, as_of: datetime.date) -> bool:
    if not policy.minimum_service_period:
        return True
    joined = getattr(employee, 'date_of_joining', None)
    if not joined:
        return False
    months = (as_of.year - joined.year) * 12 + (as_of.month - joined.month)
    return months >= policy.minimum_service_period


def ensure_event_balance(employee, leave_type: str, year: int, as_of: datetime.date | None = None) -> LeaveBalance | None:
    """The employee's balance for an on-request leave type, created now if this is their first application.

    Returns None when the type is not an on-request one (nothing to do, the normal balance lookup applies), or when the employee does
    not qualify (wrong gender, too little service); the caller's normal "no balance / not eligible" handling then applies."""
    policy = LeavePolicy.objects.filter(leave_type=leave_type, is_active=True).first()
    if not is_on_request(policy):
        return None
    existing = LeaveBalance.objects.filter(employee=employee, leave_type=leave_type, year=year).first()
    if existing:
        return existing
    as_of = as_of or datetime.date(year, 1, 1)
    if not employee_matches_policy_gender(employee, policy) or not _meets_service_requirement(employee, policy, as_of):
        return None
    entitlement = Decimal(str(policy.annual_days)) - days_taken_recently(employee, leave_type, as_of)
    balance, created = LeaveBalance.objects.get_or_create(
        employee=employee, leave_type=leave_type, year=year,
        defaults={'total_days': max(entitlement, Decimal('0')), 'used_days': 0, 'carried_forward': 0},
    )
    if created:
        logger.info('On-request %s balance of %s day(s) created for employee %s for %s', leave_type, balance.total_days, employee.pk, year)
    return balance


def hide_unused_event_balances(balances: list[LeaveBalance], employee) -> list[LeaveBalance]:
    """Drops on-request balances the employee has not touched, so maternity or paternity never shows up as a yearly balance."""
    on_request_types = set(LeavePolicy.objects.filter(grant_mode=GRANT_ON_REQUEST).values_list('leave_type', flat=True))
    if not on_request_types:
        return balances
    requested = set(
        LeaveRequest.objects.filter(employee=employee, leave_type__in=on_request_types).exclude(status__in=('rejected', 'cancelled'))
        .values_list('leave_type', 'start_date__year')
    )
    return [
        balance for balance in balances
        if balance.leave_type not in on_request_types or balance.used_days or (balance.leave_type, balance.year) in requested
    ]
