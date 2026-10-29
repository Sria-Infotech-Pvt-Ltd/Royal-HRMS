"""
Headcount, defined once. Every screen that shows "how many employees" (dashboards, the Employees directory KPIs,
attendance, payroll, branch cards) reads it from here so the same filter always gives the same number.

An employee is an account that has an employee record (a non-blank employee_id). System/admin accounts and portal
candidates have none, so they are never counted.

Buckets (mutually exclusive, so total == active + onboarding + notice_period):
- notice_period: still working, with an approved separation whose last working day is today or later.
- onboarding:    still working, onboarding not complete yet (and not on notice).
- active:        still working, onboarded, not on notice. Probation is part of active.
- probation:     informational subset of active (employment_status == probation); NOT an extra bucket.
- exited:        deactivated (is_active False). Reported next to the buckets, never part of total.

`as_of` (default today) fixes the date the notice-period rule is evaluated on, and when given explicitly also leaves out
people who join after that date.
"""
from __future__ import annotations

from datetime import date

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.accounts.models import User
from apps.accounts.services_onboarding import fully_onboarded_q, onboarding_q


def _in_branch(queryset: QuerySet, branch) -> QuerySet:
    """`branch` is a Branch instance or a branch name; matches the linked branch or the legacy name text."""
    if not branch:
        return queryset
    name = getattr(branch, 'branch_name', branch)
    branch_pk = getattr(branch, 'pk', None)
    condition = Q(branch__iexact=str(name).strip())
    if branch_pk is not None:
        condition |= Q(branch_fk_id=branch_pk)
    return queryset.filter(condition)


def current_workforce(branch=None) -> QuerySet:
    """Employees who are working now: active accounts with an employee record. The base of every headcount."""
    return _in_branch(User.objects.filter(is_active=True).exclude(employee_id=''), branch)


def get_headcount(branch=None, as_of: date | None = None, base_queryset: QuerySet | None = None) -> dict:
    """The headcount buckets described in the module docstring.

    `base_queryset` lets a caller that already narrowed the people (a manager's reports, a department filter) count that
    exact set; it must include deactivated people if `exited` should be reported, and is still stripped of blank ids.
    """
    from apps.hrms.models import SEP_APPROVED, SeparationRequest

    day = as_of or date.today()
    records = base_queryset if base_queryset is not None else User.objects.all()
    records = _in_branch(records.exclude(employee_id=''), branch)

    current = records.filter(is_active=True)
    if as_of is not None:
        current = current.filter(date_of_joining__lte=as_of)
    current = current.annotate(is_on_notice=Exists(
        SeparationRequest.objects.filter(
            employee=OuterRef('pk'), status=SEP_APPROVED, proposed_last_working_day__gte=day,
        )
    ))

    on_notice = current.filter(is_on_notice=True)
    not_on_notice = current.filter(is_on_notice=False)
    onboarded = not_on_notice.filter(fully_onboarded_q())

    active = onboarded.count()
    onboarding = not_on_notice.filter(onboarding_q()).count()
    notice_period = on_notice.count()
    return {
        'total': active + onboarding + notice_period,
        'active': active,
        'probation': onboarded.filter(employment_status=User.EMPLOYMENT_STATUS_PROBATION).count(),
        'onboarding': onboarding,
        'notice_period': notice_period,
        'exited': records.filter(is_active=False).count(),
        'as_of': day.isoformat(),
    }
