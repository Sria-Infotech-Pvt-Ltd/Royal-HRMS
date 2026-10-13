"""
Phase 7A Task C — the formula graph: dependency ordering, cycle rejection,
a sandboxed formula evaluator (no `eval()` on untrusted input — restricted
`ast` node whitelist only), and a publish-time preview over sample CTCs.

Nothing here is called by the live payroll engine yet (apps.payroll.engine
.legacy is still the only thing that writes a real EmployeePayslip) — this
is pure computation over PayStructure/PayStructureComponent, exercised by
its own tests and by PayStructurePreviewView for an admin to check a
structure before publishing it.
"""
import ast
import operator
from decimal import Decimal

from apps.payroll.models_pay_structure import PayStructureComponent


class FormulaCycleError(Exception):
    """A structure's components reference each other in a cycle (e.g. A's
    formula needs B, B's formula needs A) — no implicit iterative solving
    in this phase, matches the master prompt's own "reject cycles" rule."""


class FormulaError(Exception):
    """A formula references a code not in the structure, or uses a
    disallowed expression."""


# ── Dependency graph ─────────────────────────────────────────────────────

def _referenced_codes(component: PayStructureComponent, known_codes: set) -> set:
    """Codes this component's base/formula depends on — only ones that are
    themselves rows in the same structure count as graph edges; a formula
    referencing e.g. GROSS_FOR_PF (a named aggregate, not a structure row)
    has nothing to topologically order against, so it's skipped here and
    resolved at evaluation time instead."""
    refs = set()
    base = component.base_component_code
    if base and base in known_codes:
        refs.add(base)
    if component.formula:
        for node in ast.walk(_parse_formula(component.formula)):
            if isinstance(node, ast.Name) and node.id in known_codes:
                refs.add(node.id)
    return refs


def build_dependency_graph(structure) -> list:
    """Returns component codes in an order where every dependency is
    computed before its dependents. Raises FormulaCycleError if no such
    order exists."""
    rows = list(structure.structure_components.all())
    known_codes = {r.component_code for r in rows}
    by_code = {r.component_code: r for r in rows}

    deps = {code: _referenced_codes(by_code[code], known_codes) - {code} for code in known_codes}

    ordered = []
    visiting = set()
    visited = set()

    def visit(code, stack):
        if code in visited:
            return
        if code in visiting:
            cycle = ' -> '.join(stack + [code])
            raise FormulaCycleError(f'Cycle detected among pay components: {cycle}')
        visiting.add(code)
        for dep in deps.get(code, ()):
            visit(dep, stack + [code])
        visiting.discard(code)
        visited.add(code)
        ordered.append(code)

    for code in known_codes:
        visit(code, [])

    return ordered


# ── Sandboxed formula evaluator ──────────────────────────────────────────
# Whitelisted node types only — Name (component-code lookup), Constant/Num
# (literals), BinOp with +/-/*//, UnaryOp with -/+, and parentheses (which
# `ast` doesn't even represent as a separate node). Anything else —
# function calls, attribute access, subscripts, comprehensions, imports —
# fails to parse. This is never passed to Python's own eval()/exec().
_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _parse_formula(formula: str) -> ast.AST:
    try:
        tree = ast.parse(formula, mode='eval')
    except SyntaxError as exc:
        raise FormulaError(f'Could not parse formula {formula!r}: {exc}') from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Constant, ast.BinOp, ast.UnaryOp, ast.Expression, ast.Load)):
            continue
        if isinstance(node, ast.operator) and type(node) in _ALLOWED_BINOPS:
            continue
        if isinstance(node, ast.unaryop) and type(node) in _ALLOWED_UNARYOPS:
            continue
        raise FormulaError(f'Formula {formula!r} uses a disallowed expression: {type(node).__name__}')
    return tree.body


