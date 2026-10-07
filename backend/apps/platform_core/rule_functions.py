"""
Phase 3A Task B -- text/date/table-lookup functions for the rule engine,
plus the combined FUNCTIONS registry services_rules.py imports. Math and
logic functions live in rule_functions_numeric.py (split purely to
respect this project's ~300-line file guideline).
"""
from __future__ import annotations

import datetime
import re
from decimal import Decimal

from apps.platform_core.rule_errors import RuleError, RuleLimitExceeded
from apps.platform_core.rule_functions_numeric import (
    to_decimal,
    fn_add, fn_sub, fn_mul, fn_div, fn_min, fn_max, fn_abs, fn_round,
    fn_round_nearest_n, fn_ceil, fn_floor, fn_pow, fn_percent_of,
    fn_if, fn_case, fn_and, fn_or, fn_not, fn_coalesce, fn_in, fn_between,
    fn_is_null, fn_eq, fn_ne, fn_gt, fn_lt, fn_gte, fn_lte,
)

MAX_REGEX_LENGTH = 200
MAX_STRING_LENGTH = 10_000


def _as_date(value) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    raise RuleError(f'Not a valid date: {value!r}')


def _check_str(s, name='value') -> str:
    if not isinstance(s, str):
        raise RuleError(f'{name} must be a string.')
    if len(s) > MAX_STRING_LENGTH:
        raise RuleLimitExceeded(f'{name} exceeds the maximum string length.')
    return s


# ─── Text ────────────────────────────────────────────────────────────────────

def fn_concat(*args, ctx):
    return ''.join(_check_str(str(a) if a is not None else '') for a in args)


def fn_upper(s, *, ctx):
    return _check_str(s).upper()


def fn_lower(s, *, ctx):
    return _check_str(s).lower()


def fn_length(s, *, ctx):
    if isinstance(s, list):
        return len(s)
    return len(_check_str(s))


def fn_starts_with(s, prefix, *, ctx):
    return _check_str(s).startswith(_check_str(prefix))


def fn_contains(s, needle, *, ctx):
    if isinstance(s, list):
        return needle in s
    return _check_str(needle) in _check_str(s)


def fn_matches(s, pattern, *, ctx):
    s, pattern = _check_str(s), _check_str(pattern, 'pattern')
    if len(pattern) > MAX_REGEX_LENGTH:
        raise RuleLimitExceeded('Regex pattern too long.')
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise RuleError(f'Invalid regex: {exc}') from exc
    # re2-style safety isn't available stdlib; length limits on both the
    # pattern and the subject bound catastrophic-backtracking blast radius
    # to a small, fixed worst case rather than eliminating the class
    # entirely — documented in docs/RULES.md as a known, bounded limit.
    return compiled.search(s) is not None


# ─── Date & time ─────────────────────────────────────────────────────────────

def fn_date_diff(unit, d1, d2, *, ctx):
    d1, d2 = _as_date(d1), _as_date(d2)
    delta = d2 - d1
    if unit == 'days':
        return Decimal(delta.days)
    if unit == 'months':
        return Decimal((d2.year - d1.year) * 12 + (d2.month - d1.month))
    if unit == 'years':
        return Decimal(d2.year - d1.year)
    raise RuleError(f'Unknown date_diff unit: {unit!r}')


def fn_add_days(d, n, *, ctx):
    return _as_date(d) + datetime.timedelta(days=int(n))


def fn_add_months(d, n, *, ctx):
    import calendar
    d = _as_date(d)
    n = int(n)
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def fn_add_years(d, n, *, ctx):
    d = _as_date(d)
    try:
        return d.replace(year=d.year + int(n))
    except ValueError:
        return d.replace(month=2, day=28, year=d.year + int(n))


def fn_start_of(unit, d, *, ctx):
    d = _as_date(d)
    if unit == 'month':
        return d.replace(day=1)
    if unit == 'year':
        return d.replace(month=1, day=1)
    if unit == 'quarter':
        q_start_month = ((d.month - 1) // 3) * 3 + 1
        return d.replace(month=q_start_month, day=1)
    raise RuleError(f'Unknown start_of unit: {unit!r}')


def fn_end_of(unit, d, *, ctx):
    import calendar
    d = _as_date(d)
    if unit == 'month':
        return d.replace(day=calendar.monthrange(d.year, d.month)[1])
    if unit == 'year':
        return d.replace(month=12, day=31)
    if unit == 'quarter':
        q_start_month = ((d.month - 1) // 3) * 3 + 1
        q_end_month = q_start_month + 2
        return d.replace(month=q_end_month, day=calendar.monthrange(d.year, q_end_month)[1])
    raise RuleError(f'Unknown end_of unit: {unit!r}')


def fn_age_on(dob, as_of, *, ctx):
    dob, as_of = _as_date(dob), _as_date(as_of)
    years = as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))
    return Decimal(years)


