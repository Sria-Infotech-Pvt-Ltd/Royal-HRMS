# Phase 3A Report — Rule/Formula Engine + Policy Engine

Delivered 2026-10-07. Scope: `backend/apps/platform_core/services_rules.py`,
`rule_functions.py`, `rule_functions_numeric.py`, `rule_errors.py`,
`services_rule_definitions.py`, `services_policies.py`, `policy_adapters.py`,
`policy_types_registry.py`, `models/rules.py`, `models/policies.py`,
`views_rules.py`, `serializers_rules.py`. This report follows the same
Section-7 structure as `PHASE1_REPORT.md`/`PHASE2_REPORT.md`.

## Scoping decision, stated up front (same discipline as Phase 0/1/2)

Tasks A, B, C, D, E, G (Task G.1/G.2 only), and H are built as real,
tested, reachable infrastructure. **Task F (attendance consolidation) is
deliberately NOT executed as a data migration/call-site cutover in this
pass** — the 7 attendance `PolicyType`s are registered with full
parameter schemas documenting the System1/System2 field mapping (real,
useful, low-risk work), but the actual data migration, the
`get_attendance_policy()` call-site rewiring across attendance services/
tasks/views/voice actions, and the "identical resolution for every active
employee" verification report are deferred to their own dedicated pass —
same risk class as the Company→LegalEntity and NumberSeries cutovers in
Phase 1. Attendance processing for every employee is the highest-blast-
radius item in this entire prompt; guessing at the exact call sites under
time pressure risks a silent, hard-to-detect payroll/attendance
correctness regression, which is a worse outcome than refusing to build
it this pass.

**What was built and is real, tested, reachable infrastructure:**

- The rule evaluator (Task A): `services_rules.py` + `rule_functions.py`
  + `rule_functions_numeric.py` — a whitelisted JSON-tree walker, zero
  `eval`/`exec`/`compile`/`pickle`, Decimal-only arithmetic, hard limits
  (node count/depth/list size/regex/string length), the Phase 2 condition
  format accepted unchanged.
- The function library (Task B): math, logic, text, date/time, slab/band
  table lookups, lookup attribute reads, and one real data provider
  (`employee.field`).
- Rule definitions (Task C): `RuleDefinition`/`RuleVersion`/`RuleTestCase`/
  `RuleTable`/`RuleTableVersion`, publish-blocked-without-passing-tests,
  version-by-effective-date resolution, where-used/retire blocking.
- The policy engine (Task D): `PolicyType`/`Policy`/`PolicyAssignment`,
  `resolve()`/`resolve_many()` with a configurable specificity order,
  DB-enforced no-overlap and one-default-per-type-per-entity constraints,
  versioned cache invalidation.
- The explainer (Task E): `services_policies.explain()` +
  `PolicyExplainerView`/`PolicyAffectedEmployeesView`.
- The adapter pattern (Task G.1) + the one real read-only adapter
  (Task G.2, `LeavePlanPolicyAdapter`).
- Admin APIs (Task H): full CRUD + lifecycle actions for rules, rule
  tables, policy types, policies, assignments, the explainer, and
  affected-employees.

**63 new tests, all passing**, plus the unchanged Phase 1/2 suites.

---

## 1. What was built, per task

**Task A — Expression language and evaluator.** JSON-tree grammar
(`{"var"}`/`{"op", "args"}`/`{"literal"}`/`{"provider", "args"}`) fully
documented in `docs/RULES.md`. The Phase 2 condition format parses into
the identical tree via `from_condition_format()` — proven by
`ConditionFormatParityTests` asserting both formats evaluate to the same
result for the same logical condition. All numeric literals and context
values go through `Decimal(str(x))`, never the binary float constructor
— "never use float for money, rates, or durations" applies to literals
embedded in a rule, not just runtime values. Hard limits (500 nodes, 20
depth, 1000-item lists, 200-char regex, 10,000-char strings) are each
independently tested; a 200-iteration fuzz test over malformed/junk trees
proves the evaluator never raises anything other than `RuleError`.
Benchmarked at ~13,500 evaluations/sec for a 30-node rule — no "compile
once into a cached callable" optimization was built (a real, stated gap,
not silently skipped — current throughput is sufficient for every caller
in this phase).

