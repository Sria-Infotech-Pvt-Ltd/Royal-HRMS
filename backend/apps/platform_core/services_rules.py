"""
Phase 3A Tasks A+B — a safe, whitelisted JSON-expression evaluator. NO
`eval`, `exec`, `compile`, `pickle`, or dynamic import of admin-supplied
content anywhere in this file — every operation is a plain Python
function looked up by a fixed string key (rule_functions.FUNCTIONS),
never constructed from input.

Grammar documented in full in docs/RULES.md; this docstring covers only
the evaluator's own contract.

A node is one of:
  - a literal: number, string, bool, None, or a list of nodes
  - {"var": "name"}                          — read from context
  - {"op": "add", "args": [node, ...]}        — a function call
  - {"provider": "employee.field", "args": [...]} — a data provider call
  - the Phase 2 condition format {"all"|"any": [...]} — parsed into the
    equivalent {"op": "and"/"or", ...} tree by from_condition_format()
    so docs/CONDITIONS.md's grammar is accepted unchanged (Rule 2).

Null handling (documented, not implicit): arithmetic with a None operand
returns None; comparisons with None are False except `is_null`/`eq` with
an explicit None literal.
"""
from __future__ import annotations

import re
from decimal import Decimal

from apps.platform_core.rule_errors import RuleError, RuleLimitExceeded
from apps.platform_core.rule_functions import FUNCTIONS

MAX_NODES = 500
MAX_DEPTH = 20
MAX_LIST_SIZE = 1000

# ─── Data providers (Task B.7) ──────────────────────────────────────────────
# Read-only, registered in code, permission-aware. Adding one is a
# developer task; referencing one by name in a rule is admin configuration.
# `employee.field` is implemented for real (built on Phase 2's
# services_attributes, already permission/history-aware). The other
# providers the prompt names (attendance.count_days,
# calendar.working_days_between, org.manager_level) need deep integration
# with modules this phase doesn't touch (attendance's exact calendar
# logic, the org-chart traversal 3B's resolvers need) — registering a
# provider with a GUESSED implementation that silently disagrees with the
# real attendance/org logic would be worse than refusing. They are left
# UNREGISTERED here and documented as an open item in PHASE3A_REPORT.md
# rather than faked.

def _provider_employee_field(employee, field_code, *, ctx):
    from apps.platform_core import services_attributes as attrs
    from apps.platform_core.models import EntityDefinition
    if hasattr(employee, field_code):
        return getattr(employee, field_code)
    entity = EntityDefinition.objects.get(code='employee')
    values = attrs.read(entity, employee, for_user=None, _skip_mask=True)
    return values.get(field_code)


_PROVIDERS = {
    'employee.field': _provider_employee_field,
}


def register_provider(name: str, fn) -> None:
    """Developer-only entry point (Task B.7's documented boundary) — never
    called from admin-supplied data."""
    _PROVIDERS[name] = fn


# ─── Parsing: Phase 2 condition format -> this evaluator's tree ────────────

_CONDITION_SIMPLE_OPS = {'eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in'}


def from_condition_format(condition: dict) -> dict:
    """Converts docs/CONDITIONS.md's {"all"|"any": [...]} format into this
    module's {"op": "and"/"or", "args": [...]} tree — Rule 2's "must parse
    into the same tree" requirement."""
    if not condition:
        return {'op': 'literal', 'value': True}
    if 'all' in condition and 'any' in condition:
        raise RuleError('A condition clause cannot have both "all" and "any".')
    if 'all' in condition:
        key, py_op = 'all', 'and'
    elif 'any' in condition:
        key, py_op = 'any', 'or'
    else:
        raise RuleError('Condition must have an "all" or "any" key.')

    clauses = condition[key]
    if not isinstance(clauses, list):
        raise RuleError('"all"/"any" must be a list.')

    args = []
    for clause in clauses:
        if 'all' in clause or 'any' in clause:
            args.append(from_condition_format(clause))
            continue
        if 'field' not in clause or 'op' not in clause:
            raise RuleError('Leaf clause must have "field" and "op".')
        field_node = {'var': clause['field']}
        op = clause['op']
        value_node = {'op': 'literal', 'value': clause.get('value')}
        if op == 'not_in':
            args.append({'op': 'not', 'args': [{'op': 'in', 'args': [field_node, value_node]}]})
        elif op == 'empty':
            args.append({'op': 'is_null', 'args': [field_node]})
        elif op == 'not_empty':
            args.append({'op': 'not', 'args': [{'op': 'is_null', 'args': [field_node]}]})
        elif op in _CONDITION_SIMPLE_OPS:
            args.append({'op': op, 'args': [field_node, value_node]})
        else:
            raise RuleError(f'Unknown operator: {op!r}')
    return {'op': py_op, 'args': args}