def fn_tenure_on(joining_date, as_of, unit='months', *, ctx):
    return fn_date_diff(unit, joining_date, as_of, ctx=ctx)


def fn_day_of_week(d, *, ctx):
    return _as_date(d).strftime('%A').upper()


def fn_minutes_between(t1, t2, *, ctx):
    def _to_minutes(t):
        if isinstance(t, str):
            h, m = t.split(':')[:2]
            return int(h) * 60 + int(m)
        if isinstance(t, datetime.time):
            return t.hour * 60 + t.minute
        raise RuleError(f'Not a valid time: {t!r}')
    return Decimal(_to_minutes(t2) - _to_minutes(t1))


# ─── Table/slab/band lookups (needed by payroll/tax later) ─────────────────

def _resolve_table_rows(table_code: str, as_of) -> list[dict]:
    from django.db.models import Q
    from apps.platform_core.models import RuleTable, RuleTableVersion
    as_of = _as_date(as_of)
    table = RuleTable.objects.filter(code=table_code).first()
    if table is None:
        raise RuleError(f'Unknown rule table: {table_code!r}')
    version = RuleTableVersion.objects.filter(table=table, effective_from__lte=as_of).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)
    ).order_by('-effective_from').first()
    if version is None:
        raise RuleError(f'No version of table {table_code!r} is effective on {as_of}.')
    return version.rows


def fn_slab(value, table_code, as_of, *, ctx):
    """Progressive slab: sums the portion of `value` falling in each band
    up to and including the band it lands in. Table rows must have
    `min`/`max`(nullable)/`rate` columns (percentage applied per band)."""
    rows = _resolve_table_rows(table_code, as_of)
    value = to_decimal(value)
    if value is None:
        return None
    total = Decimal(0)
    for row in sorted(rows, key=lambda r: to_decimal(r['min'])):
        row_min = to_decimal(row['min'])
        row_max = to_decimal(row['max']) if row.get('max') is not None else None
        if value <= row_min:
            break
        band_top = min(value, row_max) if row_max is not None else value
        band_amount = band_top - row_min
        if band_amount <= 0:
            continue
        total += band_amount * to_decimal(row['rate']) / Decimal(100)
    return total


def fn_band(value, table_code, as_of, *, ctx):
    """Single matching band — returns that row's `rate`."""
    rows = _resolve_table_rows(table_code, as_of)
    value = to_decimal(value)
    if value is None:
        return None
    for row in rows:
        row_min = to_decimal(row['min'])
        row_max = to_decimal(row['max']) if row.get('max') is not None else None
        if value >= row_min and (row_max is None or value <= row_max):
            return row.get('rate')
    return None


def fn_lookup_attr(type_code, code, key, default=None, *, ctx):
    from apps.platform_core import services_lookups
    return services_lookups.get_attribute(type_code, code, key, default)


FUNCTIONS = {
    'add': fn_add, 'sub': fn_sub, 'mul': fn_mul, 'div': fn_div,
    'min': fn_min, 'max': fn_max, 'abs': fn_abs, 'round': fn_round,
    'round_nearest_n': fn_round_nearest_n, 'ceil': fn_ceil, 'floor': fn_floor,
    'pow': fn_pow, 'percent_of': fn_percent_of,
    'if': fn_if, 'case': fn_case, 'and': fn_and, 'or': fn_or, 'not': fn_not,
    'coalesce': fn_coalesce, 'in': fn_in, 'between': fn_between, 'is_null': fn_is_null,
    'eq': fn_eq, 'ne': fn_ne, 'gt': fn_gt, 'lt': fn_lt, 'gte': fn_gte, 'lte': fn_lte,
    'concat': fn_concat, 'upper': fn_upper, 'lower': fn_lower, 'length': fn_length,
    'starts_with': fn_starts_with, 'contains': fn_contains, 'matches': fn_matches,
    'date_diff': fn_date_diff, 'add_days': fn_add_days, 'add_months': fn_add_months,
    'add_years': fn_add_years, 'start_of': fn_start_of, 'end_of': fn_end_of,
    'age_on': fn_age_on, 'tenure_on': fn_tenure_on, 'day_of_week': fn_day_of_week,
    'minutes_between': fn_minutes_between, 'slab': fn_slab, 'band': fn_band,
    'lookup_attr': fn_lookup_attr,
}
