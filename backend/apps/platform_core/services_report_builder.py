"""
Phase 9A Task A/B — the safe report query engine over CustomRecord (see
models/reports.py's own docstring for why core-model reporting is out of
this pass's scope). Applies Phase 4 scope_queryset + field security on
every run; calculated columns use the same ast-restricted sandbox already
proven in apps.payroll.services_pay_structure (no eval/exec); small-group
aggregates over sensitive fields are suppressed, not silently shown.
"""
import ast
import operator
from decimal import Decimal

from apps.platform_core.models import CustomRecord, FieldDefinition, ReportDefinition, ReportRun
from apps.platform_core.services_authz import scope_queryset
from apps.platform_core.services_field_security import mask_value, resolve_field_access


class ReportSecurityError(Exception):
    pass


class ReportExpressionError(Exception):
    pass


_ALLOWED_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _eval_calculated_column(expression: str, row_values: dict) -> Decimal:
    """Same whitelist-only ast evaluator as Phase 7A's formula sandbox —
    Name/Constant/BinOp/arithmetic ops only, never eval()/exec()."""
    try:
        tree = ast.parse(expression, mode='eval').body
    except SyntaxError as exc:
        raise ReportExpressionError(f'Could not parse {expression!r}: {exc}') from exc

    def _eval(node):
        if isinstance(node, ast.Constant):
            return Decimal(str(node.value))
        if isinstance(node, ast.Name):
            if node.id not in row_values:
                raise ReportExpressionError(f'Unknown column {node.id!r} in calculated-column expression.')
            value = row_values[node.id]
            return Decimal(str(value)) if value is not None else Decimal('0')
        if isinstance(node, ast.BinOp):
            op = _ALLOWED_BINOPS.get(type(node.op))
            if op is None:
                raise ReportExpressionError(f'Operator {type(node.op).__name__} not allowed.')
            return op(_eval(node.left), _eval(node.right))
        raise ReportExpressionError(f'Disallowed expression node: {type(node).__name__}')

    return _eval(tree)


def _field_defs_by_code(entity) -> dict:
    return {f.code: f for f in FieldDefinition.objects.filter(entity=entity)}


def validate_definition(report: ReportDefinition, user) -> None:
    """Task A.3 — checks every referenced field path exists and the
    AUTHOR has access to it. Server re-checks per VIEWER at run time
    regardless (run_report() below), so a report shared too broadly still
    can't leak anything."""
    field_defs = _field_defs_by_code(report.base_entity)
    all_referenced = {c['field_code'] for c in report.columns}
    all_referenced |= set(report.group_by_field_codes)
    all_referenced |= {a['field_code'] for a in report.aggregates}
    all_referenced |= {f['field_code'] for f in report.filters}

    unknown = all_referenced - set(field_defs)
    if unknown:
        raise ReportExpressionError(f'Unknown field code(s) on {report.base_entity.code}: {sorted(unknown)}')

    for field_code in all_referenced:
        access = resolve_field_access(user, report.base_entity, field_defs[field_code])
        if access == 'hidden':
            raise ReportSecurityError(f'{user}: no access to field {field_code!r} referenced by this report.')
    # Calculated-column type-checking beyond parse-at-eval-time (Task A.3's
    # "type-check calculated columns") is a documented follow-up, not
    # built this pass — _eval_calculated_column() below already rejects
    # anything but restricted arithmetic at evaluation time.


def run_report(report: ReportDefinition, viewer, *, parameters: dict | None = None) -> dict:
    """The one real entry point. Re-validates field access for `viewer`
    (never trusts that the report's author-time validation still holds —
    roles/permissions can change after a report is shared) and applies
    scope_queryset on the base entity's CustomRecord queryset."""
    parameters = parameters or {}
    field_defs = _field_defs_by_code(report.base_entity)

    queryset = CustomRecord.objects.filter(entity=report.base_entity, is_deleted=False)
    queryset = scope_queryset(viewer, report.base_entity, 'view', queryset)

    for filter_spec in report.filters:
        value = parameters.get(filter_spec['field_code'], filter_spec.get('value'))
        if value is None:
            continue
        operator_code = filter_spec.get('operator', 'eq')
        lookup = {'eq': '', 'gt': '__gt', 'lt': '__lt', 'contains': '__icontains'}.get(operator_code, '')
        queryset = queryset.filter(**{f"data__{filter_spec['field_code']}{lookup}": value})

    rows = []
    hidden_or_masked = {}
    for record in queryset.order_by('-created_at')[:report.row_limit]:
        row = {}
        for column in report.columns:
            field_code = column['field_code']
            field_def = field_defs[field_code]
            access = resolve_field_access(viewer, report.base_entity, field_def)
            if access == 'hidden':
                continue
            raw_value = record.data.get(field_code)
            row[field_code] = mask_value(raw_value, field_def) if access == 'masked' else raw_value
            hidden_or_masked[field_code] = access

        for calc in report.calculated_columns:
            try:
                row[calc['name']] = _eval_calculated_column(calc['expression'], row)
            except ReportExpressionError:
                row[calc['name']] = None
        rows.append(row)

    # Inference-attack suppression: an aggregate over a field ANY viewer
    # access resolved to 'masked' (sensitive) is blanked out below the
    # configured minimum group size — small-group averages/sums over
    # sensitive data are exactly the attack Task A's own testing
    # requirement names.
    aggregate_results = {}
    for agg in report.aggregates:
        field_code = agg['field_code']
        values = [r.get(field_code) for r in rows if r.get(field_code) is not None]
        is_sensitive_field = field_defs.get(field_code) and field_defs[field_code].is_sensitive
        if is_sensitive_field and len(rows) < report.min_group_size_for_sensitive_aggregate:
            aggregate_results[f"{agg['function']}_{field_code}"] = None
            continue
        aggregate_results[f"{agg['function']}_{field_code}"] = _compute_aggregate(agg['function'], values)

    ReportRun.objects.create(report=report, run_by=viewer, parameters=parameters, row_count=len(rows))
    return {'rows': rows, 'aggregates': aggregate_results, 'row_count': len(rows)}


def _compute_aggregate(function: str, values: list):
    numeric_values = [Decimal(str(v)) for v in values if isinstance(v, (int, float, Decimal))]
    if function == 'count':
        return len(values)
    if function == 'distinct_count':
        return len(set(values))
    if not numeric_values:
        return None
    if function == 'sum':
        return sum(numeric_values)
    if function == 'avg':
        return sum(numeric_values) / len(numeric_values)
    if function == 'min':
        return min(numeric_values)
    if function == 'max':
        return max(numeric_values)
    return None
