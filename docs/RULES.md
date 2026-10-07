# Rule/formula engine — `apps/platform_core/services_rules.py`

A safe, whitelisted JSON-expression evaluator. **No `eval`, `exec`,
`compile`, `pickle`, or dynamic import of admin-supplied content anywhere
in this engine** — every operation is a plain Python function looked up
by a fixed string key (`rule_functions.FUNCTIONS` / `rule_functions_numeric`),
never constructed from input.

Phase 3B's workflow/notification engine must accept this grammar
unchanged — it is not re-invented per phase.

## Grammar

A node is one of:

```json
{"var": "amount"}
```
Reads a value from the evaluation context (a plain `{name: value}` dict —
never a model instance; there is no attribute access to arbitrary
objects anywhere in this engine).

```json
{"op": "gt", "args": [{"var": "amount"}, {"op": "literal", "value": 50000}]}
```
A function call. `op` must be a key in the function registry (see
below) — an unknown operator is a clean `RuleError`, never a crash.

```json
{"op": "literal", "value": 50000}
```
A literal. Bare JSON literals (`50000`, `"text"`, `true`, `null`, a list)
are also accepted directly as nodes.

```json
{"provider": "employee.field", "args": [{"var": "employee"}, {"op": "literal", "value": "department"}]}
```
A data-provider call (see "Data providers" below).

### The Phase 2 condition format is accepted unchanged

`docs/CONDITIONS.md`'s `{"all"|"any": [{"field", "op", "value"}]}` format
parses into the exact equivalent tree via `from_condition_format()` (or
automatically, by passing it straight to `evaluate()` — an empty dict or
a dict containing `"all"`/`"any"` is auto-detected). `not_in`/`empty`/
`not_empty` desugar into `not`/`is_null`/`not is_null` nodes respectively;
`eq`/`ne`/`gt`/`lt`/`gte`/`lte`/`in` map straight across.

## Types

`number` (always `Decimal`, **never `float`** — literals are converted
via `Decimal(str(x))`, never the binary float constructor, so `0.1+0.2`
behaves exactly like money arithmetic should), `integer`, `string`,
`boolean`, `date`, `datetime`, `time`, `duration`, `lookup_code`, `list`,
`null`.

### Static type-checking

`RuleDefinition.input_context` declares every variable a rule may read
and its type. `services_rule_definitions.type_check()` walks the
expression tree at publish time and rejects any `{"var": "x"}` node
naming a variable not in `input_context` — errors name the exact node
path (e.g. `$.args[0].args[1]: variable "x" is not declared`). This is
intentionally a structural check (does every variable reference resolve
to something declared), not a full type-inference pass over every
operator's argument types — operator-level type mismatches still surface
at evaluation time as a `RuleError`, not silently.

## Null handling

- Arithmetic (`add`/`sub`/`mul`/`div`/...) with any `None` operand
  returns `None` (never raises) — a rule computing on a field that
  hasn't been filled in yet gets `None`, not a crash.
- Comparisons (`gt`/`lt`/`gte`/`lte`) with a `None` operand are `False`.
- `eq`/`ne` compare `None` normally (`eq(None, None)` is `True`).
- `is_null`/`empty`/`not_empty` are the only reliable way to test for
  absence.

## Limits (hard, clean errors — never a hang)

| Limit | Value | Constant |
|---|---|---|
| Max expression nodes | 500 | `services_rules.MAX_NODES` |
| Max nesting depth | 20 | `services_rules.MAX_DEPTH` |
| Max list size | 1000 | `services_rules.MAX_LIST_SIZE` |
| Max regex pattern length | 200 chars | `rule_functions.MAX_REGEX_LENGTH` |
| Max string length | 10,000 chars | `rule_functions.MAX_STRING_LENGTH` |

Exceeding any of these raises `RuleLimitExceeded` (a subclass of
`RuleError`) — the evaluator's own fuzz test
(`tests_rules_engine.FuzzSafetyTests`) proves 200 random malformed/junk
trees never raise anything other than `RuleError`.

**Known gap, stated plainly:** `matches()`'s regex safety relies on
length limits on both the pattern and the subject string to bound
catastrophic-backtracking blast radius to a small, fixed worst case —
Python's stdlib `re` has no re2-style linear-time guarantee. This is a
deliberate, documented, bounded risk, not an oversight.