def _eval_ast(node, values: dict) -> Decimal:
    if isinstance(node, ast.Constant):
        return Decimal(str(node.value))
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise FormulaError(f'Formula references unknown code {node.id!r}')
        return values[node.id]
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if op is None:
            raise FormulaError(f'Operator {type(node.op).__name__} is not allowed in formulas')
        return op(_eval_ast(node.left, values), _eval_ast(node.right, values))
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if op is None:
            raise FormulaError(f'Unary operator {type(node.op).__name__} is not allowed in formulas')
        return op(_eval_ast(node.operand, values))
    raise FormulaError(f'Unsupported formula node: {type(node).__name__}')


def evaluate_formula(formula: str, values: dict) -> Decimal:
    """Evaluate a whitelisted arithmetic expression referencing other
    components' already-computed amounts by code. `values` must already
    contain every code the formula references (the caller is expected to
    evaluate in the dependency order build_dependency_graph() returns)."""
    return _eval_ast(_parse_formula(formula), values)


# ── Structure evaluation (sample CTCs — preview only, no writes) ────────

def evaluate_structure(structure, monthly_ctc: Decimal, is_metro: bool = False) -> dict:
    """Pure computation of one structure against one monthly CTC figure —
    used by the publish-time preview over sample CTCs. Returns
    {component_code: Decimal amount}. Raises FormulaCycleError/FormulaError
    on a bad structure; raises ValueError if the balancing component would
    go negative (matches the master prompt's "non-negative rule" for
    balancing components)."""
    order = build_dependency_graph(structure)
    rows = {r.component_code: r for r in structure.structure_components.all()}
    amounts: dict = {'CTC_MONTHLY': Decimal(monthly_ctc)}

    for code in order:
        row = rows[code]
        method = row.calculation_method or ''
        if row.formula:
            amounts[code] = evaluate_formula(row.formula, amounts)
        elif method == 'percentage' and row.base_component_code and row.value is not None:
            base_amount = amounts.get(row.base_component_code, Decimal('0'))
            amounts[code] = base_amount * row.value / 100
        elif method == 'fixed' and row.value is not None:
            amounts[code] = Decimal(row.value)
        elif method == 'metro_hra_of_basic':
            # Bridged from the legacy SalaryComponent.CALC_METRO_HRA calculation
            # type (see services_shadow_engine.py) — 50%/40% of Basic by metro
            # status, same formula as the legacy engine's own CALC_METRO_HRA branch.
            basic_amount = amounts.get(row.base_component_code or 'BASIC', Decimal('0'))
            metro_pct = Decimal('50') if is_metro else Decimal('40')
            amounts[code] = basic_amount * metro_pct / 100
        else:
            amounts[code] = Decimal('0')

        if row.min_amount is not None:
            amounts[code] = max(amounts[code], row.min_amount)
        if row.max_amount is not None:
            amounts[code] = min(amounts[code], row.max_amount)

    balancing_code = structure.balancing_component_code
    if balancing_code and balancing_code in amounts:
        others_total = sum((amt for code, amt in amounts.items() if code not in (balancing_code, 'CTC_MONTHLY')), Decimal('0'))
        balance = Decimal(monthly_ctc) - others_total
        if balance < 0:
            raise ValueError(
                f'{structure.code}: components before the balancing component {balancing_code} '
                f'already exceed the CTC ({others_total} > {monthly_ctc}).'
            )
        amounts[balancing_code] = balance

    amounts.pop('CTC_MONTHLY', None)
    return amounts


def preview_structure(structure, sample_annual_ctcs: list) -> list:
    """Publish-time preview: runs the structure against each sample annual
    CTC and returns per-CTC breakdowns, for an admin to sanity-check before
    marking a structure published. Never writes anything."""
    results = []
    for annual_ctc in sample_annual_ctcs:
        monthly = Decimal(annual_ctc) / 12
        try:
            breakdown = evaluate_structure(structure, monthly)
            results.append({'annual_ctc': annual_ctc, 'monthly_ctc': monthly, 'breakdown': breakdown, 'error': None})
        except (FormulaCycleError, FormulaError, ValueError) as exc:
            results.append({'annual_ctc': annual_ctc, 'monthly_ctc': monthly, 'breakdown': None, 'error': str(exc)})
    return results
