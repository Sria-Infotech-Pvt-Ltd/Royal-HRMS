"""
Phase 2 Task B.4 — declarative condition evaluator. Format (documented in
docs/CONDITIONS.md, which Phase 3's rule engine must accept unchanged):

    {"all"|"any": [{"field": code, "op": eq|ne|in|not_in|empty|not_empty|gt|lt|gte|lte, "value": ...}, ...]}

Nesting up to 3 levels (a clause's own "value"-less entries can
themselves be {"all": [...]} / {"any": [...]}). No code execution —
every operator is a plain Python comparison, nothing is ever eval()'d.
"""
from __future__ import annotations

MAX_NESTING_DEPTH = 3


class ConditionError(Exception):
    pass


def _get_value(values: dict, field_code: str):
    return values.get(field_code)


def _compare(op: str, actual, expected) -> bool:
    if op == 'empty':
        return actual in (None, '', [], {})
    if op == 'not_empty':
        return actual not in (None, '', [], {})
    if op == 'eq':
        return actual == expected
    if op == 'ne':
        return actual != expected
    if op == 'in':
        return actual in (expected or [])
    if op == 'not_in':
        return actual not in (expected or [])
    if op in ('gt', 'lt', 'gte', 'lte'):
        if actual is None or expected is None:
            return False
        try:
            if op == 'gt':
                return actual > expected
            if op == 'lt':
                return actual < expected
            if op == 'gte':
                return actual >= expected
            return actual <= expected
        except TypeError as exc:
            raise ConditionError(f'Cannot compare {actual!r} {op} {expected!r}') from exc
    raise ConditionError(f'Unknown operator: {op}')


def evaluate(condition: dict, values: dict, *, _depth: int = 0) -> bool:
    """Returns True if `condition` is empty (an empty dict means "always
    visible/required" — the default, unconditioned state), else evaluates
    the all/any tree against `values` (a plain {field_code: value} dict —
    callers resolve this from whatever record shape they have)."""
    if not condition:
        return True
    if _depth > MAX_NESTING_DEPTH:
        raise ConditionError(f'Condition nesting exceeds the maximum of {MAX_NESTING_DEPTH} levels.')

    if 'all' in condition and 'any' in condition:
        raise ConditionError('A condition clause cannot have both "all" and "any" at the same level.')

    if 'all' in condition:
        clauses = condition['all']
        combiner = all
    elif 'any' in condition:
        clauses = condition['any']
        combiner = any
    else:
        raise ConditionError('Condition must have an "all" or "any" key.')

    if not isinstance(clauses, list):
        raise ConditionError('"all"/"any" must be a list of clauses.')

    results = []
    for clause in clauses:
        if 'all' in clause or 'any' in clause:
            results.append(evaluate(clause, values, _depth=_depth + 1))
            continue
        if 'field' not in clause or 'op' not in clause:
            raise ConditionError(f'Leaf clause must have "field" and "op": {clause!r}')
        actual = _get_value(values, clause['field'])
        results.append(_compare(clause['op'], actual, clause.get('value')))

    return combiner(results) if results else True