**Performance:** benchmarked at ~13,500 evaluations/second for a 30-node
rule on CI-class hardware (100,000 evaluations in ~7.4s) via plain tree-
walking — no "compile once into a cached callable" optimization was
built in this phase (Task A.4 describes this as an aspiration; the
tree-walker is correct and fast enough for every caller in this phase,
including `resolve_many()`'s bulk resolution). Flagged as a future
optimization, not a correctness gap.

## Function library

**Math:** `add`, `sub`, `mul`, `div` (raises on divide-by-zero), `min`,
`max`, `abs`, `round(value, places, mode)` (modes: `half_up`, `half_even`,
`up`, `down`, `ceiling`, `floor`), `round_nearest_n(value, n, mode)`,
`ceil`, `floor`, `pow(base, exponent)` (exponent capped at ±32),
`percent_of(amount, pct)`.

**Logic:** `if(cond, then, else)`, `case(cond1, val1, cond2, val2, ..., default)`
(odd arg count), `and`, `or`, `not`, `coalesce`, `in(value, list)`,
`between(value, low, high)`, `is_null`, `eq`, `ne`, `gt`, `lt`, `gte`, `lte`.

**Text:** `concat`, `upper`, `lower`, `length`, `starts_with`, `contains`,
`matches(value, regex)` (length-limited, see above).

**Date/time:** `date_diff(unit, d1, d2)` (units: `days`/`months`/`years`),
`add_days`/`add_months`/`add_years` (month/year-end-safe — e.g.
`add_months('2026-01-31', 1)` → `2026-02-28`), `start_of`/`end_of`
(`month`/`quarter`/`year`), `age_on(dob, as_of)`, `tenure_on(joining_date,
as_of, unit)`, `day_of_week`, `minutes_between(t1, t2)`.

**Table/slab/band lookups** (needed by payroll/tax, built for them
now): `slab(value, table_code, as_of)` (progressive, like income tax
slabs — sums the rate-weighted portion of `value` falling in each band
up to where it lands), `band(value, table_code, as_of)` (single matching
band's rate). Both resolve against `RuleTable`/`RuleTableVersion` rows
effective on `as_of` (date-range exclusion-constrained, no overlaps
possible at the DB level).

**Lookup attributes:** `lookup_attr(type_code, code, key, default=None)`
— reads a Phase 1 `LookupValue.attributes` key (e.g.
`lookup_attr('LEAVE_TYPE', code, 'is_unpaid')`).

## Data providers

Read-only, registered in code by a developer (`services_rules.register_provider`)
— **using** a registered provider by name in a rule's expression is
admin configuration; **adding** one is a developer task. This boundary
is deliberate: a provider can run a bounded, permission-aware query;
nothing else in the expression tree can touch the database at all.

**Implemented in this phase:** `employee.field(employee, field_code)` —
reads a core or custom attribute via Phase 2's `services_attributes.read()`
(or a plain model attribute if `field_code` matches one).

**Named by the prompt but NOT implemented in this phase** (registering a
provider with a guessed implementation that silently disagrees with the
real module logic would be worse than refusing):
`attendance.count_days`, `calendar.working_days_between`,
`org.manager_level`. These need deep integration with attendance's exact
calendar logic and the org-chart traversal Phase 3B's approver resolvers
need — left unregistered (calling them raises a clean `RuleError: Unknown
or unregistered data provider`) and flagged as an open item for whoever
builds Phase 3B or the attendance consolidation pass.

## Writing a rule (example)

```json
{
  "all": [
    {"field": "tenure_months", "op": "gte", "value": 6},
    {"field": "employment_type", "op": "in", "value": ["PERMANENT", "PROBATION"]}
  ]
}
```
— "eligible if tenure >= 6 months and employment type is PERMANENT or
PROBATION," written in the Phase 2 condition format, evaluates
identically through this engine.

## Publishing (`services_rule_definitions.py`)

- A `RuleDefinition` cannot publish without at least one `RuleTestCase`,
  and every test case must pass (`run_test_cases()`). Test inputs must be
  synthetic — never real personal data (a process rule, not mechanically
  enforced).
- Publishing creates an immutable `RuleVersion` snapshot with an
  `effective_from` date. Consumers ALWAYS resolve via
  `get_effective_version(code, as_of)` / `evaluate_effective(code, ctx,
  as_of)` — never by reading `RuleDefinition.expression` directly, which
  is the live draft.
- `where_used(rule)` / `retire(rule)` — a rule referenced by any
  `PolicyAssignment.condition` cannot be retired without removing the
  reference first.
