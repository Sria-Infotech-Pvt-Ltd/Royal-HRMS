# Person vs. Employment — design decision (Phase 5B Task K)

**Decision only — not implemented in this phase.** `User` continues to
represent one employment record, login identity, and person all at once.

## The problem

`User` today conflates three concepts that eventually diverge:

1. **Person** — a human being, with a name, date of birth, and personal
   documents, who exists independently of any job.
2. **Login identity** — an email/password/role used to authenticate.
3. **Employment** — a specific stint of work for this company, with a
   position, placement, employment type/status, salary, and an end date.

As long as every person has exactly one employment at a time, and never
returns after leaving, this conflation is harmless. It stops being
harmless the moment any of these happen:

- **Rehire**: someone leaves and comes back. Today (and still, after this
  phase — see Task K's own instruction not to build the split) this
  reactivates the *same* `User` row with a new placement/status. That is
  fine for "did this person work here before and now works here again
  with a continuous history," but it means a rehire can never have a
  genuinely fresh employee code series restart, a different login email,
  or two separate employment timelines that don't silently merge.
- **Concurrent employment**: one person holding two employments at once
  (e.g. a consultant also doing a part-time teaching role, or — in a
  multi-entity group — working for two legal entities simultaneously).
  `Placement`'s own `placement_employee_no_overlap` exclusion constraint
  (models.py:717-731) makes this structurally impossible today: one
  employee, one open placement, company-wide, by design.
- **Multi-entity transfers**: moving an employee from one `LegalEntity`
  to another (an inter-company transfer, common in group structures) is
  today indistinguishable from "change position" — there's no concept of
  closing one employment and opening a new one under a different legal
  entity while preserving the same underlying person.
- **Login identity separate from employment**: a board member, contractor,
  or portal user who needs system access without being "an employee" (no
  `employee_type`/`Placement`/payroll row) has no clean home today — every
  `User` is implicitly assumed to be an employment.

## Options considered

### Option 1 — Keep `User` = employment (status quo)

No split. A "person" is simply whichever `User` row is currently active;
rehire reactivates it; concurrent/multi-entity employment stays
unsupported.

- **Impact on rehire**: works today, as documented (Task K's own
  instruction) — reactivate the same row, new placement/status via a
  Rehire action, optionally a new employee code if configured.
- **Impact on concurrent employment**: cannot be built without either
  relaxing `placement_employee_no_overlap` (risking the one-seat-per-
  person invariant most of this codebase's placement/approval/scope logic
  silently assumes) or layering a second "active employment" concept on
  top of `User` that doesn't actually exist as a row.
- **Impact on multi-entity transfers**: a "Transfer (Legal Entity)" action
  type could exist, but it would just change `User`'s legal-entity-scoped
  fields in place — no distinct employment history per entity, and payroll/
  compliance per entity (which the Phase 5B prompt's own Task D.1 flags as
  "blocked until multi-entity payroll exists") stays blocked regardless.
- **Migration cost**: zero — this is the only option that changes nothing.
- **Risk**: the conflation keeps compounding; every future feature that
  needs "a person" distinct from "an employment" (background checks that
  outlive one employment stint, a unified rehire-eligibility history
  across every past employment, alumni access) has to work around a model
  that doesn't represent it.

### Option 2 — Split into `Person` + `Employment`

`Person` holds identity (name, DOB, personal documents, login
credentials); `Employment` holds one row per employment stint (position,
type, status, employee code, start/end), FK'd to `Person`. A `Person` can
have N `Employment` rows (historical and/or concurrent).

- **Impact on rehire**: clean — a new `Employment` row under the same
  `Person`, with its own employee code series, own placement history,
  genuinely independent of the prior stint.
- **Impact on concurrent employment**: structurally supported — two open
  `Employment` rows for one `Person`. `Placement`'s exclusion constraint
  would need to move from "one per Person" to "one per Employment," and
  everywhere that currently does `employee.placements`/`employee.
  employment_status`/etc. would need to resolve "which Employment" first.
- **Impact on multi-entity transfers**: a transfer becomes closing one
  `Employment` and opening another, each cleanly scoped to its own legal
  entity, with its own payroll config — once Phase 7's multi-entity
  payroll exists to make that meaningful.
- **Impact on login identity**: `Person` is the natural home for
  credentials, decoupling "has a login" from "is currently employed" —
  useful for alumni/portal/board-member access.
- **Impact on history**: every existing FK to `User` across ~20+ apps
  (payroll, attendance, leave, documents, notifications, approvals,
  audit...) would need to decide whether it means "this Person" or "this
  specific Employment" — a decision that differs per FK and can't be
  mechanically inferred. `ChangeHistory`, `Placement`, `PromotionRecord`,
  this phase's own `EmploymentAction`/`EmployeeRelationship`, and every
  report/dashboard query would need re-auditing one at a time.
- **Migration cost**: very large — a genuine schema fork touching the
  single most-referenced model in the codebase, not a thin additive layer
  like every other Phase 5A/5B structure built so far. Every login,
  permission check, and `request.user` usage in every view across every
  app would need to resolve through the new indirection.
- **Risk**: the highest-blast-radius change possible in this codebase;
  wrong early decisions (e.g. "most FKs mean Employment, a few mean
  Person") are expensive to unwind once hundreds of call sites depend on
  whichever choice was made.

### Option 3 — Hybrid: `User` stays the login/permission identity; a new `EmployeeProfile`-style concept represents "a stint" without a full `Person` table

Keep `User` as both login identity and "the current/primary employment
view" (so 95% of existing code needs zero changes), but allow a `User` to
have multiple `Employment`-like stint records (so rehire creates a new
stint under the same `User`, and the rare concurrent-employment case is
representable as two stints under one `User`, enforced per-stint rather
than per-User).

- **Impact on rehire**: close to Option 2's benefit (a genuinely new stint
  record, new employee code, independent history) without creating a
  second top-level identity table — `User` remains both "the person" and
  "the login," just gains a one-to-many "stints" concept underneath.
- **Impact on concurrent employment**: supportable by moving
  `placement_employee_no_overlap` to be scoped per-stint rather than
  per-User, and adding a "current stint" resolution step wherever
  `employee.employment_status`/`employee_type`/placement is read directly
  — a smaller, more mechanical version of Option 2's larger problem,
  concentrated in the stint-resolution layer rather than spread across
  every FK in the codebase.
- **Impact on multi-entity transfers**: representable as two stints, one
  per entity, under the same `User`/login — closer to what Option 1 can
  offer today than Option 2's full separation, since `User` the login
  identity doesn't change.
- **Impact on login identity**: unchanged from today — still one login
  per `User`. Does not solve "access without being an employment" (e.g.
  alumni/board-member access) the way Option 2 does.
- **Migration cost**: moderate — smaller than Option 2 (no identity split,
  no re-auditing every FK's meaning), but still requires introducing the
  stint concept and a "current stint" resolver wherever code today reads
  `User` fields as if there's exactly one employment.
- **Risk**: a halfway point that solves rehire and concurrent-employment
  cleanly but still leaves the person/login/employment conflation partly
  in place — a reasonable next step, not a final architecture.

## Recommendation

**Option 1 (status quo) for now, re-evaluate Option 3 if/when concurrent
employment or genuine rehire-as-a-new-stint becomes a real, scheduled
requirement** — not Option 2. Reasoning:

- No current acceptance criterion, open question, or product requirement
  in Phases 0-5B actually needs concurrent employment or a login identity
  independent of employment; this phase's own rehire handling (reactivate
  the same `User`, Task K's explicit instruction) is sufficient for every
  known near-term need.
- Option 2's migration cost and blast radius (every FK across ~20 apps
  re-audited) is disproportionate to a need that hasn't materialized yet
  — building it speculatively risks exactly the kind of "approximate a
  correctness-critical change without real data to verify against" this
  session has consistently declined to do for every other phase's
  highest-risk task.
- If/when multi-entity payroll (Phase 7, per the Phase 5B prompt's own
  deferral note) or a real alumni/board-access requirement appears,
  Option 3 is the smaller, lower-risk next step — most of today's code
  keeps working unchanged, with the stint-resolution layer absorbing the
  complexity rather than spreading it everywhere.

## What this phase actually builds instead

Per the prompt's own instruction, rehire in this phase reactivates the
same `User`: a Rehire `ActionType` (not yet seeded — see
PHASE5B_REPORT.md's deferred list) would set a fresh `Placement` and
`employment_status`, and optionally a new employee code via
`EmployeeCodeSeries` (Phase "12" of the structure-cleanup plan;
pre-existing in this codebase), exactly as if hiring fresh, without a
true second employment record. **Limitation, stated plainly**: a rehired
employee's new employment is NOT distinguishable from their original one
in any report or query that counts "employments" rather than "employees"
— there is exactly one `User` row, one continuous (if gapped)
`Placement`/`EmploymentAction` history, and no way to say "this person
has been hired 3 separate times" other than counting Hire/Rehire actions
in that history.
