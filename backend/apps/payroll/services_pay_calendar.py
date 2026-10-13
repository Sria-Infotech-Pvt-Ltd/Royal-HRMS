"""
Phase 7B Task A — generate_periods() (the actual day-of-month/period-length
math PayrollSettings' fields never got wired to, see models_pay_calendar.py's
module docstring) and link_historical_cycles() (best-effort linking of
pre-existing PayrollCycle rows to a PayGroup/PayPeriod).

Weekend/holiday pay-date adjustment reuses the LEGACY `Holiday` model
(apps.hrms.models) — not the newer HolidayCalendar system — because
Holiday is what every other holiday-aware calculation in this codebase
already reads (HolidayCacheService, used by leave's working-days calc);
HolidayCalendar is a Phase 6A addition nothing else consults yet. Matching
the already-consumed model is lower-risk than introducing a second
holiday source of truth for one new feature.
"""
import calendar as calendar_module
import datetime
from dateutil.relativedelta import relativedelta

from django.db.models import Q

from apps.hrms.models import Holiday
from apps.payroll.models import PayGroup, PayPeriod, PayrollCalendar, PayrollCycle


def _clamp_day(year: int, month: int, day: int) -> int:
    """Day-of-month values like pay_day=30 don't exist in February —
    clamp to the last real day of that month, the same thing
    `date.replace(day=...)` would otherwise raise ValueError on."""
    last_day = calendar_module.monthrange(year, month)[1]
    return min(day, last_day)


def _financial_year_start(for_date: datetime.date) -> int:
    return for_date.year if for_date.month >= 4 else for_date.year - 1


def _is_holiday(for_date: datetime.date, branch) -> bool:
    qs = Holiday.objects.filter(date=for_date, is_active=True)
    # Company-wide holidays (branch=None) always apply, PLUS this branch's
    # own — mirrors Holiday's own nullable-branch "company-wide" convention.
    qs = qs.filter(Q(branch__isnull=True) | Q(branch=branch)) if branch is not None else qs.filter(branch__isnull=True)
    return qs.exists()


def _is_non_working_day(for_date: datetime.date, branch) -> bool:
    return for_date.weekday() >= 5 or _is_holiday(for_date, branch)  # Sat=5, Sun=6


def _adjust_pay_date(raw_pay_date: datetime.date, rule: str, branch) -> datetime.date:
    if rule == PayrollCalendar.ADJUST_NONE:
        return raw_pay_date
    step = -1 if rule == PayrollCalendar.ADJUST_PREVIOUS else 1
    adjusted = raw_pay_date
    # Bounded loop (any real holiday calendar clears within a handful of
    # days) — not unbounded, so a pathological all-holiday stretch can
    # never hang this.
    for _ in range(14):
        if not _is_non_working_day(adjusted, branch):
            return adjusted
        adjusted += datetime.timedelta(days=step)
    return adjusted


def _monthly_periods(calendar: PayrollCalendar, year: int) -> list:
    periods = []
    for month in range(1, 13):
        period_start = datetime.date(year, month, _clamp_day(year, month, calendar.cycle_start_day))
        end_month_date = datetime.date(year, month, 1) + relativedelta(months=1)
        period_end = datetime.date(
            end_month_date.year, end_month_date.month,
            _clamp_day(end_month_date.year, end_month_date.month, calendar.cycle_end_day),
        )
        raw_pay_date = datetime.date(
            end_month_date.year, end_month_date.month,
            _clamp_day(end_month_date.year, end_month_date.month, calendar.pay_day),
        )
        periods.append((period_start, period_end, raw_pay_date))
    return periods


def _semi_monthly_periods(calendar: PayrollCalendar, year: int) -> list:
    """First half: 1st to the 15th, pay on the 1st-half's pay day (reuses
    cycle_start_day/cycle_end_day loosely as "split point" — documented as
    a simplification; a dedicated split-day field would be Task A's own
    natural follow-up if semi-monthly sees real use)."""
    periods = []
    for month in range(1, 13):
        last_day = calendar_module.monthrange(year, month)[1]
        periods.append((
            datetime.date(year, month, 1), datetime.date(year, month, 15),
            datetime.date(year, month, 20),
        ))
        periods.append((
            datetime.date(year, month, 16), datetime.date(year, month, last_day),
            datetime.date(year, month, _clamp_day(year, month, calendar.pay_day)),
        ))
    return periods


