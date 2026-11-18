"""The filter engine: turns a JSON condition tree from the browser into a Django Q, using only what the registry allows.

The browser sends field KEYS and operator CODES. It never sends model names, ORM paths or lookup expressions: each key is
looked up in the module's registry, which owns the real path, so nothing the user types can reach a column the registry did not
list. Every value is converted to the field's own type before it touches the ORM.

    {"op": "and", "items": [
        {"field": "gender", "operator": "eq", "value": "female"},
        {"op": "or", "items": [{"field": "branch", "operator": "eq", "value": "Hyderabad"}, ...]}]}
"""
from __future__ import annotations

import datetime
import re
from decimal import Decimal, InvalidOperation

from django.db.models import Q

MAX_DEPTH = 3
MAX_CONDITIONS = 20
MAX_TEXT_LENGTH = 200
MAX_LIST_VALUES = 50

TEXT, CHOICE, DATE, DATETIME, TIME, NUMBER, BOOLEAN = 'text', 'choice', 'date', 'datetime', 'time', 'number', 'boolean'

_EMPTINESS = ('is_empty', 'is_not_empty')
OPERATORS_BY_TYPE: dict[str, tuple[str, ...]] = {
    TEXT: ('eq', 'ne', 'contains', 'not_contains', 'starts_with', 'ends_with', 'in', *_EMPTINESS),
    CHOICE: ('eq', 'ne', 'in', 'not_in', *_EMPTINESS),
    DATE: ('eq', 'ne', 'before', 'after', 'gte', 'lte', 'between', *_EMPTINESS),
    DATETIME: ('eq', 'ne', 'before', 'after', 'gte', 'lte', 'between', *_EMPTINESS),   # compared by calendar day
    TIME: ('eq', 'before', 'after', 'gte', 'lte', 'between', *_EMPTINESS),
    NUMBER: ('eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'between', *_EMPTINESS),
    BOOLEAN: ('eq', 'ne'),
}
OPERATOR_LABELS = {
    'eq': 'is', 'ne': 'is not', 'contains': 'contains', 'not_contains': 'does not contain', 'starts_with': 'starts with',
    'ends_with': 'ends with', 'in': 'is any of', 'not_in': 'is none of', 'gt': 'greater than', 'lt': 'less than',
    'gte': 'greater than or equal to', 'lte': 'less than or equal to', 'between': 'between', 'before': 'before', 'after': 'after',
    'is_empty': 'is empty', 'is_not_empty': 'is not empty',
}
_NEEDS_NO_VALUE = frozenset(_EMPTINESS)
_LOOKUP = {'gt': 'gt', 'after': 'gt', 'lt': 'lt', 'before': 'lt', 'gte': 'gte', 'lte': 'lte'}
_TIME_RE = re.compile(r'^\d{2}:\d{2}(:\d{2})?$')


class FilterError(Exception):
    """A filter request that cannot be honoured. The message is safe to show to the person who sent it."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def operators_for(spec) -> tuple[str, ...]:
    return spec.operators or OPERATORS_BY_TYPE[spec.type]


def _text(value) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise FilterError('Enter text for this filter.')
    text = str(value).strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise FilterError(f'Filter text can be at most {MAX_TEXT_LENGTH} characters.')
    return text


def _convert(spec, value):
    """The value as the field's own type, or FilterError naming the field."""
    label = spec.label
    try:
        if spec.type in (TEXT, CHOICE):
            text = _text(value)
            if spec.type == CHOICE and spec.choices and text not in {code for code, _ in spec.choices}:
                raise FilterError(f'"{text}" is not a valid choice for {label}.')
            return text
        if spec.type == NUMBER:
            if isinstance(value, bool):
                raise InvalidOperation
            return Decimal(str(value).strip())
        if spec.type == DATE:
            return datetime.date.fromisoformat(str(value).strip())
        if spec.type == DATETIME:
            # A moment is filtered by its calendar day ("on / before / after 18-11-2026"), so only the date part counts.
            return datetime.date.fromisoformat(str(value).strip()[:10])
        if spec.type == TIME:
            text = str(value).strip()
            if not _TIME_RE.match(text):
                raise ValueError
            return datetime.time.fromisoformat(text)
        if spec.type == BOOLEAN:
            if isinstance(value, bool):
                return value
            if str(value).strip().lower() in ('true', '1', 'yes'):
                return True
            if str(value).strip().lower() in ('false', '0', 'no'):
                return False
            raise ValueError
    except FilterError:
        raise
    except (ValueError, InvalidOperation, TypeError):
        raise FilterError(f'"{value}" is not a valid {spec.type} for {label}.') from None
    raise FilterError(f'{label} cannot be filtered.')


def _values_list(spec, value) -> list:
    if not isinstance(value, list) or not value:
        raise FilterError(f'Choose at least one value for {spec.label}.')
    if len(value) > MAX_LIST_VALUES:
        raise FilterError(f'Choose at most {MAX_LIST_VALUES} values for {spec.label}.')
    return [_convert(spec, entry) for entry in value]


def _is_empty_q(spec) -> Q:
    if spec.build is not None:
        raise FilterError(f'{spec.label} cannot be tested for empty.')
    empty = Q(**{f'{spec.path}__isnull': True})
    return empty | Q(**{spec.path: ''}) if spec.type in (TEXT, CHOICE) else empty


def _comparison_q(spec, operator: str, value) -> Q:
    path = f'{spec.path}__date' if spec.type == DATETIME else spec.path
    if operator == 'eq':
        converted = _convert(spec, value)
        return Q(**{f'{path}__iexact': converted}) if spec.type == TEXT else Q(**{path: converted})
    if operator == 'contains':
        return Q(**{f'{path}__icontains': _convert(spec, value)})
    if operator == 'starts_with':
        return Q(**{f'{path}__istartswith': _convert(spec, value)})
    if operator == 'ends_with':
        return Q(**{f'{path}__iendswith': _convert(spec, value)})
    if operator in _LOOKUP:
        return Q(**{f'{path}__{_LOOKUP[operator]}': _convert(spec, value)})
    if operator == 'between':
        if not isinstance(value, list) or len(value) != 2:
            raise FilterError(f'Give a start and an end for {spec.label}.')
        start, end = _convert(spec, value[0]), _convert(spec, value[1])
        if start > end:
            raise FilterError(f'The start of {spec.label} is after its end.')
        return Q(**{f'{path}__range': (start, end)})
    if operator == 'in':
        return Q(**{f'{path}__in': _values_list(spec, value)})
    raise FilterError(f'Operator "{operator}" is not supported for {spec.label}.')


_NEGATED = {'ne': 'eq', 'not_contains': 'contains', 'not_in': 'in'}


def condition_q(spec, operator: str, value) -> Q:
    """The Q for one allowed (field, operator, value). Raises FilterError for anything outside the allow-lists."""
    if operator not in operators_for(spec):
        raise FilterError(f'"{OPERATOR_LABELS.get(operator, operator)}" cannot be used with {spec.label}.')
    if spec.build is not None:
        positive = _NEGATED.get(operator, operator)
        built = spec.build(positive, _convert(spec, value) if positive != 'in' else _values_list(spec, value))
        return ~built if operator in _NEGATED else built
    if operator == 'is_empty':
        return _is_empty_q(spec)
    if operator == 'is_not_empty':
        return ~_is_empty_q(spec)
    if operator in _NEGATED:
        return ~_comparison_q(spec, _NEGATED[operator], value)
    return _comparison_q(spec, operator, value)


def _count(node) -> int:
    if isinstance(node, dict) and 'items' in node:
        return sum(_count(child) for child in node['items'])
    return 1


def _build(node, fields: dict, depth: int) -> Q:
    if not isinstance(node, dict):
        raise FilterError('A filter must be an object.')
    if 'items' in node:
        if depth > MAX_DEPTH:
            raise FilterError(f'Filter groups can be nested at most {MAX_DEPTH} levels deep.')
        joiner = node.get('op', 'and')
        if joiner not in ('and', 'or'):
            raise FilterError('A filter group must be "and" or "or".')
        items = node['items']
        if not isinstance(items, list) or not items:
            raise FilterError('A filter group cannot be empty.')
        combined = None
        for child in items:
            child_q = _build(child, fields, depth + 1)
            combined = child_q if combined is None else (combined & child_q if joiner == 'and' else combined | child_q)
        return combined
    key = node.get('field')
    spec = fields.get(key) if isinstance(key, str) else None
    if spec is None:
        raise FilterError('Unknown or unavailable filter field.')
    operator = node.get('operator')
    if not isinstance(operator, str):
        raise FilterError(f'Choose how to filter {spec.label}.')
    if operator in _NEEDS_NO_VALUE:
        return condition_q(spec, operator, None)
    if 'value' not in node:
        raise FilterError(f'Enter a value for {spec.label}.')
    return condition_q(spec, operator, node['value'])


def build_filter(tree, fields: dict) -> Q:
    """The Q for a whole filter tree, using only `fields` (key -> FieldSpec the viewer may use). An empty tree matches everything."""
    if tree in (None, {}, []):
        return Q()
    if not isinstance(tree, dict):
        raise FilterError('Filters must be an object.')
    if 'items' not in tree:
        tree = {'op': 'and', 'items': [tree]}
    if _count(tree) > MAX_CONDITIONS:
        raise FilterError(f'Use at most {MAX_CONDITIONS} filter conditions.')
    return _build(tree, fields, 1)
