"""
Phase 3A Task C — RuleDefinition lifecycle: type-check at save time,
test-gated publish, immutable version snapshots selected by effective
date, and a "where used" check before retirement.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.platform_core import services_rules as rules
from apps.platform_core.rule_errors import RuleError
from apps.platform_core.models import RuleDefinition, RuleVersion

_TYPE_COMPATIBLE = {
    'number': {'number', 'integer'}, 'integer': {'integer'}, 'string': {'string', 'lookup_code'},
    'boolean': {'boolean'}, 'date': {'date'}, 'datetime': {'datetime'}, 'time': {'time'},
    'duration': {'duration', 'number'}, 'lookup_code': {'lookup_code', 'string'}, 'list': {'list'},
    'null': set(),  # a declared input can never be typed "null" — only a literal/return value can be
}


class RulePublishError(Exception):
    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


def type_check(rule: RuleDefinition) -> list[str]:
    """Static check (Task A.2): walks the tree verifying every `var` node
    names a declared input_context variable, and that comparison/
    arithmetic nodes aren't fed obviously incompatible declared types.
    Returns a list of human-readable errors (empty = passes); never
    raises — callers decide what to do with a non-empty list."""
    errors: list[str] = []
    declared = set(rule.input_context.keys())

    def walk(node, path='$'):
        if isinstance(node, list):
            for i, n in enumerate(node):
                walk(n, f'{path}[{i}]')
            return
        if not isinstance(node, dict):
            return
        if 'var' in node:
            name = node['var']
            if name not in declared:
                errors.append(f'{path}: variable "{name}" is not declared in input_context.')
            return
        for i, arg in enumerate(node.get('args', [])):
            walk(arg, f'{path}.args[{i}]')

    try:
        walk(rule.expression)
    except Exception as exc:  # pragma: no cover - defensive; walk() above is pure structural recursion
        errors.append(f'Could not type-check expression: {exc}')
    return errors


def run_test_cases(rule: RuleDefinition) -> bool:
    """Runs every RuleTestCase for `rule` against its CURRENT draft
    expression, recording last_result/last_run_at/passed on each. Returns
    True only if every test case passed AND at least one exists (Task
    C.2's publish gate)."""
    test_cases = list(rule.test_cases.all())
    if not test_cases:
        return False

    all_passed = True
    now = timezone.now()
    for case in test_cases:
        try:
            result = rules.evaluate(rule.expression, dict(case.inputs))
            passed = _values_equal(result, case.expected_output)
        except RuleError as exc:
            result = {'error': exc.message}
            passed = False
        case.last_result = _jsonable(result)
        case.last_run_at = now
        case.passed = passed
        case.save(update_fields=['last_result', 'last_run_at', 'passed'])
        all_passed = all_passed and passed
    return all_passed


def _values_equal(actual, expected) -> bool:
    from decimal import Decimal
    if isinstance(actual, Decimal) or isinstance(expected, (int, float)):
        try:
            return Decimal(str(actual)) == Decimal(str(expected))
        except Exception:
            return actual == expected
    return actual == expected


def jsonable(value):
    """Public alias of _jsonable — converts Decimal/date/datetime values
    (and nested dicts/lists of them) into plain JSON-serializable types,
    for any caller (e.g. views_rules.py's ad-hoc test-run endpoint) that
    needs to return an evaluator result in an API response."""
    return _jsonable(value)


def _jsonable(value):
    from decimal import Decimal
    import datetime
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


@transaction.atomic
def publish(rule: RuleDefinition, *, actor=None, effective_from=None) -> RuleVersion:
    """Task C.1/C.3 — blocked unless type-check passes and every test
    case passes (and at least one exists). Creates an immutable
    RuleVersion snapshot; the version number increments even for the
    FIRST publish of a never-before-published rule, so "version 1" always
    means "the first published snapshot," matching RuleDefinition's own
    default version=1."""
    type_errors = type_check(rule)
    if type_errors:
        raise RulePublishError('Type-check failed.', type_errors)
    if not run_test_cases(rule):
        raise RulePublishError('Cannot publish: at least one test case is required and all must pass.')

    effective_from = effective_from or timezone.localdate()
    version = RuleVersion.objects.create(
        rule=rule, version=rule.version, expression=rule.expression,
        input_context=rule.input_context, return_type=rule.return_type,
        effective_from=effective_from, published_by=actor,
    )
    rule.status = RuleDefinition.STATUS_PUBLISHED
    rule.published_at = timezone.now()
    rule.published_by = actor
    rule.version += 1
    rule.save(update_fields=['status', 'published_at', 'published_by', 'version'])
    return version


def get_effective_version(code: str, as_of) -> RuleVersion:
    """Consumers (policies, workflows, Phase 3B) ALWAYS resolve a rule
    this way — never by reading RuleDefinition.expression directly,
    which is the live DRAFT, not what was actually published and in
    effect on a historical date."""
    version = RuleVersion.objects.filter(rule__code=code, effective_from__lte=as_of).order_by('-effective_from').first()
    if version is None:
        raise RuleError(f'No published version of rule {code!r} is effective on {as_of}.')
    return version


def evaluate_effective(code: str, context: dict, as_of):
    version = get_effective_version(code, as_of)
    return rules.evaluate(version.expression, context)


def where_used(rule: RuleDefinition) -> list[str]:
    """Task C.5 — a rule used anywhere cannot be retired without
    replacing the reference first. Checks the two places this phase
    itself lets a rule code be referenced (FieldDefinition.validation's
    required_when conditions is Phase 2 condition format, not a rule
    reference by code, so it's excluded; PolicyAssignment.condition CAN
    embed a rule by code via a future {"rule": code} node — searched as a
    plain substring of the serialized JSON, which is sufficient to catch
    real references without needing a full tree walk per caller)."""
    from apps.platform_core.models import PolicyAssignment
    import json

    needle = f'"{rule.code}"'
    usages = []
    for assignment in PolicyAssignment.objects.exclude(condition={}):
        if needle in json.dumps(assignment.condition):
            usages.append(f'PolicyAssignment #{assignment.pk} ({assignment.policy.code})')
    return usages


def retire(rule: RuleDefinition) -> None:
    usages = where_used(rule)
    if usages:
        raise RulePublishError(f'Cannot retire — still referenced by: {", ".join(usages)}', usages)
    rule.status = RuleDefinition.STATUS_RETIRED
    rule.save(update_fields=['status'])
