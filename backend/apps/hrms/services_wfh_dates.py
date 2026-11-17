"""Which start dates a work-from-home request may have.

A request for a day that has already happened can turn an office day, a late arrival or even an absence into a WFH day after the
fact, and the home-location check cannot be met retroactively. So by default only today or a later date is accepted; HR can allow
a few days back with the "WFH requests may start this many days in the past" setting (Attendance Config, Punch Rules).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from core.date_utils import format_date_display


def wfh_backdate_limit_days() -> int:
    """The saved limit (days in the past a request may start); 0 when settings are missing or older than the setting."""
    from core.cache_service import AttendanceSettingsCacheService

    settings_row = AttendanceSettingsCacheService.get()
    rules = getattr(settings_row, 'punch_rules', None) if settings_row else None
    return max(0, int(getattr(rules, 'wfh_max_backdated_days', 0) or 0))


def wfh_start_refusal(start: date, today: date, max_days_back: int) -> Optional[str]:
    """Why a request starting on `start` is refused today, or None if it is allowed. A future start is always allowed."""
    earliest = today - timedelta(days=max(0, max_days_back))
    if start >= earliest:
        return None
    if max_days_back <= 0:
        return 'Work from home can only be requested for today or a future date. Past dates are not allowed.'
    return (
        f'Work from home can be requested up to {max_days_back} day(s) in the past, from {format_date_display(earliest)}. '
        'Choose a later start date.'
    )
