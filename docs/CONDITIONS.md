# Declarative condition format

Used by `FieldDefinition.validation.required_when`, `FormStep.visible_when`,
`FormSection.visible_when`, and `FormFieldPlacement.visible_when`/`required_when`
(`apps/platform_core/services_conditions.py`). Evaluated by
`services_conditions.evaluate(condition, values)` — never `eval()`'d, never
executed as code.

## Shape

```json
{"all": [{"field": "employment_type", "op": "eq", "value": "contract"}]}
```

or

```json
{"any": [
  {"field": "country", "op": "in", "value": ["IN", "AE"]},
  {"field": "is_remote", "op": "eq", "value": true}
]}
```

- Top level (and each nested clause) has exactly one of `"all"` or `"any"` —
  never both at the same level.
- Each entry in the list is either another `{"all"|"any": [...]}` clause
  (nesting, up to `MAX_NESTING_DEPTH = 3`) or a leaf `{"field", "op", "value"}`.
- `"value"` is omitted for `empty`/`not_empty`.

## Operators

| op | meaning |
|---|---|
| `eq` / `ne` | equality / inequality |
| `in` / `not_in` | membership in `value` (a list) |
| `empty` / `not_empty` | `actual in (None, '', [], {})` / its negation |
| `gt` / `lt` / `gte` / `lte` | ordering comparison; raises `ConditionError` on an incomparable pair (e.g. string vs. int) rather than silently returning `False` |

An unknown operator, a malformed clause (missing `field`/`op`), both `all`
and `any` at the same level, or nesting beyond the limit all raise
`ConditionError` — never silently coerced to `False`.

## The empty-condition default — read this before using `required_when`

`evaluate({}, values)` returns `True`. This is deliberate for `visible_when`:
an unconfigured `visible_when` means "always visible," which is the correct
default for a plain, unconditional field.

**It is the wrong default for `required_when` used literally.** An empty
`required_when` must NOT make every field required regardless of its own
`required` flag. Every caller in this codebase (`services_attributes.validate()`,
`services_forms.validate_submission()`) therefore guards the call:

```python
required_when = field_def.validation.get('required_when') or {}
is_required = field_def.required or (bool(required_when) and evaluate(required_when, values))
```

i.e. `evaluate()` is only consulted when a real condition is actually
configured. This exact bug (an empty `required_when` silently requiring
every field) was caught by `tests_attributes.py`/`tests_forms.py` during
Phase 2 and fixed in both call sites — any NEW caller of `required_when`
must apply the same guard, not call `evaluate()` on it directly.

## Values dict

`values` is a plain `{field_code: value}` dict — callers resolve it from
whatever record/payload shape they have (e.g. `services_attributes.validate()`
merges the record's existing attribute values with the incoming submission
before evaluating conditions, so a condition can reference a field not
present in the current request).