# ─── Evaluation ──────────────────────────────────────────────────────────────

class _Budget:
    __slots__ = ('nodes',)

    def __init__(self):
        self.nodes = 0


def evaluate(expression: dict, context: dict) -> object:
    """Entry point. `expression` may be either this module's native tree
    or the Phase 2 condition format (auto-detected). `context` is a plain
    {name: value} dict — never a model instance (no attribute access to
    arbitrary objects, per Rule 5)."""
    if not expression or 'all' in expression or 'any' in expression:
        expression = from_condition_format(expression)
    budget = _Budget()
    return _eval_node(expression, context, budget, depth=0, path='$')


def _eval_node(node, context: dict, budget: _Budget, depth: int, path: str):
    budget.nodes += 1
    if budget.nodes > MAX_NODES:
        raise RuleLimitExceeded('Expression exceeds the maximum node count.', path)
    if depth > MAX_DEPTH:
        raise RuleLimitExceeded('Expression exceeds the maximum nesting depth.', path)

    if node is None or isinstance(node, (bool, int, float, str)):
        # Numeric literals always become Decimal (via str(), never the
        # binary float constructor) — "never use float for money, rates,
        # or durations" applies to literals embedded in a rule, not just
        # to values arriving through context.
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            return Decimal(str(node))
        return node
    if isinstance(node, list):
        if len(node) > MAX_LIST_SIZE:
            raise RuleLimitExceeded('List literal exceeds the maximum size.', path)
        return [_eval_node(n, context, budget, depth + 1, f'{path}[{i}]') for i, n in enumerate(node)]
    if not isinstance(node, dict):
        raise RuleError(f'Invalid node type: {type(node).__name__}', path)

    if 'var' in node:
        name = node['var']
        if not isinstance(name, str) or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', name):
            raise RuleError(f'Invalid variable name: {name!r}', path)
        return context.get(name)

    if 'literal' in node or node.get('op') == 'literal':
        value = node.get('value')
        if isinstance(value, list) and len(value) > MAX_LIST_SIZE:
            raise RuleLimitExceeded('List literal exceeds the maximum size.', path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return Decimal(str(value))
        return value

    if 'provider' in node:
        provider_name = node['provider']
        fn = _PROVIDERS.get(provider_name)
        if fn is None:
            raise RuleError(f'Unknown or unregistered data provider: {provider_name!r}', path)
        args = [_eval_node(a, context, budget, depth + 1, f'{path}.args[{i}]') for i, a in enumerate(node.get('args', []))]
        return fn(*args, ctx=context)

    if 'op' in node:
        op = node['op']
        fn = FUNCTIONS.get(op)
        if fn is None:
            raise RuleError(f'Unknown operator: {op!r}', path)
        args = [_eval_node(a, context, budget, depth + 1, f'{path}.args[{i}]') for i, a in enumerate(node.get('args', []))]
        try:
            return fn(*args, ctx=context)
        except RuleError:
            raise
        except Exception as exc:  # pragma: no cover - last-resort safety net
            # The whitelisted function library can still raise a plain
            # Python exception for a genuinely malformed call (wrong arg
            # count/type) — this is the "never an unhandled Python
            # exception" guarantee's final backstop, not a substitute for
            # each function's own validation.
            raise RuleError(str(exc), path) from exc

    raise RuleError(f'Malformed node — expected "var", "op", "literal" or "provider": {node!r}', path)
