"""
Maximum Late Arrivals Per Month — a company-wide tracking limit
(Settings → Leave Policy), stored on the existing AttendanceLateMarkRules
row (late_limit_enabled, max_late_arrivals_per_month).

Tracking and display only: it never changes LOP or salary. Late-mark LOP is
decided solely by the existing late-mark rule (late_marks_per_lop /
late_mark_mode, apps.attendance.services_policy.late_mark_lop_days).

Counting: days in the calendar month with is_late=True, excluding days that
are "Late (Excused)" (an approved late-arrival justification). The count
starts again on the 1st of each month — it is always computed for one
calendar month, nothing is stored or reset.

Status: within (count < maximum), reached (count == maximum),
exceeded (count > maximum).
"""
from __future__ import annotations

import calendar
from datetime import date

from django.db.models import Count

from apps.attendance.models import AttendanceLateMarkRules, AttendanceRecord, AttendanceSettings

_FIELD = AttendanceLateMarkRules._meta
DEFAULT_ENABLED = _FIELD.get_field('late_limit_enabled').default
DEFAULT_MAXIMUM = _FIELD.get_field('max_late_arrivals_per_month').default
MAX_LIMIT = 31

STATUS_WITHIN, STATUS_REACHED, STATUS_EXCEEDED = 'within', 'reached', 'exceeded'
STATUS_LABEL = {STATUS_WITHIN: 'Within limit', STATUS_REACHED: 'Limit reached', STATUS_EXCEEDED: 'Limit exceeded'}


def _rules():
    settings = (AttendanceSettings.objects.select_related('late_mark_rules')
                .filter(is_active=True).order_by('-created_at').first())
    return getattr(settings, 'late_mark_rules', None) if settings else None


def get_limit() -> dict:
    """The company's setting; model defaults when Attendance Rules were never saved."""
    rules = _rules()
    enabled = rules.late_limit_enabled if rules else DEFAULT_ENABLED
    maximum = rules.max_late_arrivals_per_month if rules else DEFAULT_MAXIMUM
    if not maximum or maximum < 1:             # never let a bad value break the screens
        maximum = DEFAULT_MAXIMUM
    return {'enabled': bool(enabled), 'maximum': int(maximum), 'configured': rules is not None}


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _late_q(year: int, month: int):
    start, end = month_bounds(year, month)
    return AttendanceRecord.objects.filter(date__range=(start, end), is_late=True, late_excused=False)


def status_for(count: int, maximum: int) -> str:
    if count > maximum:
        return STATUS_EXCEEDED
    if count == maximum:
        return STATUS_REACHED
    return STATUS_WITHIN


def summary(employee, year: int, month: int, limit: dict | None = None) -> dict:
    limit = limit or get_limit()
    count = _late_q(year, month).filter(employee=employee).count()
    out = {'enabled': limit['enabled'], 'maximum': limit['maximum'], 'late_arrivals': count,
           'year': year, 'month': month}
    if not limit['enabled']:
        return {**out, 'remaining': None, 'status': None, 'status_label': None}
    st = status_for(count, limit['maximum'])
    return {**out, 'remaining': max(limit['maximum'] - count, 0), 'status': st, 'status_label': STATUS_LABEL[st]}


def employees_at_or_over(employee_qs, year: int, month: int, *, include_reached: bool = False,
                         limit: dict | None = None) -> list[dict]:
    """Employees (from employee_qs) whose count this month is over the maximum
    (or at it, with include_reached). Empty when the limit is disabled."""
    limit = limit or get_limit()
    if not limit['enabled']:
        return []
    threshold = limit['maximum'] if include_reached else limit['maximum'] + 1
    rows = (_late_q(year, month).filter(employee__in=employee_qs)
            .values('employee_id', 'employee__full_name', 'employee__employee_id', 'employee__branch',
                    'employee__department')
            .annotate(n=Count('id')).filter(n__gte=threshold).order_by('-n', 'employee__full_name'))
    return [{
        'employee': str(r['employee_id']), 'name': r['employee__full_name'] or '',
        'employee_code': r['employee__employee_id'] or '', 'branch': r['employee__branch'] or '',
        'department': r['employee__department'] or '', 'late_arrivals': r['n'],
        'over_by': max(r['n'] - limit['maximum'], 0),
        'status': status_for(r['n'], limit['maximum']),
        'status_label': STATUS_LABEL[status_for(r['n'], limit['maximum'])],
    } for r in rows]
