"""
Phase 6A Task H — opt-in holiday calendar lookup. Does NOT replace
`core.cache_service.HolidayCacheService` (the existing resolver
leave_shared.py's working-days calculation uses) — that stays untouched.
This is additive infrastructure a future caller (or Task K's eventual
cutover) can switch to once calendars are the verified, migrated source
of truth for every branch.
"""
from __future__ import annotations

from django.db.models import Q


def is_holiday_for_employee(employee, date) -> 'HolidayCalendarEntry | None':  # noqa: F821
    """Non-optional holiday applying to `employee` on `date`, per whichever
    `HolidayCalendarAssignment` covers their branch (or the company-wide
    one, `branch__isnull=True`) and is effective on that date. Branch-
    specific assignments are preferred over company-wide ones when both
    exist for the same date (mirrors `Holiday.branch`'s own
    null-means-company-wide, branch-row-takes-precedence convention)."""
    from apps.hrms.models_holiday_calendar import HolidayCalendarAssignment

    branch_id = getattr(employee, 'branch_fk_id', None)

    base = HolidayCalendarAssignment.objects.filter(
        effective_from__lte=date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=date))

    assignment = None
    if branch_id:
        assignment = base.filter(branch_id=branch_id).select_related('calendar').first()
    if assignment is None:
        assignment = base.filter(branch__isnull=True).select_related('calendar').first()
    if assignment is None:
        return None
    return assignment.calendar.entries.filter(date=date, is_optional=False).first()
