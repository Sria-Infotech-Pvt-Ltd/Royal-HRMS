# Policy engine — `apps/platform_core/services_policies.py`

Versioned, effective-dated business parameters, assigned to employees by
various targeting strategies, resolved through `resolve()`/`resolve_many()`.
**No runtime DDL** — a `PolicyType` declares a JSON Schema; `Policy.parameters`
is validated against it, never a new table per policy type.

## Concepts

- **`PolicyType`** — registered in code (`policy_types_registry.py`,
  synced via `sync_policy_types`, also run automatically on
  `post_migrate`). Declares `parameter_schema`, `resolution_strategy`
  (`single` = one winner; `merge` = field-level merge — only `single` is
  implemented by `resolve()` in this phase, `merge` is declared but not
  yet resolved, since no registered policy type uses it), and
  `specificity_order` (see below).
- **`Policy`** — a named, versioned, effective-dated set of parameter
  values. Only one `is_default=True` policy per `(type, legal_entity)` can
  be active on any given date — enforced at the DB level by an
  `ExclusionConstraint` (not just application code), with `legal_entity`
  NULL ("global default") correctly treated as its own single slot via a
  `Coalesce(..., sentinel-UUID)` wrapper (Postgres `EXCLUDE` constraints
  otherwise treat `NULL <> NULL`, which would silently let two "global
  default" policies coexist with overlapping dates — found and fixed by
  this phase's own tests, see `PHASE3A_REPORT.md`).
- **`PolicyAssignment`** — binds a `Policy` to a target (individual
  employee, position, org unit (with `include_children`), designation,
  grade, employment type, location, legal entity, or an employee group —
  the last one is declared but not resolvable yet, see "Known gaps"
  below), with an optional `condition` (a rule expression, evaluated via
  `services_rules.evaluate()`), effective dates, and a `priority` for
  tie-breaking. No two assignments of the same policy type can overlap
  for the same target (DB exclusion constraint).

## Resolution order (specificity)

Default order, most-specific first (configurable per `PolicyType` via
`specificity_order`; falls back to `DEFAULT_SPECIFICITY_ORDER` if empty):

```
individual > position > org_unit > designation > grade >
employment_type > location > legal_entity > default
```

`resolve()`:
1. Finds every `PolicyAssignment` of the requested type effective on
   `as_of`, whose `policy.status == published`.
2. Filters out any whose **target doesn't match** the employee (see
   "Employee context" below) or whose **condition evaluates false**.
3. Among what's left, the most-specific `target_type` wins; ties break by
   `priority` (higher wins), then by the most recent `effective_from`.
4. If nothing matches, the type's default `Policy` (if any, for the
   employee's legal entity or global) wins.
5. If still nothing, raises `PolicyResolutionError` — **never** silently
   returns an empty/guessed result.

## Employee context

This phase deliberately does **not** hardcode which core-entity columns
back `position`/`org_unit`/`designation`/`grade`/`employment_type`/
`location` — `resolve()`/`resolve_many()` take an `employee_context: dict`
supplied by the caller (e.g. `{"legal_entity_id": ..., "org_unit_id": ...,
"org_unit_ancestor_ids": [...], "employment_type": "CONTRACT"}`). This
keeps the resolution function stable while later phases wire real
org-chart traversal without changing its signature. The attendance
consolidation adapter (Task F) is the first real caller that will build
this context from actual employee/placement data — not built in this
phase (see "Deferred" in `PHASE3A_REPORT.md`).

## The effective-policy explainer

`GET /api/v1/platform/policies/effective?employee=&type=&as_of=` →
`services_policies.explain()`. Returns:

```json
{
  "winner_assignment_id": 42,
  "winner_policy_id": 7,
  "parameters": {"start_time": "10:00", "grace_minutes": 10},
  "used_default": false,
  "candidates_considered": 3,
  "rejected": [
    {"assignment_id": 41, "reason": "Target does not match."},
    {"assignment_id": 40, "reason": "Condition evaluated false."}
  ]
}
```

`GET /api/v1/platform/policies/<id>/affected-employees?as_of=` — impact
analysis before publishing: every active employee for whom this specific
policy is what `resolve_many()` would currently return.

## Cache invalidation (read this before changing `resolve()`)

Every resolved `(employee, type, date)` result is cached under the
`policies` versioned metadata-cache namespace (Phase 1's `cache.py`). A
version bump invalidates **every** cached resolution for that namespace
at once — coarse, but correct — rather than computing which individual
cache keys a given `Policy`/`PolicyAssignment` change could affect, which
risks under-invalidating when a condition rule references an employee
field. The namespace bumps on any `Policy`/`PolicyAssignment`/
`RuleVersion` save/delete (`signals.py`).

**Documented limitation:** an employee's OWN field change (e.g. their
`employment_type` flips) does **not** bump the `policies` namespace —
only a `Policy`/`PolicyAssignment`/`RuleVersion` write does. A
same-day re-resolution after an employee field change can return a stale
cached result until the namespace is next bumped for an unrelated
reason. Flagged in `PHASE3A_REPORT.md` as a real, not-yet-closed gap —
"a wrong cached policy is a payroll risk" per the prompt's own warning.

## Bulk resolution

`resolve_many(policy_type_code, employees, as_of, employee_contexts=)` —
a **bounded query count regardless of employee count**: all assignments
and the default policy for the type+date are fetched once (confirmed at
exactly 3 queries via `assertNumQueries` in `tests_policies.py`,
independent of whether 10 or 10,000 employees are passed), matched in
Python against each employee's own context.

## Known gaps (stated plainly, not silently worked around)

- `TARGET_EMPLOYEE_GROUP` assignments raise `PolicyResolutionError` when
  evaluated — no saved-filter/employee-group engine exists yet to
  evaluate membership against. Refusing cleanly rather than matching
  everyone or no one.
- `resolution_strategy=merge` is declared on `PolicyType` but `resolve()`
  only implements `single` (pick one winner) — no registered policy type
  in this phase uses `merge`.
- The attendance consolidation (Task F) registers the 7 attendance
  `PolicyType`s with full parameter schemas (see
  `policy_types_registry.py`) documenting the System1/System2 field
  mapping, but the actual data migration, `get_attendance_policy()`
  call-site rewiring, and "identical resolution" verification report are
  **not executed in this phase** — see `PHASE3A_REPORT.md`.

## Adapter pattern (`policy_adapters.py`)

Every later phase (leave, WFH, expense, separation, probation, notice
period, payroll) should subclass `PolicyAdapter` rather than hand-rolling
its own flag-check-and-fallback:

```python
class SomeModulePolicyAdapter(PolicyAdapter):
    policy_type_code = 'SOME_TYPE'
    flag_code = 'policies.v2'

    def legacy_resolve(self, employee, as_of):
        ...  # today's existing logic, UNCHANGED
```

`adapter.get(employee, as_of)` checks the flag and calls either
`legacy_resolve()` or the real engine — callers never check the flag
themselves. `LeavePlanPolicyAdapter` is the one concrete adapter built in
this phase (Task G.2) — **read-only**, exposing the existing
`LeavePolicy.applicable_*` lists through the explainer without changing
leave behavior at all.