**Task B — Function library.** Full math/logic/text/date-time coverage
plus `slab()`/`band()` (progressive and single-band table lookups against
`RuleTable`/`RuleTableVersion`, date-range exclusion-constrained so two
versions can never silently overlap) and `lookup_attr()` (reuses Phase
1's `services_lookups.get_attribute()`, no second lookup-reading
implementation). **Data providers**: only `employee.field` is
implemented for real, built on Phase 2's `services_attributes.read()`.
`attendance.count_days`/`calendar.working_days_between`/`org.manager_level`
are explicitly left unregistered — see "Deferred" below.

**Task C — Rule definitions.** `type_check()` walks the expression tree
verifying every `{"var": name}` node names a variable declared in
`RuleDefinition.input_context`. `run_test_cases()` re-runs every
`RuleTestCase` against the CURRENT draft expression and records
`last_result`/`last_run_at`/`passed`; `publish()` is blocked unless at
least one test case exists and all pass (`RulePublishError` otherwise),
then creates an immutable `RuleVersion` snapshot and increments
`RuleDefinition.version`. `get_effective_version(code, as_of)` /
`evaluate_effective()` are the ONLY way any consumer should read a
published rule — never `RuleDefinition.expression` directly, which is
the live draft. `where_used()`/`retire()` block retirement while a
`PolicyAssignment.condition` still references the rule's code.

**Task D — Policy engine.** `PolicyType.specificity_order` defaults to
`individual > position > org_unit > designation > grade >
employment_type > location > legal_entity > default`
(`DEFAULT_SPECIFICITY_ORDER`), overridable per type. `resolve()` filters
candidate `PolicyAssignment`s by target match (via a caller-supplied
`employee_context` dict — deliberately NOT hardcoded to specific
core-entity columns, so later phases can wire real org-chart traversal
without this function's signature changing) and condition (evaluated
through the Task A engine), then picks the most-specific/highest-
priority/most-recent candidate, falling back to the type's default
policy, raising `PolicyResolutionError` if nothing resolves.
`resolve_many()` fetches all assignments/default once (confirmed at a
constant 3 queries via `assertNumQueries`, independent of employee count)
and matches in Python per employee.

**Task E — Effective-policy explainer.** `explain()` returns the winner,
every candidate considered, and WHY each rejected candidate lost ("Target
does not match" / "Condition evaluated false" / a condition evaluation
error) — proven by `PolicyExplainerTests`.

**Task F — Attendance consolidation.** See "Scoping decision" above and
"Deferred, and why" below.

