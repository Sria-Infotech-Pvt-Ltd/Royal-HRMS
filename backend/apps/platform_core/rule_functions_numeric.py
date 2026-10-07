"""
Phase 3A Task B -- math/logic functions for the rule engine. Split out
of rule_functions.py purely to respect this project's ~300-line file
guideline; rule_functions.py re-exports everything from here into one
combined FUNCTIONS registry so services_rules.py has a single import.
"""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal

from apps.platform_core.rule_errors import RuleError, RuleLimitExceeded

MAX_LIST_SIZE = 1000

_ROUND_MODES = {
    'half_up': ROUND_HALF_UP, 'half_even': ROUND_HALF_EVEN, 'up': ROUND_UP,
    'down': ROUND_DOWN, 'ceiling': ROUND_CEILING, 'floor': ROUND_FLOOR,
}


def to_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise RuleError('Cannot use a boolean as a number.')
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except Exception as exc:
            raise RuleError(f'Not a valid number: {value!r}') from exc
    raise RuleError(f'Not a valid number: {value!r}')


def fn_add(*args, ctx):
    nums = [to_decimal(a) for a in args]
    if any(n is None for n in nums):
        return None
    return sum(nums[1:], nums[0]) if nums else Decimal(0)


def fn_sub(a, b, *, ctx):
    a, b = to_decimal(a), to_decimal(b)
    return None if a is None or b is None else a - b


def fn_mul(*args, ctx):
    nums = [to_decimal(a) for a in args]
    if any(n is None for n in nums):
        return None
    result = Decimal(1)
    for n in nums:
        result *= n
    return result


def fn_div(a, b, *, ctx):
    a, b = to_decimal(a), to_decimal(b)
    if a is None or b is None:
        return None
    if b == 0:
        raise RuleError('Division by zero.')
    return a / b


def fn_min(*args, ctx):
    nums = [n for n in (to_decimal(a) for a in args) if n is not None]
    return min(nums) if nums else None


def fn_max(*args, ctx):
    nums = [n for n in (to_decimal(a) for a in args) if n is not None]
    return max(nums) if nums else None


def fn_abs(a, *, ctx):
    a = to_decimal(a)
    return None if a is None else abs(a)


def fn_round(value, places=0, mode='half_up', *, ctx):
    value = to_decimal(value)
    if value is None:
        return None
    if mode not in _ROUND_MODES:
        raise RuleError(f'Unknown rounding mode: {mode!r}')
    quantum = Decimal(1).scaleb(-int(places))
    return value.quantize(quantum, rounding=_ROUND_MODES[mode])


def fn_round_nearest_n(value, n, mode='half_up', *, ctx):
    value, n = to_decimal(value), to_decimal(n)
    if value is None or n is None or n == 0:
        return value
    divided = (value / n).quantize(Decimal(1), rounding=_ROUND_MODES.get(mode, ROUND_HALF_UP))
    return divided * n


def fn_ceil(a, *, ctx):
    a = to_decimal(a)
    return None if a is None else a.to_integral_value(rounding=ROUND_CEILING)


def fn_floor(a, *, ctx):
    a = to_decimal(a)
    return None if a is None else a.to_integral_value(rounding=ROUND_FLOOR)


def fn_pow(base, exponent, *, ctx):
    base = to_decimal(base)
    if base is None:
        return None
    exponent = int(exponent)
    if abs(exponent) > 32:
        raise RuleError('Exponent too large.')
    return base ** exponent


def fn_percent_of(amount, pct, *, ctx):
    amount, pct = to_decimal(amount), to_decimal(pct)
    if amount is None or pct is None:
        return None
    return amount * pct / Decimal(100)


# ─── Logic ───────────────────────────────────────────────────────────────────

def fn_if(condition, then_val, else_val, *, ctx):
    return then_val if condition else else_val


def fn_case(*args, ctx):
    """case(cond1, val1, cond2, val2, ..., default) — odd-length args."""
    if len(args) % 2 == 0:
        raise RuleError('case() needs an odd number of arguments (pairs + a default).')
    for i in range(0, len(args) - 1, 2):
        if args[i]:
            return args[i + 1]
    return args[-1]


def fn_and(*args, ctx):
    return all(bool(a) for a in args)


def fn_or(*args, ctx):
    return any(bool(a) for a in args)


def fn_not(a, *, ctx):
    return not bool(a)


def fn_coalesce(*args, ctx):
    for a in args:
        if a is not None:
            return a
    return None


def fn_in(value, collection, *, ctx):
    if not isinstance(collection, list):
        raise RuleError('in() second argument must be a list.')
    if len(collection) > MAX_LIST_SIZE:
        raise RuleLimitExceeded('List too large.')
    return value in collection


def fn_between(value, low, high, *, ctx):
    if value is None or low is None or high is None:
        return False
    return low <= value <= high


def fn_is_null(value, *, ctx):
    return value is None


def fn_eq(a, b, *, ctx):
    return a == b


def fn_ne(a, b, *, ctx):
    return a != b


def fn_gt(a, b, *, ctx):
    return False if a is None or b is None else a > b


def fn_lt(a, b, *, ctx):
    return False if a is None or b is None else a < b


def fn_gte(a, b, *, ctx):
    return False if a is None or b is None else a >= b


def fn_lte(a, b, *, ctx):
    return False if a is None or b is None else a <= b