def _fixed_length_periods(calendar: PayrollCalendar, year: int) -> list:
    """Weekly/bi-weekly/daily — deterministic from calendar.anchor_date so
    period boundaries never shift depending on which year is requested."""
    if not calendar.anchor_date or not calendar.period_length_days:
        raise ValueError(f'{calendar.code}: anchor_date and period_length_days are required for {calendar.frequency}.')

    length = datetime.timedelta(days=calendar.period_length_days)
    year_start = datetime.date(year, 1, 1)
    year_end = datetime.date(year, 12, 31)

    # Walk forward/back from the anchor to the first period_start at or
    # before year_start, then generate forward through year_end.
    cursor = calendar.anchor_date
    if cursor > year_start:
        while cursor > year_start:
            cursor -= length
    else:
        while cursor + length <= year_start:
            cursor += length

    periods = []
    pay_lag_days = calendar.period_length_days  # pay one period-length after period_end, a plain documented default
    while cursor <= year_end:
        period_start = cursor
        period_end = cursor + length - datetime.timedelta(days=1)
        raw_pay_date = period_end + datetime.timedelta(days=pay_lag_days)
        if period_end >= year_start:  # skip the lead-in period entirely before this year
            periods.append((period_start, period_end, raw_pay_date))
        cursor += length
    return periods


def generate_periods(calendar: PayrollCalendar, year: int) -> list:
    """Generates (or returns existing) PayPeriod rows covering `year` for
    `calendar`. Idempotent — re-running for the same year finds the same
    rows via get_or_create on the (calendar, period_start, period_end)
    unique constraint, rather than duplicating them."""
    if calendar.frequency == PayrollCalendar.FREQ_MONTHLY:
        raw_periods = _monthly_periods(calendar, year)
    elif calendar.frequency == PayrollCalendar.FREQ_SEMI_MONTHLY:
        raw_periods = _semi_monthly_periods(calendar, year)
    else:
        raw_periods = _fixed_length_periods(calendar, year)

    created_periods = []
    for period_start, period_end, raw_pay_date in raw_periods:
        pay_date = _adjust_pay_date(raw_pay_date, calendar.pay_date_adjustment_rule, calendar.branch)
        period, _ = PayPeriod.objects.get_or_create(
            calendar=calendar, period_start=period_start, period_end=period_end,
            defaults={
                'raw_pay_date': raw_pay_date, 'pay_date': pay_date,
                'financial_year_start': _financial_year_start(period_start),
            },
        )
        created_periods.append(period)
    return created_periods


def link_historical_cycles(pay_group: PayGroup) -> dict:
    """Best-effort: for every PayrollCycle with no pay_group/pay_period yet
    whose branch matches `pay_group`'s own branch scope, find a PayPeriod
    on pay_group.calendar whose (period_start, period_end) overlaps the
    cycle's (cycle_start, cycle_end) and link both FKs. Cycles with no
    overlapping period are left unlinked and counted separately — this is
    a real, visible gap report, not something papered over by widening the
    match or inventing a period."""
    cycles_qs = PayrollCycle.objects.filter(pay_group__isnull=True, branch=pay_group.branch)
    linked = 0
    unmatched = []
    for cycle in cycles_qs:
        period = PayPeriod.objects.filter(
            calendar=pay_group.calendar,
            period_start__lte=cycle.cycle_end, period_end__gte=cycle.cycle_start,
        ).first()
        if period is None:
            unmatched.append(str(cycle.id))
            continue
        cycle.pay_group = pay_group
        cycle.pay_period = period
        cycle.save(update_fields=['pay_group', 'pay_period'])
        linked += 1

    return {'linked': linked, 'unmatched_cycle_ids': unmatched}