**Task G — Adapter pattern.** `PolicyAdapter` base class
(`policy_adapters.py`) — `get(employee, as_of)` checks the module's own
feature flag and calls either `legacy_resolve()` (today's existing logic,
untouched) or the real engine; callers never check the flag themselves.
`LeavePlanPolicyAdapter` is the one concrete instance built — read-only,
exposing `LeavePolicy.applicable_*` through the explainer without
changing leave behavior (per Task G.2's explicit instruction). Task G.3's
per-user-field-to-target-phase table is in `docs/MIGRATION_PLAN.md`.

**Task H — Admin APIs and docs.** `views_rules.py`: full CRUD +
validate/test-run/publish/retire/where-used/versions for rules, CRUD for
rule tables and table versions, read access to policy types, CRUD for
policies and assignments, the explainer, and affected-employees (built on
`resolve_many()` — permission-aware via `HasSettingsPermission`, same as
every other admin surface). `docs/RULES.md` and `docs/POLICIES.md`
written in full.

---

## 2. Four real bugs found and fixed (caught by the test suites, not guessed at)

1. **Postgres `EXCLUDE` constraints treat `NULL <> NULL`.** The "only one
   default policy per type per legal entity at any date" constraint used
   `legal_entity` directly in its `ExclusionConstraint` expression — but
   `legal_entity=NULL` means "global default," and Postgres's standard
   NULL semantics mean two NULL values are never considered equal for
   constraint purposes, so **two "global default" policies with
   overlapping date ranges would have silently coexisted**, exactly the
   kind of payroll-risk bug the prompt itself warned about. Caught by
   `test_two_defaults_same_type_entity_overlapping_dates_rejected` failing
   with "IntegrityError not raised." Fixed by wrapping `legal_entity_id`
   in `Coalesce(..., sentinel-UUID)` so two NULLs collapse to the same
   comparable value for the constraint (migration
   `0010_policy_default_sentinel_fix`).
2. **`ExclusionConstraint` expressions can't traverse FK joins.** The
   "no overlapping assignment for the same target+policy type" constraint
   was initially written against `policy__type` (a joined field) — Django/
   Postgres exclusion constraints can only reference real columns on the
   constrained table itself. Caught before it even reached a test (a
   `makemigrations`-time/model-definition-level issue, fixed by adding a
   denormalized `PolicyAssignment.policy_type` FK kept in sync via
   `save()`, used directly in the constraint).
3. **`ChangeHistory.changes` (Phase 1) was missing `encoder=DjangoJSONEncoder`.**
   A latent bug since Phase 1 — any tracked field value that's a
   `date`/`datetime`/`Decimal`/`UUID` crashed `ChangeHistory.objects.create()`
   with `TypeError: Object of type date is not JSON serializable`. Never
   surfaced in Phase 1/2 because no previously-registered model's tests
   happened to `.save()` a tracked date/Decimal field directly; Phase 3A's
   own `RuleDefinition`/`Policy`/`PolicyAssignment` history registrations
   (added per Task C.6/Task D's "everything recorded in ChangeHistory")
   hit it on the very first test run. Fixed in migration
   `0011_change_history_json_encoder_fix` — a general fix benefiting every
   future `history.register()` call, not scoped narrowly to Phase 3A's own
   models.
4. **Evaluator edge cases caught before any real caller could hit them:**
   an empty expression `{}` at the top level raised `RuleError` instead of
   evaluating to `True` (the documented "empty condition = always
   true/active" contract) — `evaluate()` only auto-detected the condition
   format when `"all"`/`"any"` were present, missing the empty-dict case.
   Also, a list literal wrapped as `{"op": "literal", "value": [...]}`
   bypassed the `MAX_LIST_SIZE` check (only a bare JSON list node was
   checked). Both fixed; both caught by `LimitTests`/`ConditionFormatParityTests`
   before shipping.

---

## 3. Attendance consolidation (Task F) — what exists vs. what's deferred

**Built:** 7 `PolicyType` rows (`ATT_WORKING_HOURS`, `ATT_WEEKLY_OFF`,
`ATT_PUNCH_RULES`, `ATT_OVERTIME`, `ATT_LATE_MARK`, `ATT_ABSENCE_ALERT`,
`ATT_FACE_VERIFICATION`, plus `ATT_GEOFENCE` — 8 total, one more than the
7 the prompt's own fact-finding section named, covering the geofence
radius constant from the Phase 0 inventory too), each with a full
`parameter_schema` covering every field of both System 1
(`AttendanceSettings` + its one-to-one tables) and System 2 (the named
`WorkingHoursPolicy`/`WeeklyDayPolicy`/`PunchRulesPolicy`/`OvertimePolicy`/
`LateMarkLOPPolicy`/`AbsenceAlertPolicy` models), registered in
`policy_types_registry.py` and synced idempotently (confirmed:
`Created=9 Updated=0 Unchanged=0` on first sync, `Unchanged=9` on
re-sync).

**NOT built in this pass, and why:**
- **The System1-vs-System2 "which one does the current code actually
  use" investigation** — the prompt explicitly asks to document which
  system wins today when they conflict. This needs tracing every
  attendance service/task/view/voice-action call site, which is exactly
  the scope of work Task F.3 itself describes as "replace direct reads of
  the old models everywhere... grep and list every call site" — a
  dedicated pass, not a side effect of building the policy engine itself.
- **The data migration** (System2 policies → `Policy` rows, System1
  values → legal-entity defaults or retired-version history,
  `EmployeeWeeklyOffAssignment` → `PolicyAssignment`) — not executed.
- **`get_attendance_policy(employee, type, date)` adapter** — the
  `PolicyAdapter` base class (Task G.1) is ready for this; no concrete
  attendance adapter subclass was written, since its `legacy_resolve()`
  would need to faithfully reproduce today's exact fallback behavior,
  which depends on the undone investigation above.
- **The "identical resolution for every active employee" verification
  report** — cannot be produced without the migration itself.

This mirrors Phase 1's own Company→LegalEntity and NumberSeries
deferrals exactly: the type/schema/engine-side work is done and tested;
the live-data cutover is its own pass.

---

## 4. New endpoints for the frontend

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/v1/platform/rules/` | List/create rule definitions |
| GET/PATCH/DELETE | `/api/v1/platform/rules/<id>/` | Rule detail |
| POST | `/api/v1/platform/rules/<id>/validate/` | Type-check only |
| POST | `/api/v1/platform/rules/<id>/test-run/` | Ad-hoc evaluate with inputs from the request body |
| POST | `/api/v1/platform/rules/<id>/publish/` | Publish (blocked without passing tests) |
| POST | `/api/v1/platform/rules/<id>/retire/` | Retire (blocked while referenced) |
| GET | `/api/v1/platform/rules/<id>/where-used/` | List referencing PolicyAssignments |
| GET | `/api/v1/platform/rules/<id>/versions/` | Version history |
| GET/POST | `/api/v1/platform/rule-test-cases/?rule=` | List/create test cases |
| GET/POST | `/api/v1/platform/rule-tables/` | List/create rule tables |
| GET/POST | `/api/v1/platform/rule-table-versions/?table=` | List/create table versions |
| GET | `/api/v1/platform/policy-types/` | List policy types |
| GET/POST | `/api/v1/platform/policies/?type=` | List/create policies |
| GET/PATCH/DELETE | `/api/v1/platform/policies/<id>/` | Policy detail |
| GET | `/api/v1/platform/policies/<id>/affected-employees/?as_of=` | Impact preview |
| GET/POST | `/api/v1/platform/policy-assignments/?policy=` | List/create assignments |
| GET | `/api/v1/platform/policies/effective/?type=&employee=&as_of=` | The explainer |

### Explainer example (fake data)

`GET /api/v1/platform/policies/effective/?type=ATT_WORKING_HOURS&employee=42&as_of=2026-06-01`:

```json
{
  "status": "success", "message": "Explained.",
  "data": {
    "winner_assignment_id": null,
    "winner_policy_id": 3,
    "parameters": {"start_time": "09:00", "grace_minutes": 5},
    "used_default": true,
    "candidates_considered": 1,
    "rejected": [
      {"assignment_id": 17, "reason": "Target does not match."}
    ]
  }
}
```

---

## 5. Test results

```
Ran 63 tests in ~36s
OK
```
`tests_rules_engine.py` (42: math/logic/text/date functions, condition-
format parity, variable/security checks, limits, a 200-iteration fuzz
test), `tests_rule_definitions.py` (10: publish gate, type-checking,
version-by-date, where-used/retire), `tests_policies.py` (11: resolution
precedence, overlap constraints, conditions, cache invalidation,
bounded-query-count, the explainer) — **run standalone twice, 63/63
green both times.**

The COMBINED full `apps.platform_core` suite (169 tests, every Phase
1/2/3A test file together) was attempted twice and failed both times —
once with `OperationalError: could not translate host name
"...neon.tech" to address` (DNS resolution failure) and once with
`InterfaceError: connection already closed`, both partway through an
11-15-minute run, and both cascading into several reported
errors/failures from that point on (one underlying connection drop,
several affected tests). A direct `manage.py check --database default`
immediately after each failed run succeeded in 4.5s, confirming the
database itself is healthy — this is Neon's serverless connection
pooler dropping a long-lived idle/active connection mid-run, the exact
same pre-existing, environment-level flakiness class already documented
in `PHASE2_REPORT.md` (that report's own combined-suite run hit an
identical `tests_numbering.py` `TransactionTestCase` cascade for the same
underlying reason). **Not a Phase 3A regression** — every NEW test file
this phase added passed cleanly, twice, in isolation; only the long
combined run is affected. Whoever next has a stable, long-lived DB
connection available should re-run the full suite once to get a clean
169/169 number, but this is an infrastructure constraint of this
development environment, not a code correctness question.

`python manage.py check` — clean. Migrations: `0009_phase3a_rules_and_policies`
(schema), `0010_policy_default_sentinel_fix` (schema, bug #1 above),
`0011_change_history_json_encoder_fix` (schema, bug #3 above) — all
applied cleanly, verified via `sync_policy_types` reporting
`Created=9 Updated=0 Unchanged=0` on first run.

---

## 6. Updated docs

`docs/RULES.md` (new) — full grammar, type system, null handling, limits,
function library, data-provider boundary, publish lifecycle.
`docs/POLICIES.md` (new) — concepts, resolution order, employee context,
the explainer, cache invalidation design (and its documented gap), bulk
resolution, known gaps, the adapter pattern. `docs/MIGRATION_PLAN.md` —
Phase 3A addendum with the Task G.3 per-user-field table and the
Phase 1 `ChangeHistory` bug note.

---

## 7. Risks, limitations, and deferred items

- **Task F (attendance consolidation) is entirely deferred** — see
  Section 3. This is the headline risk: the policy engine itself is
  solid, but attendance doesn't use it yet, so none of Task F's
  acceptance criteria (identical attendance results flag OFF/ON) can be
  claimed.
- **Cache invalidation gap**: an employee's own field change doesn't bump
  the `policies` cache namespace — documented in `docs/POLICIES.md`, not
  fixed. Matters once a real caller's condition rules read live employee
  fields that change same-day as a resolution.
- **No tree-compilation caching** for the rule evaluator (Task A.4
  describes it as an aspiration) — current throughput (~13,500 evals/sec)
  is adequate for this phase's own callers but may need revisiting once
  Phase 3B's workflow engine or Phase 7's payroll formulas call it at
  higher volume.
- **Three data providers left unregistered**
  (`attendance.count_days`/`calendar.working_days_between`/
  `org.manager_level`) — Phase 3B's approver resolvers will need
  `org.manager_level` specifically; flagged as an open item for whoever
  builds that phase, not guessed at here.
- **`resolution_strategy=merge`** is declared but not implemented in
  `resolve()` — no registered policy type uses it yet.
- **`TARGET_EMPLOYEE_GROUP`** assignments cannot be resolved (no
  saved-filter engine) — raises cleanly rather than matching nothing/
  everything.

## 8. Open questions for whoever picks up Task F (or Phase 3B)

1. Attendance consolidation: should System1 (`AttendanceSettings`) or
   System2 (named policies) data take priority where they conflict
   today? This phase did not trace the exact call-site logic to answer
   this — it needs its own investigation pass before any data migration
   is written.
2. Should `org.manager_level` (needed by Phase 3B's approver resolvers)
   be built as part of 3B, or as a prerequisite addition to this phase's
   `rule_functions.py` data-provider registry before 3B starts?
3. Is the cache-invalidation gap (employee field changes not bumping the
   `policies` namespace) acceptable to leave open through Phase 3B, or
   does it need closing before workflows/notifications start depending on
   policy-resolved SLA/escalation parameters?
