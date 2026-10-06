"""
Phase 1 Task G — number-series allocation service. Concurrency-safe
(SELECT ... FOR UPDATE inside a transaction), generalising the pattern
apps.accounts.models.EmployeeCodeSettings.generate_employee_id already
uses for employee codes.

NOT yet wired into employee-code generation itself in this phase — see
PHASE1_REPORT.md for why that cutover (behind feature flag `numbering.v2`,
default OFF) is deferred to its own pass rather than rushed here. This
service is real, tested, working infrastructure; EmployeeCodeSettings/
EmployeeCodeSeries remain the only thing actually issuing employee codes
today.
"""
from __future__ import annotations

import datetime
import re

from django.db import transaction

from apps.platform_core.models import NumberSeries

_SEQ_TOKEN_RE = re.compile(r'\{SEQ:(\d+)\}')


class NumberSeriesExhausted(Exception):
    pass


def _reset_key(series: NumberSeries, on_date: datetime.date) -> str:
    if series.reset_period == NumberSeries.RESET_YEARLY:
        return str(on_date.year)
    if series.reset_period == NumberSeries.RESET_MONTHLY:
        return f'{on_date.year}-{on_date.month:02d}'
    if series.reset_period == NumberSeries.RESET_FINANCIAL_YEAR:
        # April-start FY convention, matching this codebase's existing
        # financial_year_start_month default (see LegalEntity) — a series
        # scoped to an entity with a different FY start is a Phase-7-era
        # refinement, not needed for the one entity this app has today.
        fy_start_year = on_date.year if on_date.month >= 4 else on_date.year - 1
        return f'FY{fy_start_year}-{fy_start_year + 1}'
    return ''


def _render(series: NumberSeries, seq: int, on_date: datetime.date, *, entity_token: str = '', branch_token: str = '') -> str:
    fy_token = _reset_key(series, on_date) if series.reset_period == NumberSeries.RESET_FINANCIAL_YEAR else ''
    # {SEQ:n}'s own n always wins over the separate `padding` field — two
    # sources of truth for the same thing (a pattern edited to {SEQ:3}
    # without also updating `padding` to 3) must not silently leave the
    # literal token un-rendered. Regex substitution, not a single
    # exact-string .replace(), is what makes this authoritative.
    rendered = _SEQ_TOKEN_RE.sub(lambda m: str(seq).zfill(int(m.group(1))), series.pattern)
    return (
        rendered
        .replace('{PREFIX}', series.prefix)
        .replace('{YYYY}', str(on_date.year))
        .replace('{YY}', str(on_date.year)[-2:])
        .replace('{MM}', f'{on_date.month:02d}')
        .replace('{FY}', fy_token)
        .replace('{ENTITY}', entity_token)
        .replace('{BRANCH}', branch_token)
    )


@transaction.atomic
def allocate(series_code: str, *, on_date: datetime.date | None = None, entity_token: str = '', branch_token: str = '') -> str:
    """Locks the series row, consumes the next value, returns the
    rendered code. Safe under concurrent callers — the row lock serialises
    allocation, same guarantee EmployeeCodeSettings.generate_employee_id
    already relies on today."""
    on_date = on_date or datetime.date.today()
    series = NumberSeries.objects.select_for_update().get(code=series_code, is_active=True)

    reset_key = _reset_key(series, on_date)
    if series.reset_period != NumberSeries.RESET_NEVER and reset_key != series.last_reset_key:
        series.next_value = 1
        series.last_reset_key = reset_key

    seq = series.next_value
    rendered = _render(series, seq, on_date, entity_token=entity_token, branch_token=branch_token)

    series.next_value = seq + 1
    series.save(update_fields=['next_value', 'last_reset_key', 'updated_at'])
    return rendered


def preview(series_code: str, *, on_date: datetime.date | None = None) -> str:
    """Read-only — shows the next value WITHOUT consuming it."""
    on_date = on_date or datetime.date.today()
    series = NumberSeries.objects.get(code=series_code, is_active=True)
    reset_key = _reset_key(series, on_date)
    seq = 1 if (series.reset_period != NumberSeries.RESET_NEVER and reset_key != series.last_reset_key) else series.next_value
    return _render(series, seq, on_date)
